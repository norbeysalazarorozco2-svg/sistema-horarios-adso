from fastapi import APIRouter

from app.schemas.catalogo import RAP, Competencia, ProgramaFormacion

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

# ⚠️ PROVISIONAL — reemplazar con datos oficiales de SofiaPlus.
# La duración pertenece al programa: el resto del sistema deriva de aquí
# cuántos trimestres existen, sin depender de las fichas registradas.
PROGRAMAS_MOCK: dict[str, ProgramaFormacion] = {
    "ADSO": ProgramaFormacion(codigo="ADSO", total_trimestres=9),
}


def obtener_programa(codigo: str) -> ProgramaFormacion | None:
    return PROGRAMAS_MOCK.get(str(codigo).strip().upper())


@router.get("/competencias", response_model=list[Competencia])
def listar_competencias() -> list[Competencia]:
    return COMPETENCIAS_MOCK


@router.get("/rap", response_model=list[RAP])
def listar_rap() -> list[RAP]:
    return RAP_MOCK
