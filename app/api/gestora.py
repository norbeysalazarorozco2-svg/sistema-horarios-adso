"""
gestora.py — Router independiente de la Gestora.
Prefijo: /api/v1/gestora
Sistema de Horarios ADSO — SENA

Alimenta la vista /perfil-gestora, que es totalmente independiente de la
interfaz del instructor:

  - Bandeja de solicitudes de asignaturas transversales.
  - Fichas & trimestres.
  - Horarios.

Todas las operaciones exigen rol de Gestora (`require_gestora`).
"""

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.auth import USUARIOS_MOCK
from app.api.catalogo import obtener_programa
from app.api.disponibilidad import es_nuevo_instructor
from app.api.perfil import SOLICITUDES_TRANSVERSALES
from app.core.carga import HORAS_INGLES_POR_JORNADA, TRANSVERSAL_INGLES, horas_continuas_maximas
from app.core.security import require_gestora
from app.schemas.gestora import (
    BLOQUES_HORARIOS,
    DIAS_SEMANA,
    ESTADOS_CERRADOS,
    ESTADOS_SOLICITUD,
    JORNADA_DE_BLOQUES,
    JORNADA_POR_BLOQUE,
    ActualizacionSolicitud,
    BandejaSolicitudes,
    BloqueHorario,
    ContadoresBandeja,
    FichaDeInstructor,
    FichaTrimestre,
    HorarioGestora,
    InstructorGestora,
    InstructorReferencia,
    ListadoInstructoresGestora,
    PerfilGestora,
    ResumenFichasTrimestres,
    ResultadoActualizacionSolicitud,
    SolicitudBandeja,
)
from app.schemas.catalogo import ProgramaFormacion


router = APIRouter(
    prefix="/api/v1/gestora",
    tags=["Gestora"],
)

# ⚠️ PROVISIONAL — datos en memoria (reemplazar con SQLAlchemy)

# Programa que coordina la Gestora; su duración sale del catálogo de programas.
PROGRAMA_GESTORA = "ADSO"


# ── Instructores vinculados a la Gestora ──────────────────────────────────────
INSTRUCTORES_GESTORA: list[dict] = [
    {
        "id": 101,
        "nombre": "Javier Montoya",
        "correo_sena": "jmontoya@sena.edu.co",
        "fecha_ingreso": "2023-02-10",
    },
    {
        "id": 202,
        "nombre": "Laura Ramírez",
        "correo_sena": "instructor.nuevo@sena.edu.co",
        "fecha_ingreso": date.today().isoformat(),
    },
    {
        "id": 103,
        "nombre": "Sandra Ospina",
        "correo_sena": "sospina@sena.edu.co",
        "fecha_ingreso": "2021-03-15",
    },
    {
        "id": 104,
        "nombre": "Andrés Villalba",
        "correo_sena": "avillalba@sena.edu.co",
        "fecha_ingreso": "2024-01-08",
    },
    {
        "id": 105,
        "nombre": "Marcela Duarte",
        "correo_sena": "mduarte@sena.edu.co",
        "fecha_ingreso": "2020-07-01",
    },
]

COMPETENCIA_WEB = "220501095 · Desarrollar aplicaciones web"
COMPETENCIA_DISENO = "220501093 · Diseñar sistemas de información"
COMPETENCIA_ANALISIS = "220501092 · Analizar requisitos de software"


# ── Fichas por trimestre ─────────────────────────────────────────────────────
# Las fichas 3365169 y 3365170 coinciden con las asignadas al instructor 101 en
# app/api/perfil.py para que la Gestora vea lo mismo que reportan los instructores.
FICHAS_GESTORA_MOCK: list[dict] = [
    {
        "id": 3365101,
        "programa": "ADSO",
        "jornada": "Diurna",
        "trimestre": 1,
        "horas_semanales": 16.0,
        "competencias": [COMPETENCIA_ANALISIS, COMPETENCIA_DISENO],
        "instructor_ids": [103, 101],
    },
    {
        "id": 3365102,
        "programa": "ADSO",
        "jornada": "Diurna",
        "trimestre": 1,
        "horas_semanales": 16.0,
        "competencias": [COMPETENCIA_WEB],
        "instructor_ids": [105],
    },
    {
        "id": 3365130,
        "programa": "ADSO",
        "jornada": "Diurna",
        "trimestre": 2,
        "horas_semanales": 16.0,
        "competencias": [COMPETENCIA_DISENO, COMPETENCIA_WEB],
        "instructor_ids": [101, 104],
    },
    {
        "id": 3365131,
        "programa": "ADSO",
        "jornada": "Tarde",
        "trimestre": 2,
        "horas_semanales": 12.0,
        "competencias": [COMPETENCIA_ANALISIS],
        "instructor_ids": [105],
    },
    {
        "id": 3365169,
        "programa": "ADSO",
        "jornada": "Diurna",
        "trimestre": 3,
        "horas_semanales": 16.0,
        "competencias": [COMPETENCIA_ANALISIS, COMPETENCIA_DISENO],
        "instructor_ids": [101],
    },
    {
        "id": 3365170,
        "programa": "ADSO",
        "jornada": "Diurna",
        "trimestre": 3,
        "horas_semanales": 16.0,
        "competencias": [COMPETENCIA_WEB],
        "instructor_ids": [101],
    },
    {
        "id": 3365171,
        "programa": "ADSO",
        "jornada": "Tarde",
        "trimestre": 3,
        "horas_semanales": 12.0,
        "competencias": [COMPETENCIA_WEB],
        "instructor_ids": [],
    },
    {
        "id": 3365200,
        "programa": "ADSO",
        "jornada": "Diurna",
        "trimestre": 4,
        "horas_semanales": 16.0,
        "competencias": [COMPETENCIA_ANALISIS, COMPETENCIA_WEB],
        "instructor_ids": [104, 103],
    },
    {
        "id": 3365201,
        "programa": "ADSO",
        "jornada": "Nocturna",
        "trimestre": 4,
        "horas_semanales": 16.0,
        "competencias": [COMPETENCIA_DISENO],
        "instructor_ids": [105],
    },
    {
        "id": 3365230,
        "programa": "ADSO",
        "jornada": "Diurna",
        "trimestre": 5,
        "horas_semanales": 16.0,
        "competencias": [COMPETENCIA_WEB, COMPETENCIA_ANALISIS],
        "instructor_ids": [101, 103],
    },
    {
        "id": 3365260,
        "programa": "ADSO",
        "jornada": "Diurna",
        "trimestre": 6,
        "horas_semanales": 16.0,
        "competencias": [COMPETENCIA_DISENO],
        "instructor_ids": [104],
    },
    {
        "id": 3365261,
        "programa": "ADSO",
        "jornada": "Diurna",
        "trimestre": 6,
        "horas_semanales": 16.0,
        "competencias": [COMPETENCIA_WEB],
        "instructor_ids": [],
    },
]

DIA_CORTO: dict[str, str] = {
    "LUNES": "Lun",
    "MARTES": "Mar",
    "MIERCOLES": "Mié",
    "JUEVES": "Jue",
    "VIERNES": "Vie",
}


# ── Inglés fijo por ficha ────────────────────────────────────────────────────
# La gestora fija Inglés en cada ficha antes de programar a ADSO: 3 h en
# Mañana/Tarde y 2 h en Noche, es decir, un bloque completo de la jornada de la
# ficha. Ese bloque queda bloqueado: ni el líder ni el motor pueden usarlo.

def bloques_de_jornada(jornada_ficha: str) -> list[str]:
    objetivo = JORNADA_DE_BLOQUES.get(jornada_ficha)
    return [b for b, j in JORNADA_POR_BLOQUE.items() if objetivo is None or j == objetivo]


# Día de Inglés por trimestre: rota para que los instructores de Inglés alcancen
# a todas las fichas (dos trimestres distintos no lo tienen el mismo día salvo
# que haya más de cinco). El lunes queda al final: suele ser del líder de ficha.
DIAS_INGLES: tuple[str, ...] = ("MARTES", "JUEVES", "MIERCOLES", "VIERNES", "LUNES")


def _fijar_ingles(fichas: list[dict]) -> dict[int, dict]:
    """Un único bloque semanal de Inglés por ficha, recurrente todo el trimestre.

    Las fichas de un mismo trimestre y jornada reciben Inglés el mismo día, en
    bloques distintos; solo si ese día se llena se pasa al siguiente. Cada
    trimestre arranca en un día distinto de DIAS_INGLES.
    """
    fijados: dict[int, dict] = {}
    usados: set[tuple[int, str, str]] = set()
    for ficha in fichas:
        jornada = JORNADA_DE_BLOQUES.get(ficha["jornada"], "Mañana")
        horas = HORAS_INGLES_POR_JORNADA[jornada]
        candidatos = [b for b in bloques_de_jornada(ficha["jornada"]) if horas_continuas_maximas([b]) == horas]
        inicio = (ficha["trimestre"] - 1) % len(DIAS_INGLES)
        dias = DIAS_INGLES[inicio:] + DIAS_INGLES[:inicio]
        dia, bloque = next(
            (d, b)
            for d in dias
            for b in candidatos
            if (ficha["trimestre"], d, b) not in usados
        )
        usados.add((ficha["trimestre"], dia, bloque))
        fijados[ficha["id"]] = {"dia": dia, "bloque": bloque, "horas": horas, "fijado_por": 1}
    return fijados


# ⚠️ PROVISIONAL — ficha_id → bloque de Inglés (reemplazar con Bloque.bloqueado en SQLAlchemy)
INGLES_FICHA: dict[int, dict] = _fijar_ingles(FICHAS_GESTORA_MOCK)


def bloque_ingles(ficha_id: int) -> dict | None:
    return INGLES_FICHA.get(ficha_id)


# ⚠️ PROVISIONAL — último horario generado (app/api/generador.py). Vacío hasta
# que la gestora pulse "Generar horario automático". Claves: generado_en,
# generado_por, sesiones, pendientes.
HORARIO_GENERADO: dict = {}


# ── Utilidades de rol ────────────────────────────────────────────────────────


def _rol(usuario: dict) -> str:
    rol = usuario.get("rol", "")
    return str(getattr(rol, "value", rol)).strip().lower()


def _gestora_id(usuario: dict) -> int:
    valor = usuario.get("sub") or usuario.get("id")
    try:
        return int(str(valor))
    except (TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="La sesión no identifica a una gestora válida.",
        ) from exc


def _exigir_gestora(usuario: dict) -> int:
    gestoras_id = _gestora_id(usuario)
    if _rol(usuario) != "gestora":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Esta operación solo está disponible para la Gestora.",
        )
    return gestoras_id


# ── Programa y trimestres ────────────────────────────────────────────────────

def _programa_gestora() -> ProgramaFormacion:
    programa = obtener_programa(PROGRAMA_GESTORA)
    if programa is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"El programa {PROGRAMA_GESTORA} no está registrado en el catálogo.",
        )
    return programa


def _validar_trimestre(trimestre: int | None) -> int | None:
    """Rechaza trimestres fuera de la duración del programa de la Gestora."""
    if trimestre is None:
        return None
    programa = _programa_gestora()
    if trimestre > programa.total_trimestres:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"El programa {programa.codigo} tiene {programa.total_trimestres} "
                f"trimestres; el trimestre {trimestre} no existe."
            ),
        )
    return trimestre


# ── Consultas sobre el padrón ────────────────────────────────────────────────

def trimestre_actual() -> int:
    """Trimestre en curso según el calendario (1–4, repetido cada tres meses)."""
    return ((date.today().month - 1) // 3) + 1


def _instructor_por_id(instructor_id: object) -> InstructorReferencia | None:
    try:
        clave = int(str(instructor_id))
    except (TypeError, ValueError):
        return None

    registrado = next(
        (
            usuario
            for usuario in INSTRUCTORES_GESTORA
            if int(usuario["id"]) == clave
        ),
        None,
    )
    if registrado is None:
        usuario_mock = next(
            (
                usuario
                for usuario in USUARIOS_MOCK
                if int(usuario.get("id", -1)) == clave
            ),
            None,
        )
        if usuario_mock is None or _rol(usuario_mock) != "instructor":
            return None
        registrado = {
            "id": clave,
            "nombre": usuario_mock["nombre"],
            "correo_sena": usuario_mock.get("correo_sena", ""),
        }

    return InstructorReferencia(
        id=int(registrado["id"]),
        nombre=str(registrado["nombre"]),
        correo_sena=str(registrado.get("correo_sena", "")),
    )


def _persona_por_id(persona_id: object) -> InstructorReferencia | None:
    """Resuelve cualquier usuario del sistema (instructor o gestora)."""
    try:
        clave = int(str(persona_id))
    except (TypeError, ValueError):
        return None

    registrada = next(
        (usuario for usuario in USUARIOS_MOCK if int(usuario.get("id", -1)) == clave),
        None,
    )
    if registrada is not None:
        return InstructorReferencia(
            id=clave,
            nombre=str(registrada["nombre"]),
            correo_sena=str(registrada.get("correo_sena", "")),
        )

    vinculado = next(
        (instructor for instructor in INSTRUCTORES_GESTORA if instructor["id"] == clave),
        None,
    )
    if vinculado is None:
        return None
    return InstructorReferencia(
        id=clave,
        nombre=str(vinculado["nombre"]),
        correo_sena=str(vinculado.get("correo_sena", "")),
    )


def _ficha_por_id(ficha_id: object) -> dict | None:
    try:
        clave = int(str(ficha_id))
    except (TypeError, ValueError):
        return None
    return next((ficha for ficha in FICHAS_GESTORA_MOCK if ficha["id"] == clave), None)


def _fichas_del_trimestre(trimestre: int) -> list[dict]:
    return [ficha for ficha in FICHAS_GESTORA_MOCK if ficha["trimestre"] == trimestre]


def _es_abierta(estado: object) -> bool:
    return str(estado or "").strip().lower() not in {
        valor.lower() for valor in ESTADOS_CERRADOS
    }


def _dias_restantes(fecha_limite: object) -> int:
    fecha = _a_fecha(fecha_limite)
    if fecha is None:
        return 0
    return (fecha - date.today()).days


def _a_fecha(valor: object) -> date | None:
    if isinstance(valor, date):
        return valor
    if not valor:
        return None
    try:
        return date.fromisoformat(str(valor))
    except ValueError:
        return None


def _solicitud_gestora(registro: dict) -> SolicitudBandeja:
    ficha = _ficha_por_id(registro.get("ficha_id"))
    fecha_limite = _a_fecha(registro.get("fecha_limite"))
    return SolicitudBandeja(
        id=int(registro.get("id", 0)),
        ficha_id=int(registro.get("ficha_id", 0)),
        ficha_programa=(ficha or {}).get("programa", "ADSO"),
        ficha_trimestre=(ficha or {}).get("trimestre"),
        instructor=(
            _instructor_por_id(registro.get("solicitada_por"))
            or InstructorReferencia(
                id=int(registro.get("solicitada_por", 0) or 0),
                nombre="Instructor",
            )
        ),
        transversales=list(registro.get("transversales", [])),
        fecha_solicitud=_a_fecha(registro.get("fecha_solicitud")) or date.today(),
        fecha_limite=fecha_limite or date.today(),
        dias_restantes=(fecha_limite - date.today()).days if fecha_limite else 0,
        estado=str(registro.get("estado", "Pendiente")),
        horas_sugeridas=registro.get("horas_sugeridas"),
        bloque_sugerido=str(registro.get("bloque_sugerido", "")),
        comentarios=str(registro.get("comentarios", "")),
        fecha_asignacion=_a_fecha(registro.get("fecha_asignacion")),
        asignada_por=_persona_por_id(registro.get("asignada_por")),
        respuesta_gestora=str(registro.get("respuesta_gestora", "")),
    )


def _solicitudes_ordenadas() -> list[SolicitudBandeja]:
    solicitudes = [_solicitud_gestora(registro) for registro in SOLICITUDES_TRANSVERSALES]
    return sorted(solicitudes, key=lambda item: (item.dias_restantes, item.id))


def _registro_solicitud(solicitud_id: int) -> dict:
    registro = next(
        (
            item
            for item in SOLICITUDES_TRANSVERSALES
            if int(item.get("id", 0)) == solicitud_id
        ),
        None,
    )
    if registro is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No existe la solicitud {solicitud_id}.",
        )
    return registro


# ── Composición del horario ──────────────────────────────────────────────────

def _bloques_fijos(trimestre: int) -> list[dict]:
    """Antes de generar: solo el Inglés fijo de cada ficha del trimestre."""
    sesiones = []
    for ficha in _fichas_del_trimestre(trimestre):
        ingles = bloque_ingles(ficha["id"])
        if ingles:
            sesiones.append(
                {
                    "ficha_id": ficha["id"],
                    "trimestre": ficha["trimestre"],
                    "dia": ingles["dia"],
                    "bloque": ingles["bloque"],
                    "horas": horas_continuas_maximas([ingles["bloque"]]),
                    "tipo": "ingles",
                    "materia": TRANSVERSAL_INGLES,
                    "instructor_id": None,
                    "instructor_nombre": None,
                    "aula": None,
                    "bloqueado": True,
                }
            )
    return sesiones


def a_bloque_horario(sesion: dict) -> BloqueHorario:
    instructor = None
    if sesion.get("instructor_id") is not None:
        instructor = _instructor_por_id(sesion["instructor_id"]) or InstructorReferencia(
            id=sesion["instructor_id"], nombre=sesion.get("instructor_nombre") or "Instructor"
        )
    return BloqueHorario(
        dia=sesion["dia"],
        dia_corto=DIA_CORTO.get(sesion["dia"], sesion["dia"].title()),
        bloque=sesion["bloque"],
        jornada=JORNADA_POR_BLOQUE.get(sesion["bloque"], "Mañana"),
        ocupada=True,
        ficha_id=sesion["ficha_id"],
        trimestre=sesion.get("trimestre"),
        tipo=sesion["tipo"],
        materia=sesion.get("materia"),
        transversal=sesion["materia"] if sesion["tipo"] in {"ingles", "transversal"} else None,
        aula=sesion.get("aula"),
        horas=sesion.get("horas") or horas_continuas_maximas([sesion["bloque"]]),
        bloqueado=sesion.get("bloqueado", False),
        instructor=instructor,
    )


def orden_sesion(sesion: dict) -> tuple:
    return BLOQUES_HORARIOS.index(sesion["bloque"]), DIAS_SEMANA.index(sesion["dia"]), sesion["ficha_id"]


# ── Endpoints ────────────────────────────────────────────────────────────────

@router.get(
    "/perfil",
    response_model=PerfilGestora,
    summary="Resumen operativo de la Gestora autenticada",
)
def consultar_perfil_gestora(usuario: dict = Depends(require_gestora)) -> PerfilGestora:
    gestoras_id = _exigir_gestora(usuario)
    trimestre = trimestre_actual()

    solicitudes = _solicitudes_ordenadas()
    fichas = _fichas_del_trimestre(trimestre)
    abiertas = [item for item in solicitudes if _es_abierta(item.estado)]

    return PerfilGestora(
        id=gestoras_id,
        nombre=str(usuario.get("nombre", "Gestora")),
        correo_sena=str(usuario.get("correo_sena", "")),
        trimestre_actual=trimestre,
        solicitudes_abiertas=len(abiertas),
        solicitudes_vencidas=sum(1 for item in abiertas if item.dias_restantes < 0),
        fichas_activas=len(fichas),
        fichas_sin_instructor=sum(1 for ficha in fichas if not ficha["instructor_ids"]),
        instructores_vinculados=len(
            {
                instructor_id
                for ficha in fichas
                for instructor_id in ficha["instructor_ids"]
            }
        ),
        horas_asignadas=round(sum(ficha["horas_semanales"] for ficha in fichas), 1),
        horas_sugeridas_pendientes=round(
            sum(item.horas_sugeridas or 0 for item in abiertas), 1
        ),
    )


@router.get(
    "/bandeja-solicitudes",
    response_model=BandejaSolicitudes,
    summary="Bandeja de solicitudes de transversales de los instructores",
)
def listar_bandeja_solicitudes(
    estado: str | None = Query(default=None, max_length=30),
    trimestre: int | None = Query(default=None, ge=1),
    usuario: dict = Depends(require_gestora),
) -> BandejaSolicitudes:
    _exigir_gestora(usuario)
    trimestre = _validar_trimestre(trimestre)
    solicitudes = _solicitudes_ordenadas()

    contadores = ContadoresBandeja(
        total=len(solicitudes),
        pendientes=sum(1 for item in solicitudes if item.estado.lower() == "pendiente"),
        en_revision=sum(1 for item in solicitudes if item.estado.lower() == "en revisión"),
        aprobadas=sum(1 for item in solicitudes if item.estado.lower() == "aprobado"),
        rechazadas=sum(1 for item in solicitudes if item.estado.lower() == "rechazado"),
        vencidas=sum(
            1
            for item in solicitudes
            if _es_abierta(item.estado) and item.dias_restantes < 0
        ),
    )

    if estado:
        objetivo = estado.strip().lower()
        solicitudes = [
            item
            for item in solicitudes
            if item.estado.lower() in {objetivo, objetivo.replace(" ", "_")}
        ]
    if trimestre:
        solicitudes = [item for item in solicitudes if item.ficha_trimestre == trimestre]

    return BandejaSolicitudes(
        solicitudes=solicitudes,
        contadores=contadores,
        estados_disponibles=list(ESTADOS_SOLICITUD),
    )


@router.post(
    "/solicitudes/{solicitud_id}/estado",
    response_model=ResultadoActualizacionSolicitud,
    status_code=status.HTTP_200_OK,
    summary="Resolver una solicitud de transversal",
)
def actualizar_estado_solicitud(
    solicitud_id: int,
    datos: ActualizacionSolicitud,
    usuario: dict = Depends(require_gestora),
) -> ResultadoActualizacionSolicitud:
    gestoras_id = _exigir_gestora(usuario)
    registro = _registro_solicitud(solicitud_id)

    if datos.estado not in ESTADOS_SOLICITUD:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Estado no válido. Usa uno de: {', '.join(ESTADOS_SOLICITUD)}.",
        )

    if not _es_abierta(datos.estado) and not datos.comentario:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Explica al instructor el motivo al cerrar la solicitud.",
        )

    registro["estado"] = datos.estado
    registro["comentario_gestora"] = datos.comentario
    registro["respuesta_gestora"] = datos.comentario
    if datos.horas_asignadas is not None:
        registro["horas_asignadas"] = datos.horas_asignadas
    if datos.bloque_asignado:
        registro["bloque_asignado"] = datos.bloque_asignado

    if _es_abierta(datos.estado):
        registro["asignada_por"] = None
        registro["fecha_asignacion"] = None
    else:
        registro["asignada_por"] = gestoras_id
        registro["fecha_asignacion"] = date.today().isoformat()

    solicitud = _solicitud_gestora(registro)
    return ResultadoActualizacionSolicitud(
        mensaje=f"Solicitud {solicitud_id} marcada como {datos.estado}.",
        solicitud=solicitud,
    )


@router.get(
    "/fichas",
    response_model=ResumenFichasTrimestres,
    summary="Fichas y trimestres gestionados por la Gestora",
)
def listar_fichas_trimestres(
    trimestre: int | None = Query(default=None, ge=1),
    usuario: dict = Depends(require_gestora),
) -> ResumenFichasTrimestres:
    _exigir_gestora(usuario)
    programa = _programa_gestora()
    trimestre = _validar_trimestre(trimestre)
    trimestre_actual_ = trimestre_actual()
    trimestre_consulta = trimestre or trimestre_actual_
    fichas = _fichas_del_trimestre(trimestre_consulta)

    abiertas_por_ficha: dict[int, int] = {}
    horas_por_ficha: dict[int, float] = {}
    for solicitud in _solicitudes_ordenadas():
        if not _es_abierta(solicitud.estado):
            continue
        abiertas_por_ficha[solicitud.ficha_id] = abiertas_por_ficha.get(solicitud.ficha_id, 0) + 1
        horas_por_ficha[solicitud.ficha_id] = horas_por_ficha.get(solicitud.ficha_id, 0) + (
            solicitud.horas_sugeridas or 0
        )

    items = [
        FichaTrimestre(
            id=ficha["id"],
            programa=ficha["programa"],
            jornada=ficha["jornada"],
            trimestre=ficha["trimestre"],
            horas_semanales=ficha["horas_semanales"],
            competencias=list(ficha["competencias"]),
            estado="Asignada" if ficha["instructor_ids"] else "Sin instructor",
            instructores=[
                referencia
                for referencia in (
                    _instructor_por_id(instructor_id)
                    for instructor_id in ficha["instructor_ids"]
                )
                if referencia is not None
            ],
            solicitudes_abiertas=abiertas_por_ficha.get(ficha["id"], 0),
            horas_transversales=round(horas_por_ficha.get(ficha["id"], 0.0), 1),
        )
        for ficha in fichas
    ]

    return ResumenFichasTrimestres(
        trimestre=trimestre_consulta,
        items=items,
        total_fichas=len(items),
        total_horas=round(sum(item.horas_semanales for item in items), 1),
        fichas_sin_instructor=sum(1 for item in items if item.estado == "Sin instructor"),
        trimestre_actual=trimestre_actual_,
        programa=programa.codigo,
        trimestres=programa.trimestres,
    )


@router.get(
    "/horarios",
    response_model=HorarioGestora,
    summary="Horario consolidado del trimestre",
)
def listar_horarios(
    trimestre: int | None = Query(default=None, ge=1),
    jornada: str = Query(default="todas", max_length=20),
    ficha: int | None = Query(default=None, description="Filtra una sola ficha."),
    usuario: dict = Depends(require_gestora),
) -> HorarioGestora:
    _exigir_gestora(usuario)
    trimestre = _validar_trimestre(trimestre)
    trimestre_consulta = trimestre or trimestre_actual()

    generado = bool(HORARIO_GENERADO)
    if generado:
        registros = [s for s in HORARIO_GENERADO["sesiones"] if s["trimestre"] == trimestre_consulta]
        pendientes = [p for p in HORARIO_GENERADO["pendientes"] if p["trimestre"] == trimestre_consulta]
    else:
        registros, pendientes = _bloques_fijos(trimestre_consulta), []

    if jornada.strip().lower() not in {"", "todas", "todos"}:
        objetivo = jornada.strip().capitalize()
        registros = [s for s in registros if JORNADA_POR_BLOQUE.get(s["bloque"]) == objetivo]
    if ficha is not None:
        registros = [s for s in registros if s["ficha_id"] == ficha]
        pendientes = [p for p in pendientes if p["ficha_id"] == ficha]

    asignaciones = [a_bloque_horario(s) for s in sorted(registros, key=orden_sesion)]
    return HorarioGestora(
        trimestre=trimestre_consulta,
        jornada=jornada,
        ficha_id=ficha,
        generado=generado,
        generado_en=HORARIO_GENERADO.get("generado_en"),
        dias=[DIA_CORTO[dia] for dia in DIAS_SEMANA],
        bloques=list(BLOQUES_HORARIOS),
        asignaciones=asignaciones,
        total_asignaciones=len(asignaciones),
        horas_asignadas=round(sum(a.horas for a in asignaciones), 1),
        huecos=len(pendientes),
        pendientes=pendientes,
    )


@router.get(
    "/instructores",
    response_model=ListadoInstructoresGestora,
    summary="Instructores vinculados a la Gestora y sus fichas",
)
def listar_instructores(usuario: dict = Depends(require_gestora)) -> ListadoInstructoresGestora:
    _exigir_gestora(usuario)
    items = [
        InstructorGestora(
            id=instructor["id"],
            nombre=instructor["nombre"],
            correo_sena=instructor.get("correo_sena", ""),
            fecha_ingreso=_a_fecha(instructor.get("fecha_ingreso")),
            es_nuevo=es_nuevo_instructor(instructor.get("fecha_ingreso")),
            fichas=[
                FichaDeInstructor(id=ficha["id"], trimestre=ficha["trimestre"], jornada=ficha["jornada"])
                for ficha in sorted(FICHAS_GESTORA_MOCK, key=lambda ficha: (ficha["trimestre"], ficha["id"]))
                if instructor["id"] in ficha["instructor_ids"]
            ],
        )
        for instructor in sorted(INSTRUCTORES_GESTORA, key=lambda instructor: instructor["nombre"])
    ]
    return ListadoInstructoresGestora(items=items, total=len(items))
