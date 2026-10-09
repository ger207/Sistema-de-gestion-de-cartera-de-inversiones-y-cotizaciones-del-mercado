from decimal import Decimal
from typing import Optional
from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field
from app.models.enums import PositionDirection, MarginType

class CryptoFuturesPositionBase(BaseModel):
    account_id: int
    asset_id: int
    direction: PositionDirection = Field(..., description="LONG o SHORT")
    margin_type: MarginType = Field(default=MarginType.ISOLATED, description="ISOLATED o CROSS")
    leverage: int = Field(default=1, ge=1, le=125, description="Nivel de apalancamiento (1x a 125x)")
    position_size: Decimal = Field(..., gt=0, description="Tamaño de la posición en unidades del subyacente")
    entry_price: Decimal = Field(..., gt=0, description="Precio promedio de entrada")
    initial_margin: Decimal = Field(..., gt=0, description="Margen inicial aportado")
    maintenance_margin_rate: Decimal = Field(default=Decimal("0.005"), description="Tasa de margen de mantenimiento")
    liquidation_price: Decimal = Field(..., gt=0, description="Precio de liquidación estimado")
    stop_loss_price: Optional[Decimal] = None
    take_profit_price: Optional[Decimal] = None
    opened_at: datetime
    notes: Optional[str] = None

class CryptoFuturesPositionCreate(CryptoFuturesPositionBase):
    pass

class CryptoFuturesPositionResponse(CryptoFuturesPositionBase):
    id: int
    is_open: bool
    closed_at: Optional[datetime] = None
    realized_pnl: Optional[Decimal] = None
    notional_value: Decimal
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

class PortfolioRiskMetricsResponse(BaseModel):
    portfolio_id: int
    total_equity_usd: Decimal
    total_equity_ars: Decimal
    fx_rate_used: Decimal
    fx_rate_type: str
    ars_exposure_ratio: Decimal
    crypto_notional_usd: Decimal
    leverage_ratio: Decimal
    var_95_daily_usd: Optional[Decimal] = None
    calculated_at: datetime
