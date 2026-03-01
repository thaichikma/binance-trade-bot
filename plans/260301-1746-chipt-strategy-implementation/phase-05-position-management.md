---
phase: 5
title: "Position Management"
status: pending
effort: 2h
depends_on: [4]
---

# Phase 5: Position Management

## Context Links

- [Phase 4: Chipt Strategy Class](./phase-04-chipt-strategy-class.md)
- [FuturesClient](/Users/admin/AI/binance-trade-bot/binance_trade_bot/clients/futures_client.py)
- [AlgoClient](/Users/admin/AI/binance-trade-bot/binance_trade_bot/clients/algo_client.py)

## Overview

Implement advanced position management including confidence-based sizing, trailing stops, and integration with FuturesClient position tracking.

**Priority:** P2
**Status:** pending

## Key Insights

From Pine Script:
1. Position size can scale with system confidence (50-90%)
2. TP/SL are point-based (configurable)
3. Futures positions have actual position state via API

From existing codebase:
1. `FuturesClient.get_position(symbol)` returns current position
2. Leverage and margin type are configurable
3. `reduceOnly=True` closes existing positions

## Requirements

### Functional

- Confidence-based position sizing (50-90% of available balance)
- Integration with FuturesClient position API
- Trailing stop option
- Partial position closing
- Max position limit

### Non-Functional

- Position state synced with exchange
- Handle position sync on startup
- Log all position changes

## Architecture

```
binance_trade_bot/
  analysis/
    position_manager.py    # Position management utilities
```

## Related Code Files

### Files to Create

- `binance_trade_bot/analysis/position_manager.py`

### Files to Modify

- `binance_trade_bot/strategies/chipt_strategy.py` (integrate position manager)
- `binance_trade_bot/analysis/__init__.py` (add exports)

## Implementation Steps

### 1. Implement position_manager.py

```python
"""
Position Management for Chipt Strategy

Handles position sizing, TP/SL, trailing stops,
and synchronization with exchange position state.
"""
from dataclasses import dataclass
from enum import Enum
from typing import Optional
import time


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

    # TP/SL
    tp_points: float = 10.0
    sl_points: float = 10.0
    use_trailing_stop: bool = False
    trailing_stop_activation: float = 5.0  # Activate after X points profit
    trailing_stop_distance: float = 3.0  # Trail by X points

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

    def _log(self, msg: str):
        if self.logger:
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
            self._log(f"Position value {position_value:.2f} below minimum {self.config.min_position_value}")
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
        import math
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
            pnl_points = current_price - pos.entry_price
        else:  # SHORT
            pos.lowest_price = min(pos.lowest_price, current_price)
            pnl_points = pos.entry_price - current_price

        pos.unrealized_pnl = pnl_points * pos.quantity

        # Check Take Profit
        if pnl_points >= self.config.tp_points:
            return "TP"

        # Check Stop Loss
        if pnl_points <= -self.config.sl_points:
            return "SL"

        # Check Trailing Stop (if enabled)
        if self.config.use_trailing_stop:
            trailing_result = self._check_trailing_stop(current_price, pnl_points)
            if trailing_result:
                return trailing_result

        return None

    def _check_trailing_stop(self, current_price: float, pnl_points: float) -> Optional[str]:
        """Check and manage trailing stop"""
        pos = self._position
        cfg = self.config

        # Activate trailing stop when profit exceeds activation threshold
        if not pos.trailing_stop_active:
            if pnl_points >= cfg.trailing_stop_activation:
                pos.trailing_stop_active = True
                self._log(f"Trailing stop activated at {pnl_points:.2f} points profit")

        if not pos.trailing_stop_active:
            return None

        # Calculate trailing stop level
        if pos.side == PositionSide.LONG:
            trailing_stop_price = pos.highest_price - cfg.trailing_stop_distance
            if current_price <= trailing_stop_price:
                return "TRAILING_SL"
        else:  # SHORT
            trailing_stop_price = pos.lowest_price + cfg.trailing_stop_distance
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
```

### 2. Update chipt_strategy.py to use PositionManager

Replace internal position tracking with PositionManager:

```python
# In initialize():
from binance_trade_bot.analysis import PositionManager, PositionConfig, PositionSide

self.position_config = PositionConfig(
    tp_points=self.config.CHIPT_TP_POINTS,
    sl_points=self.config.CHIPT_SL_POINTS,
    confidence_scaling=True,
)
self.position_manager = PositionManager(self.position_config, self.logger)

# Sync with exchange on startup
self._sync_position_state()


def _sync_position_state(self):
    """Sync position state with exchange"""
    symbol = self._get_trading_symbol()
    if symbol and hasattr(self.manager.client, 'get_position'):
        exchange_pos = self.manager.client.get_position(symbol)
        self.position_manager.sync_with_exchange(exchange_pos)


def _manage_position(self, symbol: str, current_price: float):
    """Check TP/SL via position manager"""
    result = self.position_manager.update_price(current_price)

    if result:
        self._close_position(symbol, result)
```

### 3. Add config options

Add to `config.py`:

```python
self.CHIPT_USE_TRAILING_STOP = config.getboolean(
    USER_CFG_SECTION, "chipt_use_trailing_stop", fallback=False
)
self.CHIPT_TRAILING_ACTIVATION = float(
    config.get(USER_CFG_SECTION, "chipt_trailing_activation", fallback="5.0")
)
self.CHIPT_TRAILING_DISTANCE = float(
    config.get(USER_CFG_SECTION, "chipt_trailing_distance", fallback="3.0")
)
self.CHIPT_CONFIDENCE_SCALING = config.getboolean(
    USER_CFG_SECTION, "chipt_confidence_scaling", fallback=True
)
```

## Todo List

- [ ] Create `position_manager.py`
- [ ] Implement confidence-based position sizing
- [ ] Implement trailing stop logic
- [ ] Implement exchange position sync
- [ ] Update `chipt_strategy.py` to use PositionManager
- [ ] Add new config options
- [ ] Test position sync on startup
- [ ] Test TP/SL and trailing stop

## Success Criteria

1. Position size scales correctly with confidence
2. TP/SL exits execute at correct levels
3. Trailing stop activates and trails correctly
4. Position state syncs with exchange on startup
5. All position changes logged

## Security Considerations

- Position limits prevent over-exposure
- Sync prevents orphaned positions
- Minimum position value prevents dust

## Next Steps

After completion:
1. Proceed to Phase 6: Testing & Calibration
2. Backtest strategy with historical data
