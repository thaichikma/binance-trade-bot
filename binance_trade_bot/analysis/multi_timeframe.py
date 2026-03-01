"""
Multi-Timeframe Trend Analyzer

Fetches kline data across multiple timeframes and calculates
trend direction, strength, and system confidence.

Matches Pine Script behavior from Chipt 2026 strategy.
"""
import time
from dataclasses import dataclass
from typing import Dict, Tuple, Optional
from enum import Enum

import pandas as pd

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
    "1D": Timeframe.D1,
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

    def get_trend(self, tf_name: str) -> int:
        """Get trend for a specific timeframe by name"""
        tf = TF_MAP.get(tf_name.upper())
        if tf and tf in self.trends:
            return self.trends[tf].trend
        return 0


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
    KLINES_LIMIT = 50  # EMA(20) needs ~20 bars, buffer for VWAP

    def __init__(self, binance_client, logger=None, cache_ttl: int = 30):
        """
        Args:
            binance_client: Initialized Binance client (spot or futures)
            logger: Optional logger instance
            cache_ttl: Cache TTL in seconds (default 30)
        """
        self.client = binance_client
        self.logger = logger
        self._cache_ttl = cache_ttl

        # Simple dict cache with timestamp
        self._kline_cache: Dict[str, Tuple[float, pd.DataFrame]] = {}

    def _log(self, msg: str, debug: bool = True):
        if self.logger:
            if debug:
                self.logger.debug(msg)
            else:
                self.logger.info(msg)

    def _is_cache_valid(self, cache_key: str) -> bool:
        """Check if cached entry is still valid"""
        if cache_key not in self._kline_cache:
            return False
        cached_time, _ = self._kline_cache[cache_key]
        return (time.time() - cached_time) < self._cache_ttl

    def _fetch_klines(self, symbol: str, timeframe: Timeframe) -> pd.DataFrame:
        """
        Fetch klines for a symbol/timeframe, with caching.

        Returns DataFrame with columns: open, high, low, close, volume
        """
        cache_key = f"{symbol}_{timeframe.value}"

        if self._is_cache_valid(cache_key):
            _, df = self._kline_cache[cache_key]
            return df

        try:
            # Check if this is a futures client (has futures_klines method)
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

            # Cache the result
            self._kline_cache[cache_key] = (time.time(), df)
            return df

        except Exception as e:
            self._log(f"Failed to fetch klines for {symbol} {timeframe.value}: {e}", debug=False)
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

        # Determine trend (matching Pine Script logic)
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

    def get_klines_dataframe(self, symbol: str, timeframe: str) -> pd.DataFrame:
        """
        Get klines DataFrame for a symbol/timeframe.

        Useful for additional indicator calculations.

        Args:
            symbol: Trading pair (e.g., "BTCUSDT")
            timeframe: Timeframe name (e.g., "5M", "1H")

        Returns:
            DataFrame with OHLCV data
        """
        tf = TF_MAP.get(timeframe.upper())
        if tf is None:
            return pd.DataFrame()
        return self._fetch_klines(symbol, tf)
