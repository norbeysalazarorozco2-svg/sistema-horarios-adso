from pydantic import BaseModel


class RAPTrimestre(BaseModel):
    """RAP requerido en un trimestre del programa."""

    id: int
    programa: str
    numero_trimestre: int
    rap_id: int
    competencia_id: int
