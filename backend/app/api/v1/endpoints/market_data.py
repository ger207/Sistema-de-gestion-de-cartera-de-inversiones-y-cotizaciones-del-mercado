from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.enums import FxRateType
from app.models.asset import Asset
from app.models.market_data import ExchangeRate, AssetPrice
from app.schemas.market_data import ExchangeRateResponse, AssetPriceResponse
from app.services.market_data_service import MarketDataService

router = APIRouter()

@router.post("/sync/dolar", response_model=List[ExchangeRateResponse], summary="Sincronizar tipos de cambio desde DolarApi")
async def sync_dolar(db: Session = Depends(get_db)):
    """Descarga e impacta en BD las cotizaciones de Dólar CCL, MEP, Oficial, Blue y Cripto."""
    rates = await MarketDataService.sync_dolar_rates_to_db(db)
    return rates

@router.get("/dolar/latest", response_model=List[ExchangeRateResponse], summary="Obtener últimos tipos de cambio registrados")
def get_latest_fx_rates(db: Session = Depends(get_db)):
    """Devuelve el valor más reciente registrado para cada tipo de cambio financiero."""
    rates = []
    for rate_type in FxRateType:
        latest = (
            db.query(ExchangeRate)
            .filter(ExchangeRate.rate_type == rate_type)
            .order_by(ExchangeRate.timestamp.desc())
            .first()
        )
        if latest:
            rates.append(latest)
    return rates

@router.post("/sync/asset/{asset_id}", response_model=AssetPriceResponse, summary="Sincronizar precio de un activo vía Yahoo Finance")
def sync_asset_price(asset_id: int, db: Session = Depends(get_db)):
    """Consulta la cotización actual en Yahoo Finance (soporta .BA y tickers cripto) y la guarda."""
    asset = db.query(Asset).filter(Asset.id == asset_id).first()
    if not asset:
        raise HTTPException(status_code=404, detail="Activo no encontrado")
    
    price_record = MarketDataService.sync_asset_market_price(db, asset)
    if not price_record:
        raise HTTPException(status_code=502, detail=f"No se pudo obtener precio para ticker {asset.ticker}")
    return price_record

@router.get("/merval-panel", summary="Panel general de acciones líderes del Merval")
def get_merval_panel(force_refresh: bool = False):
    """Retorna las cotizaciones en tiempo real del panel líder de Merval con apertura, cierre anterior y variación."""
    return MarketDataService.get_merval_panel(force_refresh=force_refresh)
