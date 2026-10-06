"""
main.py — Punto de entrada principal de FastAPI.
Sistema de Horarios ADSO — SENA

Compatibilidad: Starlette 1.6+ (nueva firma de TemplateResponse).
"""

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pathlib import Path
import os

from app.api.alertas import router as alertas_router
from app.api.auth import router as auth_router
from app.api.catalogo import router as catalogo_router
from app.api.malla import router as malla_router
from app.api.disponibilidad import router as disponibilidad_router
from app.api.equidad import router as equidad_router
from app.api.gestora import router as gestora_router
from app.api.horas_extra import router as horas_extra_router, solicitudes_pendientes_de
from app.api.lideres import ficha_liderada_por, router as lideres_router
from app.api.mi_ficha import instructor_id_de, router as mi_ficha_router
from app.api.trimestre import router as trimestre_router, trimestre_aprobado
from app.api.perfil import (
    router as perfil_router,
    router_transversales as transversales_router,
)
from app.core.security import (
    ROL_GESTORA,
    ROL_INSTRUCTOR,
    es_gestora,
    get_current_user_from_request,
    require_gestora,
    require_instructor,
    ruta_inicio_de_rol,
    sesion_opcional,
)
from datetime import date

# ── Rutas absolutas referidas al paquete ──────────────────────────────────────
BASE_DIR      = Path(__file__).resolve().parent   # .../norbey/app/
STATIC_DIR    = BASE_DIR / "static"
TEMPLATES_DIR = BASE_DIR / "templates"

# ── Instancia de la aplicación ────────────────────────────────────────────────
app = FastAPI(
    title="Sistema de Horarios ADSO — SENA",
    description="API para gestión de disponibilidad horaria de instructores",
    version="1.0.0",
)

# ── Archivos estáticos (/static) ──────────────────────────────────────────────
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# ── Motor de plantillas Jinja2 (Starlette 1.6+) ───────────────────────────────
# Starlette 1.6 cambió la firma: TemplateResponse(request, name, context={})
# url_for ya no se inyecta automáticamente; lo registramos como global Jinja2.
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

def _url_for(name: str, **path_params) -> str:
    """Global Jinja2 equivalente a url_for de Starlette < 1.6."""
    return str(app.url_path_for(name, **path_params))

templates.env.globals["url_for"] = _url_for

# ── Modo desarrollo ───────────────────────────────────────────────────────────
# Las herramientas de desarrollo (simular rol, cuentas demo, modo de prueba,
# catálogo de componentes) no forman parte de la interfaz de producción.
MODO_DESARROLLO = os.getenv("APP_ENV", "development").lower() != "production"
templates.env.globals["modo_desarrollo"] = MODO_DESARROLLO

# ── Routers de la API ─────────────────────────────────────────────────────────
app.include_router(auth_router)
app.include_router(catalogo_router)
app.include_router(malla_router)
app.include_router(disponibilidad_router)
app.include_router(perfil_router)
app.include_router(transversales_router)
app.include_router(gestora_router)
app.include_router(alertas_router)
app.include_router(lideres_router)
app.include_router(equidad_router)
app.include_router(trimestre_router)
app.include_router(mi_ficha_router)
app.include_router(horas_extra_router)

# ── Contexto de sesión para las vistas SSR ───────────────────────────────────

def contexto_sesion(request: Request) -> dict:
    """Datos de sesión que necesita el navbar para renderizar por rol.

    Devuelve siempre las claves `sesion_activa`, `rol` y `usuario_nombre` para
    que las plantillas no dependan de que cada ruta las haya incluido.
    """
    payload = sesion_opcional(request)
    if not payload:
        return {"sesion_activa": False, "rol": "", "usuario_nombre": ""}

    rol = payload.get("rol", "")
    return {
        "sesion_activa": True,
        "rol": str(getattr(rol, "value", rol)).strip().lower(),
        "usuario_nombre": payload.get("nombre", ""),
    }


# ── Rutas SSR (Jinja2 Templates) ─────────────────────────────────────────────

def _rol_de(usuario: dict) -> str:
    rol = usuario.get("rol", "")
    return str(getattr(rol, "value", rol)).strip().lower()


def _iniciar_sesion(request: Request, usuario: dict) -> RedirectResponse:
    """Emite el JWT, fija la cookie de sesión y redirige según el rol."""
    from app.core.security import create_access_token

    token = create_access_token(
        {
            "sub": str(usuario["id"]),
            "correo_sena": usuario["correo_sena"],
            "nombre": usuario["nombre"],
            "rol": usuario["rol"],
            "fecha_ingreso": usuario.get("fecha_ingreso"),
        }
    )
    response = RedirectResponse(
        url=ruta_inicio_de_rol(_rol_de(usuario)),
        status_code=303,
    )
    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        samesite="lax",
        secure=request.url.scheme == "https",
        path="/",
        max_age=60 * 60 * 8,
    )
    return response


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
async def home(request: Request):
    """Portada: envía a la pantalla inicial según el rol de la sesión."""
    payload = sesion_opcional(request)
    if payload:
        return RedirectResponse(
            url=ruta_inicio_de_rol(
                str(getattr(payload.get("rol", ""), "value", payload.get("rol", ""))).strip().lower()
            ),
            status_code=303,
        )

    return templates.TemplateResponse(
        request,
        "login.html",
        context=contexto_sesion(request),
    )


@app.get("/auth/login", response_class=HTMLResponse, include_in_schema=False)
async def vista_login(request: Request, error: str | None = None):
    """Renderiza el formulario de inicio de sesión."""
    from app.api.auth import USUARIOS_MOCK

    return templates.TemplateResponse(
        request,
        "login.html",
        context={
            **contexto_sesion(request),
            "error": error,
            "cuentas_demo": [
                {
                    "correo_sena": usuario["correo_sena"],
                    "nombre": usuario["nombre"],
                    "rol": str(getattr(usuario["rol"], "value", usuario["rol"])),
                }
                for usuario in USUARIOS_MOCK
            ]
            if MODO_DESARROLLO
            else [],
        },
    )


@app.post("/auth/login/ssr", response_class=HTMLResponse, include_in_schema=False)
async def procesar_login(request: Request):
    """Procesa el submit del <form> de login (SSR multipart/form-data)."""
    from app.core.security import create_access_token, verify_password
    from app.api.auth import USUARIOS_MOCK

    form = await request.form()
    correo   = str(form.get("correo_sena", ""))
    password = str(form.get("password", ""))

    usuario = next(
        (u for u in USUARIOS_MOCK if u["correo_sena"] == correo), None
    )

    if not usuario or not verify_password(password, usuario["password_hash"]):
        return templates.TemplateResponse(
            request,
            "login.html",
            context={
                **contexto_sesion(request),
                "error": "Correo o contraseña incorrectos.",
                "correo_previo": correo,
            },
            status_code=401,
        )

    return _iniciar_sesion(request, usuario)


@app.post("/auth/simular-rol", response_class=HTMLResponse, include_in_schema=False)
async def simular_rol(request: Request):
    """Selector rápido de usuario/rol para pruebas.

    Crea una sesión con una de las cuentas de demostración elegidas por rol y
    redirige a la pantalla inicial de ese rol:

      - `instructor` → /disponibilidad  (y /perfil-instructor)
      - `gestora`    → /perfil-gestora

    Herramienta de desarrollo: no existe en producción.
    """
    if not MODO_DESARROLLO:
        raise HTTPException(status_code=404)

    from app.api.auth import USUARIOS_MOCK

    form = await request.form()
    rol = str(form.get("rol", "")).strip().lower()
    correo = str(form.get("correo_sena", "")).strip()

    if rol not in {ROL_INSTRUCTOR, ROL_GESTORA}:
        return RedirectResponse(url="/auth/login?error=rol-desconocido", status_code=303)

    candidatos = [u for u in USUARIOS_MOCK if _rol_de(u) == rol]
    usuario = next((u for u in candidatos if u["correo_sena"] == correo), None) or next(
        iter(candidatos), None
    )

    if usuario is None:
        return RedirectResponse(url="/auth/login?error=sin-cuentas", status_code=303)

    return _iniciar_sesion(request, usuario)


@app.post("/auth/cerrar-sesion", response_class=HTMLResponse, include_in_schema=False)
async def cerrar_sesion():
    """Cierra la sesión borrando la cookie y vuelve al selector de login."""
    response = RedirectResponse(url="/auth/login", status_code=303)
    response.delete_cookie(key="access_token", path="/")
    return response


@app.get("/auth/registro", response_class=HTMLResponse, include_in_schema=False)
async def vista_registro(
    request: Request,
    error: str | None = None,
    success: str | None = None,
):
    """Renderiza el formulario de registro."""
    return templates.TemplateResponse(
        request,
        "registro.html",
        context={**contexto_sesion(request), "error": error, "success": success},
    )


@app.post("/auth/registro/ssr", response_class=HTMLResponse, include_in_schema=False)
async def procesar_registro(request: Request):
    """Procesa el submit del <form> de registro (SSR)."""
    from app.api.auth import USUARIOS_MOCK
    from app.core.security import get_password_hash
    from app.schemas.auth import RolEnum

    form = await request.form()
    nombre   = str(form.get("nombre", "")).strip()
    correo   = str(form.get("correo_sena", "")).strip()
    rol_str  = str(form.get("rol", "instructor"))
    password = str(form.get("password", ""))

    if any(u["correo_sena"] == correo for u in USUARIOS_MOCK):
        return templates.TemplateResponse(
            request,
            "registro.html",
            context={
                **contexto_sesion(request),
                "error": "Ese correo ya está registrado en el sistema.",
                "nombre_previo": nombre,
                "correo_previo": correo,
                "rol_previo": rol_str,
            },
            status_code=409,
        )

    rol = RolEnum.INSTRUCTOR

    nuevo = {
        "id": len(USUARIOS_MOCK) + 100,
        "correo_sena": correo,
        "nombre": nombre,
        "rol": rol,
        "password_hash": get_password_hash(password),
        "fecha_ingreso": date.today().isoformat(),
    }
    USUARIOS_MOCK.append(nuevo)

    return templates.TemplateResponse(
        request,
        "login.html",
        context={
            **contexto_sesion(request),
            "success": f"Cuenta creada para {nombre}. ¡Inicia sesión!",
            "correo_previo": correo,
        },
    )


@app.get("/disponibilidad", response_class=HTMLResponse, include_in_schema=False)
async def vista_disponibilidad(request: Request):
    """Renderiza la pantalla de la Matriz de Disponibilidad (solo Instructores)."""
    payload = sesion_opcional(request)
    if payload and es_gestora(payload):
        return RedirectResponse(url="/perfil-gestora", status_code=303)

    contexto = {
        "es_nuevo": False,
        "instructor_nombre": "",
        "bloques_ingles": [],
        **contexto_sesion(request),
    }

    if payload:
        from app.api.disponibilidad import es_nuevo_instructor
        from app.api.gestora import bloques_ingles_de_instructor

        contexto["es_nuevo"] = es_nuevo_instructor(payload.get("fecha_ingreso"))
        contexto["instructor_nombre"] = payload.get("nombre", "")
        instructor_id = instructor_id_de(payload)
        if instructor_id is not None:
            contexto["bloques_ingles"] = bloques_ingles_de_instructor(instructor_id)

    return templates.TemplateResponse(
        request,
        "disponibilidad.html",
        context=contexto,
    )


@app.get("/perfil-instructor", response_class=HTMLResponse, include_in_schema=False)
async def vista_perfil_instructor(request: Request):
    try:
        payload = get_current_user_from_request(request)
    except HTTPException:
        return RedirectResponse(url="/auth/login", status_code=303)

    if es_gestora(payload):
        return RedirectResponse(url="/perfil-gestora", status_code=303)

    try:
        require_instructor(payload)
    except HTTPException:
        return RedirectResponse(url="/disponibilidad", status_code=303)

    from app.api.disponibilidad import es_nuevo_instructor

    return templates.TemplateResponse(
        request,
        "perfil_instructor.html",
        context={
            "instructor_nombre": payload.get("nombre", ""),
            "es_nuevo": es_nuevo_instructor(payload.get("fecha_ingreso")),
            "ficha_liderada": ficha_liderada_por(instructor_id_de(payload)),
            "horas_extra_pendientes": solicitudes_pendientes_de(instructor_id_de(payload)),
            "horario_publicado": trimestre_aprobado(),
            **contexto_sesion(request),
        },
    )


@app.get("/horas-extra", response_class=HTMLResponse, include_in_schema=False)
async def vista_horas_extra(request: Request):
    """Solicitudes de horas extra que la gestora envió al instructor."""
    try:
        payload = get_current_user_from_request(request)
    except HTTPException:
        return RedirectResponse(url="/auth/login", status_code=303)

    if es_gestora(payload):
        return RedirectResponse(url="/gestora/alertas", status_code=303)

    return templates.TemplateResponse(
        request,
        "horas_extra.html",
        context={**contexto_sesion(request)},
    )


@app.get("/mi-ficha", response_class=HTMLResponse, include_in_schema=False)
async def vista_mi_ficha(request: Request):
    """Ficha que lidera el instructor; si no lidera ninguna, muestra un estado vacío."""
    try:
        payload = get_current_user_from_request(request)
    except HTTPException:
        return RedirectResponse(url="/auth/login", status_code=303)

    if es_gestora(payload):
        return RedirectResponse(url="/gestora/lideres", status_code=303)

    return templates.TemplateResponse(
        request,
        "mi_ficha.html",
        context={
            "ficha_liderada": ficha_liderada_por(instructor_id_de(payload)),
            **contexto_sesion(request),
        },
    )


# ── Vista independiente de la Gestora ────────────────────────────────────────

@app.get("/perfil-gestora", response_class=HTMLResponse, include_in_schema=False)
async def vista_perfil_gestora(request: Request):
    """Pantalla propia de la Gestora: bandeja, fichas & trimestres y horarios."""
    try:
        payload = get_current_user_from_request(request)
    except HTTPException:
        return RedirectResponse(url="/auth/login", status_code=303)

    try:
        require_gestora(payload)
    except HTTPException:
        return RedirectResponse(url="/disponibilidad", status_code=303)

    from app.api.gestora import trimestre_actual

    return templates.TemplateResponse(
        request,
        "perfil_gestora.html",
        context={
            "gestora_nombre": payload.get("nombre", ""),
            "trimestre_actual": trimestre_actual(),
            **contexto_sesion(request),
        },
    )


@app.get("/gestora/alertas", response_class=HTMLResponse, include_in_schema=False)
async def vista_alertas_gestora(request: Request):
    """Alertas de huecos: RAP sin instructor y candidatos para horas extra."""
    try:
        payload = get_current_user_from_request(request)
    except HTTPException:
        return RedirectResponse(url="/auth/login", status_code=303)

    try:
        require_gestora(payload)
    except HTTPException:
        return RedirectResponse(url="/disponibilidad", status_code=303)

    return templates.TemplateResponse(
        request,
        "alertas_gestora.html",
        context={**contexto_sesion(request)},
    )


@app.get("/gestora/trimestre", response_class=HTMLResponse, include_in_schema=False)
async def vista_trimestre_gestora(request: Request):
    """Aprobación final del trimestre: verificaciones, aprobación y reapertura (§8)."""
    try:
        payload = get_current_user_from_request(request)
    except HTTPException:
        return RedirectResponse(url="/auth/login", status_code=303)

    try:
        require_gestora(payload)
    except HTTPException:
        return RedirectResponse(url="/disponibilidad", status_code=303)

    return templates.TemplateResponse(
        request,
        "trimestre_gestora.html",
        context={**contexto_sesion(request)},
    )


@app.get("/gestora/equidad", response_class=HTMLResponse, include_in_schema=False)
async def vista_equidad_gestora(request: Request):
    """Historial de carga por trimestre y compensaciones de equidad (§6)."""
    try:
        payload = get_current_user_from_request(request)
    except HTTPException:
        return RedirectResponse(url="/auth/login", status_code=303)

    try:
        require_gestora(payload)
    except HTTPException:
        return RedirectResponse(url="/disponibilidad", status_code=303)

    return templates.TemplateResponse(
        request,
        "equidad_gestora.html",
        context={**contexto_sesion(request)},
    )


@app.get("/gestora/lideres", response_class=HTMLResponse, include_in_schema=False)
async def vista_lideres_gestora(request: Request):
    """Asignación del instructor líder de cada ficha y su bloque semanal."""
    try:
        payload = get_current_user_from_request(request)
    except HTTPException:
        return RedirectResponse(url="/auth/login", status_code=303)

    try:
        require_gestora(payload)
    except HTTPException:
        return RedirectResponse(url="/disponibilidad", status_code=303)

    return templates.TemplateResponse(
        request,
        "lideres_gestora.html",
        context={**contexto_sesion(request)},
    )


# ── Herramientas de desarrollo ───────────────────────────────────────────────

if MODO_DESARROLLO:

    @app.get("/_dev/componentes", response_class=HTMLResponse, include_in_schema=False)
    async def catalogo_componentes(request: Request, rol: str = "instructor", fase: str | None = None):
        """Catálogo del sistema visual SIPA con datos de ejemplo (solo desarrollo)."""
        rol_vista = rol if rol in {"instructor", "lider", "gestora"} else "instructor"
        return templates.TemplateResponse(
            request,
            "dev/componentes.html",
            context={
                **contexto_sesion(request),
                "rol": ROL_GESTORA if rol_vista == "gestora" else ROL_INSTRUCTOR,
                "es_lider_ficha": rol_vista == "lider",
                "rol_vista": rol_vista,
                "usuario_nombre": "Usuario de ejemplo",
                "trimestre": 3,
                "fase_actual": fase if fase in {"actualizacion", "solicitudes", "generacion"} else "solicitudes",
                "nav_activo": "panel" if rol_vista == "gestora" else "inicio",
            },
        )
