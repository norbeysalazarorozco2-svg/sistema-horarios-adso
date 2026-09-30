from enum import Enum

from pydantic import BaseModel, Field, field_validator


class BloqueHorario(str, Enum):
    BLOQUE_1 = "06:00-09:00"
    BLOQUE_2 = "09:00-12:00"
    BLOQUE_3 = "12:00-15:00"
    BLOQUE_4 = "15:00-18:00"
    BLOQUE_5 = "18:00-20:00"
    BLOQUE_6 = "20:00-22:00"


class DiaSemana(str, Enum):
    LUNES = "LUNES"
    MARTES = "MARTES"
    MIERCOLES = "MIERCOLES"
    JUEVES = "JUEVES"
    VIERNES = "VIERNES"
    SABADO = "SABADO"


class DisponibilidadBloque(BaseModel):
    dia: DiaSemana
    bloque: BloqueHorario


class RegistroDisponibilidad(BaseModel):
    competencia: str
    rap: str
    numero_trimestre: int = Field(
        default=1,
        ge=1,
        le=6,
        description="Trimestre gestionado internamente por el sistema (pertenece a las fichas, no lo elige el instructor en esta pantalla).",
    )
    reutilizar_anterior: bool = Field(
        default=False,
        description="Indica si el instructor decidió reutilizar la disponibilidad del trimestre anterior.",
    )
    bloques: list[DisponibilidadBloque] = Field(
        default_factory=list,
        description="Bloques horarios disponibles. Puede quedar con espacios sin cubrir.",
    )

    @field_validator("competencia")
    @classmethod
    def validar_competencia(cls, valor: str) -> str:
        valor = valor.strip()
        if not valor:
            raise ValueError("Debes seleccionar una competencia.")
        return valor

    @field_validator("rap")
    @classmethod
    def validar_rap(cls, valor: str) -> str:
        valor = valor.strip()
        if not valor:
            raise ValueError("Debes seleccionar un RAP.")
        return valor