from fastapi import APIRouter

from app.schemas.catalogo import Competencia, RAP

router = APIRouter(prefix="/catalogo", tags=["Catálogo"])

# ⚠️ PROVISIONAL — reemplazar con datos oficiales de SofiaPlus
COMPETENCIAS_MOCK = [
    Competencia(id=1, nombre="Analizar requisitos de software", codigo="220501092"),
    Competencia(id=2, nombre="Diseñar sistemas de información", codigo="220501093"),
    Competencia(id=3, nombre="Desarrollar aplicaciones web", codigo="220501095"),
]

# ⚠️ PROVISIONAL — reemplazar con datos oficiales de SofiaPlus
RAP_MOCK = [
    RAP(id=1, nombre="Interpretar necesidades del usuario", competencia_id=1),
    RAP(id=2, nombre="Modelar la solución de software", competencia_id=2),
    RAP(id=3, nombre="Implementar servicios web", competencia_id=3),
    RAP(id=4, nombre="Probar la aplicación desarrollada", competencia_id=3),
]


@router.get("/competencias", response_model=list[Competencia])
def listar_competencias() -> list[Competencia]:
    return COMPETENCIAS_MOCK


@router.get("/rap", response_model=list[RAP])
def listar_rap() -> list[RAP]:
    return RAP_MOCK
