# Binance API Manager - Factory/Facade for market-specific clients
from typing import Dict, Optional

from .clients.base_client import BinanceBaseClient
from .config import Config
from .database import Database
from .logger import Logger
from .models import Coin


class BinanceAPIManager:
    """
    Factory and facade for Binance market clients.
    Creates appropriate client based on trade_market config.
    Delegates all operations to the underlying client.
    """

    def __init__(self, config: Config, db: Database, logger: Logger, testnet: bool = False):
        self.config = config
        self.db = db
        self.logger = logger
        self.testnet = testnet

        # Log environment info
        self.logger.info("=" * 60)
        self.logger.info(config.get_environment_info())
        self.logger.info("=" * 60)

        # Create market-specific client
        self.client: BinanceBaseClient = self._create_client()

        # Expose stream_manager for backward compatibility
        self.stream_manager = getattr(self.client, 'stream_manager', None)
        self.cache = getattr(self.client, 'cache', None)

    def _create_client(self) -> BinanceBaseClient:
        """Factory method to create market-specific client"""
        market = self.config.TRADE_MARKET
        algo_type = self.config.ALGO_TYPE

        if market == "spot":
            from .clients.spot_client import SpotClient
            return SpotClient(self.config, self.db, self.logger, self.testnet)
        elif market == "futures":
            # Use AlgoClient if algo trading is enabled, otherwise standard FuturesClient
            if algo_type and algo_type != "none":
                from .clients.algo_client import AlgoClient
                return AlgoClient(self.config, self.db, self.logger, self.testnet)
            else:
                from .clients.futures_client import FuturesClient
                return FuturesClient(self.config, self.db, self.logger, self.testnet)
        else:
            raise ValueError(f"Unknown trade_market: {market}. Use 'spot' or 'futures'")

    # === Delegated methods ===

    def get_account(self) -> dict:
        return self.client.get_account()

    def get_ticker_price(self, ticker_symbol: str) -> Optional[float]:
        return self.client.get_ticker_price(ticker_symbol)

    def get_currency_balance(self, currency_symbol: str, force: bool = False) -> float:
        return self.client.get_currency_balance(currency_symbol, force)

    def get_trade_fees(self) -> Dict[str, float]:
        return self.client.get_trade_fees()

    def get_fee(self, origin_coin: Coin, target_coin: Coin, selling: bool):
        return self.client.get_fee(origin_coin, target_coin, selling)

    def buy_alt(self, origin_coin: Coin, target_coin: Coin):
        return self.client.buy_alt(origin_coin, target_coin)

    def sell_alt(self, origin_coin: Coin, target_coin: Coin):
        return self.client.sell_alt(origin_coin, target_coin)

    def get_symbol_filter(self, origin_symbol: str, target_symbol: str, filter_type: str):
        return self.client.get_symbol_filter(origin_symbol, target_symbol, filter_type)

    def get_alt_tick(self, origin_symbol: str, target_symbol: str):
        return self.client.get_alt_tick(origin_symbol, target_symbol)

    def get_min_notional(self, origin_symbol: str, target_symbol: str):
        return self.client.get_min_notional(origin_symbol, target_symbol)

    def setup_websockets(self):
        self.client.setup_websockets()

    def close(self):
        self.client.close()
