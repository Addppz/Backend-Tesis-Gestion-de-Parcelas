from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select

from app.database import get_session
from app.models import Parcela
from app.schemas import ParcelaCreate, ParcelaRead, SatelitalResponse

router = APIRouter(prefix="/parcelas", tags=["Parcelas"])


# ---------------------------------------------------------------------------
# POST /parcelas — Crear una nueva parcela
# ---------------------------------------------------------------------------


@router.post(
    "/",
    response_model=ParcelaRead,
    status_code=status.HTTP_201_CREATED,
    summary="Crear parcela",
    description=(
        "Crea una nueva parcela agrícola. El campo **geometria** debe cumplir "
        "el estándar Delvis: objeto con clave `coordinates`, al menos 4 puntos "
        "[longitud, latitud] y anillo cerrado."
    ),
)
def create_parcela(
    payload: ParcelaCreate,
    session: Session = Depends(get_session),
) -> ParcelaRead:
    # ParcelaCreate ya validó la geometría; procedemos a persistir.
    parcela = Parcela(
        nombre=payload.nombre,
        descripcion=payload.descripcion,
        cultivo=payload.cultivo,
        geometria=payload.geometria,
    )
    session.add(parcela)
    session.commit()
    session.refresh(parcela)
    return parcela


# ---------------------------------------------------------------------------
# GET /parcelas — Listar todas las parcelas
# ---------------------------------------------------------------------------


@router.get(
    "/",
    response_model=List[ParcelaRead],
    summary="Listar parcelas",
    description="Retorna la lista completa de parcelas registradas.",
)
def list_parcelas(session: Session = Depends(get_session)) -> List[Parcela]:
    parcelas = session.exec(select(Parcela)).all()
    return parcelas


# ---------------------------------------------------------------------------
# GET /parcelas/{id}/satelital — Formato compatible con Delvis / Sentinel-2
# ---------------------------------------------------------------------------


@router.get(
    "/{parcela_id}/satelital",
    response_model=SatelitalResponse,
    summary="Obtener parcela en formato satelital (Delvis)",
    description=(
        "Retorna la geometría de la parcela en el formato exacto requerido por "
        "el microservicio de procesamiento de imágenes Sentinel-2 de Delvis: "
        "`{\"polygon\": {\"coordinates\": [...]}}`."
    ),
)
def get_parcela_satelital(
    parcela_id: int,
    session: Session = Depends(get_session),
) -> SatelitalResponse:
    parcela = session.get(Parcela, parcela_id)
    if not parcela:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Parcela con id={parcela_id} no encontrada.",
        )
    return SatelitalResponse(**parcela.to_sentinel_format())
