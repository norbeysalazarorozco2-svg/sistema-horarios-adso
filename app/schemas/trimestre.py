from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator


NivelVerificacion = Literal["bloqueante", "advertencia"]
EstadoTrimestre = Literal["abierto", "aprobado"]


class Verificacion(BaseModel):
    id: str
    titulo: str
    nivel: NivelVerificacion
    cumple: bool
    detalle: str
    items: list[str] = Field(default_factory=list, description="Casos concretos que la incumplen.")
    enlace: str | None = Field(default=None, description="Vista donde se resuelve.")


class EventoTrimestre(BaseModel):
    tipo: Literal["aprobado", "reabierto"]
    fecha: datetime
    gestora_id: int
    gestora_nombre: str
    texto: str = Field(default="", description="Observaciones al aprobar o motivo al reabrir.")
    advertencias_aceptadas: list[str] = Field(default_factory=list)


class EstadoAprobacion(BaseModel):
    periodo: str
    estado: EstadoTrimestre
    aprobacion: EventoTrimestre | None = Field(default=None, description="Aprobación vigente, si la hay.")
    verificaciones: list[Verificacion]
    bloqueantes: int
    advertencias: int
    puede_aprobar: bool
    historial: list[EventoTrimestre] = Field(default_factory=list)


class SolicitudAprobacion(BaseModel):
    confirma_advertencias: bool = Field(
        default=False,
        description="Obligatorio si hay advertencias: la gestora las revisó y aprueba con ellas.",
    )
    observaciones: str = Field(default="", max_length=500)


class SolicitudReapertura(BaseModel):
    motivo: str = Field(max_length=300)

    @field_validator("motivo")
    @classmethod
    def validar_motivo(cls, valor: str) -> str:
        valor = valor.strip()
        if len(valor) < 5:
            raise ValueError("Indica el motivo para reabrir el trimestre.")
        return valor
