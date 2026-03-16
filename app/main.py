from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import create_db_and_tables
from app.auth_router import router as auth_router
from app.routers import router


# ---------------------------------------------------------------------------
# Lifespan: crea tablas al arrancar la aplicación
# ---------------------------------------------------------------------------


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator:
    create_db_and_tables()
    yield


# ---------------------------------------------------------------------------
# Aplicación principal
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Microservicio de Gestión de Parcelas",
    description=(
        "API REST para la gestión de parcelas agrícolas. "
        "Incluye compatibilidad con el microservicio de imágenes "
        "satelitales Sentinel-2."
    ),
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
)

# Configuración básica de CORS para permitir al frontend conectarse
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # En producción, usar el dominio exacto
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(router)


@app.get("/", tags=["Health"])
def health_check() -> dict:
    return {"status": "ok", "service": "gestion-parcelas"}
