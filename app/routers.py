from typing import List
import os
import io

import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlmodel import Session, select

from app.auth_router import get_current_user
from app.database import get_session
from app.models import Parcela, Usuario
from app.schemas import ParcelaCreate, ParcelaRead, SatelitalResponse, SatelliteProcessRequest

router = APIRouter(prefix="/parcelas", tags=["Parcelas"])

# URL base del Módulo Satelital. En producción se puede sobreescribir
# con una variable de entorno (SATELLITE_MODULE_URL) apuntando al contenedor interno.
SATELLITE_MODULE_URL = os.getenv("SATELLITE_MODULE_URL", "http://127.0.0.1:8001")



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


# ---------------------------------------------------------------------------
# POST /parcelas/{id}/process-satellite — Iniciar procesamiento satelital
# ---------------------------------------------------------------------------


@router.post(
    "/{parcela_id}/process-satellite",
    summary="Iniciar procesamiento satelital para una parcela",
    description=(
        "Toma la geometría de la parcela y la envía al Módulo Satelital "
        "para iniciar la descarga y procesamiento de imágenes Sentinel-2. "
        "El `task_id` devuelto queda vinculado a la parcela en la base de datos."
    ),
)
async def process_satellite(
    parcela_id: int,
    params: SatelliteProcessRequest,
    session: Session = Depends(get_session),
    current_user: Usuario = Depends(get_current_user),
) -> dict:
    # Verificar que la parcela existe y pertenece al usuario actual
    parcela = session.get(Parcela, parcela_id)
    if not parcela or parcela.usuario_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Parcela con id={parcela_id} no encontrada.",
        )

    # Construir el payload para el Módulo Satelital combinando
    # la geometría de la parcela con los parámetros de la petición.
    # El nombre usa el de la parcela para identificar el trabajo en el Worker.
    payload = {
        "polygon": {"coordinates": parcela.geometria["coordinates"]},
        "start_date": params.start_date.isoformat(),
        "end_date": params.end_date.isoformat(),
        "max_cloud_cover": params.max_cloud_cover,
        "max_items": params.max_items,
        "target_resolution": params.target_resolution,
        "name": parcela.nombre,
    }

    # Realizar la petición HTTP al Módulo Satelital de forma asíncrona
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{SATELLITE_MODULE_URL}/sentinel/process",
                json=payload,
            )
            response.raise_for_status()
    except httpx.ConnectError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="El Módulo Satelital no está disponible. Verifica que esté corriendo en el puerto 8001.",
        )
    except httpx.HTTPStatusError as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Error en el Módulo Satelital: {e.response.text}",
        )

    # Guardar el task_id en la base de datos de la parcela para vinculación futura
    result = response.json()
    parcela.satellite_task_id = result["task_id"]
    session.add(parcela)
    session.commit()
    session.refresh(parcela)

    return {
        "message": "Procesamiento satelital iniciado.",
        "parcela_id": parcela_id,
        "task_id": result["task_id"],
        "image_id": result.get("image_id"),
    }


# ---------------------------------------------------------------------------
# GET /parcelas/{id}/satellite-status — Consultar estado del procesamiento
# ---------------------------------------------------------------------------


@router.get(
    "/{parcela_id}/satellite-status",
    summary="Consultar estado del procesamiento satelital",
    description=(
        "Retorna el estado actual del proceso de descarga de imágenes Sentinel-2 "
        "asociado a la parcela indicada: porcentaje de avance, mensajes y resultado final."
    ),
)
async def satellite_status(
    parcela_id: int,
    session: Session = Depends(get_session),
    current_user: Usuario = Depends(get_current_user),
) -> dict:
    # Verificar que la parcela existe y pertenece al usuario actual
    parcela = session.get(Parcela, parcela_id)
    if not parcela or parcela.usuario_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Parcela con id={parcela_id} no encontrada.",
        )

    # Verificar que existe un task_id vinculado a la parcela
    if not parcela.satellite_task_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Esta parcela no tiene ningún procesamiento satelital iniciado.",
        )

    # Consultar el estado del Worker
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                f"{SATELLITE_MODULE_URL}/sentinel/status/{parcela.satellite_task_id}",
            )
            response.raise_for_status()
    except httpx.ConnectError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="El Módulo Satelital no está disponible.",
        )
    except httpx.HTTPStatusError as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Error consultando el Módulo Satelital: {e.response.text}",
        )

    return response.json()


# ---------------------------------------------------------------------------
# GET /parcelas/{id}/satellite-image — Obtener imagen RGB procesada
# ---------------------------------------------------------------------------


@router.get("/{parcela_id}/satellite-image/{index_type}")
async def get_parcela_satellite_image(
    parcela_id: int,
    index_type: str = "rgb",
    session: Session = Depends(get_session),
    current_user: Usuario = Depends(get_current_user)
):
    """
    Obtiene la imagen satelital o un índice (ndvi, ndwi, etc.) para una parcela.
    Proxy hacia el Módulo Satelital.
    """
    # Use parcela_id instead of id for consistency with other routes
    parcela = session.get(Parcela, parcela_id)
    if not parcela or parcela.usuario_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Parcela con id={parcela_id} no encontrada.",
        )
    if not parcela.satellite_task_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No hay procesamiento satelital para esta parcela")

    # Primero obtener el status para sacar el image_id real del módulo satelital
    try:
        async with httpx.AsyncClient() as client:
            status_resp = await client.get(f"{SATELLITE_MODULE_URL}/sentinel/status/{parcela.satellite_task_id}")
            status_resp.raise_for_status()
            task_data = status_resp.json()
            
            image_id = task_data.get("result", {}).get("image_id")
            if not image_id:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="El procesamiento no ha generado una imagen aún")

            # Construir URL según el tipo de índice
            if index_type.lower() == "rgb":
                image_url = f"{SATELLITE_MODULE_URL}/sentinel/image/{image_id}"
            else:
                image_url = f"{SATELLITE_MODULE_URL}/indices/{index_type.lower()}/{image_id}"

            # Proxy de la imagen (stream)
            resp = await client.get(image_url, timeout=30.0)
            resp.raise_for_status()
            
            return StreamingResponse(
                io.BytesIO(resp.content),
                media_type="image/png"
            )
    except httpx.ConnectError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="El Módulo Satelital no está disponible.",
        )
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"Error en el Módulo Satelital: {str(e)}")


@router.get(
    "/{parcela_id}/satellite-image",
    summary="Obtener imagen RGB del procesamiento satelital",
    description=(
        "Una vez que el procesamiento esté completado, retorna la URL de descarga "
        "de la imagen RGB generada por el Módulo Satelital para la parcela indicada."
    ),
)
async def satellite_image(
    parcela_id: int,
    session: Session = Depends(get_session),
    current_user: Usuario = Depends(get_current_user),
) -> dict:
    # Verificar que la parcela existe y pertenece al usuario actual
    parcela = session.get(Parcela, parcela_id)
    if not parcela or parcela.usuario_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Parcela con id={parcela_id} no encontrada.",
        )

    if not parcela.satellite_task_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Esta parcela no tiene ningún procesamiento satelital iniciado.",
        )

    # Consultar el estado para verificar que se completó
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            status_response = await client.get(
                f"{SATELLITE_MODULE_URL}/sentinel/status/{parcela.satellite_task_id}",
            )
            status_response.raise_for_status()
            task_data = status_response.json()
    except httpx.ConnectError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="El Módulo Satelital no está disponible.",
        )

    if task_data.get("status") != "completed":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"El procesamiento aún no ha finalizado. Estado actual: {task_data.get('status')}",
        )

    # Obtener el image_id del resultado para construir la URL de imagen
    result = task_data.get("result", {})
    image_id = result.get("image_id")

    if not image_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No se encontró la imagen resultante en el Módulo Satelital.",
        )

    return {
        "parcela_id": parcela_id,
        "task_id": parcela.satellite_task_id,
        "image_id": image_id,
        # URL directa al endpoint de imagen RGB del Módulo Satelital
        "image_url": f"{SATELLITE_MODULE_URL}/sentinel/image/{image_id}",
        "coverage": result.get("coverage"),
        "images_processed": result.get("images_processed"),
    }
