---
phase: 2
title: "Multi-Timeframe Analyzer"
status: pending
effort: 3h
depends_on: [1]
---

# Phase 2: Multi-Timeframe Analyzer

## Context Links

- [Phase 1: Technical Analysis Module](./phase-01-technical-analysis-module.md)
- [Pine Script Source](/Users/admin/AI/binance-trade-bot/docs/alert.md) (lines 73-100)
- [FuturesClient](/Users/admin/AI/binance-trade-bot/binance_trade_bot/clients/futures_client.py)

## Overview

Implement multi-timeframe trend analysis matching Pine Script's `request.security()` behavior. Fetches klines for 7 timeframes and calculates trend direction per TF.

**Priority:** P1
**Status:** pending

## Key Insights

From Pine Script analysis:

```pinescript
[ema1M, vwap1M] = request.security(syminfo.tickerid, "1", [ta.ema(close, 20), ta.vwap(hlc3)])
trend1M = close > ema1M and close > vwap1M ? 1 : close < ema1M and close < vwap1M ? -1 : 0
trend_strength_raw = trend1M + trend5M + trend15M + trend30M + trend1H + trend4H + trendD
```

1. 7 Timeframes: 1M, 5M, 15M, 30M, 1H, 4H, 1D
2. Per TF: EMA(20) and VWAP
3. Trend = +1 (bullish), -1 (bearish), 0 (neutral)
4. `trend_strength_raw` = sum of all trends (-7 to +7)

## Requirements

### Functional

- Fetch klines for multiple timeframes via Binance API
- Calculate EMA(20) and VWAP per timeframe
- Determine trend direction per timeframe
- Calculate aggregate trend strength (-7 to +7)
- Calculate system confidence (50-90%)

### Non-Functional

- Cache klines to reduce API calls
- Handle API rate limits gracefully
- Thread-safe for potential parallel fetching

## Architecture

```
binance_trade_bot/
  analysis/
    multi_timeframe.py    # MTF analysis class
```

## Related Code Files

### Files to Create

- `binance_trade_bot/analysis/multi_timeframe.py`

### Files to Modify

- `binance_trade_bot/analysis/__init__.py` (add exports)

## Implementation Steps

### 1. Implement multi_timeframe.py

```python
"""
Multi-Timeframe Trend Analyzer

Fetches kline data across multiple timeframes and calculates
trend direction, strength, and system confidence.
"""
import time
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
from enum import Enum

import pandas as pd
from binance.client import Client
from cachetools import TTLCache

from .indicators import ema, vwap


class Timeframe(Enum):
    """Supported timeframes matching Pine Script"""
    M1 = "1m"
    M5 = "5m"
    M15 = "15m"
    M30 = "30m"
    H1 = "1h"
    H4 = "4h"
    D1 = "1d"


# Map config strings to Timeframe enum
TF_MAP = {
    "1M": Timeframe.M1,
    "5M": Timeframe.M5,
    "15M": Timeframe.M15,
    "30M": Timeframe.M30,
    "1H": Timeframe.H1,
    "4H": Timeframe.H4,
    "D": Timeframe.D1,
}


@dataclass
class TimeframeTrend:
    """Trend data for a single timeframe"""
    timeframe: Timeframe
    ema_20: float
    vwap_value: float
    close: float
    trend: int  # +1, 0, -1


@dataclass
class TrendAnalysis:
    """Complete multi-timeframe trend analysis"""
    symbol: str
    timestamp: float
    trends: Dict[Timeframe, TimeframeTrend]
    trend_strength_raw: int  # -7 to +7
    trend_strength_pct: float  # -100 to +100
    system_confidence: float  # 50-90

    @property
    def is_bullish(self) -> bool:
        return self.trend_strength_raw > 0

    @property
    def is_bearish(self) -> bool:
        return self.trend_strength_raw < 0

    @property
    def is_neutral(self) -> bool:
        return self.trend_strength_raw == 0


class MultiTimeframeAnalyzer:
    """
    Analyzes trend across multiple timeframes.

    Matches Pine Script behavior:
    - EMA(20) and VWAP per timeframe
    - Trend = +1 if close > EMA and close > VWAP
    - Trend = -1 if close < EMA and close < VWAP
    - Trend = 0 otherwise (neutral)
    """

    # Timeframes to analyze (matching Pine Script)
    TIMEFRAMES = [
        Timeframe.M1,
        Timeframe.M5,
        Timeframe.M15,
        Timeframe.M30,
        Timeframe.H1,
        Timeframe.H4,
        Timeframe.D1,
    ]

    # Klines needed per timeframe for indicator warm-up
    KLINES_LIMIT = 50  # EMA(20) needs ~20 bars, VWAP needs full session

    def __init__(self, binance_client: Client, logger=None):
        """
        Args:
            binance_client: Initialized Binance client (spot or futures)
            logger: Optional logger instance
        """
        self.client = binance_client
        self.logger = logger

        # Cache klines per (symbol, timeframe) with 30s TTL
        # Shorter TTL for smaller timeframes would be ideal
        self._kline_cache: TTLCache = TTLCache(maxsize=100, ttl=30)

    def _log(self, msg: str):
        if self.logger:
            self.logger.debug(msg)

    def _fetch_klines(self, symbol: str, timeframe: Timeframe) -> pd.DataFrame:
        """
        Fetch klines for a symbol/timeframe, with caching.

        Returns DataFrame with columns: open, high, low, close, volume
        """
        cache_key = (symbol, timeframe.value)

        if cache_key in self._kline_cache:
            return self._kline_cache[cache_key]

        try:
            # Determine which API to use based on symbol suffix
            # Futures symbols end in USDT and we use futures_klines
            klines = self.client.get_klines(
                symbol=symbol,
                interval=timeframe.value,
                limit=self.KLINES_LIMIT
            )

            df = pd.DataFrame(klines, columns=[
                'open_time', 'open', 'high', 'low', 'close', 'volume',
                'close_time', 'quote_volume', 'trades', 'taker_buy_base',
                'taker_buy_quote', 'ignore'
            ])

            # Convert to numeric
            for col in ['open', 'high', 'low', 'close', 'volume']:
                df[col] = pd.to_numeric(df[col], errors='coerce')

            df['open_time'] = pd.to_datetime(df['open_time'], unit='ms')
            df = df.set_index('open_time')

            self._kline_cache[cache_key] = df
            return df

        except Exception as e:
            self._log(f"Failed to fetch klines for {symbol} {timeframe.value}: {e}")
            return pd.DataFrame()

    def _calculate_trend(self, df: pd.DataFrame) -> Tuple[float, float, float, int]:
        """
        Calculate EMA(20), VWAP, and trend for a kline DataFrame.

        Returns: (ema_20, vwap_value, close, trend)
        """
        if df.empty or len(df) < 20:
            return (0.0, 0.0, 0.0, 0)

        close = df['close']
        high = df['high']
        low = df['low']
        volume = df['volume']

        # Calculate indicators
        ema_20 = ema(close, 20).iloc[-1]
        vwap_val = vwap(high, low, close, volume).iloc[-1]
        current_close = close.iloc[-1]

        # Determine trend
        if current_close > ema_20 and current_close > vwap_val:
            trend = 1  # Bullish
        elif current_close < ema_20 and current_close < vwap_val:
            trend = -1  # Bearish
        else:
            trend = 0  # Neutral

        return (ema_20, vwap_val, current_close, trend)

    def analyze(self, symbol: str) -> TrendAnalysis:
        """
        Perform complete multi-timeframe trend analysis.

        Args:
            symbol: Trading pair (e.g., "BTCUSDT")

        Returns:
            TrendAnalysis with trends for all 7 timeframes
        """
        trends: Dict[Timeframe, TimeframeTrend] = {}
        trend_sum = 0

        for tf in self.TIMEFRAMES:
            df = self._fetch_klines(symbol, tf)
            ema_val, vwap_val, close_val, trend = self._calculate_trend(df)

            trends[tf] = TimeframeTrend(
                timeframe=tf,
                ema_20=ema_val,
                vwap_value=vwap_val,
                close=close_val,
                trend=trend
            )
            trend_sum += trend

        # Calculate confidence (matching Pine Script logic)
        confidence = self._calculate_confidence(trend_sum)

        return TrendAnalysis(
            symbol=symbol,
            timestamp=time.time(),
            trends=trends,
            trend_strength_raw=trend_sum,
            trend_strength_pct=(trend_sum / 7) * 100,
            system_confidence=confidence
        )

    def _calculate_confidence(self, trend_strength_raw: int) -> float:
        """
        Calculate system confidence based on trend alignment.

        Matches Pine Script:
        - 90% when all 7 TFs aligned (raw == 7 or -7)
        - 75% when 4+ TFs aligned
        - 60% when 2+ TFs aligned
        - 50% otherwise
        """
        abs_strength = abs(trend_strength_raw)

        if abs_strength == 7:
            return 90.0
        elif abs_strength >= 4:
            return 75.0
        elif abs_strength >= 2:
            return 60.0
        else:
            return 50.0

    def get_trend_for_timeframe(self, symbol: str, tf_name: str) -> int:
        """
        Get trend for a specific timeframe.

        Args:
            symbol: Trading pair
            tf_name: Timeframe name (e.g., "5M", "1H")

        Returns:
            Trend value: +1, 0, or -1
        """
        tf = TF_MAP.get(tf_name.upper())
        if tf is None:
            return 0

        df = self._fetch_klines(symbol, tf)
        _, _, _, trend = self._calculate_trend(df)
        return trend

    def clear_cache(self):
        """Clear the kline cache (e.g., on new candle)"""
        self._kline_cache.clear()
```

### 2. Update analysis/__init__.py

Add new exports:

```python
from .multi_timeframe import (
    MultiTimeframeAnalyzer,
    TrendAnalysis,
    TimeframeTrend,
    Timeframe,
    TF_MAP,
)
```

### 3. Add futures klines support

The above implementation uses `client.get_klines()` which is for spot. For futures, modify to detect and use `futures_klines`:

```python
def _fetch_klines(self, symbol: str, timeframe: Timeframe) -> pd.DataFrame:
    # ... cache check ...

    try:
        # Check if this is a futures client
        if hasattr(self.client, 'futures_klines'):
            klines = self.client.futures_klines(
                symbol=symbol,
                interval=timeframe.value,
                limit=self.KLINES_LIMIT
            )
        else:
            klines = self.client.get_klines(
                symbol=symbol,
                interval=timeframe.value,
                limit=self.KLINES_LIMIT
            )
        # ... rest of processing ...
```

## Todo List

- [ ] Create `multi_timeframe.py` with MTF analyzer class
- [ ] Implement kline fetching with caching
- [ ] Implement trend calculation per timeframe
- [ ] Implement confidence scoring
- [ ] Add futures klines support
- [ ] Update `__init__.py` with new exports
- [ ] Write unit tests for trend calculation
- [ ] Test with real Binance testnet data

## Success Criteria

1. Fetches klines for all 7 timeframes without rate limit errors
2. Trend direction matches TradingView indicator output
3. Confidence scoring matches Pine Script logic exactly
4. Cache reduces API calls by >80% in tight loops
5. Works with both SpotClient and FuturesClient

## Security Considerations

- API keys not exposed in this module (passed via client)
- Cache cleared on session end to prevent stale data
- No persistence of market data

## Next Steps

After completion:
1. Proceed to Phase 3: Signal Filters
2. Signal filters will consume TrendAnalysis output
