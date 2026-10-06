from datetime import date

from fastapi import APIRouter, HTTPException, Request, Response, status

from app.core.security import create_access_token, get_password_hash, verify_password
from app.schemas.auth import LoginRequest, RegistroRequest, RegistroResponse, RolEnum, TokenResponse

router = APIRouter(prefix="/auth", tags=["Autenticación"])

USUARIOS_MOCK = [
    {
        "id": 101,
        "correo_sena": "jmontoya@sena.edu.co",
        "nombre": "Javier Montoya",
        "rol": RolEnum.INSTRUCTOR,
        "password_hash": get_password_hash("Clave123!"),
        "fecha_ingreso": "2023-02-10",
    },
    {
        "id": 1,
        "correo_sena": "mgestora@sena.edu.co",
        "nombre": "Mónica",
        "rol": RolEnum.GESTORA,
        "password_hash": get_password_hash("Clave123!"),
        "fecha_ingreso": "2022-05-01",
    },
    {
        "id": 202,
        "correo_sena": "instructor.nuevo@sena.edu.co",
        "nombre": "Laura Ramírez",
        "rol": RolEnum.INSTRUCTOR,
        "password_hash": get_password_hash("Clave123!"),
        "fecha_ingreso": date.today().isoformat(),
    },
    {
        "id": 103,
        "correo_sena": "sospina@sena.edu.co",
        "nombre": "Sandra Ospina",
        "rol": RolEnum.INSTRUCTOR,
        "password_hash": get_password_hash("Clave123!"),
        "fecha_ingreso": "2021-03-15",
    },
    {
        "id": 104,
        "correo_sena": "avillalba@sena.edu.co",
        "nombre": "Andrés Villalba",
        "rol": RolEnum.INSTRUCTOR,
        "password_hash": get_password_hash("Clave123!"),
        "fecha_ingreso": "2024-01-08",
    },
    {
        "id": 105,
        "correo_sena": "mduarte@sena.edu.co",
        "nombre": "Marcela Duarte",
        "rol": RolEnum.INSTRUCTOR,
        "password_hash": get_password_hash("Clave123!"),
        "fecha_ingreso": "2020-07-01",
    },
]


@router.post("/login", response_model=TokenResponse)
def login(request: Request, datos: LoginRequest, response: Response) -> TokenResponse:
    usuario = next(
        (item for item in USUARIOS_MOCK if item["correo_sena"] == datos.correo_sena),
        None,
    )
    if usuario is None or not verify_password(datos.password, usuario["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Correo o contraseña incorrectos",
        )

    token = create_access_token(
        {
            "sub": str(usuario["id"]),
            "correo_sena": usuario["correo_sena"],
            "nombre": usuario["nombre"],
            "rol": usuario["rol"],
            "fecha_ingreso": usuario.get("fecha_ingreso"),
        }
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

    return TokenResponse(
        access_token=token,
        rol=usuario["rol"],
        nombre=usuario["nombre"],
    )


@router.post("/registro", response_model=RegistroResponse, status_code=status.HTTP_201_CREATED)
def registro(datos: RegistroRequest) -> RegistroResponse:
    if any(item["correo_sena"] == datos.correo_sena for item in USUARIOS_MOCK):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="El correo ya está registrado",
        )

    usuario = {
        "id": len(USUARIOS_MOCK) + 100,
        "correo_sena": datos.correo_sena,
        "nombre": datos.nombre,
        "rol": datos.rol,
        "password_hash": get_password_hash(datos.password),
        "fecha_ingreso": datos.fecha_ingreso.isoformat()
        if datos.fecha_ingreso
        else date.today().isoformat(),
    }
    USUARIOS_MOCK.append(usuario)
    return RegistroResponse(
        id=usuario["id"],
        correo_sena=usuario["correo_sena"],
        nombre=usuario["nombre"],
        rol=usuario["rol"],
        fecha_ingreso=usuario["fecha_ingreso"],
    )

