"""
gestora.py — Esquemas de la vista independiente de la Gestora.
Sistema de Horarios ADSO — SENA

Cubre las tres secciones de /perfil-gestora:
  - Bandeja de solicitudes de transversales.
  - Fichas & trimestres.
  - Horarios.
"""

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator


# ── Catálogos de la vista ────────────────────────────────────────────────────

ESTADO_ABIERTO = "Pendiente"
ESTADO_EN_REVISION = "En revisión"
ESTADO_APROBADO = "Aprobado"
ESTADO_RECHAZADO = "Rechazado"

ESTADOS_SOLICITUD: tuple[str, ...] = (
    ESTADO_ABIERTO,
    ESTADO_EN_REVISION,
    ESTADO_APROBADO,
    ESTADO_RECHAZADO,
)

ESTADOS_CERRADOS: tuple[str, ...] = (ESTADO_APROBADO, ESTADO_RECHAZADO)

EstadoSolicitud = Literal[
    "Pendiente",
    "En revisión",
    "Aprobado",
    "Rechazado",
]

JORNADA_POR_BLOQUE: dict[str, str] = {
    "06:00-09:00": "Mañana",
    "09:00-12:00": "Mañana",
    "12:00-15:00": "Tarde",
    "15:00-18:00": "Tarde",
    "18:00-20:00": "Noche",
    "20:00-22:00": "Noche",
}

BLOQUES_HORARIOS: tuple[str, ...] = tuple(JORNADA_POR_BLOQUE)

# Las fichas usan "Diurna"/"Nocturna"; los bloques, "Mañana"/"Tarde"/"Noche".
JORNADA_DE_BLOQUES: dict[str, str] = {
    "Diurna": "Mañana",
    "Mañana": "Mañana",
    "Tarde": "Tarde",
    "Nocturna": "Noche",
    "Noche": "Noche",
}

DIAS_SEMANA: tuple[str, ...] = (
    "LUNES",
    "MARTES",
    "MIERCOLES",
    "JUEVES",
    "VIERNES",
)


# ── Identidad y resumen ──────────────────────────────────────────────────────

class PerfilGestora(BaseModel):
    id: int
    nombre: str
    correo_sena: str
    rol: str = "gestora"
    trimestre_actual: int = Field(ge=1)
    solicitudes_abiertas: int = Field(ge=0)
    solicitudes_vencidas: int = Field(ge=0)
    fichas_activas: int = Field(ge=0)
    fichas_sin_instructor: int = Field(ge=0)
    instructores_vinculados: int = Field(ge=0)
    horas_asignadas: float = Field(ge=0)
    horas_sugeridas_pendientes: float = Field(ge=0)


# ── Bandeja de solicitudes ───────────────────────────────────────────────────

class InstructorReferencia(BaseModel):
    id: int
    nombre: str
    correo_sena: str = ""


class SolicitudBandeja(BaseModel):
    id: int
    ficha_id: int
    ficha_programa: str
    ficha_trimestre: int | None = None
    instructor: InstructorReferencia
    transversales: list[str]
    fecha_solicitud: date
    fecha_limite: date
    dias_restantes: int
    estado: str
    horas_sugeridas: float | None = None
    bloque_sugerido: str = ""
    comentarios: str = ""
    fecha_asignacion: date | None = None
    asignada_por: InstructorReferencia | None = None
    respuesta_gestora: str = ""


class ContadoresBandeja(BaseModel):
    total: int = Field(ge=0)
    pendientes: int = Field(ge=0)
    en_revision: int = Field(ge=0)
    aprobadas: int = Field(ge=0)
    rechazadas: int = Field(ge=0)
    vencidas: int = Field(ge=0)


class BandejaSolicitudes(BaseModel):
    solicitudes: list[SolicitudBandeja] = Field(default_factory=list)
    contadores: ContadoresBandeja = Field(default_factory=ContadoresBandeja)
    estados_disponibles: list[str] = Field(default_factory=lambda: list(ESTADOS_SOLICITUD))


class ActualizacionSolicitud(BaseModel):
    estado: EstadoSolicitud
    comentario: str = Field(default="", max_length=300)
    horas_asignadas: float | None = Field(default=None, ge=0, le=40)
    bloque_asignado: str = Field(default="", max_length=120)

    @field_validator("comentario", "bloque_asignado", mode="before")
    @classmethod
    def normalizar_texto(cls, valor: object) -> str:
        return str(valor or "").strip()


class ResultadoActualizacionSolicitud(BaseModel):
    mensaje: str
    solicitud: SolicitudBandeja


# ── Fichas & trimestres ──────────────────────────────────────────────────────

class FichaTrimestre(BaseModel):
    id: int
    programa: str
    jornada: str
    trimestre: int = Field(ge=1)
    horas_semanales: float = Field(ge=0)
    competencias: list[str] = Field(default_factory=list)
    estado: str = "Asignada"
    instructores: list[InstructorReferencia] = Field(default_factory=list)
    solicitudes_abiertas: int = Field(ge=0)
    horas_transversales: float = Field(ge=0)


class ResumenFichasTrimestres(BaseModel):
    trimestre: int = Field(ge=1)
    items: list[FichaTrimestre] = Field(default_factory=list)
    total_fichas: int = Field(ge=0)
    total_horas: float = Field(ge=0)
    fichas_sin_instructor: int = Field(ge=0)
    trimestre_actual: int = Field(ge=1)
    # Trimestres del programa según su duración (no según las fichas existentes).
    programa: str = ""
    trimestres: list[int] = Field(default_factory=list)


# ── Instructores ─────────────────────────────────────────────────────────────

class FichaDeInstructor(BaseModel):
    id: int
    trimestre: int = Field(ge=1)
    jornada: str


class InstructorGestora(BaseModel):
    """Instructor vinculado a la Gestora. Sin horas totales: el backend aún no las calcula."""

    id: int
    nombre: str
    correo_sena: str = ""
    fecha_ingreso: date | None = None
    es_nuevo: bool = False
    fichas: list[FichaDeInstructor] = Field(default_factory=list)


class ListadoInstructoresGestora(BaseModel):
    items: list[InstructorGestora] = Field(default_factory=list)
    total: int = Field(ge=0)


# ── Horarios ─────────────────────────────────────────────────────────────────

TipoSesion = Literal["ingles", "lider", "transversal", "tecnica"]


class BloqueHorario(BaseModel):
    """Una sesión semanal de una ficha. Varias fichas pueden compartir franja."""

    dia: str
    dia_corto: str
    bloque: str
    jornada: str
    ocupada: bool = False
    ficha_id: int | None = None
    trimestre: int | None = None
    tipo: TipoSesion = "tecnica"
    materia: str | None = Field(default=None, description="Competencia o transversal.")
    transversal: str | None = None
    aula: str | None = None
    horas: float = 0
    bloqueado: bool = Field(default=False, description="Bloque fijo de la gestora (p. ej. Inglés); no es variable del motor.")
    instructor: InstructorReferencia | None = None


class PendienteHorario(BaseModel):
    """Lo que el motor no pudo programar (hueco)."""

    ficha_id: int
    trimestre: int
    prioridad: Literal[1, 2]
    tipo: str
    materia: str
    horas: float
    motivo: str


class HorarioGestora(BaseModel):
    trimestre: int = Field(ge=1)
    jornada: str
    ficha_id: int | None = None
    generado: bool = Field(description="False: aún no se ha generado; solo se muestran los bloques fijos.")
    generado_en: datetime | None = None
    dias: list[str] = Field(default_factory=list)
    bloques: list[str] = Field(default_factory=list)
    asignaciones: list[BloqueHorario] = Field(default_factory=list)
    total_asignaciones: int = Field(ge=0)
    horas_asignadas: float = Field(ge=0)
    huecos: int = Field(ge=0, description="Pendientes del motor en las fichas consultadas.")
    pendientes: list[PendienteHorario] = Field(default_factory=list)


class CargaGenerada(BaseModel):
    id: int
    nombre: str
    horas: float
    tope: float


class ResultadoGeneracion(BaseModel):
    generado_en: datetime
    total_sesiones: int
    horas_programadas: float
    fichas: int
    pendientes: list[PendienteHorario]
    pendientes_prioridad_alta: int = Field(description="Huecos en fichas de trimestres 1–5 (§4: no deberían existir).")
    carga: list[CargaGenerada]
