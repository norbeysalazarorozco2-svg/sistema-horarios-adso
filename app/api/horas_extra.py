"""
horas_extra.py — Solicitudes de horas extra recibidas por el instructor.
Prefijo: /api/v1/instructor
Sistema de Horarios ADSO — SENA

Cuando un RAP queda sin instructor, la gestora propone a un instructor que ya
tiene 36–39 h cubrirlo con horas extra hasta 40 h (reglas-negocio §5). Al
solicitarlas la gestora las autoriza; el instructor acepta o rechaza, y su
respuesta aparece en la vista de alertas de la gestora.
"""

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.alertas import (
    CARGA_INSTRUCTORES_MOCK,
    SOLICITUDES_HORAS_EXTRA,
    detallar_solicitud,
    horas_extra_aceptadas,
)
from app.api.equidad import compensacion_de
from app.api.mi_ficha import instructor_id_de
from app.api.trimestre import exigir_trimestre_abierto
from app.core.carga import HORAS_ADMINISTRATIVAS, TOPE_SEMANAL
from app.core.security import require_instructor
from app.schemas.alertas import (
    BandejaHorasExtra,
    CargaInstructor,
    RespuestaHorasExtra,
    SolicitudParaInstructor,
)


router = APIRouter(
    prefix="/api/v1/instructor",
    tags=["Instructor · Horas extra"],
)


def solicitudes_pendientes_de(instructor_id: int | None) -> int:
    """Cuántas solicitudes de horas extra esperan respuesta del instructor."""
    return sum(
        1 for s in SOLICITUDES_HORAS_EXTRA
        if s["instructor_id"] == instructor_id and s["estado"] == "pendiente"
    )


def _exigir_id(usuario: dict) -> int:
    instructor_id = instructor_id_de(usuario)
    if instructor_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="La sesión no identifica a un instructor válido.",
        )
    return instructor_id


def _carga(instructor_id: int) -> CargaInstructor:
    base = CARGA_INSTRUCTORES_MOCK.get(instructor_id, {}).get("horas_formacion", 0.0)
    extra = horas_extra_aceptadas(instructor_id)
    return CargaInstructor(
        horas_formacion=base,
        horas_extra_aceptadas=extra,
        horas_administrativas=HORAS_ADMINISTRATIVAS,
        horas_totales=base + extra + HORAS_ADMINISTRATIVAS,
    )


def _para_instructor(solicitud: dict, carga: CargaInstructor) -> SolicitudParaInstructor | None:
    detalle = detallar_solicitud(solicitud)
    if detalle is None:
        return None
    con_extra = carga.horas_totales + solicitud["horas"]
    excede = solicitud["estado"] == "pendiente" and con_extra > TOPE_SEMANAL
    return SolicitudParaInstructor(
        **detalle.model_dump(),
        horas_totales_con_extra=con_extra,
        puede_aceptar=solicitud["estado"] == "pendiente" and not excede,
        motivo_bloqueo=(
            f"Aceptarla te llevaría a {con_extra:g} h, por encima del tope de {TOPE_SEMANAL} h."
            if excede else ""
        ),
    )


@router.get(
    "/horas-extra",
    response_model=BandejaHorasExtra,
    summary="Solicitudes de horas extra que la gestora envió al instructor",
)
def bandeja_horas_extra(usuario: dict = Depends(require_instructor)) -> BandejaHorasExtra:
    instructor_id = _exigir_id(usuario)
    carga = _carga(instructor_id)
    propias = sorted(
        (s for s in SOLICITUDES_HORAS_EXTRA if s["instructor_id"] == instructor_id),
        key=lambda s: (s["fecha_solicitud"], s["id"]),
        reverse=True,
    )
    detalladas = [d for d in (_para_instructor(s, carga) for s in propias) if d]
    return BandejaHorasExtra(
        carga=carga,
        compensacion=compensacion_de(instructor_id),
        pendientes=[d for d in detalladas if d.estado == "pendiente"],
        historial=[d for d in detalladas if d.estado != "pendiente"],
    )


@router.post(
    "/horas-extra/{solicitud_id}/respuesta",
    response_model=BandejaHorasExtra,
    summary="Aceptar o rechazar una solicitud de horas extra",
)
def responder_horas_extra(
    solicitud_id: int,
    datos: RespuestaHorasExtra,
    usuario: dict = Depends(require_instructor),
) -> BandejaHorasExtra:
    instructor_id = _exigir_id(usuario)
    exigir_trimestre_abierto()
    solicitud = next(
        (s for s in SOLICITUDES_HORAS_EXTRA if s["id"] == solicitud_id and s["instructor_id"] == instructor_id),
        None,
    )
    if solicitud is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="La solicitud no existe.")
    if solicitud["estado"] != "pendiente":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "La gestora canceló esta solicitud."
                if solicitud["estado"] == "cancelada"
                else "Ya respondiste esta solicitud."
            ),
        )

    if datos.acepta:
        con_extra = _carga(instructor_id).horas_totales + solicitud["horas"]
        if con_extra > TOPE_SEMANAL:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Aceptarla te llevaría a {con_extra:g} h, por encima del tope de {TOPE_SEMANAL} h.",
            )

    solicitud["estado"] = "aceptada" if datos.acepta else "rechazada"
    solicitud["motivo"] = "" if datos.acepta else datos.motivo.strip()
    solicitud["fecha_respuesta"] = date.today()
    return bandeja_horas_extra(usuario)
