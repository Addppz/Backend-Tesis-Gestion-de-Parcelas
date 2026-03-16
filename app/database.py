import os
from typing import Generator

from dotenv import load_dotenv

load_dotenv()  # Carga variables desde .env en desarrollo local

from sqlmodel import Session, SQLModel, create_engine

# ---------------------------------------------------------------------------
# Configuración de la base de datos
# ---------------------------------------------------------------------------

DATABASE_URL: str = os.environ.get(
    "DATABASE_URL",
    "postgresql://user:password@localhost:5432/gestion_parcelas",
)

# echo=True muestra las queries en consola durante el desarrollo.
# Cambia a echo=False en producción.
engine = create_engine(DATABASE_URL, echo=True)


def create_db_and_tables() -> None:
    """Crea todas las tablas definidas en los modelos SQLModel."""
    SQLModel.metadata.create_all(engine)


def get_session() -> Generator[Session, None, None]:
    """
    Dependencia FastAPI para inyectar una sesión de BD en cada endpoint.
    Garantiza que la sesión se cierre correctamente al finalizar la petición.
    """
    with Session(engine) as session:
        yield session
