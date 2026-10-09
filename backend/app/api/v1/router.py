from fastapi import APIRouter
from app.api.v1.endpoints import (
    assets,
    transactions,
    market_data,
    portfolios,
    risk
)

api_router = APIRouter()

api_router.include_router(portfolios.router, prefix="/portfolios", tags=["Carteras & Cuentas"])
api_router.include_router(assets.router, prefix="/assets", tags=["Activos"])
api_router.include_router(transactions.router, prefix="/transactions", tags=["Transacciones / Ledger"])
api_router.include_router(market_data.router, prefix="/market-data", tags=["Datos de Mercado & FX"])
api_router.include_router(risk.router, prefix="/risk", tags=["Gestión de Riesgo & Futuros"])
