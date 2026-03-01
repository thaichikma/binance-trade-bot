---
phase: 1
title: "Technical Analysis Module"
status: pending
effort: 3h
---

# Phase 1: Technical Analysis Module

## Context Links

- [Pine Script Source](/Users/admin/AI/binance-trade-bot/docs/alert.md)
- [Plan Overview](./plan.md)

## Overview

Create core technical indicator calculations mirroring Pine Script's `ta.*` functions. These are stateless functions operating on pandas Series/DataFrames.

**Priority:** P1 (blocking all other phases)
**Status:** pending

## Key Insights

1. Pine Script uses `ta.ema`, `ta.vwap`, `ta.rsi`, `ta.atr`, `ta.sma`, `ta.pivothigh`, `ta.pivotlow`
2. VWAP calculation uses `hlc3 = (high + low + close) / 3`
3. ATR uses Wilder's smoothing (EMA with alpha=1/period)
4. Pivot detection requires lookback AND lookahead (centered window)

## Requirements

### Functional

- EMA(series, period) -> pandas Series
- SMA(series, period) -> pandas Series
- VWAP(high, low, close, volume) -> pandas Series
- RSI(close, period=14) -> pandas Series
- ATR(high, low, close, period=14) -> pandas Series
- Pivot detection (high/low, length) -> pandas Series of pivot levels

### Non-Functional

- Must handle NaN at start of series gracefully
- Pure functions (no side effects)
- Numpy-vectorized where possible for performance

## Architecture

```
binance_trade_bot/
  analysis/
    __init__.py
    indicators.py    # All indicator functions
```

## Related Code Files

### Files to Create

- `binance_trade_bot/analysis/__init__.py`
- `binance_trade_bot/analysis/indicators.py`

### Files to Modify

- None

## Implementation Steps

### 1. Create analysis module structure

```bash
mkdir -p binance_trade_bot/analysis
touch binance_trade_bot/analysis/__init__.py
```

### 2. Implement indicators.py

```python
"""
Technical Analysis Indicators

Stateless indicator functions matching Pine Script ta.* behavior.
All functions accept and return pandas Series.
"""
import numpy as np
import pandas as pd
from typing import Optional


def ema(series: pd.Series, period: int) -> pd.Series:
    """
    Exponential Moving Average.
    Matches Pine Script: ta.ema(source, length)
    """
    return series.ewm(span=period, adjust=False).mean()


def sma(series: pd.Series, period: int) -> pd.Series:
    """
    Simple Moving Average.
    Matches Pine Script: ta.sma(source, length)
    """
    return series.rolling(window=period).mean()


def vwap(high: pd.Series, low: pd.Series, close: pd.Series, volume: pd.Series) -> pd.Series:
    """
    Volume Weighted Average Price.
    Matches Pine Script: ta.vwap(hlc3)

    Note: Pine's ta.vwap resets daily. For intraday, this is cumulative VWAP.
    """
    hlc3 = (high + low + close) / 3
    cumulative_vwap = (hlc3 * volume).cumsum() / volume.cumsum()
    return cumulative_vwap


def rsi(close: pd.Series, period: int = 14) -> pd.Series:
    """
    Relative Strength Index.
    Matches Pine Script: ta.rsi(source, length)

    Uses Wilder's smoothing method (EMA with alpha=1/period).
    """
    delta = close.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = (-delta).where(delta < 0, 0.0)

    # Wilder's smoothing
    avg_gain = gain.ewm(alpha=1/period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1/period, min_periods=period, adjust=False).mean()

    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
    """
    Average True Range.
    Matches Pine Script: ta.atr(length)
    """
    prev_close = close.shift(1)
    tr1 = high - low
    tr2 = (high - prev_close).abs()
    tr3 = (low - prev_close).abs()

    true_range = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    return true_range.ewm(alpha=1/period, min_periods=period, adjust=False).mean()


def pivot_high(high: pd.Series, left_bars: int, right_bars: int) -> pd.Series:
    """
    Pivot High detection.
    Matches Pine Script: ta.pivothigh(high, leftbars, rightbars)

    Returns NaN where no pivot, pivot value where detected.
    Note: Pivots are detected `right_bars` bars AFTER they occur.
    """
    result = pd.Series(index=high.index, dtype=float)
    result[:] = np.nan

    for i in range(left_bars, len(high) - right_bars):
        pivot_idx = i
        pivot_val = high.iloc[pivot_idx]

        # Check left bars
        left_ok = all(high.iloc[pivot_idx - j] <= pivot_val for j in range(1, left_bars + 1))
        # Check right bars
        right_ok = all(high.iloc[pivot_idx + j] < pivot_val for j in range(1, right_bars + 1))

        if left_ok and right_ok:
            # Pivot is confirmed at i + right_bars (when right side is complete)
            confirm_idx = pivot_idx + right_bars
            if confirm_idx < len(result):
                result.iloc[confirm_idx] = pivot_val

    return result


def pivot_low(low: pd.Series, left_bars: int, right_bars: int) -> pd.Series:
    """
    Pivot Low detection.
    Matches Pine Script: ta.pivotlow(low, leftbars, rightbars)

    Returns NaN where no pivot, pivot value where detected.
    """
    result = pd.Series(index=low.index, dtype=float)
    result[:] = np.nan

    for i in range(left_bars, len(low) - right_bars):
        pivot_idx = i
        pivot_val = low.iloc[pivot_idx]

        # Check left bars
        left_ok = all(low.iloc[pivot_idx - j] >= pivot_val for j in range(1, left_bars + 1))
        # Check right bars
        right_ok = all(low.iloc[pivot_idx + j] > pivot_val for j in range(1, right_bars + 1))

        if left_ok and right_ok:
            confirm_idx = pivot_idx + right_bars
            if confirm_idx < len(result):
                result.iloc[confirm_idx] = pivot_val

    return result


def highest(series: pd.Series, period: int) -> pd.Series:
    """
    Highest value over period.
    Matches Pine Script: ta.highest(source, length)
    """
    return series.rolling(window=period).max()


def lowest(series: pd.Series, period: int) -> pd.Series:
    """
    Lowest value over period.
    Matches Pine Script: ta.lowest(source, length)
    """
    return series.rolling(window=period).min()


def crossover(series1: pd.Series, series2: pd.Series) -> pd.Series:
    """
    Crossover detection.
    Matches Pine Script: ta.crossover(source1, source2)

    Returns True when series1 crosses above series2.
    """
    prev1 = series1.shift(1)
    prev2 = series2.shift(1)
    return (prev1 <= prev2) & (series1 > series2)


def crossunder(series1: pd.Series, series2: pd.Series) -> pd.Series:
    """
    Crossunder detection.
    Matches Pine Script: ta.crossunder(source1, source2)

    Returns True when series1 crosses below series2.
    """
    prev1 = series1.shift(1)
    prev2 = series2.shift(1)
    return (prev1 >= prev2) & (series1 < series2)
```

### 3. Create __init__.py exports

```python
"""
Technical Analysis Module

Provides indicator calculations and multi-timeframe analysis
for the Chipt 2026 trading strategy.
"""
from .indicators import (
    ema, sma, vwap, rsi, atr,
    pivot_high, pivot_low,
    highest, lowest,
    crossover, crossunder,
)

__all__ = [
    'ema', 'sma', 'vwap', 'rsi', 'atr',
    'pivot_high', 'pivot_low',
    'highest', 'lowest',
    'crossover', 'crossunder',
]
```

## Todo List

- [ ] Create `binance_trade_bot/analysis/` directory
- [ ] Implement `indicators.py` with all indicator functions
- [ ] Create `__init__.py` with exports
- [ ] Write unit tests for each indicator
- [ ] Validate EMA/RSI/ATR against known TradingView values

## Success Criteria

1. All indicator functions return correct pandas Series
2. NaN handling matches Pine Script behavior (NaN at start)
3. Unit tests pass with <0.01% variance from TradingView values
4. No external dependencies beyond pandas/numpy

## Security Considerations

- No external API calls in this module
- Pure mathematical functions, no side effects
- Input validation for period/length parameters

## Next Steps

After completion:
1. Proceed to Phase 2: Multi-Timeframe Analyzer
2. MTF analyzer will use these indicators for each timeframe
