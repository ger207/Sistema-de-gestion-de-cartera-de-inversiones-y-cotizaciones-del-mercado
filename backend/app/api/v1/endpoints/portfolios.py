from typing import List, Any, Dict
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.portfolio import Portfolio, Account
from app.models.enums import FxRateType
from app.schemas.portfolio import PortfolioCreate, PortfolioResponse, AccountCreate, AccountResponse
from app.services.portfolio_service import PortfolioService

router = APIRouter()

@router.get("/", response_model=List[PortfolioResponse], summary="Listar carteras de inversión")
def list_portfolios(db: Session = Depends(get_db)):
    return db.query(Portfolio).all()

@router.post("/", response_model=PortfolioResponse, status_code=status.HTTP_201_CREATED, summary="Crear una cartera")
def create_portfolio(portfolio_in: PortfolioCreate, db: Session = Depends(get_db)):
    portfolio = Portfolio(**portfolio_in.model_dump())
    db.add(portfolio)
    db.commit()
    db.refresh(portfolio)
    return portfolio

@router.post("/accounts", response_model=AccountResponse, status_code=status.HTTP_201_CREATED, summary="Crear cuenta/broker dentro de una cartera")
def create_account(account_in: AccountCreate, db: Session = Depends(get_db)):
    portfolio = db.query(Portfolio).filter(Portfolio.id == account_in.portfolio_id).first()
    if not portfolio:
        raise HTTPException(status_code=404, detail="Cartera no encontrada")
    
    account = Account(**account_in.model_dump())
    db.add(account)
    db.commit()
    db.refresh(account)
    return account

@router.get("/{portfolio_id}/valuation", summary="Valuación bimonetaria MTM de la cartera")
def get_valuation(
    portfolio_id: int,
    fx_type: FxRateType = Query(FxRateType.CCL, description="Tipo de cambio financiero para la conversión (CCL o MEP)"),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Retorna la posición de tenencias, valuación MTM simultánea (USD y ARS), y descompone
    el rendimiento nominal (en ARS) del rendimiento real en moneda dura (en USD),
    aislando el efecto de la devaluación.
    """
    portfolio = db.query(Portfolio).filter(Portfolio.id == portfolio_id).first()
    if not portfolio:
        raise HTTPException(status_code=404, detail="Cartera no encontrada")

    return PortfolioService.get_portfolio_valuation(db, portfolio_id, fx_type=fx_type)
