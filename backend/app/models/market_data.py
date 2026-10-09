from decimal import Decimal
from typing import Optional
from datetime import datetime
from sqlalchemy import String, Numeric, DateTime, ForeignKey, Enum as SQLEnum, UniqueConstraint, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin
from app.models.enums import FxRateType

class AssetPrice(Base, TimestampMixin):
    """
    Historial de precios de mercado (OHLCV) para valuación Mark-to-Market (MTM).
    Ingestados automáticamente mediante yfinance u otras fuentes.
    """
    __tablename__ = "asset_prices"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    asset_id: Mapped[int] = mapped_column(ForeignKey("assets.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Momento o fecha de cierre de la cotización
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    
    open_price: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 4), nullable=True)
    high_price: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 4), nullable=True)
    low_price: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 4), nullable=True)
    close_price: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    adj_close_price: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 4), nullable=True)
    volume: Mapped[Optional[Decimal]] = mapped_column(Numeric(24, 4), nullable=True)
    
    source: Mapped[str] = mapped_column(String(50), default="YFINANCE", nullable=False)

    # Relación
    asset: Mapped["Asset"] = relationship("Asset", back_populates="prices")

    __table_args__ = (
        UniqueConstraint("asset_id", "timestamp", name="uq_asset_price_timestamp"),
        Index("idx_asset_price_lookup", "asset_id", "timestamp"),
    )

    def __repr__(self) -> str:
        return f"<AssetPrice(asset_id={self.asset_id}, date={self.timestamp}, close={self.close_price})>"


class ExchangeRate(Base, TimestampMixin):
    """
    Historial de cotizaciones de tipos de cambio financieros (MEP, CCL, Oficial, Blue).
    Clave para normalizar la cartera a moneda dura (USD) y aislar la devaluación del ARS.
    """
    __tablename__ = "exchange_rates"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    
    rate_type: Mapped[FxRateType] = mapped_column(
        SQLEnum(FxRateType, native_enum=False),
        nullable=False,
        index=True
    )
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    
    buy_price: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 4), nullable=True)
    sell_price: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False) # Cotización de referencia / venta
    
    source: Mapped[str] = mapped_column(String(50), default="DOLAR_API", nullable=False)

    __table_args__ = (
        UniqueConstraint("rate_type", "timestamp", name="uq_fx_rate_timestamp"),
        Index("idx_fx_rate_lookup", "rate_type", "timestamp"),
    )

    def __repr__(self) -> str:
        return f"<ExchangeRate(type='{self.rate_type}', date={self.timestamp}, sell={self.sell_price})>"
