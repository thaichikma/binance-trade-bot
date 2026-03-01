"""
Position Management for Chipt Strategy

Handles position sizing, TP/SL, trailing stops,
and synchronization with exchange position state.
"""
import math
import time
from dataclasses import dataclass
from enum import Enum
from typing import Optional


class PositionSide(Enum):
    LONG = "LONG"
    SHORT = "SHORT"
    FLAT = "FLAT"


@dataclass
class PositionConfig:
    """Position management configuration"""
    # Sizing
    base_position_pct: float = 0.5  # 50% of balance as base
    confidence_scaling: bool = True  # Scale by confidence
    max_position_pct: float = 0.9  # Max 90% of balance

    # TP/SL (as percentage)
    tp_percent: float = 1.0  # 1% take profit
    sl_percent: float = 0.5  # 0.5% stop loss
    use_trailing_stop: bool = False
    trailing_stop_activation: float = 0.5  # Activate after 0.5% profit
    trailing_stop_distance: float = 0.3  # Trail by 0.3%

    # Limits
    max_positions: int = 1  # Max concurrent positions
    min_position_value: float = 10.0  # Min USDT value


@dataclass
class Position:
    """Current position state"""
    side: PositionSide
    symbol: str
    entry_price: float
    quantity: float
    unrealized_pnl: float = 0.0
    entry_time: float = 0.0

    # Trailing stop state
    highest_price: float = 0.0  # For long
    lowest_price: float = 0.0  # For short
    trailing_stop_active: bool = False

    @property
    def is_open(self) -> bool:
        return self.side != PositionSide.FLAT and self.quantity > 0

    @property
    def pnl_percent(self) -> float:
        """Calculate PnL as percentage"""
        if self.entry_price <= 0:
            return 0.0
        return (self.unrealized_pnl / (self.entry_price * self.quantity)) * 100


class PositionManager:
    """
    Manages position lifecycle for Chipt strategy.

    Features:
    - Confidence-based position sizing
    - TP/SL with optional trailing stop
    - Sync with exchange position state
    """

    def __init__(self, config: PositionConfig, logger=None):
        self.config = config
        self.logger = logger
        self._position: Optional[Position] = None

    def _log(self, msg: str, level: str = "info"):
        if self.logger:
            if level == "debug":
                self.logger.debug(msg)
            else:
                self.logger.info(msg)

    # ============ Position Sizing ============

    def calculate_position_size(
        self,
        available_balance: float,
        confidence: float,
        current_price: float
    ) -> float:
        """
        Calculate position size based on balance and confidence.

        Args:
            available_balance: USDT available for trading
            confidence: System confidence (50-90)
            current_price: Current price of asset

        Returns:
            Position size in quote currency (USDT)
        """
        if available_balance <= 0 or current_price <= 0:
            return 0.0

        if self.config.confidence_scaling:
            # Scale position by confidence: 50% conf = 50% of base, 90% conf = 90% of base
            scaling_factor = confidence / 100.0
        else:
            scaling_factor = 1.0

        position_value = available_balance * self.config.base_position_pct * scaling_factor

        # Apply limits
        max_value = available_balance * self.config.max_position_pct
        position_value = min(position_value, max_value)

        if position_value < self.config.min_position_value:
            self._log(
                f"Position value {position_value:.2f} below minimum {self.config.min_position_value}",
                level="debug"
            )
            return 0.0

        return position_value

    def calculate_quantity(
        self,
        position_value: float,
        price: float,
        tick_precision: int = 3
    ) -> float:
        """Calculate quantity from position value and price"""
        if price <= 0:
            return 0.0

        quantity = position_value / price
        # Round down to tick precision
        quantity = math.floor(quantity * 10**tick_precision) / float(10**tick_precision)
        return quantity

    # ============ Position Opening ============

    def open_position(
        self,
        side: PositionSide,
        symbol: str,
        entry_price: float,
        quantity: float
    ):
        """Record a new position opening"""
        self._position = Position(
            side=side,
            symbol=symbol,
            entry_price=entry_price,
            quantity=quantity,
            entry_time=time.time(),
            highest_price=entry_price,
            lowest_price=entry_price,
        )
        self._log(f"Position opened: {side.value} {quantity} {symbol} @ {entry_price}")

    # ============ Position Management ============

    def update_price(self, current_price: float) -> Optional[str]:
        """
        Update position with current price and check TP/SL.

        Returns:
            "TP", "SL", "TRAILING_SL", or None
        """
        if self._position is None or not self._position.is_open:
            return None

        pos = self._position

        # Update high/low tracking
        if pos.side == PositionSide.LONG:
            pos.highest_price = max(pos.highest_price, current_price)
            pnl_value = (current_price - pos.entry_price) * pos.quantity
            pnl_percent = ((current_price - pos.entry_price) / pos.entry_price) * 100
        else:  # SHORT
            pos.lowest_price = min(pos.lowest_price, current_price)
            pnl_value = (pos.entry_price - current_price) * pos.quantity
            pnl_percent = ((pos.entry_price - current_price) / pos.entry_price) * 100

        pos.unrealized_pnl = pnl_value

        # Check Take Profit
        if pnl_percent >= self.config.tp_percent:
            return "TP"

        # Check Stop Loss
        if pnl_percent <= -self.config.sl_percent:
            return "SL"

        # Check Trailing Stop (if enabled)
        if self.config.use_trailing_stop:
            trailing_result = self._check_trailing_stop(current_price, pnl_percent)
            if trailing_result:
                return trailing_result

        return None

    def _check_trailing_stop(self, current_price: float, pnl_percent: float) -> Optional[str]:
        """Check and manage trailing stop"""
        pos = self._position
        cfg = self.config

        # Activate trailing stop when profit exceeds activation threshold
        if not pos.trailing_stop_active:
            if pnl_percent >= cfg.trailing_stop_activation:
                pos.trailing_stop_active = True
                self._log(f"Trailing stop activated at {pnl_percent:.2f}% profit")

        if not pos.trailing_stop_active:
            return None

        # Calculate trailing stop level (as percentage from high/low)
        if pos.side == PositionSide.LONG:
            # Trailing stop is trailing_distance% below highest price
            trailing_stop_price = pos.highest_price * (1 - cfg.trailing_stop_distance / 100)
            if current_price <= trailing_stop_price:
                return "TRAILING_SL"
        else:  # SHORT
            # Trailing stop is trailing_distance% above lowest price
            trailing_stop_price = pos.lowest_price * (1 + cfg.trailing_stop_distance / 100)
            if current_price >= trailing_stop_price:
                return "TRAILING_SL"

        return None

    # ============ Position Closing ============

    def close_position(self, reason: str, close_price: float):
        """Record position closing"""
        if self._position is None:
            return

        pos = self._position
        if pos.side == PositionSide.LONG:
            realized_pnl = (close_price - pos.entry_price) * pos.quantity
        else:
            realized_pnl = (pos.entry_price - close_price) * pos.quantity

        hold_time = time.time() - pos.entry_time

        self._log(
            f"Position closed ({reason}): {pos.side.value} {pos.symbol} | "
            f"Entry: {pos.entry_price:.2f} -> Exit: {close_price:.2f} | "
            f"PnL: {realized_pnl:.2f} | Hold: {hold_time:.0f}s"
        )

        self._position = None

    # ============ Position Sync ============

    def sync_with_exchange(self, exchange_position: Optional[dict]):
        """
        Sync internal state with exchange position.

        Args:
            exchange_position: Result from FuturesClient.get_position()
        """
        if exchange_position is None:
            # No position on exchange
            if self._position is not None:
                self._log("Position sync: Exchange shows no position, clearing internal state")
                self._position = None
            return

        position_amt = float(exchange_position.get('positionAmt', 0))
        entry_price = float(exchange_position.get('entryPrice', 0))
        symbol = exchange_position.get('symbol', '')

        if position_amt == 0:
            self._position = None
            return

        # Determine side
        side = PositionSide.LONG if position_amt > 0 else PositionSide.SHORT

        # Create/update position
        self._position = Position(
            side=side,
            symbol=symbol,
            entry_price=entry_price,
            quantity=abs(position_amt),
            entry_time=time.time(),
            highest_price=entry_price,
            lowest_price=entry_price,
        )

        self._log(f"Position synced from exchange: {side.value} {abs(position_amt)} @ {entry_price}")

    # ============ Properties ============

    @property
    def current_position(self) -> Optional[Position]:
        return self._position

    @property
    def is_flat(self) -> bool:
        return self._position is None or not self._position.is_open

    @property
    def position_side(self) -> PositionSide:
        if self._position is None:
            return PositionSide.FLAT
        return self._position.side

    def reset(self):
        """Reset position state"""
        self._position = None
