from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.transaction import Transaction
from app.models.asset import Asset
from app.models.portfolio import Account
from app.schemas.transaction import TransactionCreate, TransactionResponse

router = APIRouter()

@router.get("/", response_model=List[TransactionResponse], summary="Listar transacciones registradas")
def list_transactions(account_id: int = None, skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    query = db.query(Transaction)
    if account_id:
        query = query.filter(Transaction.account_id == account_id)
    return query.order_by(Transaction.executed_at.desc()).offset(skip).limit(limit).all()

@router.post("/", response_model=TransactionResponse, status_code=status.HTTP_201_CREATED, summary="Registrar nueva transacción (Ledger)")
def create_transaction(tx_in: TransactionCreate, db: Session = Depends(get_db)):
    # Validar existencia de cuenta y activo
    account = db.query(Account).filter(Account.id == tx_in.account_id).first()
    if not account:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cuenta/broker no encontrada")
    
    asset = db.query(Asset).filter(Asset.id == tx_in.asset_id).first()
    if not asset:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Activo no encontrado")

    tx = Transaction(**tx_in.model_dump())
    db.add(tx)
    db.commit()
    db.refresh(tx)
    return tx
