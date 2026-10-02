from pydantic import BaseModel, Field


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


class ProgramaFormacion(BaseModel):
    """Programa de formación. Su duración define cuántos trimestres existen."""

    codigo: str
    total_trimestres: int = Field(ge=1)

    @property
    def trimestres(self) -> list[int]:
        return list(range(1, self.total_trimestres + 1))
