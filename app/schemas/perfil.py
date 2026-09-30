from datetime import date
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator


ModoPrueba = Literal["nuevo", "antiguo"]


TRANSVERSALES_DISPONIBLES = (
    "Inglés",
    "Ética",
    "Promover",
    "Salud Ocupacional",
)


class CompetenciaPerfil(BaseModel):
    codigo: str
    nombre: str


class FichaAsignada(BaseModel):
    id: int
    programa: str
    jornada: str
    trimestre: int = Field(ge=1, le=6)
    competencias: list[CompetenciaPerfil] = Field(default_factory=list)
    horas_semanales: float = Field(ge=0)


class SolicitudTransversal(BaseModel):
    id: int
    ficha_id: int
    solicitada_por: int
    transversales: list[str]
    fecha_solicitud: date
    fecha_limite: date
    estado: str
    asignada_por: int | None = None
    fecha_asignacion: date | None = None
    horas_sugeridas: float | None = None
    bloque_sugerido: str = ""
    comentarios: str = ""
    gestora_id: int | None = None
    gestora_nombre: str | None = None


class PerfilInstructor(BaseModel):
    id: int
    nombre: str
    correo_sena: str
    fecha_ingreso: date | None = None
    es_nuevo: bool
    antiguedad_dias: int = Field(ge=0)
    competencias: list[CompetenciaPerfil] = Field(default_factory=list)
    fichas: list[FichaAsignada] = Field(default_factory=list)
    horas_semanales: float = Field(ge=0)
    solicitudes_transversales: list[SolicitudTransversal] = Field(default_factory=list)
    modo_prueba: ModoPrueba = "antiguo"


class CambioModoPrueba(BaseModel):
    modo: ModoPrueba


class RespuestaModoPrueba(BaseModel):
    modo: ModoPrueba


class SolicitudTransversalCreate(BaseModel):
    ficha_ids: list[int] = Field(min_length=1)
    transversales: list[str] = Field(min_length=1)
    horas_sugeridas: float | None = Field(default=None, ge=0, le=40)
    bloque_sugerido: str = Field(default="", max_length=120)
    comentarios: str = Field(default="", max_length=500)

    @model_validator(mode="before")
    @classmethod
    def normalizar_seleccion(cls, datos: object) -> object:
        if not isinstance(datos, dict):
            return datos

        normalizado = dict(datos)
        if normalizado.get("ficha_ids") is None and normalizado.get("ficha_id") is not None:
            normalizado["ficha_ids"] = [normalizado["ficha_id"]]
        if normalizado.get("transversales") is None and normalizado.get("transversal") is not None:
            normalizado["transversales"] = [normalizado["transversal"]]
        return normalizado

    @field_validator("ficha_ids")
    @classmethod
    def validar_fichas(cls, fichas: list[int]) -> list[int]:
        fichas_unicas = list(dict.fromkeys(fichas))
        if not fichas_unicas or any(ficha <= 0 for ficha in fichas_unicas):
            raise ValueError("Selecciona al menos una ficha válida.")
        return fichas_unicas

    @field_validator("transversales")
    @classmethod
    def validar_transversales(cls, transversales: list[str]) -> list[str]:
        valores = [transversal.strip() for transversal in transversales]
        if any(not valor for valor in valores):
            raise ValueError("Selecciona al menos una asignatura transversal.")
        invalidas = sorted(set(valores) - set(TRANSVERSALES_DISPONIBLES))
        if invalidas:
            raise ValueError(
                "Asignaturas transversales no válidas: " + ", ".join(invalidas)
            )
        return list(dict.fromkeys(valores))

    @field_validator("bloque_sugerido", "comentarios", mode="before")
    @classmethod
    def normalizar_detalles(cls, valor: object) -> str:
        return str(valor or "").strip()


class ResultadoSolicitudTransversal(BaseModel):
    mensaje: str
    solicitudes: list[SolicitudTransversal]
