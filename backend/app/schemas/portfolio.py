from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field
from app.models.enums import Currency, AccountType

class AccountBase(BaseModel):
    name: str = Field(..., max_length=100, description="Nombre de la cuenta/broker (ej: IOL, Balanz, Binance)")
    account_type: AccountType = Field(..., description="BROKER_LOCAL, BROKER_INTL, CRYPTO_EXCHANGE, etc.")

class AccountCreate(AccountBase):
    portfolio_id: int

class AccountResponse(AccountBase):
    id: int
    portfolio_id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

class PortfolioBase(BaseModel):
    name: str = Field(..., max_length=100, description="Nombre de la cartera (ej: Cartera Principal)")
    description: Optional[str] = None
    base_currency: Currency = Field(default=Currency.USD, description="Moneda dura de referencia")
    secondary_currency: Currency = Field(default=Currency.ARS, description="Moneda local")

class PortfolioCreate(PortfolioBase):
    pass

class PortfolioResponse(PortfolioBase):
    id: int
    accounts: List[AccountResponse] = []
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
