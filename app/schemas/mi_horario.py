from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.gestora import BloqueHorario


class MiHorario(BaseModel):
    """Horario semanal del instructor: se repite todas las semanas del trimestre."""

    generado: bool = Field(description="False: la gestora aún no ha generado el horario.")
    generado_en: datetime | None = None
    dias: list[str]
    bloques: list[str]
    sesiones: list[BloqueHorario]
    horas_semanales: float
    fichas: list[int]
