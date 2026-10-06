"""Reglas de carga horaria del instructor (ver docs/reglas-negocio.md §1).

El frontend replica estos umbrales en app/static/js/carga.js; si cambian aquí,
actualízalos también allá.
"""

from collections.abc import Iterable

HORAS_FORMACION_BASE = 33
HORAS_FORMACION_MAXIMA = 36
HORAS_ADMINISTRATIVAS = 4
TOPE_SEMANAL = 40
HORAS_BASE_TOTAL = HORAS_FORMACION_BASE + HORAS_ADMINISTRATIVAS  # 37 h
MAX_HORAS_CONTINUAS_DIA = 9

# Transversal de Inglés: la gestora la fija en cada ficha, en todos los
# trimestres, antes de programar a ADSO. Ocupa un bloque completo de la jornada
# de la ficha y queda bloqueado (reglas-negocio §2, Paso 1).
TRANSVERSAL_INGLES = "Inglés"
HORAS_INGLES_POR_JORNADA: dict[str, int] = {"Mañana": 3, "Tarde": 3, "Noche": 2}


def _a_minutos(hora: str) -> int:
    horas, minutos = hora.split(":")
    return int(horas) * 60 + int(minutos)


def horas_continuas_maximas(rangos: Iterable[str]) -> float:
    """Mayor tramo continuo, en horas, formado por rangos "HH:MM-HH:MM" de un mismo día.

    Dos rangos son continuos cuando uno termina exactamente donde empieza el otro.
    """
    intervalos = sorted(
        {(_a_minutos(inicio), _a_minutos(fin)) for inicio, fin in (r.split("-") for r in rangos)}
    )
    maximo = 0
    tramo_inicio = tramo_fin = None
    for inicio, fin in intervalos:
        if tramo_fin is not None and inicio <= tramo_fin:
            tramo_fin = max(tramo_fin, fin)
        else:
            tramo_inicio, tramo_fin = inicio, fin
        maximo = max(maximo, tramo_fin - tramo_inicio)
    return maximo / 60
