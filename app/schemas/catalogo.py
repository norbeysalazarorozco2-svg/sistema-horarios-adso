from pydantic import BaseModel


class Competencia(BaseModel):
    """Competencia del catálogo de formación."""

    id: int
    nombre: str
    codigo: str


class RAP(BaseModel):
    """Resultado de aprendizaje del catálogo de formación."""

    id: int
    nombre: str
    competencia_id: int
