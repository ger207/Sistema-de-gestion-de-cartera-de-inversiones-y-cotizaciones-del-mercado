from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.asset import Asset
from app.schemas.asset import AssetCreate, AssetResponse, AssetUpdate

router = APIRouter()

@router.get("/", response_model=List[AssetResponse], summary="Listar todos los activos")
def list_assets(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    """Obtiene el catálogo de instrumentos financieros registrados."""
    assets = db.query(Asset).offset(skip).limit(limit).all()
    return assets

@router.post("/", response_model=AssetResponse, status_code=status.HTTP_201_CREATED, summary="Registrar nuevo activo")
def create_asset(asset_in: AssetCreate, db: Session = Depends(get_db)):
    """Crea un nuevo activo (ej: GGAL.BA, AAPL.BA, AL30.BA, BTC-USD)."""
    existing = db.query(Asset).filter(Asset.ticker == asset_in.ticker.upper()).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"El activo con ticker '{asset_in.ticker}' ya se encuentra registrado."
        )
    
    asset_data = asset_in.model_dump()
    asset_data["ticker"] = asset_data["ticker"].upper()
    asset = Asset(**asset_data)
    db.add(asset)
    db.commit()
    db.refresh(asset)
    return asset

@router.get("/{asset_id}", response_model=AssetResponse, summary="Obtener detalle de un activo")
def get_asset(asset_id: int, db: Session = Depends(get_db)):
    asset = db.query(Asset).filter(Asset.id == asset_id).first()
    if not asset:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Activo no encontrado")
    return asset
