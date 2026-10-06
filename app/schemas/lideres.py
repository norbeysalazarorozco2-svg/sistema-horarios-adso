from datetime import date
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from app.schemas.disponibilidad import BloqueHorario, DiaSemana, validar_dia_habil

MAX_BLOQUES_LIDER = 2


class BloqueLider(BaseModel):
    dia: DiaSemana
    bloque: BloqueHorario

    _validar_dia = field_validator("dia", mode="before")(validar_dia_habil)


class LiderAsignado(BaseModel):
    instructor_id: int
    instructor_nombre: str
    bloques: list[BloqueLider]
    asignado_por: int
    fecha_asignacion: date


class FichaLider(BaseModel):
    id: int
    programa: str
    jornada: str
    trimestre: int = Field(ge=1)
    prioridad: Literal[1, 2]
    instructor_ids: list[int] = Field(description="Instructores que ya dictan en la ficha.")
    bloques_permitidos: list[BloqueHorario] = Field(description="Bloques de la jornada de la ficha.")
    bloque_ingles: BloqueLider | None = Field(
        default=None, description="Inglés fijo de la gestora: bloqueado, no se puede asignar al líder."
    )
    lider: LiderAsignado | None = None


class InstructorLiderOpcion(BaseModel):
    id: int
    nombre: str
    es_nuevo: bool
    lidera_ficha_id: int | None = None


class ResumenLideres(BaseModel):
    total_fichas: int
    sin_lider: int


class ListadoLideres(BaseModel):
    resumen: ResumenLideres
    fichas: list[FichaLider]
    instructores: list[InstructorLiderOpcion]


class AsignacionLider(BaseModel):
    instructor_id: int
    bloques: list[BloqueLider] = Field(
        description="1 bloque obligatorio; 2 deseables, el mismo día y seguidos.",
    )

    @field_validator("bloques")
    @classmethod
    def validar_bloques(cls, bloques: list[BloqueLider]) -> list[BloqueLider]:
        claves = {(b.dia, b.bloque) for b in bloques}
        if len(claves) != len(bloques):
            raise ValueError("Hay bloques repetidos.")
        if not 1 <= len(bloques) <= MAX_BLOQUES_LIDER:
            raise ValueError(
                f"El líder necesita entre 1 y {MAX_BLOQUES_LIDER} bloques semanales con su ficha."
            )
        return bloques
