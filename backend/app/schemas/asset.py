from decimal import Decimal
from typing import Optional
from datetime import date, datetime
from pydantic import BaseModel, ConfigDict, Field
from app.models.enums import AssetClass, Currency

class AssetBase(BaseModel):
    ticker: str = Field(..., max_length=30, description="Ticker de cotización (ej: GGAL.BA, AAPL.BA, BTC-USD, AL30.BA)")
    name: str = Field(..., max_length=120, description="Nombre descriptivo del instrumento")
    asset_class: AssetClass = Field(..., description="Tipo de activo (EQUITY_LOCAL, CEDEAR, SOVEREIGN_BOND, CRYPTO_SPOT, CRYPTO_FUTURES)")
    currency: Currency = Field(..., description="Moneda de cotización principal (ARS o USD)")
    
    # CEDEARs
    cedear_ratio: Optional[Decimal] = Field(None, description="Ratio de conversión (ej: 10 para 10:1 AAPL)")
    underlying_ticker: Optional[str] = Field(None, max_length=30, description="Ticker subyacente en NYSE/NASDAQ (ej: AAPL)")
    
    # Bonos
    bond_face_value: Optional[Decimal] = Field(None, description="Valor nominal de emisión (ej: 100)")
    bond_maturity_date: Optional[date] = Field(None, description="Fecha de vencimiento")
    
    is_active: bool = True
    notes: Optional[str] = None

class AssetCreate(AssetBase):
    pass

class AssetUpdate(BaseModel):
    name: Optional[str] = None
    is_active: Optional[bool] = None
    cedear_ratio: Optional[Decimal] = None
    notes: Optional[str] = None

class AssetResponse(AssetBase):
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
