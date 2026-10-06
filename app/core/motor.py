"""Motor de programación automática de horarios (MVP voraz).

Sigue el orden de programación de docs/reglas-negocio.md §2:

  1. Inglés fijo de cada ficha (bloque bloqueado que fija la gestora).
  2. Bloques del líder de ficha (aprobados por la gestora, §3).
  3. Transversales del plan del trimestre (Ética, SST, Matemáticas…).
  4. Formación técnica en el sobrante, cruzando competencias, disponibilidad
     marcada por cada instructor y equidad de carga.

Las fichas de prioridad 1 (trimestres 1–5) se programan antes que las de
prioridad 2, que son las únicas que pueden quedar con huecos (§4).

Entradas y salidas son estructuras simples (dataclasses y dicts) para poder
reemplazar este motor por el de OR-Tools sin tocar la API ni las vistas.
"""

from collections import defaultdict
from dataclasses import dataclass, field

from app.core.carga import MAX_HORAS_CONTINUAS_DIA, horas_continuas_maximas

Franja = tuple[str, str]  # (dia, "HH:MM-HH:MM")

SIN_AULA = "Por asignar"


@dataclass
class InstructorMotor:
    id: int
    nombre: str
    tope_horas: float
    competencias: set[str] = field(default_factory=set)  # códigos de competencia
    areas: set[str] = field(default_factory=set)  # transversales que dicta
    # Franjas marcadas en Disponibilidad; None = disponible en toda la semana.
    disponibilidad: set[Franja] | None = None
    compensa_carga: bool = False  # equidad §6: se le asigna después que a los demás


@dataclass
class FichaMotor:
    id: int
    trimestre: int
    jornada: str  # "Mañana" | "Tarde" | "Noche"
    prioridad: int  # 1 o 2
    bloques: list[str]  # bloques de su jornada
    horas_tecnicas: float
    competencias: list[tuple[str, str]]  # (código, nombre)
    aula_base: str
    ingles: Franja | None = None
    lider_id: int | None = None
    bloques_lider: list[Franja] = field(default_factory=list)
    transversales: list[str] = field(default_factory=list)
    instructores_habituales: list[int] = field(default_factory=list)


@dataclass
class Aulas:
    tecnica: list[str]
    ingles: list[str]
    general: list[str]


def duracion(bloque: str) -> float:
    return horas_continuas_maximas([bloque])


class _Estado:
    """Ocupación de fichas, instructores y aulas durante la generación."""

    def __init__(self, instructores: list[InstructorMotor]):
        self.instructores = {i.id: i for i in instructores}
        self.ficha: set[tuple[int, str, str]] = set()
        self.instructor: set[tuple[int, str, str]] = set()
        self.aula: set[tuple[str, str, str]] = set()
        self.carga: dict[int, float] = defaultdict(float)
        self.rangos_dia: dict[tuple[int, str], list[str]] = defaultdict(list)
        self.docentes_ficha: dict[int, set[int]] = defaultdict(set)
        self.sesiones: list[dict] = []
        self.pendientes: list[dict] = []

    def ficha_libre(self, ficha: FichaMotor, dia: str, bloque: str) -> bool:
        return (ficha.id, dia, bloque) not in self.ficha

    def puede(self, instructor: InstructorMotor, dia: str, bloque: str, respetar_disponibilidad: bool = True) -> bool:
        if (instructor.id, dia, bloque) in self.instructor:
            return False
        if respetar_disponibilidad and instructor.disponibilidad is not None and (dia, bloque) not in instructor.disponibilidad:
            return False
        if self.carga[instructor.id] + duracion(bloque) > instructor.tope_horas:
            return False
        rangos = self.rangos_dia[(instructor.id, dia)] + [bloque]
        return horas_continuas_maximas(rangos) <= MAX_HORAS_CONTINUAS_DIA

    def elegir_aula(self, opciones: list[str], dia: str, bloque: str) -> str:
        aula = next((a for a in opciones if (a, dia, bloque) not in self.aula), SIN_AULA)
        if aula != SIN_AULA:
            self.aula.add((aula, dia, bloque))
        return aula

    def registrar(self, ficha: FichaMotor, dia: str, bloque: str, tipo: str, materia: str,
                  instructor: InstructorMotor | None, aula: str, bloqueado: bool = False) -> None:
        self.ficha.add((ficha.id, dia, bloque))
        if instructor is not None:
            self.instructor.add((instructor.id, dia, bloque))
            self.carga[instructor.id] += duracion(bloque)
            self.rangos_dia[(instructor.id, dia)].append(bloque)
            self.docentes_ficha[ficha.id].add(instructor.id)
        self.sesiones.append(
            {
                "ficha_id": ficha.id,
                "trimestre": ficha.trimestre,
                "jornada": ficha.jornada,
                "dia": dia,
                "bloque": bloque,
                "horas": duracion(bloque),
                "tipo": tipo,
                "materia": materia,
                "instructor_id": instructor.id if instructor else None,
                "instructor_nombre": instructor.nombre if instructor else None,
                "aula": aula,
                "bloqueado": bloqueado,
            }
        )

    def pendiente(self, ficha: FichaMotor, tipo: str, materia: str, horas: float, motivo: str) -> None:
        self.pendientes.append(
            {
                "ficha_id": ficha.id,
                "trimestre": ficha.trimestre,
                "prioridad": ficha.prioridad,
                "tipo": tipo,
                "materia": materia,
                "horas": horas,
                "motivo": motivo,
            }
        )


def _dias_rotados(dias: list[str], desde: int) -> list[str]:
    return [dias[(desde + k) % len(dias)] for k in range(len(dias))]


def _franjas_libres(estado: _Estado, ficha: FichaMotor, dias: list[str]):
    for dia in dias:
        for bloque in ficha.bloques:
            if estado.ficha_libre(ficha, dia, bloque):
                yield dia, bloque


def generar_horario(
    fichas: list[FichaMotor],
    instructores: list[InstructorMotor],
    aulas: Aulas,
    dias: list[str],
) -> dict:
    """Devuelve {"sesiones": [...], "pendientes": [...], "carga": {instructor_id: horas}}."""
    estado = _Estado(instructores)
    orden = sorted(fichas, key=lambda f: (f.prioridad, f.trimestre, f.id))
    posicion = {f.id: indice for indice, f in enumerate(orden)}

    # ── 1. Inglés fijo: la franja no se mueve; se busca quién lo dicte. ──
    docentes_ingles = [i for i in instructores if "Inglés" in i.areas]
    for ficha in orden:
        if ficha.ingles is None:
            continue
        dia, bloque = ficha.ingles
        docente = next((i for i in sorted(docentes_ingles, key=lambda i: estado.carga[i.id])
                        if estado.puede(i, dia, bloque)), None)
        aula = estado.elegir_aula(aulas.ingles + aulas.general, dia, bloque)
        estado.registrar(ficha, dia, bloque, "ingles", "Inglés", docente, aula, bloqueado=True)
        if docente is None:
            estado.pendiente(ficha, "transversal", "Inglés", duracion(bloque),
                             f"Ningún instructor de Inglés libre el {dia.lower()} {bloque}: rota la franja en Líderes.")

    # ── 2. Bloques del líder (aprobados por la gestora). ──
    horas_tecnicas = {f.id: f.horas_tecnicas for f in orden}
    for ficha in orden:
        lider = estado.instructores.get(ficha.lider_id) if ficha.lider_id else None
        if lider is None:
            continue
        materia = next((nombre for codigo, nombre in ficha.competencias if codigo in lider.competencias),
                       "Formación técnica")
        for dia, bloque in ficha.bloques_lider:
            if not estado.ficha_libre(ficha, dia, bloque) or not estado.puede(lider, dia, bloque, respetar_disponibilidad=False):
                estado.pendiente(ficha, "lider", materia, duracion(bloque),
                                 f"{lider.nombre} no puede dictar su bloque de líder el {dia.lower()} {bloque}.")
                continue
            aula = estado.elegir_aula([ficha.aula_base] + aulas.tecnica + aulas.general, dia, bloque)
            estado.registrar(ficha, dia, bloque, "lider", materia, lider, aula)
            horas_tecnicas[ficha.id] -= duracion(bloque)

    # ── 3. Transversales del plan del trimestre. ──
    for ficha in orden:
        for indice, transversal in enumerate(ficha.transversales):
            docentes = [i for i in instructores if transversal in i.areas]
            colocada = False
            for dia, bloque in _franjas_libres(estado, ficha, _dias_rotados(dias, posicion[ficha.id] + indice + 1)):
                docente = next((i for i in sorted(docentes, key=lambda i: estado.carga[i.id])
                                if estado.puede(i, dia, bloque)), None)
                if docente is None:
                    continue
                aula = estado.elegir_aula([ficha.aula_base] + aulas.general, dia, bloque)
                estado.registrar(ficha, dia, bloque, "transversal", transversal, docente, aula)
                colocada = True
                break
            if not colocada:
                horas = duracion(ficha.bloques[0]) if ficha.bloques else 0
                estado.pendiente(ficha, "transversal", transversal, horas,
                                 "Sin instructor transversal libre en la jornada de la ficha.")

    # ── 4. Formación técnica en el sobrante. ──
    tecnicos = [i for i in instructores if i.competencias]
    for ficha in orden:
        if not ficha.competencias or not ficha.bloques:
            continue
        horas_bloque = duracion(ficha.bloques[0])
        bloques_faltantes = max(round(horas_tecnicas[ficha.id] / horas_bloque), 0)
        horas_por_competencia = {codigo: 0.0 for codigo, _ in ficha.competencias}
        nombres = dict(ficha.competencias)

        while bloques_faltantes > 0:
            elegido = None
            for dia, bloque in _franjas_libres(estado, ficha, _dias_rotados(dias, posicion[ficha.id])):
                for codigo in sorted(horas_por_competencia, key=horas_por_competencia.get):
                    candidatos = [i for i in tecnicos if codigo in i.competencias and estado.puede(i, dia, bloque)]
                    if not candidatos:
                        continue
                    # Continuidad con la ficha, luego equidad: quien compensa carga va al final
                    # y, entre iguales, el de menos horas asignadas.
                    docente = min(
                        candidatos,
                        key=lambda i: (
                            i.id not in estado.docentes_ficha[ficha.id] and i.id not in ficha.instructores_habituales,
                            i.compensa_carga,
                            estado.carga[i.id],
                            i.id,
                        ),
                    )
                    elegido = (dia, bloque, codigo, docente)
                    break
                if elegido:
                    break

            if elegido is None:
                estado.pendiente(
                    ficha, "tecnica", ", ".join(nombres.values()), bloques_faltantes * horas_bloque,
                    "Ningún instructor con la competencia tiene disponibilidad libre en la jornada de la ficha.",
                )
                break

            dia, bloque, codigo, docente = elegido
            aula = estado.elegir_aula(aulas.tecnica + [ficha.aula_base] + aulas.general, dia, bloque)
            estado.registrar(ficha, dia, bloque, "tecnica", nombres[codigo], docente, aula)
            horas_por_competencia[codigo] += duracion(bloque)
            bloques_faltantes -= 1

    return {"sesiones": estado.sesiones, "pendientes": estado.pendientes, "carga": dict(estado.carga)}
