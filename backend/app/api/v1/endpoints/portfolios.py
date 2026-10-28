from typing import List, Any, Dict
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.portfolio import Portfolio, Account
from app.models.risk import PortfolioRiskSnapshot, CryptoFuturesPosition
from app.models.enums import FxRateType, AccountType
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

    # Crear cuenta de custodia por defecto automáticamente para habilitar operaciones inmediatas
    default_acc = Account(
        portfolio_id=portfolio.id,
        name="Cuenta Principal",
        account_type=AccountType.BROKER_LOCAL
    )
    db.add(default_acc)
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

@router.delete("/{portfolio_id}", status_code=status.HTTP_200_OK, summary="Eliminar una cartera")
def delete_portfolio(portfolio_id: int, db: Session = Depends(get_db)):
    """
    Elimina permanentemente una cartera y todas sus cuentas, transacciones
    y registros de riesgo asociados de forma segura.
    """
    portfolio = db.query(Portfolio).filter(Portfolio.id == portfolio_id).first()
    if not portfolio:
        raise HTTPException(status_code=404, detail="Cartera no encontrada")

    portfolio_name = portfolio.name

    # 1. Eliminar snapshots de riesgo asociados a esta cartera
    db.query(PortfolioRiskSnapshot).filter(PortfolioRiskSnapshot.portfolio_id == portfolio_id).delete(synchronize_session=False)

    # 2. Eliminar posiciones de futuros asociadas a las cuentas de la cartera
    account_ids = [acc.id for acc in portfolio.accounts]
    if account_ids:
        db.query(CryptoFuturesPosition).filter(CryptoFuturesPosition.account_id.in_(account_ids)).delete(synchronize_session=False)

    # 3. Eliminar la cartera (con cascade="all, delete-orphan", SQLAlchemy elimina cuentas y transacciones)
    db.delete(portfolio)
    db.commit()

    return {"message": f"Cartera '{portfolio_name}' eliminada con éxito", "id": portfolio_id}
