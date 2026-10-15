import logging
from decimal import Decimal
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
import httpx
import yfinance as yf
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.enums import FxRateType
from app.models.market_data import ExchangeRate, AssetPrice
from app.models.asset import Asset

logger = logging.getLogger(__name__)

class MarketDataService:
    """
    Servicio de obtención e ingesta de datos de mercado automatizado:
    - Tipos de cambio (MEP, CCL, Oficial, Cripto) vía DolarApi.
    - Cotizaciones históricas e intradía vía Yahoo Finance (yfinance) con sufijo .BA y tickers estándar.
    """

    @staticmethod
    async def fetch_dolar_rates() -> List[Dict[str, Any]]:
        """
        Obtiene las cotizaciones actualizadas de los tipos de cambio desde DolarApi.
        Foco especial en Dólar CCL y MEP para valuación real.
        """
        url = f"{settings.DOLAR_API_BASE_URL}/dolares"
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(url)
            response.raise_for_status()
            data = response.json()
            return data

    @classmethod
    async def sync_dolar_rates_to_db(cls, db: Session) -> List[ExchangeRate]:
        """
        Descarga los tipos de cambio financieros y los persiste en la base de datos.
        """
        raw_rates = await cls.fetch_dolar_rates()
        saved_rates = []
        
        # Mapeo de casas de DolarApi a nuestros enums FxRateType
        mapping = {
            "contadoconliqui": FxRateType.CCL,
            "bolsa": FxRateType.MEP,
            "oficial": FxRateType.OFICIAL,
            "blue": FxRateType.BLUE,
            "cripto": FxRateType.CRYPTO,
        }

        now = datetime.now(timezone.utc)

        for item in raw_rates:
            casa = item.get("casa", "").lower()
            if casa in mapping:
                rate_type = mapping[casa]
                venta = Decimal(str(item.get("venta", 0)))
                compra = Decimal(str(item.get("compra", 0))) if item.get("compra") else None

                fx_record = ExchangeRate(
                    rate_type=rate_type,
                    timestamp=now,
                    buy_price=compra,
                    sell_price=venta,
                    source="DOLAR_API"
                )
                db.add(fx_record)
                saved_rates.append(fx_record)

        db.commit()
        return saved_rates

    @classmethod
    def get_latest_fx_rate(cls, db: Session, rate_type: FxRateType = FxRateType.CCL) -> Optional[Decimal]:
        """
        Retorna la cotización más reciente de un tipo de cambio en BD.
        """
        latest = (
            db.query(ExchangeRate)
            .filter(ExchangeRate.rate_type == rate_type)
            .order_by(ExchangeRate.timestamp.desc())
            .first()
        )
        return latest.sell_price if latest else None

    @classmethod
    def sync_asset_market_price(cls, db: Session, asset: Asset) -> Optional[AssetPrice]:
        """
        Descarga la última cotización de un activo desde Yahoo Finance y la persiste en BD.
        Soporta tickers locales con sufijo .BA (ej: GGAL.BA, AAPL.BA) y cripto (ej: BTC-USD).
        """
        try:
            ticker_obj = yf.Ticker(asset.ticker)
            history = ticker_obj.history(period="1d", interval="1d")
            
            if history.empty:
                logger.warning(f"No se encontraron cotizaciones recientes para el ticker {asset.ticker}")
                return None

            last_row = history.iloc[-1]
            close_price = Decimal(str(round(last_row["Close"], 4)))
            open_price = Decimal(str(round(last_row["Open"], 4))) if "Open" in last_row else None
            high_price = Decimal(str(round(last_row["High"], 4))) if "High" in last_row else None
            low_price = Decimal(str(round(last_row["Low"], 4))) if "Low" in last_row else None
            volume = Decimal(str(last_row["Volume"])) if "Volume" in last_row else None

            # Timestamp de la fila o UTC actual
            ts = history.index[-1].to_pydatetime()
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)

            # Evitar error de integridad (UNIQUE constraint): si ya existe registro para esa fecha, actualizarlo
            existing_price = (
                db.query(AssetPrice)
                .filter(AssetPrice.asset_id == asset.id, AssetPrice.timestamp == ts)
                .first()
            )

            if existing_price:
                existing_price.open_price = open_price
                existing_price.high_price = high_price
                existing_price.low_price = low_price
                existing_price.close_price = close_price
                existing_price.volume = volume
                existing_price.source = "YFINANCE"
                db.commit()
                db.refresh(existing_price)
                return existing_price

            price_record = AssetPrice(
                asset_id=asset.id,
                timestamp=ts,
                open_price=open_price,
                high_price=high_price,
                low_price=low_price,
                close_price=close_price,
                volume=volume,
                source="YFINANCE"
            )
            db.add(price_record)
            db.commit()
            db.refresh(price_record)
            return price_record
        except Exception as e:
            logger.error(f"Error sincronizando cotización para {asset.ticker}: {str(e)}")
            db.rollback()
            return None

    # Caché en memoria para el panel Merval (evita llamadas repetitivas y se renueva cada 5 min)
    _merval_cache: List[Dict[str, Any]] = []
    _merval_cache_timestamp: Optional[datetime] = None

    MERVAL_COMPONENTS = [
        ("GGAL.BA", "Grupo Financiero Galicia"),
        ("YPFD.BA", "YPF S.A."),
        ("PAMP.BA", "Pampa Energía"),
        ("BMA.BA", "Banco Macro"),
        ("ALUA.BA", "Aluar"),
        ("TXAR.BA", "Ternium Argentina"),
        ("CRES.BA", "Cresud"),
        ("EDN.BA", "Edenor"),
        ("TGSU2.BA", "TGS (Gas del Sur)"),
        ("TRAN.BA", "Transener"),
        ("CEPU.BA", "Central Puerto"),
        ("LOMA.BA", "Loma Negra"),
        ("VALO.BA", "Banco de Valores"),
        ("MIRG.BA", "Mirgor"),
        ("SUPV.BA", "Grupo Supervielle"),
        ("BYMA.BA", "Bolsas y Mercados Arg."),
        ("COME.BA", "Soc. Comercial del Plata"),
        ("BBAR.BA", "BBVA Argentina"),
        ("TECO2.BA", "Telecom Argentina"),
    ]

    @classmethod
    def get_merval_panel(cls, force_refresh: bool = False) -> List[Dict[str, Any]]:
        """
        Devuelve el panel de cotizaciones de acciones líderes del Merval con:
        - Ticker
        - Precio Actual
        - Precio de Apertura
        - Precio de Cierre Anterior
        - Variación porcentual diaria (%)
        Se actualiza y cachea automáticamente cada 5 minutos.
        """
        now = datetime.now(timezone.utc)
        if not force_refresh and cls._merval_cache and cls._merval_cache_timestamp:
            elapsed = (now - cls._merval_cache_timestamp).total_seconds()
            if elapsed < 300:  # 5 minutos
                return cls._merval_cache

        try:
            tickers = [t[0] for t in cls.MERVAL_COMPONENTS]
            df = yf.download(tickers, period="5d", interval="1d", progress=False)
            
            panel = []
            for ticker, name in cls.MERVAL_COMPONENTS:
                try:
                    close_series = df["Close"][ticker].dropna() if "Close" in df and ticker in df["Close"] else None
                    open_series = df["Open"][ticker].dropna() if "Open" in df and ticker in df["Open"] else None
                    high_series = df["High"][ticker].dropna() if "High" in df and ticker in df["High"] else None
                    low_series = df["Low"][ticker].dropna() if "Low" in df and ticker in df["Low"] else None

                    if close_series is not None and len(close_series) >= 1:
                        current_price = float(close_series.iloc[-1])
                        prev_close = float(close_series.iloc[-2]) if len(close_series) >= 2 else current_price
                        open_price = float(open_series.iloc[-1]) if open_series is not None and len(open_series) >= 1 else current_price
                        high_price = float(high_series.iloc[-1]) if high_series is not None and len(high_series) >= 1 else current_price
                        low_price = float(low_series.iloc[-1]) if low_series is not None and len(low_series) >= 1 else current_price
                        
                        change_abs = current_price - prev_close
                        change_pct = ((change_abs / prev_close) * 100.0) if prev_close > 0 else 0.0

                        panel.append({
                            "ticker": ticker,
                            "symbol": ticker.replace(".BA", ""),
                            "name": name,
                            "current_price": round(current_price, 2),
                            "open_price": round(open_price, 2),
                            "previous_close": round(prev_close, 2),
                            "high_price": round(high_price, 2),
                            "low_price": round(low_price, 2),
                            "change_abs": round(change_abs, 2),
                            "change_pct": round(change_pct, 2),
                        })
                except Exception as ex:
                    logger.warning(f"Error procesando cotización Merval para {ticker}: {ex}")

            if panel:
                cls._merval_cache = panel
                cls._merval_cache_timestamp = now
            return cls._merval_cache
        except Exception as e:
            logger.error(f"Error descargando panel Merval: {e}")
            return cls._merval_cache or []

    # =========================================================================
    # PANEL DE CEDEARS LÍDERES
    # =========================================================================
    _cedears_cache: List[Dict[str, Any]] = []
    _cedears_cache_timestamp: Optional[datetime] = None

    CEDEARS_COMPONENTS = [
        ("SPY.BA", "SPDR S&P 500 ETF Trust"),
        ("QQQ.BA", "Invesco QQQ Trust (Nasdaq)"),
        ("DIA.BA", "SPDR Dow Jones Industrial"),
        ("AAPL.BA", "Apple Inc."),
        ("NVDA.BA", "NVIDIA Corporation"),
        ("TSLA.BA", "Tesla Inc."),
        ("MELI.BA", "MercadoLibre"),
        ("MSFT.BA", "Microsoft Corp."),
        ("AMZN.BA", "Amazon.com Inc."),
        ("META.BA", "Meta Platforms (Facebook)"),
        ("GOOGL.BA", "Alphabet Inc. (Google)"),
        ("KO.BA", "The Coca-Cola Company"),
        ("VIST.BA", "Vista Energy"),
        ("BABA.BA", "Alibaba Group"),
        ("PBR.BA", "Petrobras"),
        ("BBD.BA", "Banco Bradesco"),
        ("DISN.BA", "The Walt Disney Company"),
        ("AMD.BA", "Advanced Micro Devices"),
        ("VALE.BA", "Vale S.A."),
        ("WMT.BA", "Walmart Inc."),
        ("XOM.BA", "Exxon Mobil"),
        ("JNJ.BA", "Johnson & Johnson"),
        ("MCD.BA", "McDonald's Corp."),
    ]

    @classmethod
    def get_cedears_panel(cls, force_refresh: bool = False) -> List[Dict[str, Any]]:
        """
        Devuelve el panel de cotizaciones de los principales CEDEARs operados en ByMA con:
        - Ticker
        - Precio Actual ($ ARS)
        - Precio de Apertura ($ ARS)
        - Precio de Cierre Anterior ($ ARS)
        - Variación porcentual diaria (%)
        - Máximo y Mínimo
        Se actualiza y cachea automáticamente cada 5 minutos.
        """
        now = datetime.now(timezone.utc)
        if not force_refresh and cls._cedears_cache and cls._cedears_cache_timestamp:
            elapsed = (now - cls._cedears_cache_timestamp).total_seconds()
            if elapsed < 300:
                return cls._cedears_cache

        try:
            tickers = [t[0] for t in cls.CEDEARS_COMPONENTS]
            df = yf.download(tickers, period="5d", interval="1d", progress=False)

            panel = []
            for ticker, name in cls.CEDEARS_COMPONENTS:
                try:
                    close_series = df["Close"][ticker].dropna() if "Close" in df and ticker in df["Close"] else None
                    open_series = df["Open"][ticker].dropna() if "Open" in df and ticker in df["Open"] else None
                    high_series = df["High"][ticker].dropna() if "High" in df and ticker in df["High"] else None
                    low_series = df["Low"][ticker].dropna() if "Low" in df and ticker in df["Low"] else None

                    if close_series is not None and len(close_series) >= 1:
                        current_price = float(close_series.iloc[-1])
                        prev_close = float(close_series.iloc[-2]) if len(close_series) >= 2 else current_price
                        open_price = float(open_series.iloc[-1]) if open_series is not None and len(open_series) >= 1 else current_price
                        high_price = float(high_series.iloc[-1]) if high_series is not None and len(high_series) >= 1 else current_price
                        low_price = float(low_series.iloc[-1]) if low_series is not None and len(low_series) >= 1 else current_price

                        change_abs = current_price - prev_close
                        change_pct = ((change_abs / prev_close) * 100.0) if prev_close > 0 else 0.0

                        panel.append({
                            "ticker": ticker,
                            "symbol": ticker.replace(".BA", ""),
                            "name": name,
                            "current_price": round(current_price, 2),
                            "open_price": round(open_price, 2),
                            "previous_close": round(prev_close, 2),
                            "high_price": round(high_price, 2),
                            "low_price": round(low_price, 2),
                            "change_abs": round(change_abs, 2),
                            "change_pct": round(change_pct, 2),
                        })
                except Exception as ex:
                    logger.warning(f"Error procesando cotización CEDEAR para {ticker}: {ex}")

            if panel:
                cls._cedears_cache = panel
                cls._cedears_cache_timestamp = now
            return cls._cedears_cache
        except Exception as e:
            logger.error(f"Error descargando panel CEDEARs: {e}")
            return cls._cedears_cache or []

    # =========================================================================
    # PANEL DE CRIPTOMONEDAS PRINCIPALES (BTC, ETH, SOL)
    # =========================================================================
    _crypto_cache: List[Dict[str, Any]] = []
    _crypto_cache_timestamp: Optional[datetime] = None

    CRYPTO_COMPONENTS = [
        ("BTC-USD", "Bitcoin", "BTC"),
        ("ETH-USD", "Ethereum", "ETH"),
        ("SOL-USD", "Solana", "SOL"),
    ]

    @classmethod
    def get_crypto_panel(cls, force_refresh: bool = False) -> List[Dict[str, Any]]:
        """
        Devuelve las cotizaciones en tiempo real para Bitcoin, Ethereum y Solana con:
        - Ticker y Símbolo
        - Precio Actual (USD)
        - Apertura (USD)
        - Cierre Anterior (USD)
        - Variación 24h (%)
        - Máximo y Mínimo 24h
        """
        now = datetime.now(timezone.utc)
        if not force_refresh and cls._crypto_cache and cls._crypto_cache_timestamp:
            elapsed = (now - cls._crypto_cache_timestamp).total_seconds()
            if elapsed < 300:
                return cls._crypto_cache

        try:
            tickers = [t[0] for t in cls.CRYPTO_COMPONENTS]
            df = yf.download(tickers, period="5d", interval="1d", progress=False)

            panel = []
            for ticker, name, symbol in cls.CRYPTO_COMPONENTS:
                try:
                    close_series = df["Close"][ticker].dropna() if "Close" in df and ticker in df["Close"] else None
                    open_series = df["Open"][ticker].dropna() if "Open" in df and ticker in df["Open"] else None
                    high_series = df["High"][ticker].dropna() if "High" in df and ticker in df["High"] else None
                    low_series = df["Low"][ticker].dropna() if "Low" in df and ticker in df["Low"] else None

                    if close_series is not None and len(close_series) >= 1:
                        current_price = float(close_series.iloc[-1])
                        prev_close = float(close_series.iloc[-2]) if len(close_series) >= 2 else current_price
                        open_price = float(open_series.iloc[-1]) if open_series is not None and len(open_series) >= 1 else current_price
                        high_price = float(high_series.iloc[-1]) if high_series is not None and len(high_series) >= 1 else current_price
                        low_price = float(low_series.iloc[-1]) if low_series is not None and len(low_series) >= 1 else current_price

                        change_abs = current_price - prev_close
                        change_pct = ((change_abs / prev_close) * 100.0) if prev_close > 0 else 0.0

                        panel.append({
                            "ticker": ticker,
                            "symbol": symbol,
                            "name": name,
                            "current_price": round(current_price, 2),
                            "open_price": round(open_price, 2),
                            "previous_close": round(prev_close, 2),
                            "high_price": round(high_price, 2),
                            "low_price": round(low_price, 2),
                            "change_abs": round(change_abs, 2),
                            "change_pct": round(change_pct, 2),
                        })
                except Exception as ex:
                    logger.warning(f"Error procesando cotización cripto para {ticker}: {ex}")

            if panel:
                cls._crypto_cache = panel
                cls._crypto_cache_timestamp = now
            return cls._crypto_cache
        except Exception as e:
            logger.error(f"Error descargando panel Cripto: {e}")
            return cls._crypto_cache or []
