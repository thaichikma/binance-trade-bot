---
phase: 6
title: "Testing & Calibration"
status: pending
effort: 2h
depends_on: [1, 2, 3, 4, 5]
---

# Phase 6: Testing & Calibration

## Context Links

- [Plan Overview](./plan.md)
- [Backtest Script](/Users/admin/AI/binance-trade-bot/backtest.py)
- [Pine Script Source](/Users/admin/AI/binance-trade-bot/docs/alert.md)

## Overview

Validate the Python implementation against the Pine Script original, run backtests, and calibrate parameters for live trading.

**Priority:** P2
**Status:** pending

## Key Insights

1. Existing `backtest.py` in repo can be extended
2. Pine Script can export alerts/signals for comparison
3. Binance testnet available for paper trading
4. FuturesClient already supports testnet mode

## Requirements

### Functional

- Unit tests for all indicator functions
- Backtest framework with historical data
- Signal comparison with TradingView exports
- Paper trading validation on testnet
- Performance metrics (win rate, Sharpe, drawdown)

### Non-Functional

- Tests run in <30 seconds
- Backtest processes 1 year of data in <5 minutes
- Clear test output with pass/fail indicators

## Architecture

```
binance_trade_bot/
  tests/
    test_indicators.py
    test_multi_timeframe.py
    test_signal_filters.py
    test_chipt_strategy.py
  backtest_chipt.py          # Chipt-specific backtest
```

## Related Code Files

### Files to Create

- `binance_trade_bot/tests/test_indicators.py`
- `binance_trade_bot/tests/test_multi_timeframe.py`
- `binance_trade_bot/tests/test_signal_filters.py`
- `backtest_chipt.py`

### Files to Modify

- None (new test files only)

## Implementation Steps

### 1. Create test_indicators.py

```python
"""
Unit tests for technical indicators.

Validates calculations against known values from TradingView.
"""
import unittest
import pandas as pd
import numpy as np

from binance_trade_bot.analysis.indicators import (
    ema, sma, vwap, rsi, atr,
    pivot_high, pivot_low,
    highest, lowest,
    crossover, crossunder,
)


class TestEMA(unittest.TestCase):
    def test_ema_basic(self):
        """EMA(20) on simple series"""
        data = pd.Series([i for i in range(1, 51)])
        result = ema(data, 20)

        # EMA should be below the linear series
        self.assertLess(result.iloc[-1], data.iloc[-1])
        # But should be trending up
        self.assertGreater(result.iloc[-1], result.iloc[-10])

    def test_ema_nan_handling(self):
        """EMA should produce NaN for insufficient data"""
        data = pd.Series([1, 2, 3])
        result = ema(data, 20)
        # Should still produce values (EMA starts from first value)
        self.assertFalse(result.isna().all())


class TestRSI(unittest.TestCase):
    def test_rsi_overbought(self):
        """RSI should be high on consistent up moves"""
        # Consistently rising prices
        data = pd.Series([100 + i for i in range(30)])
        result = rsi(data, 14)

        # RSI should be very high (overbought)
        self.assertGreater(result.iloc[-1], 70)

    def test_rsi_oversold(self):
        """RSI should be low on consistent down moves"""
        # Consistently falling prices
        data = pd.Series([100 - i for i in range(30)])
        result = rsi(data, 14)

        # RSI should be very low (oversold)
        self.assertLess(result.iloc[-1], 30)

    def test_rsi_range(self):
        """RSI should always be between 0 and 100"""
        np.random.seed(42)
        data = pd.Series(100 + np.random.randn(100).cumsum())
        result = rsi(data, 14)

        valid_values = result.dropna()
        self.assertTrue((valid_values >= 0).all())
        self.assertTrue((valid_values <= 100).all())


class TestATR(unittest.TestCase):
    def test_atr_positive(self):
        """ATR should always be positive"""
        high = pd.Series([105, 106, 107, 108, 109] * 10)
        low = pd.Series([95, 94, 93, 92, 91] * 10)
        close = pd.Series([100, 101, 102, 103, 104] * 10)

        result = atr(high, low, close, 14)
        valid_values = result.dropna()
        self.assertTrue((valid_values > 0).all())


class TestPivots(unittest.TestCase):
    def test_pivot_high_detection(self):
        """Pivot high should detect local maxima"""
        # Create data with clear pivot at index 5
        data = pd.Series([1, 2, 3, 4, 5, 6, 5, 4, 3, 2, 1])
        #                                ^-- pivot at index 5

        result = pivot_high(data, 3, 3)

        # Pivot should be detected at confirmation bar (index 5 + 3 = 8)
        self.assertEqual(result.iloc[8], 6.0)

    def test_pivot_low_detection(self):
        """Pivot low should detect local minima"""
        # Create data with clear pivot at index 5
        data = pd.Series([10, 8, 6, 4, 2, 1, 2, 4, 6, 8, 10])
        #                                ^-- pivot at index 5

        result = pivot_low(data, 3, 3)

        # Pivot should be detected at confirmation bar
        self.assertEqual(result.iloc[8], 1.0)


class TestCrossovers(unittest.TestCase):
    def test_crossover(self):
        """Crossover detection"""
        s1 = pd.Series([1, 2, 3, 4, 5])
        s2 = pd.Series([3, 3, 3, 3, 3])

        result = crossover(s1, s2)

        # Crossover at index 3 (when s1 goes from 3 to 4, crossing 3)
        self.assertTrue(result.iloc[3])
        self.assertFalse(result.iloc[4])

    def test_crossunder(self):
        """Crossunder detection"""
        s1 = pd.Series([5, 4, 3, 2, 1])
        s2 = pd.Series([3, 3, 3, 3, 3])

        result = crossunder(s1, s2)

        # Crossunder at index 3 (when s1 goes from 3 to 2, crossing 3)
        self.assertTrue(result.iloc[3])


if __name__ == '__main__':
    unittest.main()
```

### 2. Create backtest_chipt.py

```python
#!/usr/bin/env python3
"""
Backtest script for Chipt 2026 strategy.

Usage:
    python backtest_chipt.py --symbol BTCUSDT --start 2025-01-01 --end 2025-12-31

Downloads historical data from Binance and simulates strategy execution.
"""
import argparse
from datetime import datetime
from dataclasses import dataclass
from typing import List, Optional
import pandas as pd

from binance.client import Client

from binance_trade_bot.analysis import (
    MultiTimeframeAnalyzer,
    SignalFilters,
    FilterConfig,
    PositionManager,
    PositionConfig,
    PositionSide,
)


@dataclass
class BacktestTrade:
    """Record of a backtest trade"""
    entry_time: datetime
    exit_time: Optional[datetime]
    side: str
    entry_price: float
    exit_price: float
    quantity: float
    pnl: float
    exit_reason: str


@dataclass
class BacktestResult:
    """Backtest results summary"""
    symbol: str
    start_date: str
    end_date: str
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float
    total_pnl: float
    max_drawdown: float
    sharpe_ratio: float
    trades: List[BacktestTrade]


class ChiptBacktester:
    """Backtesting engine for Chipt strategy"""

    def __init__(
        self,
        symbol: str,
        initial_balance: float = 10000.0,
        filter_config: Optional[FilterConfig] = None,
        position_config: Optional[PositionConfig] = None,
    ):
        self.symbol = symbol
        self.initial_balance = initial_balance
        self.balance = initial_balance

        # Initialize components
        self.filter_config = filter_config or FilterConfig()
        self.position_config = position_config or PositionConfig()

        self.signal_filters = SignalFilters(self.filter_config)
        self.position_manager = PositionManager(self.position_config)

        # Binance client for data (no API key needed for klines)
        self.client = Client()

        # Results tracking
        self.trades: List[BacktestTrade] = []
        self.equity_curve: List[float] = []

    def fetch_data(self, start_date: str, end_date: str) -> pd.DataFrame:
        """Fetch historical klines"""
        print(f"Fetching {self.symbol} data from {start_date} to {end_date}...")

        klines = self.client.get_historical_klines(
            self.symbol,
            Client.KLINE_INTERVAL_5MINUTE,
            start_date,
            end_date
        )

        df = pd.DataFrame(klines, columns=[
            'open_time', 'open', 'high', 'low', 'close', 'volume',
            'close_time', 'quote_volume', 'trades', 'taker_buy_base',
            'taker_buy_quote', 'ignore'
        ])

        for col in ['open', 'high', 'low', 'close', 'volume']:
            df[col] = pd.to_numeric(df[col])

        df['open_time'] = pd.to_datetime(df['open_time'], unit='ms')
        df = df.set_index('open_time')

        print(f"Fetched {len(df)} candles")
        return df

    def run(self, start_date: str, end_date: str) -> BacktestResult:
        """Run backtest"""
        df = self.fetch_data(start_date, end_date)

        # We need enough bars for indicator warmup
        warmup = 60
        bar_index = 0

        print(f"Running backtest on {len(df) - warmup} bars...")

        for i in range(warmup, len(df)):
            bar_index += 1
            current_bar = df.iloc[i]
            current_price = current_bar['close']
            current_time = df.index[i]

            # Get slice for indicator calculation
            df_slice = df.iloc[max(0, i-100):i+1]

            # Check existing position
            if not self.position_manager.is_flat:
                result = self.position_manager.update_price(current_price)
                if result:
                    self._close_trade(current_price, current_time, result)

            # Evaluate new entries (simplified - no MTF in backtest)
            if self.position_manager.is_flat:
                self._evaluate_entry(df_slice, bar_index, current_price, current_time)

            # Track equity
            self.equity_curve.append(self.balance)

        # Close any open position at end
        if not self.position_manager.is_flat:
            self._close_trade(df.iloc[-1]['close'], df.index[-1], "END")

        return self._calculate_results(start_date, end_date)

    def _evaluate_entry(self, df: pd.DataFrame, bar_index: int, price: float, time: datetime):
        """Evaluate entry signals (simplified without full MTF)"""
        # Simplified trend detection using EMA
        from binance_trade_bot.analysis.indicators import ema, sma

        close = df['close']
        ema_20 = ema(close, 20).iloc[-1]

        # Simple trend: above EMA = bullish, below = bearish
        is_bullish = price > ema_20
        is_bearish = price < ema_20

        # Volume filter
        volume = df['volume']
        vol_avg = sma(volume, 50).iloc[-1]
        vol_ok = volume.iloc[-1] > vol_avg

        if is_bullish and vol_ok:
            self._open_trade("LONG", price, time)
        elif is_bearish and vol_ok:
            self._open_trade("SHORT", price, time)

    def _open_trade(self, side: str, price: float, time: datetime):
        """Open a new trade"""
        # Calculate position size (simplified)
        position_value = self.balance * 0.5
        quantity = position_value / price

        self.position_manager.open_position(
            PositionSide.LONG if side == "LONG" else PositionSide.SHORT,
            self.symbol,
            price,
            quantity
        )

        self.trades.append(BacktestTrade(
            entry_time=time,
            exit_time=None,
            side=side,
            entry_price=price,
            exit_price=0.0,
            quantity=quantity,
            pnl=0.0,
            exit_reason=""
        ))

    def _close_trade(self, price: float, time: datetime, reason: str):
        """Close current trade"""
        if not self.trades:
            return

        trade = self.trades[-1]
        trade.exit_time = time
        trade.exit_price = price
        trade.exit_reason = reason

        # Calculate PnL
        if trade.side == "LONG":
            trade.pnl = (price - trade.entry_price) * trade.quantity
        else:
            trade.pnl = (trade.entry_price - price) * trade.quantity

        self.balance += trade.pnl
        self.position_manager.close_position(reason, price)

    def _calculate_results(self, start_date: str, end_date: str) -> BacktestResult:
        """Calculate final results"""
        winning = [t for t in self.trades if t.pnl > 0]
        losing = [t for t in self.trades if t.pnl <= 0]

        total_pnl = sum(t.pnl for t in self.trades)
        win_rate = len(winning) / len(self.trades) if self.trades else 0

        # Calculate max drawdown
        peak = self.initial_balance
        max_dd = 0
        for equity in self.equity_curve:
            peak = max(peak, equity)
            dd = (peak - equity) / peak
            max_dd = max(max_dd, dd)

        # Simplified Sharpe (annualized)
        import numpy as np
        if len(self.equity_curve) > 1:
            returns = pd.Series(self.equity_curve).pct_change().dropna()
            sharpe = (returns.mean() / returns.std()) * np.sqrt(252 * 288) if returns.std() > 0 else 0
        else:
            sharpe = 0

        return BacktestResult(
            symbol=self.symbol,
            start_date=start_date,
            end_date=end_date,
            total_trades=len(self.trades),
            winning_trades=len(winning),
            losing_trades=len(losing),
            win_rate=win_rate,
            total_pnl=total_pnl,
            max_drawdown=max_dd,
            sharpe_ratio=sharpe,
            trades=self.trades
        )


def main():
    parser = argparse.ArgumentParser(description="Backtest Chipt 2026 strategy")
    parser.add_argument("--symbol", default="BTCUSDT", help="Trading symbol")
    parser.add_argument("--start", default="2025-01-01", help="Start date (YYYY-MM-DD)")
    parser.add_argument("--end", default="2025-12-31", help="End date (YYYY-MM-DD)")
    parser.add_argument("--balance", type=float, default=10000, help="Initial balance")
    args = parser.parse_args()

    backtester = ChiptBacktester(
        symbol=args.symbol,
        initial_balance=args.balance,
    )

    result = backtester.run(args.start, args.end)

    print("\n" + "=" * 50)
    print("BACKTEST RESULTS")
    print("=" * 50)
    print(f"Symbol: {result.symbol}")
    print(f"Period: {result.start_date} to {result.end_date}")
    print(f"Total Trades: {result.total_trades}")
    print(f"Win Rate: {result.win_rate:.1%}")
    print(f"Total PnL: ${result.total_pnl:.2f}")
    print(f"Max Drawdown: {result.max_drawdown:.1%}")
    print(f"Sharpe Ratio: {result.sharpe_ratio:.2f}")
    print("=" * 50)


if __name__ == "__main__":
    main()
```

### 3. Testing checklist

```markdown
## Manual Testing Checklist

### Unit Tests
- [ ] Run `python -m pytest binance_trade_bot/tests/`
- [ ] All indicator tests pass
- [ ] Filter tests pass
- [ ] Position manager tests pass

### Backtest Validation
- [ ] Run backtest on 1 month of data
- [ ] Compare signal count with TradingView
- [ ] Verify TP/SL exits match expected prices
- [ ] Check drawdown calculation

### Paper Trading (Testnet)
- [ ] Configure testnet in user.cfg
- [ ] Run strategy for 1 hour
- [ ] Verify signals generated
- [ ] Verify positions opened/closed
- [ ] Check logs for filter decisions

### TradingView Comparison
- [ ] Export alerts from TradingView (CSV)
- [ ] Run Python strategy on same period
- [ ] Compare signal timestamps (within 1 bar)
- [ ] Compare signal directions
- [ ] Document any discrepancies
```

## Todo List

- [ ] Create `tests/` directory structure
- [ ] Implement `test_indicators.py`
- [ ] Implement `test_multi_timeframe.py`
- [ ] Implement `test_signal_filters.py`
- [ ] Create `backtest_chipt.py`
- [ ] Run backtest on 1 month of data
- [ ] Compare with TradingView signals
- [ ] Paper trade on testnet for 24h
- [ ] Document calibration results

## Success Criteria

1. All unit tests pass
2. Backtest completes without errors
3. Signal timing within 1 bar of TradingView
4. Paper trading shows expected behavior
5. Performance metrics documented

## Calibration Notes

Parameters to tune based on backtest:

| Parameter | Default | Range | Notes |
|-----------|---------|-------|-------|
| momentum_threshold | 0.01 | 0.005-0.02 | Lower = more signals |
| tp_points | 10 | 5-50 | Asset-dependent |
| sl_points | 10 | 5-50 | Risk tolerance |
| min_signal_distance | 5 | 3-20 | Prevent overtrading |
| higher_tf | 5M | 5M-4H | Filter sensitivity |

## Security Considerations

- Testnet keys only for paper trading
- No real funds until validation complete
- Position size limits in place

## Next Steps

After validation:
1. Deploy to production with small position size
2. Monitor for 1 week
3. Gradually increase position size
4. Document live performance
