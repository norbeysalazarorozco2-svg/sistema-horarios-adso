from datetime import date
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.equidad import Compensacion


EstadoAlerta = Literal["abierta", "confirmacion_solicitada", "cubierta"]
EstadoSolicitudHorasExtra = Literal["pendiente", "aceptada", "rechazada", "cancelada"]


class CandidatoHueco(BaseModel):
    """Instructor que domina el RAP y aún tiene margen hasta el tope de 40 h."""

    id: int
    nombre: str
    horas_formacion: float = Field(ge=0, description="Incluye las horas extra ya aceptadas.")
    horas_administrativas: float = Field(ge=0)
    horas_totales: float = Field(ge=0)
    margen_horas: float = Field(ge=0, description="Horas que le quedan hasta el tope semanal.")
    horas_que_cubre: float = Field(ge=0)
    cubre_hueco: bool
    extra_trimestre_anterior: bool = Field(
        description="Llegó a 40 h con horas extra el trimestre anterior; por equidad se propone al final.",
    )
    nota_equidad: str = ""


class SolicitudConfirmacion(BaseModel):
    """Solicitud de horas extra de la gestora a un instructor, y su respuesta."""

    id: int
    alerta_id: int
    instructor_id: int
    instructor_nombre: str
    horas: float = Field(gt=0, description="Horas extra solicitadas para cubrir el hueco.")
    fecha_solicitud: date
    estado: EstadoSolicitudHorasExtra
    motivo: str = Field(default="", description="Motivo del rechazo, si lo hubo.")
    fecha_respuesta: date | None = None


class SolicitudDetallada(SolicitudConfirmacion):
    """Solicitud con el contexto del hueco (ficha y RAP)."""

    ficha_id: int
    jornada: str
    trimestre: int
    prioridad: Literal[1, 2]
    rap_nombre: str
    competencia_nombre: str
    bloques: list[str]


class AlertaHueco(BaseModel):
    id: int
    ficha_id: int
    jornada: str
    trimestre: int = Field(ge=1)
    prioridad: Literal[1, 2] = Field(description="1: trimestres 1–5 (sin huecos). 2: trimestres 6–7.")
    rap_id: int
    rap_nombre: str
    competencia_codigo: str
    competencia_nombre: str
    horas_requeridas: float = Field(gt=0)
    horas_pendientes: float = Field(ge=0, description="Horas que siguen sin instructor.")
    bloques: list[str] = Field(default_factory=list)
    estado: EstadoAlerta
    solicitud: SolicitudConfirmacion | None = Field(default=None, description="Solicitud pendiente, si hay.")
    respuestas: list[SolicitudConfirmacion] = Field(
        default_factory=list,
        description="Solicitudes aceptadas o rechazadas por los instructores.",
    )
    candidatos: list[CandidatoHueco] = Field(default_factory=list)


class ResumenAlertas(BaseModel):
    total: int
    abiertas: int
    abiertas_prioridad_alta: int
    en_confirmacion: int
    cubiertas: int


class ListadoAlertas(BaseModel):
    resumen: ResumenAlertas
    respuestas_recientes: list[SolicitudDetallada] = Field(
        description="Últimas respuestas de los instructores, la más reciente primero.",
    )
    alertas: list[AlertaHueco]


class SolicitudConfirmacionCreate(BaseModel):
    instructor_id: int


# ── Lado del instructor ──────────────────────────────────────────────────────

class CargaInstructor(BaseModel):
    horas_formacion: float = Field(ge=0, description="Formación base, sin horas extra.")
    horas_extra_aceptadas: float = Field(ge=0)
    horas_administrativas: float = Field(ge=0)
    horas_totales: float = Field(ge=0)


class SolicitudParaInstructor(SolicitudDetallada):
    horas_totales_con_extra: float = Field(description="Carga total si acepta esta solicitud.")
    puede_aceptar: bool
    motivo_bloqueo: str = ""


class BandejaHorasExtra(BaseModel):
    carga: CargaInstructor
    compensacion: Compensacion | None = Field(
        default=None,
        description="Si debe recibir menos carga este trimestre (§6).",
    )
    pendientes: list[SolicitudParaInstructor]
    historial: list[SolicitudParaInstructor]


class RespuestaHorasExtra(BaseModel):
    acepta: bool
    motivo: str = Field(default="", max_length=300)
