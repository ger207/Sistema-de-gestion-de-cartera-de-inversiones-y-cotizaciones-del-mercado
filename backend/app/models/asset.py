from decimal import Decimal
from typing import Optional, List
from datetime import date
from sqlalchemy import String, Numeric, Boolean, Date, Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin
from app.models.enums import AssetClass, Currency

class Asset(Base, TimestampMixin):
    """
    Catálogo centralizado de activos financieros e instrumentos.
    Soporta: Acciones Merval, CEDEARs, Bonos Soberanos, Cripto Spot y Contratos Derivados.
    """
    __tablename__ = "assets"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    
    # Símbolo con el que se consulta en Yahoo Finance u otra fuente (ej: GGAL.BA, AAPL.BA, BTC-USD, AL30.BA)
    ticker: Mapped[str] = mapped_column(String(30), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    
    asset_class: Mapped[AssetClass] = mapped_column(
        SQLEnum(AssetClass, native_enum=False),
        index=True,
        nullable=False
    )
    
    # Moneda de cotización/operación por defecto
    currency: Mapped[Currency] = mapped_column(
        SQLEnum(Currency, native_enum=False),
        nullable=False
    )
    
    # Atributos específicos para CEDEARs
    # cedear_ratio: Cantidad de CEDEARs equivalentes a 1 acción subyacente (ej: 10.0 para AAPL, 20.0 para SPY)
    cedear_ratio: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 4), nullable=True)
    underlying_ticker: Mapped[Optional[str]] = mapped_column(String(30), nullable=True) # ej: AAPL, SPY
    
    # Atributos específicos para Bonos Soberanos / Renta Fija
    bond_face_value: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 4), nullable=True) # Valor nominal base (ej: 100)
    bond_maturity_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)           # Fecha de vencimiento
    
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Relaciones
    transactions: Mapped[List["Transaction"]] = relationship(
        "Transaction", back_populates="asset", cascade="all, delete-orphan"
    )
    prices: Mapped[List["AssetPrice"]] = relationship(
        "AssetPrice", back_populates="asset", cascade="all, delete-orphan"
    )
    futures_positions: Mapped[List["CryptoFuturesPosition"]] = relationship(
        "CryptoFuturesPosition", back_populates="asset"
    )

    def __repr__(self) -> str:
        return f"<Asset(ticker='{self.ticker}', class='{self.asset_class}', currency='{self.currency}')>"
