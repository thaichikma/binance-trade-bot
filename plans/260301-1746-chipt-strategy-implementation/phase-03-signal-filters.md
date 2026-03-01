---
phase: 3
title: "Signal Filters"
status: pending
effort: 3h
depends_on: [1, 2]
---

# Phase 3: Signal Filters

## Context Links

- [Phase 1: Technical Analysis Module](./phase-01-technical-analysis-module.md)
- [Phase 2: Multi-Timeframe Analyzer](./phase-02-multi-timeframe-analyzer.md)
- [Pine Script Source](/Users/admin/AI/binance-trade-bot/docs/alert.md) (lines 169-192)

## Overview

Implement all signal filters from the Pine Script strategy. Filters determine whether a potential signal should be executed based on momentum, trend alignment, volume, breakouts, and repeated signal restrictions.

**Priority:** P1
**Status:** pending

## Key Insights

From Pine Script (lines 169-192):

```pinescript
// Momentum Filter
early_sell_signal = use_momentum_filter ? price_change < -momentum_threshold : true
early_buy_signal = use_momentum_filter ? price_change > momentum_threshold : true

// Trend Filter
sell_trend_ok = use_trend_filter ? bearish_trend_ok : true
buy_trend_ok = use_trend_filter ? bullish_trend_ok : true

// Lower TF Filter
sell_lower_tf_ok = use_lower_tf_filter ? (not lower_tf_bullish and lower_tf_not_neutral) : true
buy_lower_tf_ok = use_lower_tf_filter ? (not lower_tf_bearish and lower_tf_not_neutral) : true

// Volume Filter
volCondition = volume > volAvg50 and ta.change(volShort) > 0
sell_volume_ok = use_volume_filter ? volCondition : true

// Breakout Filter
sell_breakout_ok = use_breakout_filter ? close < lowestBreakout[1] : true
buy_breakout_ok = use_breakout_filter ? close > highestBreakout[1] : true

// Repeated Signal Restriction
sell_allowed = not restrict_repeated_signals or (last_signal != "Sell" or trend changed)
```

## Requirements

### Functional

Implement these filters (all toggleable via config):

| Filter | Purpose | Buy Condition | Sell Condition |
|--------|---------|---------------|----------------|
| Momentum | Price change threshold | price_change > threshold | price_change < -threshold |
| Trend | Higher TF alignment | higher_tf_trend == 1 | higher_tf_trend == -1 |
| Lower TF | Prevent counter-trend | lower_tf != -1 | lower_tf != 1 |
| Volume | Above-average volume | volume > SMA(50) | volume > SMA(50) |
| Breakout | Price breaks structure | close > prev_high | close < prev_low |
| Min Distance | Bar spacing | bars_since_signal >= min | bars_since_signal >= min |
| Repeated Signal | Prevent spam | last != BUY or trend_changed | last != SELL or trend_changed |

### Non-Functional

- Each filter independent and composable
- Configurable enable/disable per filter
- Return detailed filter results for logging/debugging

## Architecture

```
binance_trade_bot/
  analysis/
    signal_filters.py    # Filter implementations
```

## Related Code Files

### Files to Create

- `binance_trade_bot/analysis/signal_filters.py`

### Files to Modify

- `binance_trade_bot/analysis/__init__.py` (add exports)

## Implementation Steps

### 1. Implement signal_filters.py

```python
"""
Signal Filters for Chipt 2026 Strategy

Each filter returns True if the signal is allowed, False if blocked.
Filters are composable and individually toggleable.
"""
from dataclasses import dataclass, field
from typing import Dict, Optional
import pandas as pd

from .indicators import sma, atr, highest, lowest
from .multi_timeframe import TrendAnalysis, Timeframe, TF_MAP


@dataclass
class FilterConfig:
    """Configuration for signal filters"""
    # Enable/disable flags
    use_momentum_filter: bool = True
    use_trend_filter: bool = True
    use_lower_tf_filter: bool = True
    use_volume_filter: bool = True
    use_breakout_filter: bool = True
    restrict_repeated_signals: bool = True

    # Parameters
    momentum_threshold_base: float = 0.01  # 1% base threshold
    min_signal_distance: int = 5  # Minimum bars between signals
    volume_long_period: int = 50  # SMA period for volume
    volume_short_period: int = 5  # Short volume SMA
    breakout_period: int = 5  # Lookback for breakout levels

    # Timeframe selections
    higher_tf: str = "5M"
    lower_tf: str = "5M"
    restrict_tf: str = "5M"


@dataclass
class FilterResult:
    """Result of filter evaluation"""
    passed: bool
    reason: str = ""

    def __bool__(self):
        return self.passed


@dataclass
class SignalFilterResults:
    """Complete filter evaluation results"""
    momentum_ok: FilterResult = field(default_factory=lambda: FilterResult(True))
    trend_ok: FilterResult = field(default_factory=lambda: FilterResult(True))
    lower_tf_ok: FilterResult = field(default_factory=lambda: FilterResult(True))
    volume_ok: FilterResult = field(default_factory=lambda: FilterResult(True))
    breakout_ok: FilterResult = field(default_factory=lambda: FilterResult(True))
    distance_ok: FilterResult = field(default_factory=lambda: FilterResult(True))
    repeated_ok: FilterResult = field(default_factory=lambda: FilterResult(True))

    @property
    def all_passed(self) -> bool:
        return all([
            self.momentum_ok,
            self.trend_ok,
            self.lower_tf_ok,
            self.volume_ok,
            self.breakout_ok,
            self.distance_ok,
            self.repeated_ok,
        ])

    def to_dict(self) -> Dict[str, bool]:
        return {
            "momentum": self.momentum_ok.passed,
            "trend": self.trend_ok.passed,
            "lower_tf": self.lower_tf_ok.passed,
            "volume": self.volume_ok.passed,
            "breakout": self.breakout_ok.passed,
            "distance": self.distance_ok.passed,
            "repeated": self.repeated_ok.passed,
        }


class SignalFilters:
    """
    Signal filter evaluator for Chipt 2026 strategy.

    Evaluates all filters for BUY/SELL signals and returns
    detailed results for logging and decision making.
    """

    def __init__(self, config: FilterConfig):
        self.config = config

        # State tracking
        self._last_signal: Optional[str] = None  # "BUY", "SELL", or None
        self._last_signal_bar: int = -999  # Bar index of last signal
        self._last_trend: int = 0  # Trend at last signal

    def evaluate_buy(
        self,
        df: pd.DataFrame,
        trend_analysis: TrendAnalysis,
        bar_index: int,
    ) -> SignalFilterResults:
        """
        Evaluate all filters for a BUY signal.

        Args:
            df: OHLCV DataFrame for current timeframe
            trend_analysis: MTF trend analysis result
            bar_index: Current bar index

        Returns:
            SignalFilterResults with all filter evaluations
        """
        results = SignalFilterResults()
        cfg = self.config

        # 1. Momentum Filter
        if cfg.use_momentum_filter:
            results.momentum_ok = self._check_momentum_buy(df)

        # 2. Trend Filter (higher TF alignment)
        if cfg.use_trend_filter:
            results.trend_ok = self._check_trend_buy(trend_analysis)

        # 3. Lower TF Filter
        if cfg.use_lower_tf_filter:
            results.lower_tf_ok = self._check_lower_tf_buy(trend_analysis)

        # 4. Volume Filter
        if cfg.use_volume_filter:
            results.volume_ok = self._check_volume(df)

        # 5. Breakout Filter
        if cfg.use_breakout_filter:
            results.breakout_ok = self._check_breakout_buy(df)

        # 6. Min Signal Distance
        results.distance_ok = self._check_distance(bar_index)

        # 7. Repeated Signal Restriction
        if cfg.restrict_repeated_signals:
            results.repeated_ok = self._check_repeated_buy(trend_analysis)

        return results

    def evaluate_sell(
        self,
        df: pd.DataFrame,
        trend_analysis: TrendAnalysis,
        bar_index: int,
    ) -> SignalFilterResults:
        """
        Evaluate all filters for a SELL signal.

        Args:
            df: OHLCV DataFrame for current timeframe
            trend_analysis: MTF trend analysis result
            bar_index: Current bar index

        Returns:
            SignalFilterResults with all filter evaluations
        """
        results = SignalFilterResults()
        cfg = self.config

        # 1. Momentum Filter
        if cfg.use_momentum_filter:
            results.momentum_ok = self._check_momentum_sell(df)

        # 2. Trend Filter
        if cfg.use_trend_filter:
            results.trend_ok = self._check_trend_sell(trend_analysis)

        # 3. Lower TF Filter
        if cfg.use_lower_tf_filter:
            results.lower_tf_ok = self._check_lower_tf_sell(trend_analysis)

        # 4. Volume Filter
        if cfg.use_volume_filter:
            results.volume_ok = self._check_volume(df)

        # 5. Breakout Filter
        if cfg.use_breakout_filter:
            results.breakout_ok = self._check_breakout_sell(df)

        # 6. Min Signal Distance
        results.distance_ok = self._check_distance(bar_index)

        # 7. Repeated Signal Restriction
        if cfg.restrict_repeated_signals:
            results.repeated_ok = self._check_repeated_sell(trend_analysis)

        return results

    def record_signal(self, signal: str, bar_index: int, trend: int):
        """Record that a signal was generated"""
        self._last_signal = signal
        self._last_signal_bar = bar_index
        self._last_trend = trend

    # ============ Momentum Filter ============

    def _get_momentum_threshold(self, df: pd.DataFrame) -> float:
        """
        Calculate dynamic momentum threshold based on ATR.

        Pine Script: momentum_threshold = momentum_threshold_base * (1 + volatility_factor * 2)
        """
        close = df['close']
        high = df['high']
        low = df['low']

        atr_val = atr(high, low, close, 14).iloc[-1]
        volatility_factor = atr_val / close.iloc[-1]

        return self.config.momentum_threshold_base * (1 + volatility_factor * 2)

    def _check_momentum_buy(self, df: pd.DataFrame) -> FilterResult:
        """Check if price change exceeds momentum threshold for BUY"""
        close = df['close']
        price_change = ((close.iloc[-1] - close.iloc[-2]) / close.iloc[-2]) * 100
        threshold = self._get_momentum_threshold(df)

        if price_change > threshold:
            return FilterResult(True, f"price_change={price_change:.3f}% > {threshold:.3f}%")
        return FilterResult(False, f"price_change={price_change:.3f}% <= {threshold:.3f}%")

    def _check_momentum_sell(self, df: pd.DataFrame) -> FilterResult:
        """Check if price change exceeds momentum threshold for SELL"""
        close = df['close']
        price_change = ((close.iloc[-1] - close.iloc[-2]) / close.iloc[-2]) * 100
        threshold = self._get_momentum_threshold(df)

        if price_change < -threshold:
            return FilterResult(True, f"price_change={price_change:.3f}% < -{threshold:.3f}%")
        return FilterResult(False, f"price_change={price_change:.3f}% >= -{threshold:.3f}%")

    # ============ Trend Filter ============

    def _check_trend_buy(self, trend_analysis: TrendAnalysis) -> FilterResult:
        """Check if higher TF trend is bullish"""
        tf = TF_MAP.get(self.config.higher_tf.upper())
        if tf and tf in trend_analysis.trends:
            trend = trend_analysis.trends[tf].trend
            if trend == 1:
                return FilterResult(True, f"higher_tf={self.config.higher_tf} bullish")
            return FilterResult(False, f"higher_tf={self.config.higher_tf} not bullish (trend={trend})")
        return FilterResult(True, "higher_tf not available")

    def _check_trend_sell(self, trend_analysis: TrendAnalysis) -> FilterResult:
        """Check if higher TF trend is bearish"""
        tf = TF_MAP.get(self.config.higher_tf.upper())
        if tf and tf in trend_analysis.trends:
            trend = trend_analysis.trends[tf].trend
            if trend == -1:
                return FilterResult(True, f"higher_tf={self.config.higher_tf} bearish")
            return FilterResult(False, f"higher_tf={self.config.higher_tf} not bearish (trend={trend})")
        return FilterResult(True, "higher_tf not available")

    # ============ Lower TF Filter ============

    def _check_lower_tf_buy(self, trend_analysis: TrendAnalysis) -> FilterResult:
        """Prevent BUY if lower TF is bearish"""
        tf = TF_MAP.get(self.config.lower_tf.upper())
        if tf and tf in trend_analysis.trends:
            trend = trend_analysis.trends[tf].trend
            # Pine: not lower_tf_bearish and lower_tf_not_neutral
            if trend != -1 and trend != 0:
                return FilterResult(True, f"lower_tf={self.config.lower_tf} not bearish")
            return FilterResult(False, f"lower_tf={self.config.lower_tf} is bearish/neutral (trend={trend})")
        return FilterResult(True, "lower_tf not available")

    def _check_lower_tf_sell(self, trend_analysis: TrendAnalysis) -> FilterResult:
        """Prevent SELL if lower TF is bullish"""
        tf = TF_MAP.get(self.config.lower_tf.upper())
        if tf and tf in trend_analysis.trends:
            trend = trend_analysis.trends[tf].trend
            # Pine: not lower_tf_bullish and lower_tf_not_neutral
            if trend != 1 and trend != 0:
                return FilterResult(True, f"lower_tf={self.config.lower_tf} not bullish")
            return FilterResult(False, f"lower_tf={self.config.lower_tf} is bullish/neutral (trend={trend})")
        return FilterResult(True, "lower_tf not available")

    # ============ Volume Filter ============

    def _check_volume(self, df: pd.DataFrame) -> FilterResult:
        """
        Check if volume is above average with increasing momentum.

        Pine Script: volume > volAvg50 and ta.change(volShort) > 0
        """
        volume = df['volume']
        vol_avg = sma(volume, self.config.volume_long_period).iloc[-1]
        vol_short = sma(volume, self.config.volume_short_period)
        vol_change = vol_short.iloc[-1] - vol_short.iloc[-2]

        current_vol = volume.iloc[-1]

        if current_vol > vol_avg and vol_change > 0:
            return FilterResult(True, f"volume={current_vol:.0f} > avg={vol_avg:.0f}, change={vol_change:.0f}")
        return FilterResult(False, f"volume={current_vol:.0f}, avg={vol_avg:.0f}, change={vol_change:.0f}")

    # ============ Breakout Filter ============

    def _check_breakout_buy(self, df: pd.DataFrame) -> FilterResult:
        """Check if price breaks above previous high"""
        close = df['close'].iloc[-1]
        prev_highest = highest(df['high'], self.config.breakout_period).iloc[-2]

        if close > prev_highest:
            return FilterResult(True, f"close={close:.2f} > prev_high={prev_highest:.2f}")
        return FilterResult(False, f"close={close:.2f} <= prev_high={prev_highest:.2f}")

    def _check_breakout_sell(self, df: pd.DataFrame) -> FilterResult:
        """Check if price breaks below previous low"""
        close = df['close'].iloc[-1]
        prev_lowest = lowest(df['low'], self.config.breakout_period).iloc[-2]

        if close < prev_lowest:
            return FilterResult(True, f"close={close:.2f} < prev_low={prev_lowest:.2f}")
        return FilterResult(False, f"close={close:.2f} >= prev_low={prev_lowest:.2f}")

    # ============ Distance Filter ============

    def _check_distance(self, bar_index: int) -> FilterResult:
        """Check minimum bar distance since last signal"""
        bars_since = bar_index - self._last_signal_bar
        min_dist = self.config.min_signal_distance

        if bars_since >= min_dist:
            return FilterResult(True, f"bars_since={bars_since} >= min={min_dist}")
        return FilterResult(False, f"bars_since={bars_since} < min={min_dist}")

    # ============ Repeated Signal Filter ============

    def _check_repeated_buy(self, trend_analysis: TrendAnalysis) -> FilterResult:
        """Prevent repeated BUY signals in same trend"""
        tf = TF_MAP.get(self.config.restrict_tf.upper())
        current_trend = 0
        if tf and tf in trend_analysis.trends:
            current_trend = trend_analysis.trends[tf].trend

        # Allow if: last signal wasn't BUY, OR trend changed, OR current trend isn't bullish
        if self._last_signal != "BUY":
            return FilterResult(True, "last_signal was not BUY")
        if current_trend != self._last_trend:
            return FilterResult(True, f"trend changed from {self._last_trend} to {current_trend}")
        if current_trend != 1:
            return FilterResult(True, f"current trend is not bullish ({current_trend})")

        return FilterResult(False, "repeated BUY in same bullish trend")

    def _check_repeated_sell(self, trend_analysis: TrendAnalysis) -> FilterResult:
        """Prevent repeated SELL signals in same trend"""
        tf = TF_MAP.get(self.config.restrict_tf.upper())
        current_trend = 0
        if tf and tf in trend_analysis.trends:
            current_trend = trend_analysis.trends[tf].trend

        # Allow if: last signal wasn't SELL, OR trend changed, OR current trend isn't bearish
        if self._last_signal != "SELL":
            return FilterResult(True, "last_signal was not SELL")
        if current_trend != self._last_trend:
            return FilterResult(True, f"trend changed from {self._last_trend} to {current_trend}")
        if current_trend != -1:
            return FilterResult(True, f"current trend is not bearish ({current_trend})")

        return FilterResult(False, "repeated SELL in same bearish trend")

    def reset_state(self):
        """Reset filter state (e.g., on strategy restart)"""
        self._last_signal = None
        self._last_signal_bar = -999
        self._last_trend = 0
```

### 2. Update analysis/__init__.py

```python
from .signal_filters import (
    SignalFilters,
    FilterConfig,
    FilterResult,
    SignalFilterResults,
)
```

## Todo List

- [ ] Create `signal_filters.py` with all filter implementations
- [ ] Implement FilterConfig dataclass
- [ ] Implement each filter method
- [ ] Add state tracking for repeated signal restriction
- [ ] Update `__init__.py` with exports
- [ ] Write unit tests for each filter
- [ ] Test filter combinations
- [ ] Validate against Pine Script outputs

## Success Criteria

1. Each filter can be independently enabled/disabled
2. Filter results provide detailed reason strings
3. Repeated signal restriction tracks state correctly
4. All filters match Pine Script logic exactly
5. Filter evaluation completes in <10ms

## Security Considerations

- No external API calls (uses pre-fetched data)
- State is ephemeral (resets on restart)
- No user input directly used in calculations

## Next Steps

After completion:
1. Proceed to Phase 4: Chipt Strategy Class
2. Strategy class will orchestrate filters with MTF analyzer
