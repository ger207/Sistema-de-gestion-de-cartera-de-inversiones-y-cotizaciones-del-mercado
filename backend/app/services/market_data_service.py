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
