from decimal import Decimal
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models.enums import TransactionType, Currency, FxRateType, AssetClass
from app.models.portfolio import Portfolio, Account
from app.models.asset import Asset
from app.models.transaction import Transaction
from app.models.market_data import AssetPrice, ExchangeRate
from app.services.market_data_service import MarketDataService

class PortfolioService:
    """
    Motor contable y de valuación bimonetaria.
    Calcula:
    1. Posición actual (Holdings) y Precio Promedio Ponderado (PPP) de compra.
    2. Valuación Mark-to-Market (MTM) bimonetaria simultánea (USD y ARS).
    3. PnL Nominal (en ARS) vs PnL Real en moneda dura (en USD), aislando el efecto devaluatorio.
    """

    @classmethod
    def calculate_holdings(cls, db: Session, portfolio_id: int) -> List[Dict[str, Any]]:
        """
        Recorre el libro contable de transacciones y genera las tenencias consolidadas
        con su respectivo costo base ponderado (PPP) tanto en ARS como en USD.
        """
        # Obtener todas las cuentas del portafolio
        account_ids = [acc.id for acc in db.query(Account.id).filter(Account.portfolio_id == portfolio_id).all()]
        if not account_ids:
            return []

        # Obtener todas las transacciones ordenadas cronológicamente
        txs = (
            db.query(Transaction)
            .filter(Transaction.account_id.in_(account_ids))
            .order_by(Transaction.executed_at.asc())
            .all()
        )

        # Estructura de consolidación por activo
        # asset_id -> {qty, total_cost_ars, total_cost_usd}
        holdings_map: Dict[int, Dict[str, Any]] = {}

        for tx in txs:
            asset_id = tx.asset_id
            if asset_id not in holdings_map:
                holdings_map[asset_id] = {
                    "asset": tx.asset,
                    "quantity": Decimal("0.0"),
                    "total_cost_ars": Decimal("0.0"),
                    "total_cost_usd": Decimal("0.0"),
                }

            h = holdings_map[asset_id]
            
            # Determinamos costo de esta transacción en ambas monedas usando el fx_rate del momento
            fx = tx.fx_rate if tx.fx_rate and tx.fx_rate > 0 else Decimal("1.0")

            if tx.currency == Currency.ARS:
                cost_ars = tx.net_amount
                cost_usd = (tx.net_amount / fx) if fx > 0 else Decimal("0.0")
            else: # USD / USDT
                cost_usd = tx.net_amount
                cost_ars = tx.net_amount * fx

            if tx.transaction_type == TransactionType.BUY:
                h["quantity"] += tx.quantity
                h["total_cost_ars"] += cost_ars
                h["total_cost_usd"] += cost_usd

            elif tx.transaction_type == TransactionType.SELL:
                if h["quantity"] > 0:
                    # Reducción proporcional del costo base (PPP)
                    sell_ratio = min(tx.quantity / h["quantity"], Decimal("1.0"))
                    h["total_cost_ars"] -= h["total_cost_ars"] * sell_ratio
                    h["total_cost_usd"] -= h["total_cost_usd"] * sell_ratio
                    h["quantity"] -= tx.quantity

        # Filtrar activos con tenencia remanente positiva (> 0)
        active_holdings = [h for h in holdings_map.values() if h["quantity"] > Decimal("0.00000001")]
        return active_holdings

    @classmethod
    def get_portfolio_valuation(
        cls, 
        db: Session, 
        portfolio_id: int, 
        fx_type: FxRateType = FxRateType.CCL
    ) -> Dict[str, Any]:
        """
        Valuación integral de la cartera a precios de mercado actuales (MTM).
        Descompone la rentabilidad en:
        - Rendimiento Nominal en ARS (afectado por inflación y devaluación).
        - Rendimiento Real en USD (aislando la devaluación mediante el tipo de cambio financiero seleccionado).
        """
        current_fx_rate = MarketDataService.get_latest_fx_rate(db, fx_type) or Decimal("1200.0")
        raw_holdings = cls.calculate_holdings(db, portfolio_id)

        holdings_summary = []
        total_value_usd = Decimal("0.0")
        total_cost_usd = Decimal("0.0")
        total_value_ars = Decimal("0.0")
        total_cost_ars = Decimal("0.0")

        for h in raw_holdings:
            asset: Asset = h["asset"]
            qty = h["quantity"]
            cost_ars = h["total_cost_ars"]
            cost_usd = h["total_cost_usd"]

            # Obtener último precio registrado del activo
            latest_price_obj = (
                db.query(AssetPrice)
                .filter(AssetPrice.asset_id == asset.id)
                .order_by(AssetPrice.timestamp.desc())
                .first()
            )
            unit_price = latest_price_obj.close_price if latest_price_obj else Decimal("0.0")

            # Valuación MTM según moneda de cotización del activo
            if asset.currency == Currency.ARS:
                # Activo cotiza en ARS (ej: GGAL.BA, CEDEAR AAPL.BA)
                current_market_ars = qty * unit_price
                current_market_usd = current_market_ars / current_fx_rate if current_fx_rate > 0 else Decimal("0.0")
            else:
                # Activo cotiza en USD o Cripto (ej: BTC-USD)
                current_market_usd = qty * unit_price
                current_market_ars = current_market_usd * current_fx_rate

            # Rendimientos
            pnl_ars = current_market_ars - cost_ars
            pnl_usd = current_market_usd - cost_usd

            pnl_pct_ars = (pnl_ars / cost_ars * Decimal("100")) if cost_ars > 0 else Decimal("0.0")
            pnl_pct_usd = (pnl_usd / cost_usd * Decimal("100")) if cost_usd > 0 else Decimal("0.0")

            holdings_summary.append({
                "asset_id": asset.id,
                "ticker": asset.ticker,
                "name": asset.name,
                "asset_class": asset.asset_class.value if hasattr(asset.asset_class, "value") else str(asset.asset_class),
                "quantity": float(qty),
                "latest_unit_price": float(unit_price),
                "quote_currency": asset.currency.value if hasattr(asset.currency, "value") else str(asset.currency),
                
                # Métricas en Moneda Dura (USD) - RENDIMIENTO REAL
                "cost_basis_usd": float(round(cost_usd, 2)),
                "current_value_usd": float(round(current_market_usd, 2)),
                "unrealized_pnl_usd": float(round(pnl_usd, 2)),
                "pnl_pct_usd": float(round(pnl_pct_usd, 2)),

                # Métricas en Pesos (ARS) - VALOR NOMINAL
                "cost_basis_ars": float(round(cost_ars, 2)),
                "current_value_ars": float(round(current_market_ars, 2)),
                "unrealized_pnl_ars": float(round(pnl_ars, 2)),
                "pnl_pct_ars": float(round(pnl_pct_ars, 2)),
            })

            total_value_usd += current_market_usd
            total_cost_usd += cost_usd
            total_value_ars += current_market_ars
            total_cost_ars += cost_ars

        total_pnl_usd = total_value_usd - total_cost_usd
        total_pnl_ars = total_value_ars - total_cost_ars
        total_pnl_pct_usd = (total_pnl_usd / total_cost_usd * Decimal("100")) if total_cost_usd > 0 else Decimal("0.0")
        total_pnl_pct_ars = (total_pnl_ars / total_cost_ars * Decimal("100")) if total_cost_ars > 0 else Decimal("0.0")

        return {
            "portfolio_id": portfolio_id,
            "valuation_fx_type": fx_type.value if hasattr(fx_type, "value") else str(fx_type),
            "fx_rate_applied": float(current_fx_rate),
            "total_value_usd": float(round(total_value_usd, 2)),
            "total_cost_usd": float(round(total_cost_usd, 2)),
            "total_pnl_usd": float(round(total_pnl_usd, 2)),
            "total_pnl_pct_usd": float(round(total_pnl_pct_usd, 2)),
            "total_value_ars": float(round(total_value_ars, 2)),
            "total_cost_ars": float(round(total_cost_ars, 2)),
            "total_pnl_ars": float(round(total_pnl_ars, 2)),
            "total_pnl_pct_ars": float(round(total_pnl_pct_ars, 2)),
            "holdings": holdings_summary,
            "calculated_at": datetime.now(timezone.utc).isoformat(),
        }
