import sys
from pathlib import Path
from decimal import Decimal
from datetime import datetime, timezone, timedelta

# Agregar la raíz del backend al path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.database import SessionLocal
from app.models.enums import (
    Currency, AssetClass, TransactionType, FxRateType,
    AccountType, PositionDirection, MarginType
)
from app.models.portfolio import Portfolio, Account
from app.models.asset import Asset
from app.models.transaction import Transaction
from app.models.market_data import ExchangeRate, AssetPrice
from app.models.risk import CryptoFuturesPosition

def seed_data():
    db = SessionLocal()
    try:
        print("[INFO] Iniciando precarga de datos de prueba...")

        # 1. Cartera Principal
        portfolio = db.query(Portfolio).filter(Portfolio.name == "Cartera Universitaria").first()
        if not portfolio:
            portfolio = Portfolio(
                name="Cartera Universitaria",
                description="Cartera para seguimiento de tesis / proyecto integrador",
                base_currency=Currency.USD,
                secondary_currency=Currency.ARS
            )
            db.add(portfolio)
            db.commit()
            db.refresh(portfolio)
            print(f"[OK] Cartera creada: {portfolio.name} (Base: {portfolio.base_currency})")

        # 2. Cuentas
        acc_local = db.query(Account).filter(Account.name == "IOL Inversiones").first()
        if not acc_local:
            acc_local = Account(
                portfolio_id=portfolio.id,
                name="IOL Inversiones",
                account_type=AccountType.BROKER_LOCAL
            )
            db.add(acc_local)

        acc_crypto = db.query(Account).filter(Account.name == "Binance").first()
        if not acc_crypto:
            acc_crypto = Account(
                portfolio_id=portfolio.id,
                name="Binance",
                account_type=AccountType.CRYPTO_EXCHANGE
            )
            db.add(acc_crypto)
        db.commit()
        db.refresh(acc_local)
        db.refresh(acc_crypto)
        print("[OK] Cuentas de custodia creadas: IOL Inversiones y Binance")

        # 3. Activos representativos
        sample_assets = [
            {
                "ticker": "GGAL.BA",
                "name": "Grupo Financiero Galicia S.A.",
                "asset_class": AssetClass.EQUITY_LOCAL,
                "currency": Currency.ARS,
            },
            {
                "ticker": "AAPL.BA",
                "name": "Apple Inc. (CEDEAR)",
                "asset_class": AssetClass.CEDEAR,
                "currency": Currency.ARS,
                "cedear_ratio": Decimal("10.0"),
                "underlying_ticker": "AAPL",
            },
            {
                "ticker": "AL30.BA",
                "name": "Bono Soberano Bonar 2030 (AL30)",
                "asset_class": AssetClass.SOVEREIGN_BOND,
                "currency": Currency.ARS,
                "bond_face_value": Decimal("100.0"),
            },
            {
                "ticker": "BTC-USD",
                "name": "Bitcoin Spot (USD)",
                "asset_class": AssetClass.CRYPTO_SPOT,
                "currency": Currency.USD,
            },
            {
                "ticker": "BTCUSDT",
                "name": "Bitcoin Perpetual Contract",
                "asset_class": AssetClass.CRYPTO_FUTURES,
                "currency": Currency.USDT,
            }
        ]

        assets_dict = {}
        for a_data in sample_assets:
            existing = db.query(Asset).filter(Asset.ticker == a_data["ticker"]).first()
            if not existing:
                asset = Asset(**a_data)
                db.add(asset)
                db.commit()
                db.refresh(asset)
                assets_dict[a_data["ticker"]] = asset
            else:
                assets_dict[a_data["ticker"]] = existing
        print(f"[OK] {len(sample_assets)} activos de catalogo registrados (Merval, CEDEARs, Bonos, Cripto).")

        # 4. Tipos de Cambio Iniciales (CCL y MEP)
        now = datetime.now(timezone.utc)
        fx_ccl = ExchangeRate(
            rate_type=FxRateType.CCL,
            timestamp=now,
            buy_price=Decimal("1240.0"),
            sell_price=Decimal("1250.0"),
            source="DOLAR_API_SEED"
        )
        fx_mep = ExchangeRate(
            rate_type=FxRateType.MEP,
            timestamp=now,
            buy_price=Decimal("1210.0"),
            sell_price=Decimal("1215.0"),
            source="DOLAR_API_SEED"
        )
        db.add_all([fx_ccl, fx_mep])
        db.commit()

        # 5. Transacciones de compra históricas (para mostrar el cálculo bimonetario)
        # Compra 1: 10 CEDEARs de Apple a $15,000 ARS cuando el CCL estaba a $1,000 ARS
        # Costo ARS: $150,000. Costo USD real: $150 USD.
        tx1 = Transaction(
            account_id=acc_local.id,
            asset_id=assets_dict["AAPL.BA"].id,
            transaction_type=TransactionType.BUY,
            executed_at=now - timedelta(days=60),
            quantity=Decimal("10.0"),
            price=Decimal("15000.0"),
            currency=Currency.ARS,
            fee=Decimal("150.0"),
            fx_rate=Decimal("1000.0"), # CCL al momento del trade
            fx_rate_type=FxRateType.CCL,
            notes="Compra CEDEAR Apple"
        )

        # Compra 2: 0.05 BTC a $60,000 USD
        tx2 = Transaction(
            account_id=acc_crypto.id,
            asset_id=assets_dict["BTC-USD"].id,
            transaction_type=TransactionType.BUY,
            executed_at=now - timedelta(days=30),
            quantity=Decimal("0.05"),
            price=Decimal("60000.0"),
            currency=Currency.USD,
            fee=Decimal("3.0"),
            fx_rate=Decimal("1150.0"),
            fx_rate_type=FxRateType.CCL,
            notes="Compra Spot BTC"
        )
        db.add_all([tx1, tx2])
        db.commit()

        # 6. Cotizaciones de mercado actuales simuladas
        price_aapl = AssetPrice(
            asset_id=assets_dict["AAPL.BA"].id,
            timestamp=now,
            close_price=Decimal("20000.0"), # Subió en pesos de 15,000 a 20,000 (+33.3% nominal)
            source="SEED"
        )
        price_btc = AssetPrice(
            asset_id=assets_dict["BTC-USD"].id,
            timestamp=now,
            close_price=Decimal("68000.0"), # Subió en USD de 60,000 a 68,000
            source="SEED"
        )
        db.add_all([price_aapl, price_btc])
        db.commit()

        # 7. Posición de futuros cripto con parámetros de riesgo
        fut_pos = CryptoFuturesPosition(
            account_id=acc_crypto.id,
            asset_id=assets_dict["BTCUSDT"].id,
            direction=PositionDirection.LONG,
            margin_type=MarginType.ISOLATED,
            leverage=5, # 5x apalancamiento
            position_size=Decimal("0.2"), # 0.2 BTC
            entry_price=Decimal("65000.0"),
            initial_margin=Decimal("2600.0"),
            maintenance_margin_rate=Decimal("0.005"),
            liquidation_price=Decimal("53000.0"),
            stop_loss_price=Decimal("62000.0"),
            take_profit_price=Decimal("75000.0"),
            opened_at=now - timedelta(days=5),
            notes="Long BTC Swing Trade 5x"
        )
        db.add(fut_pos)
        db.commit()

        print("[OK] Base de datos sembrada con exito. Listo para probar la API.")
    except Exception as e:
        db.rollback()
        print(f"[ERROR] Error al poblar datos: {e}")
        raise e
    finally:
        db.close()

if __name__ == "__main__":
    seed_data()
