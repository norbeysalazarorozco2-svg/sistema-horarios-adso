"""
generador.py — Botón "Generar horario automático" de la Gestora.
Prefijo: /api/v1/gestora/horarios
Sistema de Horarios ADSO — SENA

Reúne los datos del centro (fichas, plan de transversales por trimestre,
Inglés fijo, líderes, disponibilidad marcada por cada instructor, equidad y
aulas), ejecuta el motor de app/core/motor.py y guarda el resultado en
HORARIO_GENERADO (app/api/gestora.py), de donde lo leen el horario
consolidado de la gestora y "Mi horario" de cada instructor.

Se genera el horario de todas las fichas a la vez: un instructor dicta en
fichas de varios trimestres y no puede quedar en dos lugares a la misma hora.
"""

from datetime import datetime

from fastapi import APIRouter, Depends

from app.api.disponibilidad import ALMACEN_DISPONIBILIDAD
from app.api.gestora import (
    FICHAS_GESTORA_MOCK,
    HORARIO_GENERADO,
    INSTRUCTORES_GESTORA,
    bloque_ingles,
    bloques_de_jornada,
)
from app.api.lideres import LIDERES_FICHA
from app.api.perfil import PERFILES_MOCK, SOLICITUDES_TRANSVERSALES
from app.api.trimestre import exigir_trimestre_abierto
from app.core.carga import HORAS_FORMACION_BASE, TRANSVERSAL_INGLES
from app.core.motor import Aulas, FichaMotor, InstructorMotor, generar_horario
from app.core.security import require_gestora
from app.schemas.gestora import (
    DIAS_SEMANA,
    ESTADO_APROBADO,
    JORNADA_DE_BLOQUES,
    CargaGenerada,
    PendienteHorario,
    ResultadoGeneracion,
)

router = APIRouter(
    prefix="/api/v1/gestora/horarios",
    tags=["Gestora · Generación de horario"],
)

# ⚠️ PROVISIONAL — plan de transversales por trimestre del programa (además del
# Inglés fijo, que va en todos). Reemplazar con el plan oficial de SofiaPlus.
PLAN_TRIMESTRE: dict[int, list[str]] = {
    1: ["Matemáticas", "Comunicación"],
    2: ["Ética", "SST"],
    3: ["Matemáticas", "Cultura física"],
    4: ["Ética", "Emprendimiento"],
    5: ["SST", "Comunicación"],
    6: ["Emprendimiento"],
    7: ["Ética"],
    8: ["Emprendimiento"],
    9: [],
}

# ⚠️ PROVISIONAL — instructores de transversales (no inician sesión en el MVP).
# Sin disponibilidad marcada: se asumen disponibles toda la semana.
INSTRUCTORES_TRANSVERSALES: list[dict] = [
    {"id": 301, "nombre": "Carolina Ríos", "areas": {TRANSVERSAL_INGLES}},
    {"id": 302, "nombre": "David Grajales", "areas": {TRANSVERSAL_INGLES}},
    {"id": 303, "nombre": "Óscar Mejía", "areas": {"Matemáticas"}},
    {"id": 304, "nombre": "Patricia Henao", "areas": {"Ética", "Comunicación"}},
    {"id": 305, "nombre": "Felipe Arango", "areas": {"SST", "Cultura física"}},
    {"id": 306, "nombre": "Natalia Cardona", "areas": {"Emprendimiento", "Comunicación"}},
]

# ⚠️ PROVISIONAL — ambientes del centro.
AULAS = Aulas(
    tecnica=["Lab. Software 1", "Lab. Software 2", "Lab. Software 3"],
    ingles=["Ambiente Bilingüismo"],
    general=["Ambiente 201", "Ambiente 202", "Ambiente 203", "Ambiente 204", "Ambiente 205"],
)


def _prioridad(trimestre: int) -> int:
    return 1 if trimestre <= 5 else 2


def _disponibilidad_marcada(instructor_id: int) -> set[tuple[str, str]]:
    """Franjas del último registro de disponibilidad que guardó el instructor."""
    registros = ALMACEN_DISPONIBILIDAD.get(str(instructor_id), {}).values()
    ultimo = max(registros, key=lambda r: r.get("guardado_en", ""), default=None)
    return {(b["dia"], b["bloque"]) for b in (ultimo or {}).get("bloques", [])}


def _instructores() -> list[InstructorMotor]:
    from app.api.equidad import compensacion_de  # equidad depende de gestora

    tecnicos = [
        InstructorMotor(
            id=int(i["id"]),
            nombre=str(i["nombre"]),
            tope_horas=HORAS_FORMACION_BASE,
            competencias={c["codigo"] for c in PERFILES_MOCK.get(str(i["id"]), {}).get("competencias", [])},
            disponibilidad=_disponibilidad_marcada(int(i["id"])),
            compensa_carga=compensacion_de(int(i["id"])) is not None,
        )
        for i in INSTRUCTORES_GESTORA
    ]
    transversales = [
        InstructorMotor(id=t["id"], nombre=t["nombre"], tope_horas=HORAS_FORMACION_BASE, areas=set(t["areas"]))
        for t in INSTRUCTORES_TRANSVERSALES
    ]
    return tecnicos + transversales


def _transversales_de(ficha: dict) -> list[str]:
    """Plan del trimestre más las transversales aprobadas a la ficha (sin repetir Inglés)."""
    lista = list(PLAN_TRIMESTRE.get(ficha["trimestre"], []))
    for solicitud in SOLICITUDES_TRANSVERSALES:
        if solicitud.get("ficha_id") == ficha["id"] and solicitud.get("estado") == ESTADO_APROBADO:
            lista += [t for t in solicitud.get("transversales", []) if t != TRANSVERSAL_INGLES and t not in lista]
    return lista


def _fichas() -> list[FichaMotor]:
    fichas = []
    for indice, ficha in enumerate(FICHAS_GESTORA_MOCK):
        ingles = bloque_ingles(ficha["id"])
        lider = LIDERES_FICHA.get(ficha["id"])
        fichas.append(
            FichaMotor(
                id=ficha["id"],
                trimestre=ficha["trimestre"],
                jornada=JORNADA_DE_BLOQUES.get(ficha["jornada"], "Mañana"),
                prioridad=_prioridad(ficha["trimestre"]),
                bloques=bloques_de_jornada(ficha["jornada"]),
                horas_tecnicas=float(ficha["horas_semanales"]),
                competencias=[tuple(c.split(" · ", 1)) for c in ficha["competencias"]],
                aula_base=AULAS.general[indice % len(AULAS.general)],
                ingles=(ingles["dia"], ingles["bloque"]) if ingles else None,
                lider_id=lider["instructor_id"] if lider else None,
                bloques_lider=[(b["dia"], b["bloque"]) for b in lider["bloques"]] if lider else [],
                transversales=_transversales_de(ficha),
                instructores_habituales=list(ficha["instructor_ids"]),
            )
        )
    return fichas


@router.post(
    "/generar",
    response_model=ResultadoGeneracion,
    summary="Generar automáticamente el horario de todas las fichas",
)
def generar(usuario: dict = Depends(require_gestora)) -> ResultadoGeneracion:
    exigir_trimestre_abierto()
    instructores = _instructores()
    resultado = generar_horario(_fichas(), instructores, AULAS, list(DIAS_SEMANA))

    HORARIO_GENERADO.clear()
    HORARIO_GENERADO.update(
        generado_en=datetime.now(),
        generado_por=int(usuario.get("sub") or usuario.get("id")),
        sesiones=resultado["sesiones"],
        pendientes=resultado["pendientes"],
    )

    pendientes = [PendienteHorario(**p) for p in resultado["pendientes"]]
    return ResultadoGeneracion(
        generado_en=HORARIO_GENERADO["generado_en"],
        total_sesiones=len(resultado["sesiones"]),
        horas_programadas=sum(s["horas"] for s in resultado["sesiones"]),
        fichas=len({s["ficha_id"] for s in resultado["sesiones"]}),
        pendientes=pendientes,
        pendientes_prioridad_alta=sum(1 for p in pendientes if p.prioridad == 1),
        carga=[
            CargaGenerada(id=i.id, nombre=i.nombre, horas=resultado["carga"].get(i.id, 0.0), tope=i.tope_horas)
            for i in instructores
            if resultado["carga"].get(i.id)
        ],
    )
