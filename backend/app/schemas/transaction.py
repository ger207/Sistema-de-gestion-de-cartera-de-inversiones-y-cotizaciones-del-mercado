from decimal import Decimal
from typing import Optional
from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field
from app.models.enums import TransactionType, Currency, FxRateType

class TransactionBase(BaseModel):
    account_id: int = Field(..., description="ID de la cuenta/broker de custodia")
    asset_id: int = Field(..., description="ID del activo operado")
    transaction_type: TransactionType = Field(..., description="BUY, SELL, DIVIDEND, COUPON, etc.")
    executed_at: datetime = Field(..., description="Fecha y hora de ejecución del trade")
    settlement_date: Optional[datetime] = Field(None, description="Fecha de liquidación efectiva")
    quantity: Decimal = Field(..., gt=0, description="Cantidad operada con alta precisión")
    price: Decimal = Field(..., ge=0, description="Precio unitario en la moneda original")
    currency: Currency = Field(..., description="Moneda del trade (ARS, USD, USDT)")
    fee: Decimal = Field(default=Decimal("0.0"), ge=0, description="Comisiones o aranceles")
    fee_currency: Optional[Currency] = None
    fx_rate: Optional[Decimal] = Field(None, gt=0, description="Tipo de cambio (CCL/MEP) al momento de ejecución")
    fx_rate_type: Optional[FxRateType] = None
    notes: Optional[str] = None

class TransactionCreate(TransactionBase):
    pass

class TransactionResponse(TransactionBase):
    id: int
    gross_amount: Decimal
    net_amount: Decimal
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
