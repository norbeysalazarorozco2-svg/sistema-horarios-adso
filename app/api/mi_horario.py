"""
mi_horario.py — "Mi horario" del instructor.
Prefijo: /api/v1/instructor
Sistema de Horarios ADSO — SENA

Solo lectura: las sesiones que el motor le asignó al instructor autenticado en
el último horario generado por la gestora (fichas, competencias y aulas). El
motor solo usa las franjas que el instructor marcó en Disponibilidad.
"""

from fastapi import APIRouter, Depends

from app.api.gestora import HORARIO_GENERADO, a_bloque_horario, orden_sesion
from app.api.mi_ficha import instructor_id_de
from app.core.security import require_instructor
from app.schemas.gestora import BLOQUES_HORARIOS, DIAS_SEMANA
from app.schemas.mi_horario import MiHorario

router = APIRouter(
    prefix="/api/v1/instructor",
    tags=["Instructor · Mi horario"],
)


@router.get(
    "/mi-horario",
    response_model=MiHorario,
    summary="Horario semanal del instructor autenticado",
)
def consultar_mi_horario(usuario: dict = Depends(require_instructor)) -> MiHorario:
    instructor_id = instructor_id_de(usuario)
    sesiones = sorted(
        (s for s in HORARIO_GENERADO.get("sesiones", []) if s["instructor_id"] == instructor_id),
        key=orden_sesion,
    )
    return MiHorario(
        generado=bool(HORARIO_GENERADO),
        generado_en=HORARIO_GENERADO.get("generado_en"),
        dias=list(DIAS_SEMANA),
        bloques=list(BLOQUES_HORARIOS),
        sesiones=[a_bloque_horario(s) for s in sesiones],
        horas_semanales=sum(s["horas"] for s in sesiones),
        fichas=sorted({s["ficha_id"] for s in sesiones}),
    )
