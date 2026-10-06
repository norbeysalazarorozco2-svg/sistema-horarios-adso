"""
equidad.py — Historial de carga y equidad entre trimestres.
Prefijo: /api/v1/gestora/equidad
Sistema de Horarios ADSO — SENA

Regla (docs/reglas-negocio.md §6): si en un trimestre un instructor llegó a
40 h para tapar un hueco, se guarda en su historial y en el trimestre
siguiente se le asigna menos carga. Aquí "para tapar un hueco" significa que
llegó al tope con horas extra; la carga recomendada al compensar es la base
(37 h, sin horas extra).

Este módulo no importa app.api.alertas al cargar (alertas depende de él);
las consultas de carga en curso lo hacen de forma diferida.
"""

from datetime import date

from fastapi import APIRouter, Depends

from app.api.disponibilidad import es_nuevo_instructor
from app.api.gestora import INSTRUCTORES_GESTORA
from app.core.carga import HORAS_ADMINISTRATIVAS, HORAS_BASE_TOTAL, TOPE_SEMANAL
from app.core.security import require_gestora
from app.schemas.equidad import Compensacion, EquidadInstructor, ListadoEquidad, RegistroCarga


router = APIRouter(
    prefix="/api/v1/gestora/equidad",
    tags=["Gestora · Equidad"],
)

Periodo = tuple[int, int]  # (año, trimestre 1–4 del calendario)
TRIMESTRES_VISIBLES = 3


def periodo_actual() -> Periodo:
    hoy = date.today()
    return hoy.year, (hoy.month - 1) // 3 + 1


def desplazar(periodo: Periodo, trimestres: int) -> Periodo:
    indice = periodo[0] * 4 + (periodo[1] - 1) + trimestres
    return indice // 4, indice % 4 + 1


def etiqueta(periodo: Periodo) -> str:
    return f"{periodo[0]}-T{periodo[1]}"


def _registro(formacion: float, extra: float) -> dict:
    return {
        "horas_formacion": formacion,
        "horas_extra": extra,
        "horas_totales": formacion + extra + HORAS_ADMINISTRATIVAS,
    }


# ⚠️ PROVISIONAL — Instructor.historial_carga (reemplazar con SQLAlchemy).
# instructor_id → {(año, trimestre): registro}. Los datos de ejemplo se ubican
# relativos al trimestre en curso para que la demo funcione en cualquier fecha.
_ACTUAL = periodo_actual()
_T1, _T2, _T3 = (desplazar(_ACTUAL, -n) for n in (1, 2, 3))
HISTORIAL_CARGA: dict[int, dict[Periodo, dict]] = {
    101: {_T3: _registro(33, 0), _T2: _registro(33, 3), _T1: _registro(33, 0)},
    103: {_T3: _registro(33, 0), _T2: _registro(32, 0), _T1: _registro(33, 0)},
    104: {_T3: _registro(33, 0), _T2: _registro(33, 0), _T1: _registro(32, 4)},
    105: {_T3: _registro(36, 0), _T2: _registro(36, 0), _T1: _registro(36, 0)},
}


def _a_schema(periodo: Periodo, registro: dict) -> RegistroCarga:
    return RegistroCarga(
        periodo=etiqueta(periodo),
        llego_al_tope=registro["horas_totales"] >= TOPE_SEMANAL,
        **registro,
    )


def compensacion_de(instructor_id: int) -> Compensacion | None:
    """Compensación pendiente si el trimestre anterior llegó a 40 h con horas extra."""
    anterior = desplazar(periodo_actual(), -1)
    registro = HISTORIAL_CARGA.get(instructor_id, {}).get(anterior)
    if registro is None or registro["horas_extra"] <= 0 or registro["horas_totales"] < TOPE_SEMANAL:
        return None
    return Compensacion(
        periodo=etiqueta(anterior),
        horas_totales=registro["horas_totales"],
        horas_extra=registro["horas_extra"],
        carga_maxima_recomendada=HORAS_BASE_TOTAL,
    )


def _carga_en_curso(instructor_id: int) -> dict:
    from app.api.alertas import CARGA_INSTRUCTORES_MOCK, horas_extra_aceptadas

    base = CARGA_INSTRUCTORES_MOCK.get(instructor_id, {}).get("horas_formacion", 0.0)
    return _registro(base, horas_extra_aceptadas(instructor_id))


def listado_equidad() -> ListadoEquidad:
    actual = periodo_actual()
    periodos = [desplazar(actual, -n) for n in range(TRIMESTRES_VISIBLES, 0, -1)]
    instructores = []
    for instructor in INSTRUCTORES_GESTORA:
        instructor_id = int(instructor["id"])
        historial = HISTORIAL_CARGA.get(instructor_id, {})
        en_curso = _carga_en_curso(instructor_id)
        compensacion = compensacion_de(instructor_id)
        instructores.append(
            EquidadInstructor(
                id=instructor_id,
                nombre=str(instructor["nombre"]),
                es_nuevo=es_nuevo_instructor(instructor.get("fecha_ingreso")),
                historial=[_a_schema(p, historial[p]) if p in historial else None for p in periodos],
                en_curso=_a_schema(actual, en_curso),
                en_curso_registrado=actual in historial,
                compensacion=compensacion,
                excede_recomendacion=bool(
                    compensacion and en_curso["horas_totales"] > compensacion.carga_maxima_recomendada
                ),
            )
        )
    instructores.sort(key=lambda i: (i.compensacion is None, i.nombre))
    return ListadoEquidad(
        periodo_actual=etiqueta(actual),
        periodos=[etiqueta(p) for p in periodos],
        a_compensar=sum(1 for i in instructores if i.compensacion),
        instructores=instructores,
    )


@router.get(
    "",
    response_model=ListadoEquidad,
    summary="Historial de carga por trimestre y compensaciones pendientes",
)
def listar_equidad(_usuario: dict = Depends(require_gestora)) -> ListadoEquidad:
    return listado_equidad()


@router.post(
    "/cierre",
    response_model=ListadoEquidad,
    summary="Guardar la carga del trimestre en curso en el historial",
    description=(
        "Registra (o actualiza) la carga actual de cada instructor como cierre del "
        "trimestre en curso. El trimestre siguiente usará este registro para la regla de equidad."
    ),
)
def registrar_cierre(_usuario: dict = Depends(require_gestora)) -> ListadoEquidad:
    # Import diferido: trimestre.py depende de este módulo.
    from app.api.trimestre import exigir_trimestre_abierto

    exigir_trimestre_abierto()
    actual = periodo_actual()
    for instructor in INSTRUCTORES_GESTORA:
        instructor_id = int(instructor["id"])
        HISTORIAL_CARGA.setdefault(instructor_id, {})[actual] = _carga_en_curso(instructor_id)
    return listado_equidad()
