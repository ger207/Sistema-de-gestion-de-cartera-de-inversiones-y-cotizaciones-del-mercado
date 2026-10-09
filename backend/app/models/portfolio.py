from typing import List, Optional
from sqlalchemy import String, ForeignKey, Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin
from app.models.enums import Currency, AccountType

class Portfolio(Base, TimestampMixin):
    """
    Cartera global del inversor. Puede contener múltiples cuentas (brokers, exchanges).
    Permite consolidar la posición y evaluar el rendimiento bimonetario global.
    """
    __tablename__ = "portfolios"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    
    # Moneda dura para aislar la inflación/devaluación (USD por defecto)
    base_currency: Mapped[Currency] = mapped_column(
        SQLEnum(Currency, native_enum=False),
        default=Currency.USD,
        nullable=False
    )
    # Moneda local de comparación (ARS por defecto)
    secondary_currency: Mapped[Currency] = mapped_column(
        SQLEnum(Currency, native_enum=False),
        default=Currency.ARS,
        nullable=False
    )

    # Relaciones
    accounts: Mapped[List["Account"]] = relationship(
        "Account", back_populates="portfolio", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Portfolio(id={self.id}, name='{self.name}', base='{self.base_currency}')>"


class Account(Base, TimestampMixin):
    """
    Cuenta específica de custodia / ejecución (ej. Broker IOL, Balanz, Binance, Bybit).
    """
    __tablename__ = "accounts"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    portfolio_id: Mapped[int] = mapped_column(ForeignKey("portfolios.id", ondelete="CASCADE"), nullable=False)
    
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    account_type: Mapped[AccountType] = mapped_column(
        SQLEnum(AccountType, native_enum=False),
        nullable=False
    )

    # Relaciones
    portfolio: Mapped["Portfolio"] = relationship("Portfolio", back_populates="accounts")
    transactions: Mapped[List["Transaction"]] = relationship(
        "Transaction", back_populates="account", cascade="all, delete-orphan"
    )
    futures_positions: Mapped[List["CryptoFuturesPosition"]] = relationship(
        "CryptoFuturesPosition", back_populates="account", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Account(id={self.id}, name='{self.name}', type='{self.account_type}')>"
