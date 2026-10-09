from decimal import Decimal
from typing import Optional
from datetime import datetime
from sqlalchemy import String, Numeric, DateTime, ForeignKey, Enum as SQLEnum, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin
from app.models.enums import TransactionType, Currency, FxRateType

class Transaction(Base, TimestampMixin):
    """
    Libro de registro (Ledger) de movimientos financieros.
    Cada registro es inmutable para asegurar trazabilidad contable y cálculo de costo base (PPP / FIFO).
    Guarda el tipo de cambio (FX) al momento exacto de la operación para reconciliación bimonetaria.
    """
    __tablename__ = "transactions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False, index=True)
    asset_id: Mapped[int] = mapped_column(ForeignKey("assets.id", ondelete="RESTRICT"), nullable=False, index=True)
    
    transaction_type: Mapped[TransactionType] = mapped_column(
        SQLEnum(TransactionType, native_enum=False),
        nullable=False,
        index=True
    )
    
    # Fecha/hora de concertación del trade
    executed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    # Fecha de liquidación (T+0, T+1, T+2 para bonos y acciones)
    settlement_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Cantidad: Alta precisión (24, 8) para fracciones de cripto (Satoshis) y nominales de bonos
    quantity: Mapped[Decimal] = mapped_column(Numeric(24, 8), nullable=False)
    
    # Precio unitario en la moneda original de la transacción
    price: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    
    # Moneda en la que se pactó y liquidó la operación (ARS, USD, USDT)
    currency: Mapped[Currency] = mapped_column(
        SQLEnum(Currency, native_enum=False),
        nullable=False
    )
    
    # Comisiones / Aranceles de broker / Gas / Funding
    fee: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("0.0"), nullable=False)
    fee_currency: Mapped[Optional[Currency]] = mapped_column(
        SQLEnum(Currency, native_enum=False),
        nullable=True
    )

    # Reconciliación Bimonetaria Inmediata:
    # Tipo de cambio (FX) implícito o explícito a la fecha del trade (ej. CCL o MEP)
    # Permite saber inmediatamente: "¿Cuántos USD costó realmente esta compra hecha en ARS?"
    fx_rate: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 4), nullable=True)
    fx_rate_type: Mapped[Optional[FxRateType]] = mapped_column(
        SQLEnum(FxRateType, native_enum=False),
        nullable=True
    )

    notes: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Relaciones
    account: Mapped["Account"] = relationship("Account", back_populates="transactions")
    asset: Mapped["Asset"] = relationship("Asset", back_populates="transactions")

    __table_args__ = (
        Index("idx_transactions_account_executed", "account_id", "executed_at"),
        Index("idx_transactions_asset_executed", "asset_id", "executed_at"),
    )

    @property
    def gross_amount(self) -> Decimal:
        """Monto bruto sin comisiones en la moneda de transacción."""
        return self.quantity * self.price

    @property
    def net_amount(self) -> Decimal:
        """Monto neto liquidado en la moneda de transacción."""
        if self.transaction_type in (TransactionType.BUY, TransactionType.WITHDRAWAL, TransactionType.FEE):
            return self.gross_amount + self.fee
        return self.gross_amount - self.fee

    def __repr__(self) -> str:
        return (
            f"<Transaction(id={self.id}, type='{self.transaction_type}', "
            f"asset_id={self.asset_id}, qty={self.quantity}, price={self.price} {self.currency})>"
        )
