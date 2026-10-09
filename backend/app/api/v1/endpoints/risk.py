from decimal import Decimal
from typing import List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.risk import CryptoFuturesPosition
from app.models.portfolio import Account
from app.models.asset import Asset
from app.models.market_data import AssetPrice
from app.schemas.risk import CryptoFuturesPositionCreate, CryptoFuturesPositionResponse

router = APIRouter()

@router.get("/futures", response_model=List[CryptoFuturesPositionResponse], summary="Listar posiciones de futuros cripto")
def list_futures_positions(account_id: int = None, is_open: bool = True, db: Session = Depends(get_db)):
    query = db.query(CryptoFuturesPosition).filter(CryptoFuturesPosition.is_open == is_open)
    if account_id:
        query = query.filter(CryptoFuturesPosition.account_id == account_id)
    return query.all()

@router.post("/futures", response_model=CryptoFuturesPositionResponse, status_code=status.HTTP_201_CREATED, summary="Registrar posición/parámetros de futuros")
def create_futures_position(pos_in: CryptoFuturesPositionCreate, db: Session = Depends(get_db)):
    account = db.query(Account).filter(Account.id == pos_in.account_id).first()
    if not account:
        raise HTTPException(status_code=404, detail="Cuenta no encontrada")
    
    asset = db.query(Asset).filter(Asset.id == pos_in.asset_id).first()
    if not asset:
        raise HTTPException(status_code=404, detail="Activo cripto no encontrado")

    position = CryptoFuturesPosition(**pos_in.model_dump())
    db.add(position)
    db.commit()
    db.refresh(position)
    return position

@router.get("/futures/{position_id}/risk-status", summary="Monitorear riesgo de liquidación y margen en tiempo real")
def get_position_risk_status(position_id: int, db: Session = Depends(get_db)) -> Dict[str, Any]:
    pos = db.query(CryptoFuturesPosition).filter(CryptoFuturesPosition.id == position_id).first()
    if not pos:
        raise HTTPException(status_code=404, detail="Posición no encontrada")

    # Obtener último precio del activo subyacente
    latest_price_obj = (
        db.query(AssetPrice)
        .filter(AssetPrice.asset_id == pos.asset_id)
        .order_by(AssetPrice.timestamp.desc())
        .first()
    )
    current_price = latest_price_obj.close_price if latest_price_obj else pos.entry_price

    unrealized_pnl = pos.calculate_unrealized_pnl(current_price)
    distance_to_liq_pct = pos.distance_to_liquidation_pct(current_price)

    # Estado de alerta según buffer de liquidación
    risk_level = "LOW"
    if distance_to_liq_pct < Decimal("5.0"):
        risk_level = "CRITICAL_LIQUIDATION_RISK"
    elif distance_to_liq_pct < Decimal("15.0"):
        risk_level = "HIGH"
    elif distance_to_liq_pct < Decimal("30.0"):
        risk_level = "MODERATE"

    return {
        "position_id": pos.id,
        "ticker": pos.asset.ticker,
        "direction": pos.direction,
        "leverage": f"{pos.leverage}x",
        "entry_price": pos.entry_price,
        "current_price": current_price,
        "liquidation_price": pos.liquidation_price,
        "stop_loss_price": pos.stop_loss_price,
        "take_profit_price": pos.take_profit_price,
        "unrealized_pnl_usd": round(unrealized_pnl, 2),
        "distance_to_liquidation_pct": round(distance_to_liq_pct, 2),
        "risk_level": risk_level,
    }
