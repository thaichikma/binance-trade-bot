---
phase: 4
title: "Chipt Strategy Class"
status: pending
effort: 3h
depends_on: [1, 2, 3]
---

# Phase 4: Chipt Strategy Class

## Context Links

- [Phase 1: Technical Analysis Module](./phase-01-technical-analysis-module.md)
- [Phase 2: Multi-Timeframe Analyzer](./phase-02-multi-timeframe-analyzer.md)
- [Phase 3: Signal Filters](./phase-03-signal-filters.md)
- [AutoTrader Base](/Users/admin/AI/binance-trade-bot/binance_trade_bot/auto_trader.py)
- [Default Strategy](/Users/admin/AI/binance-trade-bot/binance_trade_bot/strategies/default_strategy.py)
- [Strategy Loading](/Users/admin/AI/binance-trade-bot/binance_trade_bot/strategies/__init__.py)

## Overview

Implement the main Chipt strategy class that extends AutoTrader, orchestrating MTF analysis, signal filters, and trade execution. This is the core integration point.

**Priority:** P1
**Status:** pending

## Key Insights

1. Strategy must extend `AutoTrader` and implement `scout()` method
2. File must be named `chipt_strategy.py` to be discovered by `get_strategy("chipt")`
3. Strategy receives `BinanceAPIManager` which auto-routes to correct client (Spot/Futures/Algo)
4. Main loop calls `scout()` every `SCOUT_SLEEP_TIME` seconds

## Requirements

### Functional

- Implement `scout()` method for signal detection
- Integrate MTF analyzer for trend analysis
- Apply all signal filters before executing trades
- Support both LONG and SHORT positions (futures mode)
- Execute via FuturesClient.buy_alt() / sell_alt()
- Optionally use AlgoClient for TWAP/VP execution

### Non-Functional

- Log all filter decisions for debugging
- Track position state internally
- Handle API errors gracefully
- Respect existing database schema

## Architecture

```
binance_trade_bot/
  strategies/
    chipt_strategy.py    # Main strategy class
```

## Related Code Files

### Files to Create

- `binance_trade_bot/strategies/chipt_strategy.py`

### Files to Modify

- `binance_trade_bot/config.py` (add Chipt config options)

## Implementation Steps

### 1. Extend Config for Chipt settings

Add to `config.py`:

```python
# In Config.__init__(), add after existing config reads:

# Chipt Strategy Settings
self.CHIPT_PIVOT_LENGTH = int(
    os.environ.get("CHIPT_PIVOT_LENGTH") or
    config.get(USER_CFG_SECTION, "chipt_pivot_length", fallback="5")
)
self.CHIPT_MOMENTUM_THRESHOLD = float(
    os.environ.get("CHIPT_MOMENTUM_THRESHOLD") or
    config.get(USER_CFG_SECTION, "chipt_momentum_threshold", fallback="0.01")
)
self.CHIPT_TP_POINTS = int(
    os.environ.get("CHIPT_TP_POINTS") or
    config.get(USER_CFG_SECTION, "chipt_tp_points", fallback="10")
)
self.CHIPT_SL_POINTS = int(
    os.environ.get("CHIPT_SL_POINTS") or
    config.get(USER_CFG_SECTION, "chipt_sl_points", fallback="10")
)
self.CHIPT_MIN_SIGNAL_DISTANCE = int(
    os.environ.get("CHIPT_MIN_SIGNAL_DISTANCE") or
    config.get(USER_CFG_SECTION, "chipt_min_signal_distance", fallback="5")
)
self.CHIPT_USE_MOMENTUM_FILTER = (
    os.environ.get("CHIPT_USE_MOMENTUM_FILTER", "true").lower() == "true" or
    config.getboolean(USER_CFG_SECTION, "chipt_use_momentum_filter", fallback=True)
)
self.CHIPT_USE_TREND_FILTER = (
    os.environ.get("CHIPT_USE_TREND_FILTER", "true").lower() == "true" or
    config.getboolean(USER_CFG_SECTION, "chipt_use_trend_filter", fallback=True)
)
self.CHIPT_USE_VOLUME_FILTER = (
    os.environ.get("CHIPT_USE_VOLUME_FILTER", "true").lower() == "true" or
    config.getboolean(USER_CFG_SECTION, "chipt_use_volume_filter", fallback=True)
)
self.CHIPT_USE_BREAKOUT_FILTER = (
    os.environ.get("CHIPT_USE_BREAKOUT_FILTER", "true").lower() == "true" or
    config.getboolean(USER_CFG_SECTION, "chipt_use_breakout_filter", fallback=True)
)
self.CHIPT_HIGHER_TF = (
    os.environ.get("CHIPT_HIGHER_TF") or
    config.get(USER_CFG_SECTION, "chipt_higher_tf", fallback="5M")
)
self.CHIPT_LOWER_TF = (
    os.environ.get("CHIPT_LOWER_TF") or
    config.get(USER_CFG_SECTION, "chipt_lower_tf", fallback="5M")
)
```

### 2. Implement chipt_strategy.py

```python
"""
Chipt 2026 Trading Strategy

Multi-timeframe trend-following strategy with confidence-based
position sizing and multiple signal filters.

Ported from Pine Script indicator "Chipt 2026".
"""
from datetime import datetime
from typing import Optional
import pandas as pd

from binance_trade_bot.auto_trader import AutoTrader
from binance_trade_bot.analysis import (
    MultiTimeframeAnalyzer,
    TrendAnalysis,
    SignalFilters,
    FilterConfig,
)
from binance_trade_bot.models import Coin


class Strategy(AutoTrader):
    """
    Chipt 2026 multi-timeframe trend strategy.

    Signal Generation:
    - Analyzes 7 timeframes (1M to 1D)
    - Calculates trend alignment and system confidence
    - Applies momentum, trend, volume, breakout filters

    Position Management:
    - LONG when all buy filters pass
    - SHORT when all sell filters pass
    - Position size scaled by confidence (50-90%)
    """

    def initialize(self):
        """Initialize strategy components"""
        super().initialize()

        self.logger.info("=" * 50)
        self.logger.info("Initializing Chipt 2026 Strategy")
        self.logger.info("=" * 50)

        # Get underlying Binance client for klines
        self._binance_client = self.manager.client.binance_client

        # Initialize MTF analyzer
        self.mtf_analyzer = MultiTimeframeAnalyzer(
            binance_client=self._binance_client,
            logger=self.logger
        )

        # Initialize signal filters
        self.filter_config = FilterConfig(
            use_momentum_filter=self.config.CHIPT_USE_MOMENTUM_FILTER,
            use_trend_filter=self.config.CHIPT_USE_TREND_FILTER,
            use_lower_tf_filter=True,
            use_volume_filter=self.config.CHIPT_USE_VOLUME_FILTER,
            use_breakout_filter=self.config.CHIPT_USE_BREAKOUT_FILTER,
            restrict_repeated_signals=True,
            momentum_threshold_base=self.config.CHIPT_MOMENTUM_THRESHOLD,
            min_signal_distance=self.config.CHIPT_MIN_SIGNAL_DISTANCE,
            higher_tf=self.config.CHIPT_HIGHER_TF,
            lower_tf=self.config.CHIPT_LOWER_TF,
        )
        self.signal_filters = SignalFilters(self.filter_config)

        # Position tracking
        self._current_position: Optional[str] = None  # "LONG", "SHORT", or None
        self._position_entry_price: float = 0.0
        self._bar_index: int = 0

        # TP/SL settings
        self._tp_points = self.config.CHIPT_TP_POINTS
        self._sl_points = self.config.CHIPT_SL_POINTS

        self.logger.info(f"Filter Config: {self.filter_config}")
        self.logger.info(f"TP: {self._tp_points} points, SL: {self._sl_points} points")

    def scout(self):
        """
        Main strategy loop - called every SCOUT_SLEEP_TIME seconds.

        1. Fetch current market data
        2. Perform MTF trend analysis
        3. Evaluate buy/sell filters
        4. Execute trades if conditions met
        5. Manage existing positions (TP/SL)
        """
        self._bar_index += 1

        # Get the primary trading symbol
        symbol = self._get_trading_symbol()
        if not symbol:
            return

        # Status update
        print(
            f"{datetime.now()} - CHIPT - Scouting {symbol} | "
            f"Position: {self._current_position or 'FLAT'} | "
            f"Bar: {self._bar_index}",
            end="\r"
        )

        # 1. Perform MTF analysis
        trend_analysis = self.mtf_analyzer.analyze(symbol)

        self.logger.debug(
            f"MTF Analysis: strength={trend_analysis.trend_strength_raw}/7, "
            f"confidence={trend_analysis.system_confidence}%"
        )

        # 2. Fetch current timeframe data for filters
        df = self._fetch_ohlcv(symbol, "5m", limit=60)
        if df.empty:
            self.logger.warning(f"Failed to fetch OHLCV for {symbol}")
            return

        current_price = df['close'].iloc[-1]

        # 3. Check existing position for TP/SL
        if self._current_position:
            self._manage_position(symbol, current_price)

        # 4. Evaluate entry signals (only if flat)
        if self._current_position is None:
            self._evaluate_entries(symbol, df, trend_analysis)

    def _get_trading_symbol(self) -> Optional[str]:
        """Get the primary trading symbol from config"""
        # For Chipt, we typically trade a single symbol
        # Use the first coin in supported list + bridge
        if self.config.SUPPORTED_COIN_LIST:
            coin_symbol = self.config.SUPPORTED_COIN_LIST[0]
            return f"{coin_symbol}{self.config.BRIDGE_SYMBOL}"
        return None

    def _fetch_ohlcv(self, symbol: str, interval: str, limit: int = 60) -> pd.DataFrame:
        """Fetch OHLCV data from Binance"""
        try:
            # Use futures klines if available
            if hasattr(self._binance_client, 'futures_klines'):
                klines = self._binance_client.futures_klines(
                    symbol=symbol, interval=interval, limit=limit
                )
            else:
                klines = self._binance_client.get_klines(
                    symbol=symbol, interval=interval, limit=limit
                )

            df = pd.DataFrame(klines, columns=[
                'open_time', 'open', 'high', 'low', 'close', 'volume',
                'close_time', 'quote_volume', 'trades', 'taker_buy_base',
                'taker_buy_quote', 'ignore'
            ])

            for col in ['open', 'high', 'low', 'close', 'volume']:
                df[col] = pd.to_numeric(df[col], errors='coerce')

            return df

        except Exception as e:
            self.logger.error(f"Failed to fetch OHLCV: {e}")
            return pd.DataFrame()

    def _evaluate_entries(
        self,
        symbol: str,
        df: pd.DataFrame,
        trend_analysis: TrendAnalysis
    ):
        """Evaluate entry signals and execute if filters pass"""

        # Evaluate BUY filters
        buy_filters = self.signal_filters.evaluate_buy(
            df, trend_analysis, self._bar_index
        )

        # Evaluate SELL filters
        sell_filters = self.signal_filters.evaluate_sell(
            df, trend_analysis, self._bar_index
        )

        # Log filter results
        self.logger.debug(f"BUY filters: {buy_filters.to_dict()}")
        self.logger.debug(f"SELL filters: {sell_filters.to_dict()}")

        # Execute based on filter results and trend bias
        if buy_filters.all_passed and trend_analysis.is_bullish:
            self._execute_long(symbol, trend_analysis)

        elif sell_filters.all_passed and trend_analysis.is_bearish:
            self._execute_short(symbol, trend_analysis)

    def _execute_long(self, symbol: str, trend_analysis: TrendAnalysis):
        """Execute LONG entry"""
        self.logger.info("=" * 40)
        self.logger.info(f"SIGNAL: LONG {symbol}")
        self.logger.info(f"Confidence: {trend_analysis.system_confidence}%")
        self.logger.info(f"Trend Strength: {trend_analysis.trend_strength_raw}/7")
        self.logger.info("=" * 40)

        # Get coin objects for trade execution
        coin_symbol = symbol.replace(self.config.BRIDGE_SYMBOL, "")
        origin_coin = Coin(coin_symbol)
        target_coin = self.config.BRIDGE

        # Execute via manager (routes to FuturesClient or AlgoClient)
        result = self.manager.buy_alt(origin_coin, target_coin)

        if result:
            self._current_position = "LONG"
            self._position_entry_price = self.manager.get_ticker_price(symbol) or 0.0

            # Record signal for filter state
            restrict_trend = trend_analysis.trends.get(
                self.signal_filters.config.restrict_tf
            )
            self.signal_filters.record_signal(
                "BUY",
                self._bar_index,
                restrict_trend.trend if restrict_trend else 0
            )

            self.logger.info(f"LONG position opened at {self._position_entry_price}")
        else:
            self.logger.error("Failed to execute LONG entry")

    def _execute_short(self, symbol: str, trend_analysis: TrendAnalysis):
        """Execute SHORT entry"""
        self.logger.info("=" * 40)
        self.logger.info(f"SIGNAL: SHORT {symbol}")
        self.logger.info(f"Confidence: {trend_analysis.system_confidence}%")
        self.logger.info(f"Trend Strength: {trend_analysis.trend_strength_raw}/7")
        self.logger.info("=" * 40)

        # Get coin objects for trade execution
        coin_symbol = symbol.replace(self.config.BRIDGE_SYMBOL, "")
        origin_coin = Coin(coin_symbol)
        target_coin = self.config.BRIDGE

        # Execute via manager (sell_alt opens SHORT in futures mode)
        result = self.manager.sell_alt(origin_coin, target_coin)

        if result:
            self._current_position = "SHORT"
            self._position_entry_price = self.manager.get_ticker_price(symbol) or 0.0

            # Record signal for filter state
            restrict_trend = trend_analysis.trends.get(
                self.signal_filters.config.restrict_tf
            )
            self.signal_filters.record_signal(
                "SELL",
                self._bar_index,
                restrict_trend.trend if restrict_trend else 0
            )

            self.logger.info(f"SHORT position opened at {self._position_entry_price}")
        else:
            self.logger.error("Failed to execute SHORT entry")

    def _manage_position(self, symbol: str, current_price: float):
        """Manage existing position - check TP/SL"""
        if self._current_position == "LONG":
            pnl_points = current_price - self._position_entry_price

            # Take Profit
            if pnl_points >= self._tp_points:
                self.logger.info(f"LONG TP hit: +{pnl_points:.2f} points")
                self._close_position(symbol, "TP")

            # Stop Loss
            elif pnl_points <= -self._sl_points:
                self.logger.info(f"LONG SL hit: {pnl_points:.2f} points")
                self._close_position(symbol, "SL")

        elif self._current_position == "SHORT":
            pnl_points = self._position_entry_price - current_price

            # Take Profit
            if pnl_points >= self._tp_points:
                self.logger.info(f"SHORT TP hit: +{pnl_points:.2f} points")
                self._close_position(symbol, "TP")

            # Stop Loss
            elif pnl_points <= -self._sl_points:
                self.logger.info(f"SHORT SL hit: {pnl_points:.2f} points")
                self._close_position(symbol, "SL")

    def _close_position(self, symbol: str, reason: str):
        """Close current position"""
        self.logger.info(f"Closing {self._current_position} position ({reason})")

        coin_symbol = symbol.replace(self.config.BRIDGE_SYMBOL, "")
        origin_coin = Coin(coin_symbol)
        target_coin = self.config.BRIDGE

        # Close position
        if self._current_position == "LONG":
            # Sell to close long
            self.manager.sell_alt(origin_coin, target_coin)
        else:
            # Buy to close short
            self.manager.buy_alt(origin_coin, target_coin)

        self._current_position = None
        self._position_entry_price = 0.0
        self.logger.info("Position closed")
```

### 3. Add to .user.cfg.example

```ini
# Chipt Strategy Settings (only used when strategy=chipt)
chipt_pivot_length = 5
chipt_momentum_threshold = 0.01
chipt_tp_points = 10
chipt_sl_points = 10
chipt_min_signal_distance = 5
chipt_use_momentum_filter = true
chipt_use_trend_filter = true
chipt_use_volume_filter = true
chipt_use_breakout_filter = true
chipt_higher_tf = 5M
chipt_lower_tf = 5M
```

## Todo List

- [ ] Add Chipt config options to `config.py`
- [ ] Create `chipt_strategy.py` extending AutoTrader
- [ ] Implement `scout()` method with MTF analysis
- [ ] Implement filter evaluation and trade execution
- [ ] Implement position management (TP/SL)
- [ ] Update `.user.cfg.example` with Chipt options
- [ ] Test strategy discovery via `get_strategy("chipt")`
- [ ] Integration test with FuturesClient

## Success Criteria

1. `get_strategy("chipt")` returns Strategy class
2. Strategy executes LONG/SHORT based on filter results
3. TP/SL management closes positions correctly
4. All filters logged for debugging
5. Works with both spot and futures modes

## Security Considerations

- API keys handled by existing manager
- Position sizes validated before execution
- Error handling prevents partial state

## Next Steps

After completion:
1. Proceed to Phase 5: Position Management
2. Add advanced position sizing and risk management
