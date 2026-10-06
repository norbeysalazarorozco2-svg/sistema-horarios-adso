"""
lideres.py — Asignación del instructor líder de ficha.
Prefijo: /api/v1/gestora/lideres
Sistema de Horarios ADSO — SENA

Reglas (docs/reglas-negocio.md §3 y §8, docs/modelo_datos.md):
  - Cada ficha tiene un líder (`instructor_lider_id`) que permanece fijo en el trimestre.
  - Un instructor lidera como máximo una ficha (`lidera_ficha_id`).
  - Obligatorio: mínimo 1 clase a la semana con su ficha.
    Deseable: 2 clases, en bloque, el mismo día.
  - Solo la gestora aprueba al líder.
  - La gestora fija (y puede mover) el bloque de Inglés de cada ficha; ese
    bloque queda bloqueado para el líder y para el motor.

Todas las operaciones exigen rol de Gestora (`require_gestora`).
"""

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.alertas import prioridad_de_trimestre
from app.api.disponibilidad import es_nuevo_instructor
from app.api.gestora import FICHAS_GESTORA_MOCK, INGLES_FICHA, INSTRUCTORES_GESTORA, bloque_ingles
from app.core.carga import HORAS_INGLES_POR_JORNADA, horas_continuas_maximas
from app.api.trimestre import exigir_trimestre_abierto
from app.core.security import require_gestora
from app.schemas.disponibilidad import BloqueHorario
from app.schemas.gestora import JORNADA_DE_BLOQUES, JORNADA_POR_BLOQUE
from app.schemas.lideres import (
    AsignacionLider,
    BloqueLider,
    FichaLider,
    InstructorLiderOpcion,
    LiderAsignado,
    ListadoLideres,
    ResumenLideres,
)


router = APIRouter(
    prefix="/api/v1/gestora/lideres",
    tags=["Gestora · Líderes de ficha"],
)

# ⚠️ PROVISIONAL — datos en memoria (reemplazar con Ficha.instructor_lider_id en SQLAlchemy)
# ficha_id → líder asignado. El instructor 101 (cuenta demo) lidera la 3365169.
LIDERES_FICHA: dict[int, dict] = {
    3365169: {
        "instructor_id": 101,
        "bloques": [
            {"dia": "LUNES", "bloque": "06:00-09:00"},
            {"dia": "LUNES", "bloque": "09:00-12:00"},
        ],
        "asignado_por": 1,
        "fecha_asignacion": date(2026, 9, 1),
    },
    3365131: {
        "instructor_id": 105,
        "bloques": [{"dia": "MIERCOLES", "bloque": "12:00-15:00"}],
        "asignado_por": 1,
        "fecha_asignacion": date(2026, 9, 1),
    },
}


def ficha_liderada_por(instructor_id: int) -> int | None:
    return next((fid for fid, r in LIDERES_FICHA.items() if r["instructor_id"] == instructor_id), None)


def bloques_ideales(bloques: list[dict]) -> bool:
    """Deseable (§3): 2 bloques seguidos, el mismo día."""
    if len(bloques) != 2 or bloques[0]["dia"] != bloques[1]["dia"]:
        return False
    rangos = [b["bloque"] for b in bloques]
    duracion = sum(horas_continuas_maximas([r]) for r in rangos)
    return horas_continuas_maximas(rangos) == duracion


def _instructor(instructor_id: int) -> dict | None:
    return next((i for i in INSTRUCTORES_GESTORA if int(i["id"]) == instructor_id), None)


def _ficha_o_404(ficha_id: int) -> dict:
    ficha = next((f for f in FICHAS_GESTORA_MOCK if f["id"] == ficha_id), None)
    if ficha is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"No existe la ficha {ficha_id}.")
    return ficha


def bloques_permitidos(jornada: str) -> list[BloqueHorario]:
    objetivo = JORNADA_DE_BLOQUES.get(jornada)
    return [BloqueHorario(b) for b, j in JORNADA_POR_BLOQUE.items() if objetivo is None or j == objetivo]


def _ficha_lider(ficha: dict) -> FichaLider:
    registro = LIDERES_FICHA.get(ficha["id"])
    lider = None
    if registro:
        instructor = _instructor(registro["instructor_id"]) or {}
        lider = LiderAsignado(
            instructor_nombre=instructor.get("nombre", f"Instructor {registro['instructor_id']}"),
            **registro,
        )
    return FichaLider(
        id=ficha["id"],
        programa=ficha["programa"],
        jornada=ficha["jornada"],
        trimestre=ficha["trimestre"],
        prioridad=prioridad_de_trimestre(ficha["trimestre"]),
        instructor_ids=ficha["instructor_ids"],
        bloques_permitidos=bloques_permitidos(ficha["jornada"]),
        bloque_ingles=bloque_ingles(ficha["id"]),
        lider=lider,
    )


@router.get(
    "",
    response_model=ListadoLideres,
    summary="Fichas con su líder y los instructores que pueden liderarlas",
)
def listar_lideres(_usuario: dict = Depends(require_gestora)) -> ListadoLideres:
    fichas = [_ficha_lider(f) for f in sorted(FICHAS_GESTORA_MOCK, key=lambda f: (f["trimestre"], f["id"]))]
    lidera = {registro["instructor_id"]: ficha_id for ficha_id, registro in LIDERES_FICHA.items()}
    instructores = [
        InstructorLiderOpcion(
            id=int(i["id"]),
            nombre=str(i["nombre"]),
            es_nuevo=es_nuevo_instructor(i.get("fecha_ingreso")),
            lidera_ficha_id=lidera.get(int(i["id"])),
        )
        for i in INSTRUCTORES_GESTORA
    ]
    return ListadoLideres(
        resumen=ResumenLideres(
            total_fichas=len(fichas),
            sin_lider=sum(1 for f in fichas if f.lider is None),
        ),
        fichas=fichas,
        instructores=instructores,
    )


@router.put(
    "/{ficha_id}",
    response_model=FichaLider,
    summary="Asignar (o cambiar) el líder de una ficha con sus bloques semanales",
)
def asignar_lider(
    ficha_id: int,
    datos: AsignacionLider,
    usuario: dict = Depends(require_gestora),
) -> FichaLider:
    exigir_trimestre_abierto()
    ficha = _ficha_o_404(ficha_id)
    if _instructor(datos.instructor_id) is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="El instructor no está vinculado a la gestora.",
        )

    otra_ficha = next(
        (fid for fid, r in LIDERES_FICHA.items() if r["instructor_id"] == datos.instructor_id and fid != ficha_id),
        None,
    )
    if otra_ficha is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"El instructor ya es líder de la ficha {otra_ficha}.",
        )

    permitidos = set(bloques_permitidos(ficha["jornada"]))
    fuera = [b for b in datos.bloques if b.bloque not in permitidos]
    if fuera:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"El bloque {fuera[0].bloque.value} no pertenece a la jornada {ficha['jornada']} de la ficha.",
        )

    ingles = bloque_ingles(ficha_id)
    if ingles and any(b.dia.value == ingles["dia"] and b.bloque.value == ingles["bloque"] for b in datos.bloques):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"{ingles['dia'].capitalize()} {ingles['bloque']} está bloqueado: "
                "es el Inglés fijo de la ficha."
            ),
        )

    LIDERES_FICHA[ficha_id] = {
        "instructor_id": datos.instructor_id,
        "bloques": [{"dia": b.dia.value, "bloque": b.bloque.value} for b in datos.bloques],
        "asignado_por": int(usuario.get("sub") or usuario.get("id")),
        "fecha_asignacion": date.today(),
    }
    return _ficha_lider(ficha)


@router.put(
    "/{ficha_id}/ingles",
    response_model=FichaLider,
    summary="Mover el bloque fijo de Inglés de una ficha",
)
def fijar_ingles(
    ficha_id: int,
    datos: BloqueLider,
    usuario: dict = Depends(require_gestora),
) -> FichaLider:
    exigir_trimestre_abierto()
    ficha = _ficha_o_404(ficha_id)
    dia, bloque = datos.dia.value, datos.bloque.value

    jornada = JORNADA_DE_BLOQUES.get(ficha["jornada"], "Mañana")
    horas = HORAS_INGLES_POR_JORNADA[jornada]
    if datos.bloque not in bloques_permitidos(ficha["jornada"]) or horas_continuas_maximas([bloque]) != horas:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Inglés en jornada {jornada} va en un bloque de {horas} h de esa jornada; {bloque} no lo es.",
        )

    lider = LIDERES_FICHA.get(ficha_id)
    if lider and any(b["dia"] == dia and b["bloque"] == bloque for b in lider["bloques"]):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"{dia.capitalize()} {bloque} es un bloque del líder de la ficha. Cámbialo primero.",
        )

    # El horario consolidado del trimestre muestra una ficha por celda.
    otra = next(
        (
            f["id"]
            for f in FICHAS_GESTORA_MOCK
            if f["id"] != ficha_id
            and f["trimestre"] == ficha["trimestre"]
            and INGLES_FICHA.get(f["id"], {}).get("dia") == dia
            and INGLES_FICHA.get(f["id"], {}).get("bloque") == bloque
        ),
        None,
    )
    if otra is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"La ficha {otra} del mismo trimestre ya tiene Inglés el {dia.lower()} {bloque}.",
        )

    INGLES_FICHA[ficha_id] = {
        "dia": dia,
        "bloque": bloque,
        "horas": horas,
        "fijado_por": int(usuario.get("sub") or usuario.get("id")),
    }
    return _ficha_lider(ficha)


@router.delete(
    "/{ficha_id}",
    response_model=FichaLider,
    summary="Quitar el líder de una ficha",
)
def quitar_lider(ficha_id: int, _usuario: dict = Depends(require_gestora)) -> FichaLider:
    exigir_trimestre_abierto()
    ficha = _ficha_o_404(ficha_id)
    LIDERES_FICHA.pop(ficha_id, None)
    return _ficha_lider(ficha)
