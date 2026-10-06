from pydantic import BaseModel, Field


class RegistroCarga(BaseModel):
    """Carga semanal de un instructor en un trimestre (modelo_datos: historial_carga)."""

    periodo: str = Field(examples=["2026-T3"])
    horas_formacion: float = Field(ge=0, description="Formación sin horas extra.")
    horas_extra: float = Field(ge=0)
    horas_totales: float = Field(ge=0, description="Formación + extra + administrativas.")
    llego_al_tope: bool


class Compensacion(BaseModel):
    """El instructor llegó a 40 h con horas extra en el trimestre anterior (§6)."""

    periodo: str
    horas_totales: float
    horas_extra: float
    carga_maxima_recomendada: float = Field(description="Este trimestre, sin horas extra.")


class EquidadInstructor(BaseModel):
    id: int
    nombre: str
    es_nuevo: bool
    historial: list[RegistroCarga | None] = Field(description="Alineado con ListadoEquidad.periodos.")
    en_curso: RegistroCarga
    en_curso_registrado: bool = Field(description="El cierre del trimestre en curso ya se guardó.")
    compensacion: Compensacion | None = None
    excede_recomendacion: bool = Field(
        default=False,
        description="Debe compensar pero su carga en curso supera la recomendada.",
    )


class ListadoEquidad(BaseModel):
    periodo_actual: str
    periodos: list[str] = Field(description="Trimestres cerrados anteriores, del más antiguo al más reciente.")
    a_compensar: int
    instructores: list[EquidadInstructor]
