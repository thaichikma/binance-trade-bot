# Algo Trading Client for TWAP and Volume Participation orders
from typing import Optional

from .futures_client import FuturesClient
from ..config import Config
from ..database import Database
from ..logger import Logger
from ..models import Coin


class AlgoClient(FuturesClient):
    """
    Binance Algo Trading client for TWAP and Volume Participation orders.
    Extends FuturesClient since algo orders are futures-based.
    """

    def __init__(self, config: Config, db: Database, logger: Logger, testnet: bool = False):
        super().__init__(config, db, logger, testnet)

        # Algo-specific configuration
        self.algo_type = config.ALGO_TYPE.lower()  # "twap", "vp", or "none"
        self.twap_duration = getattr(config, 'TWAP_DURATION', 300)  # Default 5 minutes
        self.vp_urgency = getattr(config, 'VP_URGENCY', 'LOW')  # LOW, MEDIUM, HIGH

        self.logger.info(f"AlgoClient initialized: type={self.algo_type}, duration={self.twap_duration}s, urgency={self.vp_urgency}")

    # ============ TWAP Methods ============

    def place_twap_order(self, symbol: str, side: str, quantity: float, duration: Optional[int] = None) -> dict:
        """
        Place TWAP (Time-Weighted Average Price) order.

        Args:
            symbol: Trading pair (e.g., "BTCUSDT")
            side: "BUY" or "SELL"
            quantity: Order quantity
            duration: Duration in seconds (300-86400). Uses config default if None.

        Returns:
            Response with algoId for tracking

        Note:
            - Minimum order size: 10,000 USDT equivalent
            - Duration: 5 minutes to 24 hours
            - No WebSocket notifications - must poll for status
        """
        if duration is None:
            duration = self.twap_duration

        # Validate duration range
        if duration < 300 or duration > 86400:
            raise ValueError(f"TWAP duration must be 300-86400 seconds, got {duration}")

        self.logger.info(f"Placing TWAP order: {side} {quantity} {symbol} over {duration}s")

        try:
            params = {
                "symbol": symbol,
                "side": side,
                "quantity": quantity,
                "duration": duration,
            }

            # Use raw API request since python-binance may not have algo methods
            response = self.binance_client._request_futures_api(
                'post',
                'algo/futures/newOrderTwap',
                signed=True,
                data=params,
                version=1
            )

            if response.get('code') == 0:
                algo_id = response.get('algoId')
                self.logger.info(f"TWAP order placed successfully: algoId={algo_id}")
            else:
                self.logger.error(f"TWAP order failed: {response}")

            return response

        except Exception as e:
            self.logger.error(f"Failed to place TWAP order: {e}")
            raise

    # ============ Volume Participation Methods ============

    def place_vp_order(self, symbol: str, side: str, quantity: float, urgency: Optional[str] = None) -> dict:
        """
        Place Volume Participation order.

        Args:
            symbol: Trading pair (e.g., "BTCUSDT")
            side: "BUY" or "SELL"
            quantity: Order quantity
            urgency: "LOW" (1-10%), "MEDIUM" (10-30%), "HIGH" (30-50%). Uses config default if None.

        Returns:
            Response with algoId for tracking

        Note:
            - Minimum order size: 10,000 USDT equivalent
            - Adaptive to market conditions
            - No WebSocket notifications - must poll for status
        """
        if urgency is None:
            urgency = self.vp_urgency

        urgency = urgency.upper()
        if urgency not in ['LOW', 'MEDIUM', 'HIGH']:
            raise ValueError(f"VP urgency must be LOW/MEDIUM/HIGH, got {urgency}")

        self.logger.info(f"Placing VP order: {side} {quantity} {symbol} urgency={urgency}")

        try:
            params = {
                "symbol": symbol,
                "side": side,
                "quantity": quantity,
                "urgency": urgency,
            }

            # Use raw API request since python-binance may not have algo methods
            response = self.binance_client._request_futures_api(
                'post',
                'algo/futures/newOrderVp',
                signed=True,
                data=params,
                version=1
            )

            if response.get('code') == 0:
                algo_id = response.get('algoId')
                self.logger.info(f"VP order placed successfully: algoId={algo_id}")
            else:
                self.logger.error(f"VP order failed: {response}")

            return response

        except Exception as e:
            self.logger.error(f"Failed to place VP order: {e}")
            raise

    # ============ Query Methods ============

    def get_algo_order_status(self, algo_id: int) -> dict:
        """
        Query status of a specific algo order.

        Args:
            algo_id: Algo order ID from creation response

        Returns:
            Order status details including execution progress
        """
        try:
            # Query from historical orders (includes both open and closed)
            response = self.binance_client._request_futures_api(
                'get',
                'algo/futures/historicalOrders',
                signed=True,
                data={'algoId': algo_id},
                version=1
            )

            if response.get('total', 0) > 0:
                orders = response.get('orders', [])
                if orders:
                    return orders[0]

            self.logger.warning(f"No status found for algoId={algo_id}")
            return {}

        except Exception as e:
            self.logger.error(f"Failed to get algo order status for {algo_id}: {e}")
            raise

    def cancel_algo_order(self, algo_id: int) -> dict:
        """
        Cancel an active algo order.

        Args:
            algo_id: Algo order ID to cancel

        Returns:
            Cancellation response
        """
        self.logger.info(f"Canceling algo order: algoId={algo_id}")

        try:
            response = self.binance_client._request_futures_api(
                'delete',
                'algo/futures/order',
                signed=True,
                data={'algoId': algo_id},
                version=1
            )

            if response.get('code') == 0:
                self.logger.info(f"Algo order canceled: algoId={algo_id}")
            else:
                self.logger.error(f"Failed to cancel algo order: {response}")

            return response

        except Exception as e:
            self.logger.error(f"Failed to cancel algo order {algo_id}: {e}")
            raise

    def get_open_algo_orders(self) -> list:
        """
        Get all open algo orders.

        Returns:
            List of open algo orders
        """
        try:
            response = self.binance_client._request_futures_api(
                'get',
                'algo/futures/openOrders',
                signed=True,
                version=1
            )
            return response.get('orders', [])
        except Exception as e:
            self.logger.error(f"Failed to get open algo orders: {e}")
            return []

    def get_sub_orders(self, algo_id: int) -> list:
        """
        Get sub-orders (child orders) for an algo order.

        Args:
            algo_id: Algo order ID

        Returns:
            List of sub-orders with execution details
        """
        try:
            response = self.binance_client._request_futures_api(
                'get',
                'algo/futures/subOrders',
                signed=True,
                data={'algoId': algo_id},
                version=1
            )
            return response.get('subOrders', [])
        except Exception as e:
            self.logger.error(f"Failed to get sub-orders for {algo_id}: {e}")
            return []

    # ============ Override Trading Methods ============

    def buy_alt(self, origin_coin: Coin, target_coin: Coin):
        """
        Execute buy order - uses algo orders if algo_type is configured.
        Falls back to standard futures order if algo_type is "none".
        """
        if self.algo_type == "none":
            return super().buy_alt(origin_coin, target_coin)

        # Use algo order
        return self._buy_alt_algo(origin_coin, target_coin)

    def sell_alt(self, origin_coin: Coin, target_coin: Coin):
        """
        Execute sell order - uses algo orders if algo_type is configured.
        Falls back to standard futures order if algo_type is "none".
        """
        if self.algo_type == "none":
            return super().sell_alt(origin_coin, target_coin)

        # Use algo order
        return self._sell_alt_algo(origin_coin, target_coin)

    # ============ Internal Algo Trading Methods ============

    def _buy_alt_algo(self, origin_coin: Coin, target_coin: Coin):
        """Internal buy implementation using algo orders"""
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

        self.logger.info(f"BUY (ALGO) {symbol} QTY: {quantity} @ {current_price}")

        try:
            # Place algo order based on type
            if self.algo_type == "twap":
                order = self.place_twap_order(symbol, "BUY", quantity)
            elif self.algo_type == "vp":
                order = self.place_vp_order(symbol, "BUY", quantity)
            else:
                raise ValueError(f"Unknown algo_type: {self.algo_type}")

            # Update trade log
            trade_log.set_ordered(0, target_balance, quantity)

            # Note: Algo orders don't have immediate execution
            # Status must be polled separately
            self.logger.info(f"Algo BUY order submitted: {order}")

            return order

        except Exception as e:
            self.logger.error(f"Failed to place algo buy order for {symbol}: {e}")
            return None

    def _sell_alt_algo(self, origin_coin: Coin, target_coin: Coin):
        """Internal sell implementation using algo orders"""
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
            self.logger.info(f"Closing LONG position (ALGO) for {symbol}, quantity: {quantity}")
        else:
            # Open new short position or use available balance
            target_balance = self.get_currency_balance(target_symbol)
            current_price = self.get_ticker_price(symbol)
            if not current_price:
                self.logger.error(f"Failed to get price for {symbol}")
                return None
            quantity = self._calculate_quantity(origin_symbol, target_symbol, target_balance, current_price)
            self.logger.info(f"Opening SHORT position (ALGO) for {symbol}, quantity: {quantity}")

        try:
            # Place algo order based on type
            if self.algo_type == "twap":
                order = self.place_twap_order(symbol, "SELL", quantity)
            elif self.algo_type == "vp":
                order = self.place_vp_order(symbol, "SELL", quantity)
            else:
                raise ValueError(f"Unknown algo_type: {self.algo_type}")

            # Update trade log
            trade_log.set_ordered(0, 0, quantity)

            # Note: Algo orders don't have immediate execution
            # Status must be polled separately
            self.logger.info(f"Algo SELL order submitted: {order}")

            return order

        except Exception as e:
            self.logger.error(f"Failed to place algo sell order for {symbol}: {e}")
            return None
