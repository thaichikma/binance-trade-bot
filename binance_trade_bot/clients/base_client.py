# Abstract base class for Binance market clients
from abc import ABC, abstractmethod
from typing import Dict, Optional

from ..config import Config
from ..logger import Logger


class BinanceBaseClient(ABC):
    """Abstract base class for all Binance market clients (Spot, Futures, Algo)"""

    def __init__(self, config: Config, logger: Logger, testnet: bool = False):
        self.config = config
        self.logger = logger
        self.testnet = testnet

    @abstractmethod
    def get_account(self) -> dict:
        """Get account information"""
        pass

    @abstractmethod
    def get_ticker_price(self, symbol: str) -> Optional[float]:
        """Get ticker price for a symbol"""
        pass

    @abstractmethod
    def get_currency_balance(self, symbol: str, force: bool = False) -> float:
        """Get balance for a specific currency"""
        pass

    @abstractmethod
    def get_trade_fees(self) -> Dict[str, float]:
        """Get trade fees for all symbols"""
        pass

    @abstractmethod
    def buy_alt(self, origin_coin, target_coin):
        """Execute buy order"""
        pass

    @abstractmethod
    def sell_alt(self, origin_coin, target_coin):
        """Execute sell order"""
        pass

    @abstractmethod
    def setup_websockets(self):
        """Initialize WebSocket connections"""
        pass

    @abstractmethod
    def close(self):
        """Close all connections"""
        pass
