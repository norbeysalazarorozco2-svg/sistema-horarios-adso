from datetime import date
from enum import Enum

from pydantic import BaseModel, field_validator


class RolEnum(str, Enum):
    """Roles permitidos en el sistema."""

    INSTRUCTOR = "instructor"
    GESTORA = "gestora"


class LoginRequest(BaseModel):
    """Datos requeridos para iniciar sesión."""

    correo_sena: str
    password: str


class TokenResponse(BaseModel):
    """Respuesta de autenticación con un token de acceso."""

    access_token: str
    token_type: str = "bearer"
    rol: RolEnum
    nombre: str


class RegistroRequest(BaseModel):
    """Datos requeridos para registrar un usuario."""

    correo_sena: str
    nombre: str
    rol: RolEnum = RolEnum.INSTRUCTOR
    password: str
    fecha_ingreso: date | None = None

    @field_validator("rol")
    @classmethod
    def validar_rol(cls, rol: RolEnum) -> RolEnum:
        if rol != RolEnum.INSTRUCTOR:
            raise ValueError("El registro público solo permite cuentas de instructor.")
        return rol

    @field_validator("fecha_ingreso")
    @classmethod
    def validar_fecha_ingreso(cls, fecha: date | None) -> date | None:
        if fecha and fecha > date.today():
            raise ValueError("La fecha de ingreso no puede ser futura.")
        return fecha

    @field_validator("password")
    @classmethod
    def validar_password(cls, password: str) -> str:
        patron_especial = r'[!@#$%^&*()_+\-=\[\]{};\':"\\|,.<>/?]'
        if (
            len(password) < 8
            or not any(caracter.isupper() for caracter in password)
            or not any(caracter.isdigit() for caracter in password)
            or not any(caracter in patron_especial for caracter in password)
        ):
            raise ValueError(
                "La contraseña debe tener 8+ caracteres, una mayúscula, "
                "un número y un carácter especial"
            )
        return password


class RegistroResponse(BaseModel):
    """Respuesta del registro de usuario."""

    id: int
    correo_sena: str
    nombre: str
    rol: RolEnum
    fecha_ingreso: date | None = None


