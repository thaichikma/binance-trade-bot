#!python3
import time

from .binance_api_manager import BinanceAPIManager
from .config import Config
from .database import Database
from .logger import Logger
from .scheduler import SafeScheduler
from .strategies import get_strategy


def main():
    logger = Logger()
    logger.info("=" * 60)
    logger.info("BINANCE TRADE BOT - Starting")
    logger.info("=" * 60)

    config = Config()

    # Validate configuration
    if not config.BINANCE_API_KEY or not config.BINANCE_API_SECRET_KEY:
        logger.error("API keys not configured. Please check user.cfg")
        return

    if config.TESTNET:
        logger.warning("*" * 60)
        logger.warning("  TESTNET MODE ACTIVE - No real funds will be used")
        logger.warning("*" * 60)

    db = Database(logger, config)
    manager = BinanceAPIManager(config, db, logger, config.TESTNET)

    # Validate API connectivity and permissions
    try:
        account = manager.get_account()
        logger.info(f"API connection successful. Account type: {account.get('accountType', 'SPOT')}")
    except Exception as e:  # pylint: disable=broad-except
        logger.error("Couldn't access Binance API - API keys may be wrong or lack sufficient permissions")
        logger.error(e)
        if config.TESTNET:
            logger.error("For testnet, ensure you're using API keys from https://testnet.binance.vision")
        return
    strategy = get_strategy(config.STRATEGY)
    if strategy is None:
        logger.error("Invalid strategy name")
        return
    trader = strategy(manager, db, logger, config)
    logger.info(f"Chosen strategy: {config.STRATEGY}")

    logger.info("Creating database schema if it doesn't already exist")
    db.create_database()

    db.set_coins(config.SUPPORTED_COIN_LIST)
    db.migrate_old_state()

    trader.initialize()

    schedule = SafeScheduler(logger)
    schedule.every(config.SCOUT_SLEEP_TIME).seconds.do(trader.scout).tag("scouting")
    schedule.every(1).minutes.do(trader.update_values).tag("updating value history")
    schedule.every(1).minutes.do(db.prune_scout_history).tag("pruning scout history")
    schedule.every(1).hours.do(db.prune_value_history).tag("pruning value history")
    try:
        while True:
            schedule.run_pending()
            time.sleep(1)
    finally:
        manager.stream_manager.close()