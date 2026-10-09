import sys
from pathlib import Path
from decimal import Decimal

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.database import SessionLocal
from app.models.enums import FxRateType
from app.models.portfolio import Portfolio
from app.models.risk import CryptoFuturesPosition
from app.services.portfolio_service import PortfolioService

def test_valuation():
    db = SessionLocal()
    try:
        portfolio = db.query(Portfolio).first()
        assert portfolio is not None, "No se encontro la cartera"

        print(f"\n--- VALUACION BIMONETARIA: {portfolio.name} ---")
        val = PortfolioService.get_portfolio_valuation(db, portfolio.id, fx_type=FxRateType.CCL)
        
        print(f"Tipo de cambio CCL aplicado: ${val['fx_rate_applied']} ARS/USD")
        print("\n[RESULTADOS EN MONEDA DURA - RENDIMIENTO REAL]")
        print(f"Costo Total Base:   ${val['total_cost_usd']} USD")
        print(f"Valor Actual MTM:   ${val['total_value_usd']} USD")
        print(f"Ganancia Real:      ${val['total_pnl_usd']} USD ({val['total_pnl_pct_usd']}%)")

        print("\n[RESULTADOS EN PESOS - VALOR NOMINAL CON ILUSION MONETARIA]")
        print(f"Costo Total Base:   ${val['total_cost_ars']} ARS")
        print(f"Valor Actual MTM:   ${val['total_value_ars']} ARS")
        print(f"Ganancia Nominal:   ${val['total_pnl_ars']} ARS ({val['total_pnl_pct_ars']}%)")

        print("\n[DESGLOSE POR ACTIVO]")
        for h in val["holdings"]:
            print(f"- {h['ticker']} ({h['name']}):")
            print(f"  Cantidad: {h['quantity']} | Precio Unit: {h['latest_unit_price']} {h['quote_currency']}")
            print(f"  PnL USD:  ${h['unrealized_pnl_usd']} ({h['pnl_pct_usd']}%)")
            print(f"  PnL ARS:  ${h['unrealized_pnl_ars']} ({h['pnl_pct_ars']}%)")

        print("\n--- MONITOREO DE RIESGO DE FUTUROS CRIPTO ---")
        fut = db.query(CryptoFuturesPosition).first()
        if fut:
            dist = fut.distance_to_liquidation_pct(Decimal("67000.0"))
            pnl = fut.calculate_unrealized_pnl(Decimal("67000.0"))
            print(f"Posicion: {fut.asset.ticker} {fut.direction.value} {fut.leverage}x")
            print(f"Precio Entrada: ${fut.entry_price} | Liquidacion: ${fut.liquidation_price}")
            print(f"PnL no realizado (a $67,000): ${round(pnl, 2)} USD")
            print(f"Distancia a liquidacion: {round(dist, 2)}%")

        print("\n[OK] Test completado con exito.")
    finally:
        db.close()

if __name__ == "__main__":
    test_valuation()
