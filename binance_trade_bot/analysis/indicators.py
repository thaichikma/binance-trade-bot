"""
Technical Analysis Indicators

Stateless indicator functions matching Pine Script ta.* behavior.
All functions accept and return pandas Series.
"""
import numpy as np
import pandas as pd
from typing import Union


def ema(series: pd.Series, period: int) -> pd.Series:
    """
    Exponential Moving Average.
    Matches Pine Script: ta.ema(source, length)
    """
    if period < 1:
        raise ValueError("Period must be >= 1")
    return series.ewm(span=period, adjust=False).mean()


def sma(series: pd.Series, period: int) -> pd.Series:
    """
    Simple Moving Average.
    Matches Pine Script: ta.sma(source, length)
    """
    if period < 1:
        raise ValueError("Period must be >= 1")
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
    if period < 1:
        raise ValueError("Period must be >= 1")

    delta = close.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = (-delta).where(delta < 0, 0.0)

    # Wilder's smoothing
    avg_gain = gain.ewm(alpha=1/period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1/period, min_periods=period, adjust=False).mean()

    rs = avg_gain / avg_loss
    rsi_values = 100 - (100 / (1 + rs))

    # Handle division by zero (when avg_loss is 0)
    rsi_values = rsi_values.fillna(100)
    return rsi_values


def atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
    """
    Average True Range.
    Matches Pine Script: ta.atr(length)
    """
    if period < 1:
        raise ValueError("Period must be >= 1")

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
    if left_bars < 1 or right_bars < 1:
        raise ValueError("left_bars and right_bars must be >= 1")

    result = pd.Series(index=high.index, dtype=float)
    result[:] = np.nan

    for i in range(left_bars, len(high) - right_bars):
        pivot_idx = i
        pivot_val = high.iloc[pivot_idx]

        # Check left bars (must be <= pivot)
        left_ok = all(high.iloc[pivot_idx - j] <= pivot_val for j in range(1, left_bars + 1))
        # Check right bars (must be < pivot)
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
    if left_bars < 1 or right_bars < 1:
        raise ValueError("left_bars and right_bars must be >= 1")

    result = pd.Series(index=low.index, dtype=float)
    result[:] = np.nan

    for i in range(left_bars, len(low) - right_bars):
        pivot_idx = i
        pivot_val = low.iloc[pivot_idx]

        # Check left bars (must be >= pivot)
        left_ok = all(low.iloc[pivot_idx - j] >= pivot_val for j in range(1, left_bars + 1))
        # Check right bars (must be > pivot)
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
    if period < 1:
        raise ValueError("Period must be >= 1")
    return series.rolling(window=period).max()


def lowest(series: pd.Series, period: int) -> pd.Series:
    """
    Lowest value over period.
    Matches Pine Script: ta.lowest(source, length)
    """
    if period < 1:
        raise ValueError("Period must be >= 1")
    return series.rolling(window=period).min()


def crossover(series1: pd.Series, series2: Union[pd.Series, float]) -> pd.Series:
    """
    Crossover detection.
    Matches Pine Script: ta.crossover(source1, source2)

    Returns True when series1 crosses above series2.
    """
    if isinstance(series2, (int, float)):
        series2 = pd.Series(series2, index=series1.index)

    prev1 = series1.shift(1)
    prev2 = series2.shift(1)
    return (prev1 <= prev2) & (series1 > series2)


def crossunder(series1: pd.Series, series2: Union[pd.Series, float]) -> pd.Series:
    """
    Crossunder detection.
    Matches Pine Script: ta.crossunder(source1, source2)

    Returns True when series1 crosses below series2.
    """
    if isinstance(series2, (int, float)):
        series2 = pd.Series(series2, index=series1.index)

    prev1 = series1.shift(1)
    prev2 = series2.shift(1)
    return (prev1 >= prev2) & (series1 < series2)


def change(series: pd.Series, length: int = 1) -> pd.Series:
    """
    Price change over length bars.
    Matches Pine Script: ta.change(source, length)
    """
    return series.diff(length)


def percent_change(series: pd.Series, length: int = 1) -> pd.Series:
    """
    Percentage price change over length bars.
    Returns value as percentage (e.g., 1.5 for 1.5%)
    """
    return (series.diff(length) / series.shift(length)) * 100


def volatility_factor(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
    """
    ATR-based volatility factor.
    From Pine Script: volatility_factor = atr / close
    """
    atr_values = atr(high, low, close, period)
    return atr_values / close


def cumulative_volume_delta(close: pd.Series, volume: pd.Series) -> pd.Series:
    """
    Cumulative Volume Delta (CVD).
    From Pine Script:
        delta_volume = close > close[1] ? volume : close < close[1] ? -volume : 0
        raw_cvd := raw_cvd + delta_volume
    """
    prev_close = close.shift(1)
    delta_volume = np.where(
        close > prev_close, volume,
        np.where(close < prev_close, -volume, 0)
    )
    return pd.Series(delta_volume, index=close.index).cumsum()
