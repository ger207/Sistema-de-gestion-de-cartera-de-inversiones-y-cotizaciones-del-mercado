import enum

class Currency(str, enum.Enum):
    USD = "USD"
    ARS = "ARS"
    USDT = "USDT"

class AssetClass(str, enum.Enum):
    EQUITY_LOCAL = "EQUITY_LOCAL"          # Acciones Merval (ej: GGAL.BA, YPFD.BA)
    CEDEAR = "CEDEAR"                      # CEDEARs (ej: AAPL.BA, SPY.BA)
    SOVEREIGN_BOND = "SOVEREIGN_BOND"      # Bonos Soberanos (ej: AL30, GD30)
    CRYPTO_SPOT = "CRYPTO_SPOT"            # Cripto Spot (ej: BTC-USD, ETH-USD)
    CRYPTO_FUTURES = "CRYPTO_FUTURES"      # Futuros / Perpetuos Cripto
    CASH = "CASH"                          # Efectivo / Liquidez

class TransactionType(str, enum.Enum):
    BUY = "BUY"
    SELL = "SELL"
    DEPOSIT = "DEPOSIT"
    WITHDRAWAL = "WITHDRAWAL"
    DIVIDEND = "DIVIDEND"                  # Cobro de dividendos
    COUPON = "COUPON"                      # Cobro de renta de bonos
    AMORTIZATION = "AMORTIZATION"          # Devolución de capital de bonos
    FEE = "FEE"                            # Comisiones de broker
    FUNDING_FEE = "FUNDING_FEE"            # Tasa de financiamiento en derivados

class FxRateType(str, enum.Enum):
    CCL = "CCL"                            # Contado con Liquidación
    MEP = "MEP"                            # Dólar Bolsa
    OFICIAL = "OFICIAL"                    # Dólar Oficial BNA
    BLUE = "BLUE"                          # Dólar Libre / Informal
    CRYPTO = "CRYPTO"                      # Dólar Cripto

class AccountType(str, enum.Enum):
    BROKER_LOCAL = "BROKER_LOCAL"          # IOL, Balanz, Cocos, etc.
    BROKER_INTL = "BROKER_INTL"            # Interactive Brokers, etc.
    CRYPTO_EXCHANGE = "CRYPTO_EXCHANGE"    # Binance, Bybit, etc.
    BANK = "BANK"
    COLD_WALLET = "COLD_WALLET"

class PositionDirection(str, enum.Enum):
    LONG = "LONG"
    SHORT = "SHORT"

class MarginType(str, enum.Enum):
    ISOLATED = "ISOLATED"
    CROSS = "CROSS"
