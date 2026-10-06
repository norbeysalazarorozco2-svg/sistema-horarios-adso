"""
mi_ficha.py — Vista "Mi ficha" del instructor líder.
Prefijo: /api/v1/instructor
Sistema de Horarios ADSO — SENA

Solo lectura: el líder consulta su ficha, sus bloques semanales, el equipo de
instructores, los RAP sin cubrir y las transversales. Las decisiones (líder,
horas extra, transversales) siguen siendo de la gestora (reglas-negocio §8).
"""

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.alertas import alertas_de_ficha, prioridad_de_trimestre
from app.api.gestora import FICHAS_GESTORA_MOCK, INSTRUCTORES_GESTORA, bloque_ingles
from app.api.lideres import LIDERES_FICHA, bloques_ideales, bloques_permitidos, ficha_liderada_por
from app.api.perfil import SOLICITUDES_TRANSVERSALES
from app.core.security import require_instructor
from app.schemas.mi_ficha import (
    FichaResumen,
    HuecoDeFicha,
    InstructorDeFicha,
    MiFicha,
    TransversalDeFicha,
)


router = APIRouter(
    prefix="/api/v1/instructor",
    tags=["Instructor · Mi ficha"],
)


def instructor_id_de(usuario: dict) -> int | None:
    try:
        return int(str(usuario.get("sub") or usuario.get("id")))
    except (TypeError, ValueError):
        return None


@router.get(
    "/mi-ficha",
    response_model=MiFicha,
    summary="Ficha que lidera el instructor autenticado",
    responses={404: {"description": "El instructor no es líder de ninguna ficha."}},
)
def consultar_mi_ficha(usuario: dict = Depends(require_instructor)) -> MiFicha:
    instructor_id = instructor_id_de(usuario)
    ficha_id = ficha_liderada_por(instructor_id) if instructor_id is not None else None
    ficha = next((f for f in FICHAS_GESTORA_MOCK if f["id"] == ficha_id), None)
    if ficha is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No eres líder de ninguna ficha este trimestre.",
        )

    registro = LIDERES_FICHA[ficha["id"]]
    nombres = {int(i["id"]): str(i["nombre"]) for i in INSTRUCTORES_GESTORA}
    # El líder aparece primero aunque no dicte otra materia en la ficha.
    equipo = [instructor_id] + [i for i in ficha["instructor_ids"] if i != instructor_id]

    return MiFicha(
        ficha=FichaResumen(
            id=ficha["id"],
            programa=ficha["programa"],
            jornada=ficha["jornada"],
            trimestre=ficha["trimestre"],
            prioridad=prioridad_de_trimestre(ficha["trimestre"]),
            competencias=ficha["competencias"],
        ),
        bloques_lider=registro["bloques"],
        bloques_ideales=bloques_ideales(registro["bloques"]),
        fecha_asignacion=registro["fecha_asignacion"],
        bloques_jornada=bloques_permitidos(ficha["jornada"]),
        bloque_ingles=bloque_ingles(ficha["id"]),
        instructores=[
            InstructorDeFicha(id=i, nombre=nombres.get(i, f"Instructor {i}"), es_lider=i == instructor_id)
            for i in equipo
        ],
        huecos=[
            HuecoDeFicha(
                rap_nombre=a.rap_nombre,
                competencia_nombre=a.competencia_nombre,
                horas_requeridas=a.horas_requeridas,
                bloques=a.bloques,
                estado=a.estado,
            )
            for a in alertas_de_ficha(ficha["id"])
        ],
        transversales=[
            TransversalDeFicha(
                id=s["id"],
                transversales=s.get("transversales", []),
                estado=s.get("estado", ""),
                fecha_limite=s.get("fecha_limite"),
            )
            for s in SOLICITUDES_TRANSVERSALES
            if s.get("ficha_id") == ficha["id"]
        ],
    )
