from enum import Enum

from pydantic import BaseModel, Field, field_validator, model_validator

from app.core.carga import MAX_HORAS_CONTINUAS_DIA, horas_continuas_maximas


class BloqueHorario(str, Enum):
    BLOQUE_1 = "06:00-09:00"
    BLOQUE_2 = "09:00-12:00"
    BLOQUE_3 = "12:00-15:00"
    BLOQUE_4 = "15:00-18:00"
    BLOQUE_5 = "18:00-20:00"
    BLOQUE_6 = "20:00-22:00"


class DiaSemana(str, Enum):
    """Jornada habitual del SENA: lunes a viernes (no se programa el sábado)."""

    LUNES = "LUNES"
    MARTES = "MARTES"
    MIERCOLES = "MIERCOLES"
    JUEVES = "JUEVES"
    VIERNES = "VIERNES"


def validar_dia_habil(valor):
    """Rechaza fines de semana con un mensaje claro antes de validar el enum."""
    if isinstance(valor, str) and valor.strip().upper() in {"SABADO", "SÁBADO", "DOMINGO"}:
        raise ValueError("Solo se programa de lunes a viernes; el sábado no es un día hábil.")
    return valor


class DisponibilidadBloque(BaseModel):
    dia: DiaSemana
    bloque: BloqueHorario

    _validar_dia = field_validator("dia", mode="before")(validar_dia_habil)


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

    @model_validator(mode="after")
    def validar_horas_continuas(self) -> "RegistroDisponibilidad":
        rangos_por_dia: dict[DiaSemana, list[str]] = {}
        for item in self.bloques:
            rangos_por_dia.setdefault(item.dia, []).append(item.bloque.value)
        for dia, rangos in rangos_por_dia.items():
            continuas = horas_continuas_maximas(rangos)
            if continuas > MAX_HORAS_CONTINUAS_DIA:
                raise ValueError(
                    f"{dia.value.capitalize()}: {continuas:g} h continuas superan el máximo "
                    f"de {MAX_HORAS_CONTINUAS_DIA} h por día."
                )
        return self
