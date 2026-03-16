from typing import Any, Dict, List, Optional

from sqlalchemy import Column
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, SQLModel


# ---------------------------------------------------------------------------
# Modelo de Parcela
# ---------------------------------------------------------------------------


class Parcela(SQLModel, table=True):
    """
    Modelo de Parcela agrícola.
    El campo geometria sigue el estándar de Delvis:
    {"coordinates": [[lon, lat], [lon, lat], ..., [lon, lat]]}
    en EPSG:4326 (WGS84), con anillo cerrado (primer punto == último punto).
    """

    __tablename__ = "parcelas"

    id: Optional[int] = Field(default=None, primary_key=True)
    nombre: str = Field(index=True, description="Nombre identificador de la parcela")
    descripcion: str = Field(description="Descripción detallada de la parcela")
    cultivo: str = Field(description="Tipo de cultivo sembrado en la parcela")
    geometria: Dict[str, Any] = Field(
        default={},
        sa_column=Column(JSONB),
        description=(
            "Geometría en formato Delvis: "
            '{"coordinates": [[lon, lat], ..., [lon, lat]]}'
        ),
    )

    def to_sentinel_format(self) -> Dict[str, Any]:
        """
        Retorna la geometría en el formato exacto requerido por el
        microservicio de procesamiento de imágenes Sentinel-2 (Delvis).
        """
        return {"polygon": {"coordinates": self.geometria["coordinates"]}}


# ---------------------------------------------------------------------------
# Modelo de Usuario (autenticación JWT)
# ---------------------------------------------------------------------------


class Usuario(SQLModel, table=True):
    """
    Modelo de usuario para autenticación basada en JWT.
    La contraseña nunca se almacena en texto plano; siempre se guarda
    como hash bcrypt mediante la capa de servicio de autenticación.
    """

    __tablename__ = "usuarios"

    id: Optional[int] = Field(default=None, primary_key=True)
    nombre: str = Field(description="Nombre completo del usuario")
    email: str = Field(
        unique=True,
        index=True,
        description="Correo electrónico único (usado como login)",
    )
    hashed_password: str = Field(description="Contraseña hasheada con bcrypt")
    is_active: bool = Field(
        default=True,
        description="Indica si la cuenta está activa",
    )
