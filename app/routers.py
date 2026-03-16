from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select

from app.auth_router import get_current_user
from app.database import get_session
from app.models import Parcela, Usuario
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
    current_user: Usuario = Depends(get_current_user),
) -> ParcelaRead:
    # ParcelaCreate ya validó la geometría; procedemos a persistir.
    parcela = Parcela(
        nombre=payload.nombre,
        descripcion=payload.descripcion,
        cultivo=payload.cultivo,
        geometria=payload.geometria,
        usuario_id=current_user.id,
    )
    session.add(parcela)
    session.commit()
    session.refresh(parcela)
    return parcela


# ---------------------------------------------------------------------------
# GET /parcelas — Listar todas las parcelas (del usuario actual)
# ---------------------------------------------------------------------------


@router.get(
    "/",
    response_model=List[ParcelaRead],
    summary="Listar parcelas",
    description="Retorna la lista de parcelas registradas pertenecientes al usuario actual.",
)
def list_parcelas(
    session: Session = Depends(get_session),
    current_user: Usuario = Depends(get_current_user),
) -> List[Parcela]:
    parcelas = session.exec(select(Parcela).where(Parcela.usuario_id == current_user.id)).all()
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
    current_user: Usuario = Depends(get_current_user),
) -> SatelitalResponse:
    parcela = session.get(Parcela, parcela_id)
    if not parcela or parcela.usuario_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Parcela con id={parcela_id} no encontrada.",
        )
    return SatelitalResponse(**parcela.to_sentinel_format())


# ---------------------------------------------------------------------------
# PUT /parcelas/{id} — Actualizar parcela
# ---------------------------------------------------------------------------


@router.put(
    "/{parcela_id}",
    response_model=ParcelaRead,
    summary="Actualizar parcela",
    description="Actualiza los metadatos y la geometría de una parcela.",
)
def update_parcela(
    parcela_id: int,
    payload: ParcelaCreate,
    session: Session = Depends(get_session),
    current_user: Usuario = Depends(get_current_user),
) -> ParcelaRead:
    parcela = session.get(Parcela, parcela_id)
    if not parcela or parcela.usuario_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Parcela con id={parcela_id} no encontrada.",
        )
    
    parcela.nombre = payload.nombre
    parcela.descripcion = payload.descripcion
    parcela.cultivo = payload.cultivo
    parcela.geometria = payload.geometria
    
    session.add(parcela)
    session.commit()
    session.refresh(parcela)
    return parcela


# ---------------------------------------------------------------------------
# DELETE /parcelas/{id} — Eliminar parcela
# ---------------------------------------------------------------------------


@router.delete(
    "/{parcela_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Eliminar parcela",
    description="Elimina de forma permanente una parcela.",
)
def delete_parcela(
    parcela_id: int,
    session: Session = Depends(get_session),
    current_user: Usuario = Depends(get_current_user),
):
    parcela = session.get(Parcela, parcela_id)
    if not parcela or parcela.usuario_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Parcela con id={parcela_id} no encontrada.",
        )
    
    session.delete(parcela)
    session.commit()
    return None
