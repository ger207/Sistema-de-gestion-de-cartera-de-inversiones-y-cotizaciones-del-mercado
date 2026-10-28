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
    def calculate_positions_and_pnl(cls, db: Session, portfolio_id: int):
        """
        Recorre el libro contable de transacciones y genera:
        1. Tenencias activas abiertas con su costo base ponderado (PPP).
        2. Posiciones cerradas con su resultado realizado acumulado (Realized PnL).
        3. Resumen agregado de PnL realizado tanto en ARS como en USD.
        """
        account_ids = [acc.id for acc in db.query(Account.id).filter(Account.portfolio_id == portfolio_id).all()]
        if not account_ids:
            return [], [], {
                "realized_pnl_usd": Decimal("0.0"),
                "realized_pnl_ars": Decimal("0.0"),
                "realized_cost_usd": Decimal("0.0"),
                "realized_cost_ars": Decimal("0.0"),
            }

        # Obtener todas las transacciones ordenadas cronológicamente
        txs = (
            db.query(Transaction)
            .filter(Transaction.account_id.in_(account_ids))
            .order_by(Transaction.executed_at.asc())
            .all()
        )

        holdings_map: Dict[int, Dict[str, Any]] = {}
        total_realized_pnl_ars = Decimal("0.0")
        total_realized_pnl_usd = Decimal("0.0")
        total_realized_cost_ars = Decimal("0.0")
        total_realized_cost_usd = Decimal("0.0")

        for tx in txs:
            asset_id = tx.asset_id
            if asset_id not in holdings_map:
                holdings_map[asset_id] = {
                    "asset": tx.asset,
                    "quantity": Decimal("0.0"),
                    "total_cost_ars": Decimal("0.0"),
                    "total_cost_usd": Decimal("0.0"),
                    "realized_pnl_ars": Decimal("0.0"),
                    "realized_pnl_usd": Decimal("0.0"),
                    "realized_cost_ars": Decimal("0.0"),
                    "realized_cost_usd": Decimal("0.0"),
                }

            h = holdings_map[asset_id]
            fx = tx.fx_rate if tx.fx_rate and tx.fx_rate > 0 else Decimal("1.0")

            if tx.transaction_type == TransactionType.BUY:
                if tx.currency == Currency.ARS:
                    cost_ars = tx.net_amount
                    cost_usd = (tx.net_amount / fx) if fx > 0 else Decimal("0.0")
                else: # USD / USDT
                    cost_usd = tx.net_amount
                    cost_ars = tx.net_amount * fx

                h["quantity"] += tx.quantity
                h["total_cost_ars"] += cost_ars
                h["total_cost_usd"] += cost_usd

            elif tx.transaction_type == TransactionType.SELL:
                if tx.currency == Currency.ARS:
                    proceeds_ars = tx.net_amount
                    proceeds_usd = (tx.net_amount / fx) if fx > 0 else Decimal("0.0")
                else: # USD / USDT
                    proceeds_usd = tx.net_amount
                    proceeds_ars = tx.net_amount * fx

                if h["quantity"] > Decimal("0.0"):
                    # Reducción proporcional del costo base (PPP)
                    sell_ratio = min(tx.quantity / h["quantity"], Decimal("1.0"))
                    cost_sold_ars = h["total_cost_ars"] * sell_ratio
                    cost_sold_usd = h["total_cost_usd"] * sell_ratio

                    realized_gain_ars = proceeds_ars - cost_sold_ars
                    realized_gain_usd = proceeds_usd - cost_sold_usd

                    h["total_cost_ars"] -= cost_sold_ars
                    h["total_cost_usd"] -= cost_sold_usd
                    h["quantity"] -= tx.quantity

                    h["realized_pnl_ars"] += realized_gain_ars
                    h["realized_pnl_usd"] += realized_gain_usd
                    h["realized_cost_ars"] += cost_sold_ars
                    h["realized_cost_usd"] += cost_sold_usd

                    total_realized_pnl_ars += realized_gain_ars
                    total_realized_pnl_usd += realized_gain_usd
                    total_realized_cost_ars += cost_sold_ars
                    total_realized_cost_usd += cost_sold_usd
                else:
                    h["quantity"] -= tx.quantity

        # Filtrar activos con tenencia remanente positiva (> 0)
        active_holdings = [h for h in holdings_map.values() if h["quantity"] > Decimal("0.00000001")]
        # Posiciones totalmente cerradas que registraron ventas
        closed_holdings = [
            h for h in holdings_map.values() 
            if h["quantity"] <= Decimal("0.00000001") and (h["realized_cost_usd"] > 0 or h["realized_cost_ars"] > 0)
        ]

        summary_realized = {
            "realized_pnl_usd": total_realized_pnl_usd,
            "realized_pnl_ars": total_realized_pnl_ars,
            "realized_cost_usd": total_realized_cost_usd,
            "realized_cost_ars": total_realized_cost_ars,
        }

        return active_holdings, closed_holdings, summary_realized

    @classmethod
    def calculate_holdings(cls, db: Session, portfolio_id: int) -> List[Dict[str, Any]]:
        active_holdings, _, _ = cls.calculate_positions_and_pnl(db, portfolio_id)
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
        - Acumulación de Ganancias/Pérdidas Realizadas en ventas cerradas + Ganancias Latentes abiertas.
        """
        current_fx_rate = MarketDataService.get_latest_fx_rate(db, fx_type) or Decimal("1200.0")
        active_holdings, closed_holdings, realized_summary = cls.calculate_positions_and_pnl(db, portfolio_id)

        holdings_summary = []
        open_value_usd = Decimal("0.0")
        open_cost_usd = Decimal("0.0")
        open_value_ars = Decimal("0.0")
        open_cost_ars = Decimal("0.0")

        for h in active_holdings:
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

            avg_price_usd = (cost_usd / qty) if qty > 0 else Decimal("0.0")
            avg_price_ars = (cost_ars / qty) if qty > 0 else Decimal("0.0")

            holdings_summary.append({
                "asset_id": asset.id,
                "ticker": asset.ticker,
                "name": asset.name,
                "asset_class": asset.asset_class.value if hasattr(asset.asset_class, "value") else str(asset.asset_class),
                "quantity": float(qty),
                "latest_unit_price": float(unit_price),
                "quote_currency": asset.currency.value if hasattr(asset.currency, "value") else str(asset.currency),
                
                # Precio Promedio de Compra (PPP) Bimonetario
                "avg_buy_price_usd": float(round(avg_price_usd, 2)),
                "avg_buy_price_ars": float(round(avg_price_ars, 2)),

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

            open_value_usd += current_market_usd
            open_cost_usd += cost_usd
            open_value_ars += current_market_ars
            open_cost_ars += cost_ars

        # Detalle de posiciones cerradas con ganancias realizadas
        closed_summary = []
        for ch in closed_holdings:
            asset: Asset = ch["asset"]
            c_cost_usd = ch["realized_cost_usd"]
            c_pnl_usd = ch["realized_pnl_usd"]
            c_cost_ars = ch["realized_cost_ars"]
            c_pnl_ars = ch["realized_pnl_ars"]

            c_pct_usd = (c_pnl_usd / c_cost_usd * Decimal("100")) if c_cost_usd > 0 else Decimal("0.0")
            c_pct_ars = (c_pnl_ars / c_cost_ars * Decimal("100")) if c_cost_ars > 0 else Decimal("0.0")

            closed_summary.append({
                "asset_id": asset.id,
                "ticker": asset.ticker,
                "name": asset.name,
                "asset_class": asset.asset_class.value if hasattr(asset.asset_class, "value") else str(asset.asset_class),
                "realized_cost_usd": float(round(c_cost_usd, 2)),
                "realized_pnl_usd": float(round(c_pnl_usd, 2)),
                "pnl_pct_usd": float(round(c_pct_usd, 2)),
                "realized_cost_ars": float(round(c_cost_ars, 2)),
                "realized_pnl_ars": float(round(c_pnl_ars, 2)),
                "pnl_pct_ars": float(round(c_pct_ars, 2)),
            })

        unrealized_pnl_usd = open_value_usd - open_cost_usd
        unrealized_pnl_ars = open_value_ars - open_cost_ars

        realized_pnl_usd = realized_summary["realized_pnl_usd"]
        realized_pnl_ars = realized_summary["realized_pnl_ars"]
        realized_cost_usd = realized_summary["realized_cost_usd"]
        realized_cost_ars = realized_summary["realized_cost_ars"]

        # Rendimiento Total = Ganancias/Pérdidas Realizadas en Ventas + Latentes en Tenencias Abiertas
        total_pnl_usd = unrealized_pnl_usd + realized_pnl_usd
        total_pnl_ars = unrealized_pnl_ars + realized_pnl_ars

        # Base de costo total invertida (posiciones abiertas + posiciones ya cerradas)
        total_invested_cost_usd = open_cost_usd + realized_cost_usd
        total_invested_cost_ars = open_cost_ars + realized_cost_ars

        total_pnl_pct_usd = (total_pnl_usd / total_invested_cost_usd * Decimal("100")) if total_invested_cost_usd > 0 else Decimal("0.0")
        total_pnl_pct_ars = (total_pnl_ars / total_invested_cost_ars * Decimal("100")) if total_invested_cost_ars > 0 else Decimal("0.0")

        return {
            "portfolio_id": portfolio_id,
            "valuation_fx_type": fx_type.value if hasattr(fx_type, "value") else str(fx_type),
            "fx_rate_applied": float(current_fx_rate),
            "total_value_usd": float(round(open_value_usd, 2)),
            "total_cost_usd": float(round(open_cost_usd, 2)),
            "total_invested_cost_usd": float(round(total_invested_cost_usd, 2)),
            "unrealized_pnl_usd": float(round(unrealized_pnl_usd, 2)),
            "realized_pnl_usd": float(round(realized_pnl_usd, 2)),
            "total_pnl_usd": float(round(total_pnl_usd, 2)),
            "total_pnl_pct_usd": float(round(total_pnl_pct_usd, 2)),
            "total_value_ars": float(round(open_value_ars, 2)),
            "total_cost_ars": float(round(open_cost_ars, 2)),
            "total_invested_cost_ars": float(round(total_invested_cost_ars, 2)),
            "unrealized_pnl_ars": float(round(unrealized_pnl_ars, 2)),
            "realized_pnl_ars": float(round(realized_pnl_ars, 2)),
            "total_pnl_ars": float(round(total_pnl_ars, 2)),
            "total_pnl_pct_ars": float(round(total_pnl_pct_ars, 2)),
            "holdings": holdings_summary,
            "closed_positions": closed_summary,
            "calculated_at": datetime.now(timezone.utc).isoformat(),
        }
