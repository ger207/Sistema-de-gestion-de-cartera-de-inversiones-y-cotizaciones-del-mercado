from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.core.database import engine
from app.models import Base
from app.services.scheduler import start_scheduler, stop_scheduler

# Crear tablas directamente en la BD (útil en SQLite para desarrollo rápido inicial)
Base.metadata.create_all(bind=engine)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Inicialización del planificador en segundo plano
    start_scheduler()
    yield
    # Detención controlada al apagar el servidor
    stop_scheduler()

app = FastAPI(
    title=settings.PROJECT_NAME,
    description="Backend de gestión de carteras bimonetarias (USD/ARS CCL/MEP) y control de riesgo financiero.",
    version="0.1.0",
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    lifespan=lifespan,
)

# CORS para permitir conexión del futuro frontend web
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from app.api.v1.router import api_router
app.include_router(api_router, prefix=settings.API_V1_STR)

@app.get("/health", tags=["Sistema"])
def health_check():
    return {
        "status": "healthy",
        "project": settings.PROJECT_NAME,
        "base_currency": settings.BASE_CURRENCY,
        "secondary_currency": settings.SECONDARY_CURRENCY
    }
