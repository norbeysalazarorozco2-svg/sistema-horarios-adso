"""
disponibilidad.py — Router de disponibilidad horaria.
Prefijo: /api/v1/instructor
Sistema de Horarios ADSO — SENA

Reglas de negocio:
  - Al guardar se exige competencia, RAP y al menos un bloque horario.
  - La disponibilidad se maneja por trimestre.
  - Se permite reutilizar la disponibilidad del trimestre anterior.
  - Se permite guardar la matriz con espacios sin cubrir (sin validación de cobertura total).
"""

import calendar
from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException, status

from app.core.security import require_instructor
from app.schemas.disponibilidad import RegistroDisponibilidad

router = APIRouter(
    prefix="/api/v1/instructor",
    tags=["Disponibilidad"],
)

# ⚠️ PROVISIONAL — persistencia en memoria (reemplazar con SQLAlchemy)
ALMACEN_DISPONIBILIDAD: dict[str, dict[int, dict]] = {}

MESES_NUEVO_INSTRUCTOR = 3
RANGO_TRIMESTRES = range(1, 7)


def _restar_meses(fecha_actual: date, meses: int) -> date:
    mes = fecha_actual.month - meses
    anio = fecha_actual.year
    if mes <= 0:
        mes += 12
        anio -= 1
    dia = min(fecha_actual.day, calendar.monthrange(anio, mes)[1])
    return date(anio, mes, dia)


def es_nuevo_instructor(fecha_ingreso: object) -> bool:
    """True si el instructor ingresó dentro de los últimos 3 meses."""
    if not fecha_ingreso:
        return False
    try:
        if isinstance(fecha_ingreso, date):
            fecha = fecha_ingreso
        else:
            fecha = date.fromisoformat(str(fecha_ingreso))
    except ValueError:
        return False
    hoy = date.today()
    if fecha > hoy:
        return False
    return fecha >= _restar_meses(hoy, MESES_NUEVO_INSTRUCTOR)


def _bloques_previos(instructor_id: object, trimestre: int) -> list[dict] | None:
    """Devuelve los bloques guardados en el trimestre anterior, si existen."""
    anterior = ALMACEN_DISPONIBILIDAD.get(str(instructor_id), {}).get(trimestre - 1)
    return anterior.get("bloques") if anterior else None


@router.post(
    "/disponibilidad",
    status_code=status.HTTP_200_OK,
    summary="Registrar disponibilidad del instructor por trimestre",
    description=(
        "Recibe la competencia, RAP y los bloques horarios disponibles del instructor "
        "autenticado. Exige competencia, RAP y al menos un bloque. "
        "Si `reutilizar_anterior` es True y no se envían bloques, copia la disponibilidad "
        "del trimestre anterior."
    ),
)
def registrar_disponibilidad(
    registro: RegistroDisponibilidad,
    usuario: dict = Depends(require_instructor),
) -> dict:
    instructor_id = usuario.get("sub") or usuario.get("id")

    bloques_finales = [
        {"dia": b.dia.value, "bloque": b.bloque.value} for b in registro.bloques
    ]

    reutilizado = False
    if len(bloques_finales) == 0 and registro.reutilizar_anterior:
        previos = _bloques_previos(instructor_id, registro.numero_trimestre)
        if previos:
            bloques_finales = [dict(bloque) for bloque in previos]
            reutilizado = True

    if len(bloques_finales) == 0:
        if registro.reutilizar_anterior:
            detalle = (
                "Debes seleccionar al menos un bloque de horario. "
                "No se encontró disponibilidad previa para reutilizar."
            )
        else:
            detalle = "Debes seleccionar al menos un bloque de horario."
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=detalle)

    ALMACEN_DISPONIBILIDAD.setdefault(str(instructor_id), {})[registro.numero_trimestre] = {
        "competencia": registro.competencia,
        "rap": registro.rap,
        "bloques": bloques_finales,
        "guardado_en": datetime.utcnow().isoformat(),
    }

    return {
        "mensaje": "Disponibilidad registrada correctamente",
        "instructor_id": instructor_id,
        "instructor_nombre": usuario.get("nombre", "Desconocido"),
        "es_nuevo": es_nuevo_instructor(usuario.get("fecha_ingreso")),
        "trimestre": registro.numero_trimestre,
        "reutilizado": reutilizado,
        "bloques_recibidos": len(bloques_finales),
        "bloques": bloques_finales,
    }


@router.get(
    "/disponibilidad/{trimestre}",
    status_code=status.HTTP_200_OK,
    summary="Consultar disponibilidad del instructor por trimestre",
    description=(
        "Devuelve la disponibilidad guardada para un trimestre, junto con datos de apoyo "
        "para la reutilización (si existe disponibilidad del trimestre anterior) y el estado "
        "de instructor nuevo del usuario autenticado."
    ),
)
def consultar_disponibilidad(
    trimestre: int,
    usuario: dict = Depends(require_instructor),
) -> dict:
    if trimestre not in RANGO_TRIMESTRES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"El trimestre debe estar entre {RANGO_TRIMESTRES.start} y {RANGO_TRIMESTRES.stop - 1}.",
        )

    instructor_id = usuario.get("sub") or usuario.get("id")
    guardado = ALMACEN_DISPONIBILIDAD.get(str(instructor_id), {}).get(trimestre)

    return {
        "instructor_id": instructor_id,
        "instructor_nombre": usuario.get("nombre", "Desconocido"),
        "es_nuevo": es_nuevo_instructor(usuario.get("fecha_ingreso")),
        "trimestre": trimestre,
        "tiene_disponibilidad": guardado is not None,
        "competencia": (guardado or {}).get("competencia"),
        "rap": (guardado or {}).get("rap"),
        "bloques": (guardado or {}).get("bloques", []),
        "reutilizable_anterior": bool(_bloques_previos(instructor_id, trimestre)),
    }