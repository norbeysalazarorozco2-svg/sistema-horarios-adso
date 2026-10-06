from datetime import date
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.alertas import EstadoAlerta
from app.schemas.disponibilidad import BloqueHorario
from app.schemas.lideres import BloqueLider


class FichaResumen(BaseModel):
    id: int
    programa: str
    jornada: str
    trimestre: int = Field(ge=1)
    prioridad: Literal[1, 2]
    competencias: list[str] = Field(default_factory=list)


class InstructorDeFicha(BaseModel):
    id: int
    nombre: str
    es_lider: bool


class HuecoDeFicha(BaseModel):
    rap_nombre: str
    competencia_nombre: str
    horas_requeridas: float
    bloques: list[str]
    estado: EstadoAlerta


class TransversalDeFicha(BaseModel):
    id: int
    transversales: list[str]
    estado: str
    fecha_limite: date | None = None


class MiFicha(BaseModel):
    """Lo que ve el instructor líder sobre la ficha que lidera."""

    ficha: FichaResumen
    bloques_lider: list[BloqueLider]
    bloques_ideales: bool = Field(description="2 bloques seguidos el mismo día (regla blanda §3).")
    fecha_asignacion: date
    bloques_jornada: list[BloqueHorario]
    bloque_ingles: BloqueLider | None = Field(default=None, description="Inglés fijo de la gestora (bloqueado).")
    instructores: list[InstructorDeFicha]
    huecos: list[HuecoDeFicha]
    transversales: list[TransversalDeFicha]
