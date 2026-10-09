from decimal import Decimal
from typing import Optional
from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field
from app.models.enums import FxRateType

class AssetPriceCreate(BaseModel):
    asset_id: int
    timestamp: datetime
    open_price: Optional[Decimal] = None
    high_price: Optional[Decimal] = None
    low_price: Optional[Decimal] = None
    close_price: Decimal
    adj_close_price: Optional[Decimal] = None
    volume: Optional[Decimal] = None
    source: str = "YFINANCE"

class AssetPriceResponse(AssetPriceCreate):
    id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class ExchangeRateCreate(BaseModel):
    rate_type: FxRateType
    timestamp: datetime
    buy_price: Optional[Decimal] = None
    sell_price: Decimal
    source: str = "DOLAR_API"

class ExchangeRateResponse(ExchangeRateCreate):
    id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class DolarApiItem(BaseModel):
    moneda: str
    casa: str
    nombre: str
    compra: Optional[Decimal] = None
    venta: Decimal
    fechaActualizacion: datetime
