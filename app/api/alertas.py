"""
alertas.py — Alertas de huecos para la Gestora.
Prefijo: /api/v1/gestora/alertas
Sistema de Horarios ADSO — SENA

Regla (docs/reglas-negocio.md §5): si un RAP queda sin instructor se lanza una
alerta, y el sistema propone como "tentativo para horas extra hasta 40 h" a los
instructores que dominan ese RAP y ya tienen 36–37 h. Solo la gestora puede
solicitar y autorizar esas horas extra.

Todas las operaciones exigen rol de Gestora (`require_gestora`).
"""

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.catalogo import COMPETENCIAS_MOCK, RAP_MOCK
from app.api.equidad import compensacion_de
from app.api.trimestre import exigir_trimestre_abierto
from app.api.gestora import FICHAS_GESTORA_MOCK, INSTRUCTORES_GESTORA
from app.core.carga import HORAS_ADMINISTRATIVAS, TOPE_SEMANAL
from app.core.security import require_gestora
from app.schemas.alertas import (
    AlertaHueco,
    CandidatoHueco,
    ListadoAlertas,
    ResumenAlertas,
    SolicitudConfirmacion,
    SolicitudConfirmacionCreate,
    SolicitudDetallada,
)


router = APIRouter(
    prefix="/api/v1/gestora/alertas",
    tags=["Gestora · Alertas"],
)

# Carga total desde la que un instructor se propone para horas extra (§5: "36-37h").
HORAS_MINIMAS_CANDIDATO = 36

# ⚠️ PROVISIONAL — datos en memoria (reemplazar con SQLAlchemy y el motor de horarios)

# RAP que el motor no pudo cubrir. `ficha_id` referencia FICHAS_GESTORA_MOCK y
# `rap_id` referencia RAP_MOCK del catálogo.
HUECOS_RAP_MOCK: list[dict] = [
    {
        "id": 1,
        "ficha_id": 3365171,
        "rap_id": 3,
        "horas_requeridas": 6.0,
        "bloques": ["MARTES 15:00-18:00", "LUNES 15:00-18:00"],  # jueves 15-18 es Inglés fijo
    },
    {
        "id": 2,
        "ficha_id": 3365171,
        "rap_id": 4,
        "horas_requeridas": 3.0,
        "bloques": ["VIERNES 12:00-15:00"],
    },
    {
        "id": 3,
        "ficha_id": 3365101,
        "rap_id": 1,
        "horas_requeridas": 3.0,
        "bloques": ["MIERCOLES 06:00-09:00"],
    },
    {
        "id": 4,
        "ficha_id": 3365261,
        "rap_id": 3,
        "horas_requeridas": 3.0,
        "bloques": ["LUNES 09:00-12:00"],
    },
    {
        "id": 5,
        "ficha_id": 3365169,
        "rap_id": 2,
        "horas_requeridas": 3.0,
        "bloques": ["MIERCOLES 09:00-12:00"],
    },
]

# Carga base (sin horas extra) y competencias de los instructores de INSTRUCTORES_GESTORA.
# Las 32 h de 101 coinciden con sus fichas en app/api/perfil.py.
CARGA_INSTRUCTORES_MOCK: dict[int, dict] = {
    101: {"horas_formacion": 32.0, "competencias": ["220501092", "220501093", "220501095"]},
    202: {"horas_formacion": 20.0, "competencias": ["220501095"]},
    103: {"horas_formacion": 32.0, "competencias": ["220501092", "220501095"]},
    104: {"horas_formacion": 33.0, "competencias": ["220501093", "220501095"]},
    105: {"horas_formacion": 36.0, "competencias": ["220501092", "220501093", "220501095"]},
}

# Solicitudes de horas extra de la gestora a los instructores (historial completo).
# estado: pendiente → aceptada | rechazada (responde el instructor) | cancelada (la gestora).
SOLICITUDES_HORAS_EXTRA: list[dict] = [
    {
        "id": 1,
        "alerta_id": 1,
        "instructor_id": 103,
        "instructor_nombre": "Sandra Ospina",
        "horas": 4.0,
        "fecha_solicitud": date(2026, 10, 2),
        "estado": "rechazada",
        "motivo": "Los martes en la tarde dicto en otra sede.",
        "fecha_respuesta": date(2026, 10, 3),
    },
    {
        "id": 2,
        "alerta_id": 3,
        "instructor_id": 101,
        "instructor_nombre": "Javier Montoya",
        "horas": 3.0,
        "fecha_solicitud": date(2026, 10, 5),
        "estado": "pendiente",
        "motivo": "",
        "fecha_respuesta": None,
    },
]


def prioridad_de_trimestre(trimestre: int) -> int:
    """Prioridad 1 (trimestres 1–5, nunca con huecos) o 2 (6–7, se permite hueco)."""
    return 1 if trimestre <= 5 else 2


# ── Carga y solicitudes ──────────────────────────────────────────────────────

def horas_extra_aceptadas(instructor_id: int) -> float:
    return sum(
        s["horas"] for s in SOLICITUDES_HORAS_EXTRA
        if s["instructor_id"] == instructor_id and s["estado"] == "aceptada"
    )


def horas_formacion_actuales(instructor_id: int) -> float | None:
    """Formación base más horas extra aceptadas; None si no hay datos de carga."""
    carga = CARGA_INSTRUCTORES_MOCK.get(instructor_id)
    if carga is None:
        return None
    return carga["horas_formacion"] + horas_extra_aceptadas(instructor_id)


def _solicitudes_de(alerta_id: int, *estados: str) -> list[dict]:
    return [s for s in SOLICITUDES_HORAS_EXTRA if s["alerta_id"] == alerta_id and s["estado"] in estados]


def _candidatos(hueco: dict, competencia_codigo: str, horas_pendientes: float) -> list[CandidatoHueco]:
    # Quien ya aceptó o rechazó este hueco no se vuelve a proponer.
    respondieron = {s["instructor_id"] for s in _solicitudes_de(hueco["id"], "aceptada", "rechazada")}
    candidatos = []
    for instructor in INSTRUCTORES_GESTORA:
        instructor_id = int(instructor["id"])
        carga = CARGA_INSTRUCTORES_MOCK.get(instructor_id)
        if carga is None or instructor_id in respondieron or competencia_codigo not in carga["competencias"]:
            continue
        formacion = horas_formacion_actuales(instructor_id)
        total = formacion + HORAS_ADMINISTRATIVAS
        if not HORAS_MINIMAS_CANDIDATO <= total < TOPE_SEMANAL:
            continue
        margen = TOPE_SEMANAL - total
        compensacion = compensacion_de(instructor_id)
        candidatos.append(
            CandidatoHueco(
                id=instructor_id,
                nombre=str(instructor["nombre"]),
                horas_formacion=formacion,
                horas_administrativas=HORAS_ADMINISTRATIVAS,
                horas_totales=total,
                margen_horas=margen,
                horas_que_cubre=min(margen, horas_pendientes),
                cubre_hueco=margen >= horas_pendientes,
                extra_trimestre_anterior=compensacion is not None,
                nota_equidad=(
                    f"Llegó a {compensacion.horas_totales:g} h con horas extra en {compensacion.periodo}: "
                    "por equidad, evita pedirle horas extra este trimestre."
                    if compensacion else ""
                ),
            )
        )
    # Equidad (§6): quien ya hizo horas extra va al final; luego, mayor margen primero.
    return sorted(candidatos, key=lambda c: (c.extra_trimestre_anterior, -c.margen_horas, c.nombre))


def _construir_alerta(hueco: dict) -> AlertaHueco | None:
    ficha = next((f for f in FICHAS_GESTORA_MOCK if f["id"] == hueco["ficha_id"]), None)
    rap = next((r for r in RAP_MOCK if r.id == hueco["rap_id"]), None)
    competencia = next((c for c in COMPETENCIAS_MOCK if rap and c.id == rap.competencia_id), None)
    if ficha is None or rap is None or competencia is None:
        return None

    cubiertas = sum(s["horas"] for s in _solicitudes_de(hueco["id"], "aceptada"))
    pendientes = max(hueco["horas_requeridas"] - cubiertas, 0.0)
    solicitud = next(iter(_solicitudes_de(hueco["id"], "pendiente")), None)
    if pendientes == 0:
        estado = "cubierta"
    elif solicitud:
        estado = "confirmacion_solicitada"
    else:
        estado = "abierta"

    return AlertaHueco(
        id=hueco["id"],
        ficha_id=ficha["id"],
        jornada=ficha["jornada"],
        trimestre=ficha["trimestre"],
        prioridad=prioridad_de_trimestre(ficha["trimestre"]),
        rap_id=rap.id,
        rap_nombre=rap.nombre,
        competencia_codigo=competencia.codigo,
        competencia_nombre=competencia.nombre,
        horas_requeridas=hueco["horas_requeridas"],
        horas_pendientes=pendientes,
        bloques=hueco["bloques"],
        estado=estado,
        solicitud=SolicitudConfirmacion(**solicitud) if solicitud else None,
        respuestas=[SolicitudConfirmacion(**s) for s in _solicitudes_de(hueco["id"], "aceptada", "rechazada")],
        candidatos=_candidatos(hueco, competencia.codigo, pendientes) if pendientes else [],
    )


def detallar_solicitud(solicitud: dict) -> SolicitudDetallada | None:
    hueco = next((h for h in HUECOS_RAP_MOCK if h["id"] == solicitud["alerta_id"]), None)
    alerta = _construir_alerta(hueco) if hueco else None
    if alerta is None:
        return None
    return SolicitudDetallada(
        **solicitud,
        ficha_id=alerta.ficha_id,
        jornada=alerta.jornada,
        trimestre=alerta.trimestre,
        prioridad=alerta.prioridad,
        rap_nombre=alerta.rap_nombre,
        competencia_nombre=alerta.competencia_nombre,
        bloques=alerta.bloques,
    )


def todas_las_alertas() -> list[AlertaHueco]:
    return [a for a in map(_construir_alerta, HUECOS_RAP_MOCK) if a is not None]


def alertas_de_ficha(ficha_id: int) -> list[AlertaHueco]:
    """Huecos de una ficha, para vistas que no son de la gestora (p. ej. Mi ficha)."""
    alertas = (_construir_alerta(h) for h in HUECOS_RAP_MOCK if h["ficha_id"] == ficha_id)
    return [a for a in alertas if a is not None]


def _alerta_o_404(alerta_id: int) -> AlertaHueco:
    hueco = next((h for h in HUECOS_RAP_MOCK if h["id"] == alerta_id), None)
    alerta = _construir_alerta(hueco) if hueco else None
    if alerta is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="La alerta no existe.")
    return alerta


# ── Endpoints de la gestora ──────────────────────────────────────────────────

ORDEN_ESTADO = {"abierta": 0, "confirmacion_solicitada": 1, "cubierta": 2}
MAX_RESPUESTAS_RECIENTES = 5


@router.get(
    "",
    response_model=ListadoAlertas,
    summary="RAP sin instructor, candidatos tentativos y respuestas de los instructores",
)
def listar_alertas(
    trimestre: int | None = Query(default=None, ge=1),
    _usuario: dict = Depends(require_gestora),
) -> ListadoAlertas:
    alertas = todas_las_alertas()
    if trimestre is not None:
        alertas = [a for a in alertas if a.trimestre == trimestre]
    alertas.sort(key=lambda a: (ORDEN_ESTADO[a.estado], a.prioridad, a.trimestre, a.ficha_id))

    respondidas = sorted(
        (s for s in SOLICITUDES_HORAS_EXTRA if s["estado"] in {"aceptada", "rechazada"}),
        key=lambda s: (s["fecha_respuesta"], s["id"]),
        reverse=True,
    )
    recientes = [d for d in map(detallar_solicitud, respondidas[:MAX_RESPUESTAS_RECIENTES]) if d]

    abiertas = [a for a in alertas if a.estado == "abierta"]
    return ListadoAlertas(
        resumen=ResumenAlertas(
            total=len(alertas),
            abiertas=len(abiertas),
            abiertas_prioridad_alta=sum(1 for a in abiertas if a.prioridad == 1),
            en_confirmacion=sum(1 for a in alertas if a.estado == "confirmacion_solicitada"),
            cubiertas=sum(1 for a in alertas if a.estado == "cubierta"),
        ),
        respuestas_recientes=recientes,
        alertas=alertas,
    )


@router.post(
    "/{alerta_id}/solicitar-confirmacion",
    response_model=AlertaHueco,
    summary="Solicitar a un instructor candidato que confirme las horas extra",
)
def solicitar_confirmacion(
    alerta_id: int,
    datos: SolicitudConfirmacionCreate,
    _usuario: dict = Depends(require_gestora),
) -> AlertaHueco:
    exigir_trimestre_abierto()
    alerta = _alerta_o_404(alerta_id)
    if alerta.estado != "abierta":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Este hueco ya está cubierto."
                if alerta.estado == "cubierta"
                else "Esta alerta ya tiene una confirmación solicitada."
            ),
        )
    candidato = next((c for c in alerta.candidatos if c.id == datos.instructor_id), None)
    if candidato is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="El instructor no es candidato para este hueco.",
        )

    SOLICITUDES_HORAS_EXTRA.append(
        {
            "id": max((s["id"] for s in SOLICITUDES_HORAS_EXTRA), default=0) + 1,
            "alerta_id": alerta_id,
            "instructor_id": candidato.id,
            "instructor_nombre": candidato.nombre,
            "horas": candidato.horas_que_cubre,
            "fecha_solicitud": date.today(),
            "estado": "pendiente",
            "motivo": "",
            "fecha_respuesta": None,
        }
    )
    return _alerta_o_404(alerta_id)


@router.delete(
    "/{alerta_id}/solicitar-confirmacion",
    response_model=AlertaHueco,
    summary="Cancelar la solicitud pendiente y reabrir la alerta",
)
def cancelar_confirmacion(
    alerta_id: int,
    _usuario: dict = Depends(require_gestora),
) -> AlertaHueco:
    exigir_trimestre_abierto()
    _alerta_o_404(alerta_id)
    for solicitud in _solicitudes_de(alerta_id, "pendiente"):
        solicitud["estado"] = "cancelada"
        solicitud["fecha_respuesta"] = date.today()
    return _alerta_o_404(alerta_id)
