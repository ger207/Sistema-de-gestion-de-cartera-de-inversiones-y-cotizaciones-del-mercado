import logging
from datetime import datetime, timezone
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from app.core.database import SessionLocal
from app.models.asset import Asset
from app.services.market_data_service import MarketDataService

logger = logging.getLogger("scheduler")
scheduler = AsyncIOScheduler()

async def job_sync_market_data():
    """
    Tarea periódica ejecutada cada 5 minutos:
    1. Sincroniza cotizaciones de Dólar CCL, MEP, Oficial y Cripto desde DolarApi.
    2. Sincroniza precios de cierre/intradía de todos los activos activos desde Yahoo Finance (yfinance).
    """
    logger.info("Iniciando sincronizacion periodica de mercado (FX + Activos)...")
    db = SessionLocal()
    try:
        # 1. Sincronizar tipos de cambio
        saved_rates = await MarketDataService.sync_dolar_rates_to_db(db)
        logger.info(f"Sincronizados {len(saved_rates)} tipos de cambio (DolarApi).")

        # 2. Sincronizar todos los activos activos
        active_assets = db.query(Asset).filter(Asset.is_active == True).all()
        synced_count = 0
        for asset in active_assets:
            # Excluir activos sintéticos como efectivo puro
            if asset.asset_class.value == "CASH":
                continue
            
            try:
                price_rec = MarketDataService.sync_asset_market_price(db, asset)
                if price_rec:
                    synced_count += 1
                    logger.info(f"Precio actualizado: {asset.ticker} -> {price_rec.close_price}")
            except Exception as asset_err:
                db.rollback()
                logger.warning(f"Error sincronizando activo {asset.ticker}: {asset_err}")

        # 3. Refrescar paneles de mercado (Merval, CEDEARs y Criptomonedas)
        MarketDataService.get_merval_panel(force_refresh=True)
        MarketDataService.get_cedears_panel(force_refresh=True)
        MarketDataService.get_crypto_panel(force_refresh=True)
        logger.info("Paneles de mercado actualizados: Merval, CEDEARs y Criptomonedas (BTC, ETH, SOL).")

        logger.info(f"Sincronizacion completada: {synced_count}/{len(active_assets)} activos actualizados.")
    except Exception as e:
        db.rollback()
        logger.error(f"Error durante la sincronizacion periodica: {str(e)}")
    finally:
        db.close()

def start_scheduler():
    """Inicia el planificador de tareas en segundo plano."""
    if not scheduler.running:
        scheduler.add_job(
            job_sync_market_data,
            trigger=IntervalTrigger(minutes=5),
            id="sync_market_data_5min",
            name="Sincronizacion de mercado cada 5 minutos",
            replace_existing=True,
            next_run_time=datetime.now(timezone.utc)  # Ejecuta una primera corrida al arrancar
        )
        scheduler.start()
        logger.info("Planificador APScheduler iniciado: Sincronizacion cada 5 minutos activa.")

def stop_scheduler():
    """Detiene el planificador."""
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("Planificador APScheduler detenido.")
