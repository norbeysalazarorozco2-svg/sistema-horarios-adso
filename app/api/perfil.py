from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.auth import USUARIOS_MOCK
from app.api.disponibilidad import es_nuevo_instructor
from app.core.security import require_instructor
from app.schemas.perfil import (
    CambioModoPrueba,
    CompetenciaPerfil,
    FichaAsignada,
    PerfilInstructor,
    RespuestaModoPrueba,
    ResultadoSolicitudTransversal,
    SolicitudTransversal,
    SolicitudTransversalCreate,
)


router = APIRouter(
    prefix="/api/v1/instructor",
    tags=["Perfil del instructor"],
)

router_transversales = APIRouter(
    prefix="/api/transversales",
    tags=["Solicitudes de transversales"],
)

COMPETENCIAS_JAVIER = [
    {
        "codigo": "220501092",
        "nombre": "Analizar requisitos de software",
    },
    {
        "codigo": "220501093",
        "nombre": "Diseñar sistemas de información",
    },
    {
        "codigo": "220501095",
        "nombre": "Desarrollar aplicaciones web",
    },
]

COMP_ANALISIS, COMP_DISENO, COMP_WEB = COMPETENCIAS_JAVIER

PERFILES_MOCK: dict[str, dict] = {
    "101": {
        "competencias": COMPETENCIAS_JAVIER,
        "turnos_preferidos": ["Mañana", "Tarde"],
    },
    "103": {"competencias": [COMP_ANALISIS, COMP_WEB], "turnos_preferidos": ["Mañana"]},
    "104": {"competencias": [COMP_DISENO, COMP_WEB], "turnos_preferidos": ["Mañana", "Tarde"]},
    "105": {"competencias": COMPETENCIAS_JAVIER, "turnos_preferidos": ["Mañana", "Tarde", "Noche"]},
}

FICHAS_MOCK: dict[str, list[dict]] = {
    "101": [
        {
            "id": 3365169,
            "programa": "ADSO",
            "jornada": "Diurna",
            "trimestre": 3,
            "competencias": COMPETENCIAS_JAVIER[:2],
            "horas_semanales": 16.0,
        },
        {
            "id": 3365170,
            "programa": "ADSO",
            "jornada": "Diurna",
            "trimestre": 3,
            "competencias": COMPETENCIAS_JAVIER[2:],
            "horas_semanales": 16.0,
        },
    ],
    # Las fichas coinciden con FICHAS_GESTORA_MOCK y las horas suman la carga
    # base de CARGA_INSTRUCTORES_MOCK (app/api/alertas.py): 32, 33 y 36 h.
    "103": [
        {
            "id": 3365101,
            "programa": "ADSO",
            "jornada": "Diurna",
            "trimestre": 1,
            "competencias": [COMP_ANALISIS],
            "horas_semanales": 12.0,
        },
        {
            "id": 3365200,
            "programa": "ADSO",
            "jornada": "Diurna",
            "trimestre": 4,
            "competencias": [COMP_ANALISIS, COMP_WEB],
            "horas_semanales": 10.0,
        },
        {
            "id": 3365230,
            "programa": "ADSO",
            "jornada": "Diurna",
            "trimestre": 5,
            "competencias": [COMP_WEB],
            "horas_semanales": 10.0,
        },
    ],
    "104": [
        {
            "id": 3365130,
            "programa": "ADSO",
            "jornada": "Diurna",
            "trimestre": 2,
            "competencias": [COMP_DISENO, COMP_WEB],
            "horas_semanales": 12.0,
        },
        {
            "id": 3365200,
            "programa": "ADSO",
            "jornada": "Diurna",
            "trimestre": 4,
            "competencias": [COMP_WEB],
            "horas_semanales": 11.0,
        },
        {
            "id": 3365260,
            "programa": "ADSO",
            "jornada": "Diurna",
            "trimestre": 6,
            "competencias": [COMP_DISENO],
            "horas_semanales": 10.0,
        },
    ],
    "105": [
        {
            "id": 3365102,
            "programa": "ADSO",
            "jornada": "Diurna",
            "trimestre": 1,
            "competencias": [COMP_WEB],
            "horas_semanales": 12.0,
        },
        {
            "id": 3365131,
            "programa": "ADSO",
            "jornada": "Tarde",
            "trimestre": 2,
            "competencias": [COMP_ANALISIS],
            "horas_semanales": 12.0,
        },
        {
            "id": 3365201,
            "programa": "ADSO",
            "jornada": "Nocturna",
            "trimestre": 4,
            "competencias": [COMP_DISENO],
            "horas_semanales": 12.0,
        },
    ],
}

SOLICITUDES_TRANSVERSALES: list[dict] = []
MODO_PRUEBA_POR_USUARIO: dict[str, str] = {}


def _instructor_id(usuario: dict) -> int:
    valor = usuario.get("sub") or usuario.get("id")
    try:
        return int(str(valor))
    except (TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="La sesión no identifica a un instructor válido.",
        ) from exc


def _rol(usuario: dict) -> str:
    rol = usuario.get("rol", "")
    return str(getattr(rol, "value", rol)).lower()


def _exigir_instructor(usuario: dict) -> int:
    instructor_id = _instructor_id(usuario)
    if _rol(usuario) != "instructor":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Esta operación solo está disponible para instructores.",
        )
    return instructor_id


def _usuario_registrado(instructor_id: int) -> dict | None:
    return next(
        (
            usuario
            for usuario in USUARIOS_MOCK
            if int(usuario.get("id", -1)) == instructor_id
        ),
        None,
    )


def _gestora_registrada() -> dict | None:
    return next((usuario for usuario in USUARIOS_MOCK if _rol(usuario) == "gestora"), None)


def _fecha_ingreso(valor: object) -> date | None:
    if not valor:
        return None
    if isinstance(valor, date):
        return valor
    try:
        return date.fromisoformat(str(valor))
    except ValueError:
        return None


def _identidad(usuario: dict, instructor_id: int) -> tuple[str, str, date | None]:
    registrado = _usuario_registrado(instructor_id) or {}
    nombre = usuario.get("nombre") or registrado.get("nombre") or "Instructor"
    correo = usuario.get("correo_sena") or registrado.get("correo_sena") or ""
    fecha = _fecha_ingreso(usuario.get("fecha_ingreso") or registrado.get("fecha_ingreso"))
    return str(nombre), str(correo), fecha


def _fichas(instructor_id: int) -> list[FichaAsignada]:
    return [
        FichaAsignada.model_validate(ficha)
        for ficha in FICHAS_MOCK.get(str(instructor_id), [])
    ]


def _modo_prueba(instructor_id: int, fecha_ingreso: date | None) -> str:
    modo = MODO_PRUEBA_POR_USUARIO.get(str(instructor_id))
    if modo in {"nuevo", "antiguo"}:
        return modo
    return "nuevo" if es_nuevo_instructor(fecha_ingreso) else "antiguo"


def _fichas_segun_modo(instructor_id: int, modo: str) -> list[FichaAsignada]:
    if modo == "nuevo":
        return []
    return _fichas(instructor_id) or _fichas(101)


def _competencias_segun_modo(instructor_id: int, modo: str) -> list[CompetenciaPerfil]:
    if modo == "nuevo":
        return []
    perfil = PERFILES_MOCK.get(str(instructor_id), {})
    if not perfil:
        perfil = PERFILES_MOCK["101"]
    return [
        CompetenciaPerfil.model_validate(item)
        for item in perfil.get("competencias", [])
    ]


def _solicitudes(instructor_id: int) -> list[SolicitudTransversal]:
    return [
        SolicitudTransversal.model_validate(solicitud)
        for solicitud in SOLICITUDES_TRANSVERSALES
        if solicitud.get("solicitada_por") == instructor_id
    ]


def _antiguedad_dias(fecha_ingreso: date | None) -> int:
    if fecha_ingreso is None:
        return 0
    return max((date.today() - fecha_ingreso).days, 0)


@router.post(
    "/modo-prueba",
    response_model=RespuestaModoPrueba,
    status_code=status.HTTP_200_OK,
    summary="Cambiar temporalmente el modo de prueba del instructor",
)
def cambiar_modo_prueba(
    datos: CambioModoPrueba,
    usuario: dict = Depends(require_instructor),
) -> RespuestaModoPrueba:
    instructor_id = _exigir_instructor(usuario)
    MODO_PRUEBA_POR_USUARIO[str(instructor_id)] = datos.modo
    return RespuestaModoPrueba(modo=datos.modo)


def _horas_extra(instructor_id: int) -> float:
    # Import diferido: app.api.alertas depende (vía gestora) de este módulo.
    from app.api.alertas import horas_extra_aceptadas

    return horas_extra_aceptadas(instructor_id)


@router.get(
    "/perfil",
    response_model=PerfilInstructor,
    summary="Consultar el perfil del instructor autenticado",
)
def consultar_perfil(usuario: dict = Depends(require_instructor)) -> PerfilInstructor:
    instructor_id = _exigir_instructor(usuario)
    nombre, correo, fecha_ingreso = _identidad(usuario, instructor_id)
    modo = _modo_prueba(instructor_id, fecha_ingreso)
    es_nuevo = modo == "nuevo"
    fichas = _fichas_segun_modo(instructor_id, modo)
    competencias = _competencias_segun_modo(instructor_id, modo)
    solicitudes = [] if es_nuevo else _solicitudes(instructor_id)

    return PerfilInstructor(
        id=instructor_id,
        nombre=nombre,
        correo_sena=correo,
        fecha_ingreso=fecha_ingreso,
        es_nuevo=es_nuevo,
        antiguedad_dias=_antiguedad_dias(fecha_ingreso),
        competencias=competencias,
        fichas=fichas,
        horas_semanales=sum(ficha.horas_semanales for ficha in fichas),
        horas_extra_autorizadas=0 if es_nuevo else _horas_extra(instructor_id),
        solicitudes_transversales=solicitudes,
        modo_prueba=modo,
    )


def _crear_solicitudes_transversales(
    datos: SolicitudTransversalCreate,
    usuario: dict,
) -> ResultadoSolicitudTransversal:
    instructor_id = _exigir_instructor(usuario)
    _, _, fecha_ingreso = _identidad(usuario, instructor_id)
    modo = _modo_prueba(instructor_id, fecha_ingreso)

    if modo == "nuevo":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="El modo Instructor Nuevo no tiene fichas a cargo para solicitar transversales.",
        )

    fichas_disponibles = {
        ficha.id: ficha for ficha in _fichas_segun_modo(instructor_id, modo)
    }
    fichas_no_asignadas = sorted(set(datos.ficha_ids) - set(fichas_disponibles))
    if fichas_no_asignadas:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solo puedes solicitar transversales para tus fichas a cargo.",
        )

    pendientes_por_ficha: dict[int, set[str]] = {}
    for solicitud in _solicitudes(instructor_id):
        if solicitud.estado.lower() not in {"pendiente", "en revisión", "en_revision"}:
            continue
        pendientes_por_ficha.setdefault(solicitud.ficha_id, set()).update(
            solicitud.transversales
        )

    conflictos = {
        ficha_id: sorted(set(datos.transversales) & pendientes)
        for ficha_id, pendientes in pendientes_por_ficha.items()
        if ficha_id in datos.ficha_ids and set(datos.transversales) & pendientes
    }
    if conflictos:
        detalle = "; ".join(
            f"Ficha {ficha_id}: {', '.join(asignaturas)}"
            for ficha_id, asignaturas in conflictos.items()
        )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Ya existe una solicitud pendiente para {detalle}.",
        )

    gestora = _gestora_registrada()
    if gestora is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="No hay una Gestora configurada para recibir la solicitud.",
        )

    fecha_solicitud = date.today()
    fecha_limite = fecha_solicitud + timedelta(days=7)
    siguiente_id = max(
        (solicitud.get("id", 0) for solicitud in SOLICITUDES_TRANSVERSALES),
        default=0,
    ) + 1
    nuevas_solicitudes: list[dict] = []

    for ficha_id in datos.ficha_ids:
        solicitud = {
            "id": siguiente_id,
            "ficha_id": ficha_id,
            "solicitada_por": instructor_id,
            "transversales": list(datos.transversales),
            "fecha_solicitud": fecha_solicitud.isoformat(),
            "fecha_limite": fecha_limite.isoformat(),
            "estado": "Pendiente",
            "asignada_por": None,
            "fecha_asignacion": None,
            "horas_sugeridas": datos.horas_sugeridas,
            "bloque_sugerido": datos.bloque_sugerido,
            "comentarios": datos.comentarios,
            "gestora_id": int(gestora["id"]),
            "gestora_nombre": str(gestora["nombre"]),
        }
        siguiente_id += 1
        nuevas_solicitudes.append(solicitud)

    SOLICITUDES_TRANSVERSALES.extend(nuevas_solicitudes)
    return ResultadoSolicitudTransversal(
        mensaje="Solicitud enviada a la Gestora para coordinación.",
        solicitudes=[
            SolicitudTransversal.model_validate(solicitud)
            for solicitud in nuevas_solicitudes
        ],
    )


@router.post(
    "/solicitudes-transversales",
    response_model=ResultadoSolicitudTransversal,
    status_code=status.HTTP_201_CREATED,
    summary="Solicitar bloques para asignaturas transversales",
)
def solicitar_transversales(
    datos: SolicitudTransversalCreate,
    usuario: dict = Depends(require_instructor),
) -> ResultadoSolicitudTransversal:
    return _crear_solicitudes_transversales(datos, usuario)


@router_transversales.post(
    "/solicitar",
    response_model=ResultadoSolicitudTransversal,
    status_code=status.HTTP_201_CREATED,
    summary="Enviar una solicitud de transversal a la Gestora",
)
def solicitar_transversales_alias(
    datos: SolicitudTransversalCreate,
    usuario: dict = Depends(require_instructor),
) -> ResultadoSolicitudTransversal:
    return _crear_solicitudes_transversales(datos, usuario)
