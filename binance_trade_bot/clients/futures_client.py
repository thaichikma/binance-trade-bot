# Futures market client implementation
import math
import time
import traceback
from typing import Dict, Optional

from binance.client import Client
from binance.exceptions import BinanceAPIException
from cachetools import TTLCache, cached

from .base_client import BinanceBaseClient
from ..config import Config
from ..database import Database
from ..logger import Logger
from ..models import Coin


class FuturesClient(BinanceBaseClient):
    """Binance Futures (USDT-Margined) market client"""

    def __init__(self, config: Config, db: Database, logger: Logger, testnet: bool = False):
        super().__init__(config, logger, testnet)
        self.db = db

        # Initialize Binance client
        self.binance_client = Client(
            config.BINANCE_API_KEY,
            config.BINANCE_API_SECRET_KEY,
            testnet=testnet,
        )

        # Futures-specific configurations
        self.leverage = getattr(config, 'FUTURES_LEVERAGE', 1)
        self.margin_type = getattr(config, 'FUTURES_MARGIN_TYPE', 'CROSSED')

        # Cache for balances and positions
        self._balance_cache = {}
        self._position_cache = {}
        self._last_balance_update = 0

    def setup_websockets(self):
        """Initialize WebSocket connections for futures"""
        # Futures WebSocket support will be added in future phases
        self.logger.info("Futures WebSocket streams not yet implemented")
        pass

    def close(self):
        """Close all connections"""
        # Cleanup when needed
        pass

    @cached(cache=TTLCache(maxsize=1, ttl=43200))
    def get_trade_fees(self) -> Dict[str, float]:
        """Get futures trading fees"""
        # Futures uses different fee structure but similar to spot
        # Default: 0.04% maker, 0.04% taker for USDT futures
        if not self.testnet:
            # Futures API doesn't have direct fee endpoint like spot
            # Use account commission rate
            account_info = self.binance_client.futures_account()
            fee_tier = account_info.get('feeTier', 0)
            # Default fee based on tier (simplified)
            return {symbol: 0.0004 for symbol in self._get_all_symbols()}
        # Testnet emulation
        return {symbol: 0.0004 for symbol in self._get_all_symbols()}

    def _get_all_symbols(self):
        """Get all futures symbols"""
        exchange_info = self.binance_client.futures_exchange_info()
        return [s['symbol'] for s in exchange_info['symbols']]

    def get_account(self) -> dict:
        """Get futures account information"""
        return self.binance_client.futures_account()

    def get_ticker_price(self, symbol: str) -> Optional[float]:
        """Get ticker price for a futures symbol"""
        try:
            ticker = self.binance_client.futures_symbol_ticker(symbol=symbol)
            return float(ticker['price'])
        except Exception as e:
            self.logger.warning(f"Failed to get ticker price for {symbol}: {e}")
            return None

    def get_currency_balance(self, currency_symbol: str, force: bool = False) -> float:
        """Get balance for a specific currency in futures account"""
        # Check cache first
        if not force and time.time() - self._last_balance_update < 5:
            return self._balance_cache.get(currency_symbol, 0.0)

        # Refresh balance cache
        account = self.binance_client.futures_account()
        self._balance_cache = {
            asset['asset']: float(asset['availableBalance'])
            for asset in account['assets']
        }
        self._last_balance_update = time.time()

        return self._balance_cache.get(currency_symbol, 0.0)

    def get_position(self, symbol: str) -> Optional[dict]:
        """Get current position for a symbol"""
        try:
            positions = self.binance_client.futures_position_information(symbol=symbol)
            if positions:
                position = positions[0]
                # Only return if there's an actual position
                if float(position['positionAmt']) != 0:
                    return position
            return None
        except Exception as e:
            self.logger.warning(f"Failed to get position for {symbol}: {e}")
            return None

    def set_leverage(self, symbol: str, leverage: int):
        """Set leverage for a symbol"""
        try:
            result = self.binance_client.futures_change_leverage(
                symbol=symbol,
                leverage=leverage
            )
            self.logger.info(f"Set leverage for {symbol} to {leverage}x: {result}")
            return result
        except BinanceAPIException as e:
            # Leverage may already be set
            if 'No need to change leverage' in str(e):
                self.logger.info(f"Leverage already set for {symbol}")
                return None
            self.logger.error(f"Failed to set leverage for {symbol}: {e}")
            raise

    def set_margin_type(self, symbol: str, margin_type: str):
        """Set margin type (CROSSED or ISOLATED) for a symbol"""
        try:
            result = self.binance_client.futures_change_margin_type(
                symbol=symbol,
                marginType=margin_type
            )
            self.logger.info(f"Set margin type for {symbol} to {margin_type}: {result}")
            return result
        except BinanceAPIException as e:
            # Margin type may already be set
            if 'No need to change margin type' in str(e):
                self.logger.info(f"Margin type already set for {symbol}")
                return None
            self.logger.error(f"Failed to set margin type for {symbol}: {e}")
            raise

    def _setup_symbol(self, symbol: str):
        """Configure leverage and margin type for a symbol"""
        try:
            self.set_margin_type(symbol, self.margin_type)
            self.set_leverage(symbol, self.leverage)
        except Exception as e:
            self.logger.warning(f"Failed to setup {symbol}: {e}")

    def retry(self, func, *args, **kwargs):
        """Retry mechanism for API calls"""
        for attempt in range(20):
            try:
                return func(*args, **kwargs)
            except Exception:
                self.logger.warning(f"Failed to execute {func.__name__}. Trying Again (attempt {attempt}/20)")
                if attempt == 0:
                    self.logger.warning(traceback.format_exc())
                time.sleep(1)
        return None

    def get_symbol_info(self, symbol: str):
        """Get symbol information from futures exchange"""
        exchange_info = self.binance_client.futures_exchange_info()
        for s in exchange_info['symbols']:
            if s['symbol'] == symbol:
                return s
        return None

    def get_symbol_filter(self, origin_symbol: str, target_symbol: str, filter_type: str):
        """Get symbol filter for futures pair"""
        symbol = origin_symbol + target_symbol
        symbol_info = self.get_symbol_info(symbol)
        if symbol_info:
            return next(
                _filter
                for _filter in symbol_info['filters']
                if _filter['filterType'] == filter_type
            )
        return None

    @cached(cache=TTLCache(maxsize=2000, ttl=43200))
    def get_alt_tick(self, origin_symbol: str, target_symbol: str):
        """Get tick size for a futures pair"""
        symbol = origin_symbol + target_symbol
        symbol_info = self.get_symbol_info(symbol)
        if symbol_info:
            step_size = next(
                f['stepSize'] for f in symbol_info['filters']
                if f['filterType'] == 'LOT_SIZE'
            )
            if step_size.find("1") == 0:
                return 1 - step_size.find(".")
            return step_size.find("1") - 1
        return 3  # Default

    @cached(cache=TTLCache(maxsize=2000, ttl=43200))
    def get_min_notional(self, origin_symbol: str, target_symbol: str):
        """Get minimum notional value for a futures pair"""
        symbol = origin_symbol + target_symbol
        symbol_info = self.get_symbol_info(symbol)
        if symbol_info:
            min_notional_filter = next(
                (f for f in symbol_info['filters'] if f['filterType'] == 'MIN_NOTIONAL'),
                None
            )
            if min_notional_filter:
                return float(min_notional_filter['notional'])
        return 10.0  # Default minimum

    def _calculate_quantity(self, origin_symbol: str, target_symbol: str,
                           balance: float, price: float):
        """Calculate order quantity based on available balance"""
        symbol = origin_symbol + target_symbol
        tick_precision = self.get_alt_tick(origin_symbol, target_symbol)

        # For futures, we use USDT balance to calculate position size
        quantity = balance / price

        # Round down to tick precision
        quantity = math.floor(quantity * 10**tick_precision) / float(10**tick_precision)

        return quantity

    def buy_alt(self, origin_coin: Coin, target_coin: Coin):
        """Execute buy order (open long position)"""
        return self.retry(self._buy_alt, origin_coin, target_coin)

    def _buy_alt(self, origin_coin: Coin, target_coin: Coin):
        """Internal buy implementation for futures (open long)"""
        trade_log = self.db.start_trade_log(origin_coin, target_coin, False)
        origin_symbol, target_symbol = origin_coin.symbol, target_coin.symbol
        symbol = origin_symbol + target_symbol

        # Setup symbol configuration
        self._setup_symbol(symbol)

        # Clear balance cache
        self._balance_cache.clear()

        # Get balances
        target_balance = self.get_currency_balance(target_symbol)

        # Get current price
        current_price = self.get_ticker_price(symbol)
        if not current_price:
            self.logger.error(f"Failed to get price for {symbol}")
            return None

        # Calculate quantity
        quantity = self._calculate_quantity(origin_symbol, target_symbol, target_balance, current_price)

        self.logger.info(f"BUY (LONG) {symbol} QTY: {quantity} @ {current_price}")

        try:
            # Place market order to open long position
            order = self.binance_client.futures_create_order(
                symbol=symbol,
                side='BUY',
                type='MARKET',
                quantity=quantity,
            )
            self.logger.info(f"Futures BUY order placed: {order}")

            # Update trade log
            trade_log.set_ordered(0, target_balance, quantity)

            # Wait for order to fill
            time.sleep(1)

            # Get filled order details
            filled_order = self.binance_client.futures_get_order(
                symbol=symbol,
                orderId=order['orderId']
            )

            cumulative_quote = float(filled_order.get('cumQuote', 0))
            trade_log.set_complete(cumulative_quote)

            self.logger.info(f"Opened LONG position for {origin_symbol}")
            return order

        except Exception as e:
            self.logger.error(f"Failed to buy {symbol}: {e}")
            return None

    def sell_alt(self, origin_coin: Coin, target_coin: Coin):
        """Execute sell order (close long or open short position)"""
        return self.retry(self._sell_alt, origin_coin, target_coin)

    def _sell_alt(self, origin_coin: Coin, target_coin: Coin):
        """Internal sell implementation for futures"""
        trade_log = self.db.start_trade_log(origin_coin, target_coin, True)
        origin_symbol, target_symbol = origin_coin.symbol, target_coin.symbol
        symbol = origin_symbol + target_symbol

        # Setup symbol configuration
        self._setup_symbol(symbol)

        # Check if we have an open position to close
        position = self.get_position(symbol)

        if position and float(position['positionAmt']) > 0:
            # Close existing long position
            quantity = abs(float(position['positionAmt']))
            self.logger.info(f"Closing LONG position for {symbol}, quantity: {quantity}")
            reduce_only = True
        else:
            # Open new short position or use available balance
            target_balance = self.get_currency_balance(target_symbol)
            current_price = self.get_ticker_price(symbol)
            if not current_price:
                self.logger.error(f"Failed to get price for {symbol}")
                return None
            quantity = self._calculate_quantity(origin_symbol, target_symbol, target_balance, current_price)
            reduce_only = False
            self.logger.info(f"Opening SHORT position for {symbol}, quantity: {quantity}")

        try:
            # Place market sell order
            order = self.binance_client.futures_create_order(
                symbol=symbol,
                side='SELL',
                type='MARKET',
                quantity=quantity,
                reduceOnly=reduce_only,
            )
            self.logger.info(f"Futures SELL order placed: {order}")

            # Update trade log
            trade_log.set_ordered(0, 0, quantity)

            # Wait for order to fill
            time.sleep(1)

            # Get filled order details
            filled_order = self.binance_client.futures_get_order(
                symbol=symbol,
                orderId=order['orderId']
            )

            cumulative_quote = float(filled_order.get('cumQuote', 0))
            trade_log.set_complete(cumulative_quote)

            self.logger.info(f"Sold {origin_symbol} (Futures)")
            return order

        except Exception as e:
            self.logger.error(f"Failed to sell {symbol}: {e}")
            return None

    def get_fee(self, origin_coin: Coin, target_coin: Coin, selling: bool):
        """Get fee for futures trading"""
        # Simplified fee calculation for futures
        # Futures typically has flat 0.04% taker fee
        return 0.0004
