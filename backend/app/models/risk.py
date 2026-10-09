from decimal import Decimal
from typing import Optional
from datetime import datetime
from sqlalchemy import String, Numeric, DateTime, ForeignKey, Boolean, Enum as SQLEnum, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin
from app.models.enums import PositionDirection, MarginType

class CryptoFuturesPosition(Base, TimestampMixin):
    """
    Control de posiciones y parámetros de riesgo en contratos de futuros/perpetuos cripto.
    Permite monitorear margen, apalancamiento, precio de liquidación y niveles de Stop-Loss.
    """
    __tablename__ = "crypto_futures_positions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False, index=True)
    asset_id: Mapped[int] = mapped_column(ForeignKey("assets.id", ondelete="RESTRICT"), nullable=False, index=True)
    
    direction: Mapped[PositionDirection] = mapped_column(
        SQLEnum(PositionDirection, native_enum=False),
        nullable=False
    )
    margin_type: Mapped[MarginType] = mapped_column(
        SQLEnum(MarginType, native_enum=False),
        default=MarginType.ISOLATED,
        nullable=False
    )
    
    # Apalancamiento configurado (ej: 5 para 5x, 10 para 10x)
    leverage: Mapped[int] = mapped_column(nullable=False, default=1)
    
    # Tamaño de la posición en unidades del activo subyacente (ej: 0.5 BTC)
    position_size: Mapped[Decimal] = mapped_column(Numeric(24, 8), nullable=False)
    
    # Precio promedio de entrada
    entry_price: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    
    # Margen inicial / Colateral aportado (habitualmente en USDT o USD)
    initial_margin: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    
    # Tasa de margen de mantenimiento del exchange (ej: 0.005 para 0.5%)
    maintenance_margin_rate: Mapped[Decimal] = mapped_column(
        Numeric(8, 4),
        default=Decimal("0.005"),
        nullable=False
    )
    
    # Precio de liquidación estimado o provisto por el exchange
    liquidation_price: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    
    # Parámetros de mitigación de riesgo (Take-Profit / Stop-Loss)
    stop_loss_price: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 4), nullable=True)
    take_profit_price: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 4), nullable=True)

    is_open: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    opened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    closed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    
    # PnL realizado al momento del cierre (en USD/USDT)
    realized_pnl: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 4), nullable=True)
    
    notes: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Relaciones
    account: Mapped["Account"] = relationship("Account", back_populates="futures_positions")
    asset: Mapped["Asset"] = relationship("Asset", back_populates="futures_positions")

    @property
    def notional_value(self) -> Decimal:
        """Valor nocional total de la posición (position_size * entry_price)."""
        return self.position_size * self.entry_price

    def calculate_unrealized_pnl(self, current_price: Decimal) -> Decimal:
        """Calcula el PnL no realizado dado el precio actual de mercado."""
        if self.direction == PositionDirection.LONG:
            return (current_price - self.entry_price) * self.position_size
        else:
            return (self.entry_price - current_price) * self.position_size

    def distance_to_liquidation_pct(self, current_price: Decimal) -> Decimal:
        """Distancia porcentual al precio de liquidación (buffer de seguridad)."""
        if current_price == Decimal("0"):
            return Decimal("0")
        diff = abs(current_price - self.liquidation_price)
        return (diff / current_price) * Decimal("100")


class PortfolioRiskSnapshot(Base, TimestampMixin):
    """
    Fotografía histórica periódica del perfil de riesgo de la cartera global.
    Permite auditar el VaR (Value at Risk), apalancamiento consolidado y exposición cambiaria.
    """
    __tablename__ = "portfolio_risk_snapshots"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    portfolio_id: Mapped[int] = mapped_column(ForeignKey("portfolios.id", ondelete="CASCADE"), nullable=False, index=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)

    # Valuación neta consolidada (Equity)
    total_equity_usd: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    total_equity_ars: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    
    # Tipo de cambio CCL/MEP utilizado para la conversión
    fx_rate_used: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    
    # Métricas de riesgo de mercado
    ars_exposure_ratio: Mapped[Decimal] = mapped_column(Numeric(8, 4), nullable=False) # % de cartera en activos ARS
    crypto_notional_usd: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("0.0"), nullable=False)
    leverage_ratio: Mapped[Decimal] = mapped_column(Numeric(8, 4), default=Decimal("1.0"), nullable=False)
    
    # Value at Risk 95% diario estimado (en USD)
    var_95_daily_usd: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 4), nullable=True)

    __table_args__ = (
        Index("idx_risk_snapshot_portfolio_time", "portfolio_id", "timestamp"),
    )
