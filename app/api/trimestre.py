"""
trimestre.py — Aprobación final del trimestre (cierre / publicación del horario).
Prefijo: /api/v1/gestora/trimestre
Sistema de Horarios ADSO — SENA

Solo la gestora aprueba el trimestre (reglas-negocio §8). Antes de aprobar se
revisan las reglas del sistema:

  Bloquean la aprobación
    - Huecos en fichas de prioridad alta (§4: trimestres 1–5 nunca con huecos).
    - Solicitudes de horas extra sin respuesta del instructor.
    - Instructores por encima del tope de 40 h (§1).
  Advierten (la gestora puede aprobar si las acepta)
    - Huecos en fichas de prioridad baja (§4: se permiten).
    - Fichas sin líder y líderes con un solo bloque (§3).
    - Transversales sin resolver (§2).
    - Instructores que debían compensar carga y la superan (§6).

Al aprobar se publica el horario, se guarda el cierre del trimestre para la
regla de equidad y se congelan los cambios (líderes y horas extra) hasta que
la gestora lo reabra. `exigir_trimestre_abierto` es el guardia que usan esos
módulos; por eso este archivo solo importa los demás de forma diferida.
"""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.equidad import etiqueta, periodo_actual
from app.core.security import require_gestora
from app.schemas.trimestre import (
    EstadoAprobacion,
    EventoTrimestre,
    SolicitudAprobacion,
    SolicitudReapertura,
    Verificacion,
)


router = APIRouter(
    prefix="/api/v1/gestora/trimestre",
    tags=["Gestora · Aprobación del trimestre"],
)

MAX_ITEMS = 6

# ⚠️ PROVISIONAL — en memoria (reemplazar con SQLAlchemy).
# periodo ("2026-T4") → {"estado": "abierto" | "aprobado", "historial": [evento, ...]}
TRIMESTRES: dict[str, dict] = {}


def _registro(periodo: str) -> dict:
    return TRIMESTRES.setdefault(periodo, {"estado": "abierto", "historial": []})


def trimestre_aprobado(periodo: str | None = None) -> dict | None:
    """Evento de aprobación vigente del periodo (por defecto, el en curso)."""
    registro = TRIMESTRES.get(periodo or etiqueta(periodo_actual()))
    if not registro or registro["estado"] != "aprobado":
        return None
    return registro["historial"][-1]


def exigir_trimestre_abierto() -> None:
    """Guardia: los cambios de programación se congelan con el trimestre aprobado."""
    if trimestre_aprobado():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"El trimestre {etiqueta(periodo_actual())} ya fue aprobado y publicado. "
                "La gestora debe reabrirlo para hacer cambios."
            ),
        )


# ── Verificaciones ───────────────────────────────────────────────────────────

def _verificacion(id_: str, titulo: str, nivel: str, items: list[str], ok: str, mal: str,
                  enlace: str | None) -> Verificacion:
    return Verificacion(
        id=id_,
        titulo=titulo,
        nivel=nivel,
        cumple=not items,
        detalle=ok if not items else mal.format(n=len(items)),
        items=items[:MAX_ITEMS] + ([f"… y {len(items) - MAX_ITEMS} más"] if len(items) > MAX_ITEMS else []),
        enlace=None if not items else enlace,
    )


def _verificaciones() -> list[Verificacion]:
    from app.api.alertas import SOLICITUDES_HORAS_EXTRA, detallar_solicitud, horas_formacion_actuales, todas_las_alertas
    from app.api.equidad import listado_equidad
    from app.api.gestora import FICHAS_GESTORA_MOCK, INSTRUCTORES_GESTORA
    from app.api.lideres import LIDERES_FICHA
    from app.api.perfil import SOLICITUDES_TRANSVERSALES
    from app.core.carga import HORAS_ADMINISTRATIVAS, TOPE_SEMANAL
    from app.schemas.gestora import ESTADOS_CERRADOS

    sin_cubrir = [a for a in todas_las_alertas() if a.estado != "cubierta"]

    def hueco(a) -> str:
        return f"{a.rap_nombre} · Ficha {a.ficha_id} (T{a.trimestre}) · {a.horas_pendientes:g} h"

    pendientes = [
        d for d in (detallar_solicitud(s) for s in SOLICITUDES_HORAS_EXTRA if s["estado"] == "pendiente") if d
    ]
    sobre_tope = []
    for instructor in INSTRUCTORES_GESTORA:
        formacion = horas_formacion_actuales(int(instructor["id"]))
        if formacion is not None and formacion + HORAS_ADMINISTRATIVAS > TOPE_SEMANAL:
            sobre_tope.append(f"{instructor['nombre']} · {formacion + HORAS_ADMINISTRATIVAS:g} h")

    sin_lider = [f"Ficha {f['id']} (T{f['trimestre']} · {f['jornada']})" for f in FICHAS_GESTORA_MOCK if f["id"] not in LIDERES_FICHA]
    un_bloque = [f"Ficha {fid}" for fid, r in LIDERES_FICHA.items() if len(r["bloques"]) < 2]
    cerrados = {e.lower() for e in ESTADOS_CERRADOS}
    transversales = [
        f"Ficha {s['ficha_id']} · {', '.join(s.get('transversales', []))} ({s.get('estado', '')})"
        for s in SOLICITUDES_TRANSVERSALES
        if str(s.get("estado", "")).strip().lower() not in cerrados
    ]
    equidad = [
        f"{i.nombre} · {i.en_curso.horas_totales:g} h (máx. {i.compensacion.carga_maxima_recomendada:g} h)"
        for i in listado_equidad().instructores if i.excede_recomendacion
    ]

    return [
        _verificacion(
            "huecos_prioridad_alta", "Fichas de prioridad alta sin huecos", "bloqueante",
            [hueco(a) for a in sin_cubrir if a.prioridad == 1],
            "Todas las fichas de 1.º a 5.º trimestre tienen sus RAP cubiertos.",
            "{n} RAP sin cubrir en fichas de 1.º a 5.º trimestre: nunca pueden quedar con huecos.",
            "/gestora/alertas",
        ),
        _verificacion(
            "horas_extra_pendientes", "Solicitudes de horas extra respondidas", "bloqueante",
            [f"{d.instructor_nombre} · {d.rap_nombre} · Ficha {d.ficha_id}" for d in pendientes],
            "Ningún instructor tiene solicitudes de horas extra sin responder.",
            "{n} solicitud(es) de horas extra esperan respuesta del instructor (o cancélalas).",
            "/gestora/alertas",
        ),
        _verificacion(
            "tope_semanal", "Nadie supera las 40 h", "bloqueante", sobre_tope,
            "Todos los instructores están dentro del tope de 40 h semanales.",
            "{n} instructor(es) superan el tope absoluto de 40 h.",
            "/gestora/equidad",
        ),
        _verificacion(
            "huecos_prioridad_baja", "Huecos en fichas de 6.º–7.º trimestre", "advertencia",
            [hueco(a) for a in sin_cubrir if a.prioridad == 2],
            "No quedan huecos en fichas de prioridad baja.",
            "{n} RAP sin cubrir en fichas de prioridad baja. Se permite si no hay instructor disponible.",
            "/gestora/alertas",
        ),
        _verificacion(
            "fichas_sin_lider", "Fichas con líder", "advertencia", sin_lider,
            "Todas las fichas tienen líder.",
            "{n} ficha(s) sin líder: el líder debe tener al menos una clase semanal con su ficha.",
            "/gestora/lideres",
        ),
        _verificacion(
            "lideres_un_bloque", "Líderes con 2 bloques seguidos", "advertencia", un_bloque,
            "Todos los líderes tienen 2 bloques con su ficha.",
            "{n} líder(es) con un solo bloque. Lo deseable son 2 seguidos el mismo día.",
            "/gestora/lideres",
        ),
        _verificacion(
            "transversales", "Transversales resueltas", "advertencia", transversales,
            "No hay solicitudes de transversales sin resolver.",
            "{n} solicitud(es) de transversales siguen abiertas.",
            "/perfil-gestora#solicitudes",
        ),
        _verificacion(
            "equidad", "Compensaciones de equidad respetadas", "advertencia", equidad,
            "Quienes debían compensar carga están dentro de lo recomendado.",
            "{n} instructor(es) debían recibir menos carga y la superan.",
            "/gestora/equidad",
        ),
    ]


def _estado() -> EstadoAprobacion:
    periodo = etiqueta(periodo_actual())
    registro = _registro(periodo)
    verificaciones = _verificaciones()
    bloqueantes = sum(1 for v in verificaciones if v.nivel == "bloqueante" and not v.cumple)
    aprobado = registro["estado"] == "aprobado"
    return EstadoAprobacion(
        periodo=periodo,
        estado=registro["estado"],
        aprobacion=EventoTrimestre(**registro["historial"][-1]) if aprobado else None,
        verificaciones=verificaciones,
        bloqueantes=bloqueantes,
        advertencias=sum(1 for v in verificaciones if v.nivel == "advertencia" and not v.cumple),
        puede_aprobar=not aprobado and bloqueantes == 0,
        historial=[EventoTrimestre(**e) for e in reversed(registro["historial"])],
    )


def _gestora(usuario: dict) -> tuple[int, str]:
    return int(str(usuario.get("sub") or usuario.get("id"))), str(usuario.get("nombre", "Gestora"))


# ── Endpoints ────────────────────────────────────────────────────────────────

@router.get(
    "",
    response_model=EstadoAprobacion,
    summary="Estado del trimestre en curso y verificaciones previas a la aprobación",
)
def consultar_trimestre(_usuario: dict = Depends(require_gestora)) -> EstadoAprobacion:
    return _estado()


@router.post(
    "/aprobar",
    response_model=EstadoAprobacion,
    summary="Aprobar el trimestre y publicar el horario",
)
def aprobar_trimestre(
    datos: SolicitudAprobacion,
    usuario: dict = Depends(require_gestora),
) -> EstadoAprobacion:
    estado = _estado()
    if estado.estado == "aprobado":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"El trimestre {estado.periodo} ya está aprobado.")
    if estado.bloqueantes:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"No se puede aprobar: hay {estado.bloqueantes} verificación(es) bloqueante(s) sin cumplir.",
        )
    advertencias = [v.titulo for v in estado.verificaciones if v.nivel == "advertencia" and not v.cumple]
    if advertencias and not datos.confirma_advertencias:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Confirma que revisaste las advertencias antes de aprobar.",
        )

    # Guarda la carga del trimestre para la regla de equidad (§6).
    from app.api.equidad import registrar_cierre

    registrar_cierre(usuario)

    gestora_id, gestora_nombre = _gestora(usuario)
    registro = _registro(estado.periodo)
    registro["estado"] = "aprobado"
    registro["historial"].append(
        {
            "tipo": "aprobado",
            "fecha": datetime.now(),
            "gestora_id": gestora_id,
            "gestora_nombre": gestora_nombre,
            "texto": datos.observaciones.strip(),
            "advertencias_aceptadas": advertencias,
        }
    )
    return _estado()


@router.post(
    "/reabrir",
    response_model=EstadoAprobacion,
    summary="Reabrir un trimestre aprobado para hacer cambios",
)
def reabrir_trimestre(
    datos: SolicitudReapertura,
    usuario: dict = Depends(require_gestora),
) -> EstadoAprobacion:
    periodo = etiqueta(periodo_actual())
    registro = _registro(periodo)
    if registro["estado"] != "aprobado":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"El trimestre {periodo} no está aprobado.")

    gestora_id, gestora_nombre = _gestora(usuario)
    registro["estado"] = "abierto"
    registro["historial"].append(
        {
            "tipo": "reabierto",
            "fecha": datetime.now(),
            "gestora_id": gestora_id,
            "gestora_nombre": gestora_nombre,
            "texto": datos.motivo,
            "advertencias_aceptadas": [],
        }
    )
    return _estado()
