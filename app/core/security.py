import bcrypt
from datetime import datetime, timedelta
import os
import secrets
from typing import Optional

from fastapi import Cookie, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt

SECRET_KEY = os.getenv("SECRET_KEY")
if not SECRET_KEY:
    if os.getenv("APP_ENV", "development").lower() == "production":
        raise RuntimeError("Debe configurar SECRET_KEY en producción.")
    SECRET_KEY = secrets.token_urlsafe(32)

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 480  # El token durará 8 horas

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login", auto_error=False)

# ── Roles y rutas de inicio ──────────────────────────────────────────────────
ROL_INSTRUCTOR = "instructor"
ROL_GESTORA = "gestora"

RUTA_INICIO_POR_ROL: dict[str, str] = {
    ROL_INSTRUCTOR: "/disponibilidad",
    ROL_GESTORA: "/perfil-gestora",
}


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Compara la contraseña en texto plano ingresado con la contraseña encriptada."""
    try:
        return bcrypt.checkpw(
            plain_password.encode("utf-8"), hashed_password.encode("utf-8")
        )
    except Exception:
        return False


def get_password_hash(password: str) -> str:
    """Encripta una contraseña antes de guardarla."""
    pwd_bytes = password.encode("utf-8")
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(pwd_bytes, salt).decode("utf-8")



def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Genera el token JWT firmado para la sesión del usuario."""
    to_encode = data.copy()

    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode.update({
        "exp": expire,
        "iat": datetime.utcnow(),
        "jti": secrets.token_urlsafe(16),
    })
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def decode_access_token(token: str) -> dict:
    """Valida el token JWT y devuelve sus datos."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="No se pudo validar la sesión",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: Optional[str] = payload.get("sub")
        if user_id is None:
            raise credentials_exception
        return payload
    except JWTError as exc:
        raise credentials_exception from exc


def _decode_session(tokens: tuple[str | None, ...]) -> dict:
    candidates = list(dict.fromkeys(token for token in tokens if token))
    if not candidates:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No se pudo validar la sesión",
            headers={"WWW-Authenticate": "Bearer"},
        )

    for candidate in candidates:
        try:
            return decode_access_token(candidate)
        except HTTPException:
            continue

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="No se pudo validar la sesión",
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_current_user(
    token: str | None = Depends(oauth2_scheme),
    access_token: str | None = Cookie(default=None, alias="access_token"),
) -> dict:
    return _decode_session((token, access_token))


def get_current_user_from_request(request: Request) -> dict:
    authorization = request.headers.get("authorization", "")
    scheme, _, token = authorization.partition(" ")
    bearer = token.strip() if scheme.lower() == "bearer" else None
    return _decode_session((bearer, request.cookies.get("access_token")))


def sesion_opcional(request: Request) -> dict | None:
    """Devuelve la sesión activa o None si no hay una válida (para vistas SSR)."""
    try:
        return get_current_user_from_request(request)
    except HTTPException:
        return None


def rol_de(usuario: dict | None) -> str:
    """Rol normalizado del usuario; acepta RolEnum, cadenas o un payload vacío."""
    if not usuario:
        return ""
    rol = usuario.get("rol", "")
    return str(getattr(rol, "value", rol)).strip().lower()


def es_gestora(usuario: dict | None) -> bool:
    return rol_de(usuario) == ROL_GESTORA


def es_instructor(usuario: dict | None) -> bool:
    return rol_de(usuario) == ROL_INSTRUCTOR


def ruta_inicio_de_rol(rol: str) -> str:
    """Pantalla de inicio asociada al rol indicado."""
    return RUTA_INICIO_POR_ROL.get(str(rol or "").strip().lower(), "/disponibilidad")


def ruta_inicio_de_usuario(usuario: dict | None) -> str:
    """Pantalla de inicio asociada al usuario autenticado."""
    return ruta_inicio_de_rol(rol_de(usuario))


def require_instructor(usuario: dict = Depends(get_current_user)) -> dict:
    if not es_instructor(usuario):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Esta operación solo está disponible para instructores.",
        )
    return usuario


def require_gestora(usuario: dict = Depends(get_current_user)) -> dict:
    """Guard de rol exclusivo de la Gestora."""
    if not es_gestora(usuario):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Esta operación solo está disponible para la Gestora.",
        )
    return usuario
