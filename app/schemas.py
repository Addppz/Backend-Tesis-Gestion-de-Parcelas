from typing import Any, Dict, List, Optional
from datetime import date

from pydantic import field_validator, model_validator
from sqlmodel import SQLModel


# ---------------------------------------------------------------------------
# Esquemas de entrada / salida (no son tablas de BD)
# ---------------------------------------------------------------------------


class ParcelaCreate(SQLModel):
    """
    Schema de creación. Aplica validaciones estrictas de geometría antes
    de persistir en la base de datos.
    """

    nombre: str
    descripcion: str
    cultivo: str
    geometria: Dict[str, Any]

    @model_validator(mode="after")
    def validar_geometria(self) -> "ParcelaCreate":
        geo = self.geometria

        # 1. Debe contener la clave "coordinates"
        if "coordinates" not in geo:
            raise ValueError(
                "El campo 'geometria' debe contener la clave 'coordinates'."
            )

        coords: List = geo["coordinates"]

        # 2. Debe tener al menos 4 puntos
        if not isinstance(coords, list) or len(coords) < 4:
            raise ValueError(
                "La lista 'coordinates' debe contener al menos 4 puntos "
                "([lon, lat]) para formar un polígono válido."
            )

        # 3. Cada punto debe ser una lista/tupla de dos números
        for i, punto in enumerate(coords):
            if not isinstance(punto, (list, tuple)) or len(punto) != 2:
                raise ValueError(
                    f"El punto en la posición {i} debe ser una lista "
                    "de dos elementos [longitud, latitud]."
                )

        # 4. Anillo cerrado: primer punto == último punto
        if coords[0] != coords[-1]:
            raise ValueError(
                "La geometría debe formar un anillo cerrado: "
                "el primer punto debe ser idéntico al último. "
                f"Primero={coords[0]}, Último={coords[-1]}"
            )

        return self


class ParcelaRead(SQLModel):
    """Schema de lectura (respuesta de la API)."""

    id: int
    nombre: str
    descripcion: str
    cultivo: str
    geometria: Dict[str, Any]
    usuario_id: Optional[int]
    # Devuelve el task_id del Módulo Satelital si ya existe un proceso iniciado
    satellite_task_id: Optional[str] = None


class SatelitalResponse(SQLModel):
    """Respuesta del endpoint /satelital, compatible con Delvis."""

    polygon: Dict[str, Any]


class SatelliteProcessRequest(SQLModel):
    """
    Parámetros que envía el frontend para solicitar el procesamiento
    satelital de una parcela. La geometría se obtiene automáticamente
    de la parcela en la base de datos.
    """

    start_date: date
    end_date: date
    max_cloud_cover: int = 10
    max_items: int = 30
    target_resolution: int = 10


# ---------------------------------------------------------------------------
# Schemas de Usuario (autenticación)
# ---------------------------------------------------------------------------


class UsuarioCreate(SQLModel):
    """Schema para registrar un nuevo usuario."""

    nombre: str
    email: str
    password: str


class UsuarioRead(SQLModel):
    """Schema de respuesta (nunca expone la contraseña)."""

    id: int
    nombre: str
    email: str
    is_active: bool


class LoginRequest(SQLModel):
    """Credenciales para iniciar sesión."""

    email: str
    password: str


class Token(SQLModel):
    """Respuesta del endpoint de login con el JWT generado."""

    access_token: str
    token_type: str = "bearer"
