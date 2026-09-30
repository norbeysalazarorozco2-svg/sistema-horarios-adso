from fastapi import APIRouter

from app.schemas.malla import RAPTrimestre

router = APIRouter(prefix="/malla", tags=["Malla curricular"])

# ⚠️ PROVISIONAL — reemplazar con datos oficiales de SofiaPlus
RAP_REQUERIDOS_MOCK = [
    RAPTrimestre(id=1, programa="ADSO", numero_trimestre=1, rap_id=1, competencia_id=1),
    RAPTrimestre(id=2, programa="ADSO", numero_trimestre=2, rap_id=2, competencia_id=2),
    RAPTrimestre(id=3, programa="ADSO", numero_trimestre=3, rap_id=3, competencia_id=3),
    RAPTrimestre(id=4, programa="ADSO", numero_trimestre=4, rap_id=4, competencia_id=3),
]


@router.get(
    "/requeridos/{programa}/{numero_trimestre}",
    response_model=list[RAPTrimestre],
)
def listar_rap_requeridos(programa: str, numero_trimestre: int) -> list[RAPTrimestre]:
    return [
        rap
        for rap in RAP_REQUERIDOS_MOCK
        if rap.programa.upper() == programa.upper()
        and rap.numero_trimestre == numero_trimestre
    ]
