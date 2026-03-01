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
    Timeframe,
    TF_MAP,
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
    - SHORT when all sell filters pass (futures mode)
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

        # TP/SL settings (as percentage)
        self._tp_percent = self.config.CHIPT_TP_PERCENT
        self._sl_percent = self.config.CHIPT_SL_PERCENT
        self._min_confidence = self.config.CHIPT_MIN_CONFIDENCE

        # Determine if we're in futures mode
        self._is_futures = self.config.TRADE_MARKET.lower() == "futures"

        self.logger.info(f"Mode: {'FUTURES' if self._is_futures else 'SPOT'}")
        self.logger.info(f"Min Confidence: {self._min_confidence}%")
        self.logger.info(f"TP: {self._tp_percent}%, SL: {self._sl_percent}%")
        self.logger.info(f"Filters: momentum={self.config.CHIPT_USE_MOMENTUM_FILTER}, "
                        f"trend={self.config.CHIPT_USE_TREND_FILTER}, "
                        f"volume={self.config.CHIPT_USE_VOLUME_FILTER}, "
                        f"breakout={self.config.CHIPT_USE_BREAKOUT_FILTER}")

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
            self.logger.warning("No trading symbol configured")
            return

        # Status update
        print(
            f"{datetime.now()} - CHIPT - Scouting {symbol} | "
            f"Position: {self._current_position or 'FLAT'} | "
            f"Bar: {self._bar_index}",
            end="\r"
        )

        # 1. Perform MTF analysis
        try:
            trend_analysis = self.mtf_analyzer.analyze(symbol)
        except Exception as e:
            self.logger.error(f"MTF analysis failed: {e}")
            return

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
            return  # Don't evaluate entries while in position

        # 4. Check minimum confidence
        if trend_analysis.system_confidence < self._min_confidence:
            self.logger.debug(
                f"Confidence {trend_analysis.system_confidence}% < "
                f"min {self._min_confidence}%, skipping"
            )
            return

        # 5. Evaluate entry signals (only if flat)
        self._evaluate_entries(symbol, df, trend_analysis)

    def _get_trading_symbol(self) -> Optional[str]:
        """Get the primary trading symbol from config"""
        if self.config.SUPPORTED_COIN_LIST:
            coin_symbol = self.config.SUPPORTED_COIN_LIST[0]
            return f"{coin_symbol}{self.config.BRIDGE_SYMBOL}"
        return None

    def _fetch_ohlcv(self, symbol: str, interval: str, limit: int = 60) -> pd.DataFrame:
        """Fetch OHLCV data from Binance"""
        try:
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

        # Evaluate SELL filters (for SHORT in futures, or exit in spot)
        sell_filters = self.signal_filters.evaluate_sell(
            df, trend_analysis, self._bar_index
        )

        # Log filter results
        self.logger.debug(f"BUY filters: {buy_filters.to_dict()}")
        self.logger.debug(f"SELL filters: {sell_filters.to_dict()}")

        # Execute based on filter results and trend bias
        if buy_filters.all_passed and trend_analysis.is_bullish:
            self._execute_long(symbol, trend_analysis, df['close'].iloc[-1])

        elif sell_filters.all_passed and trend_analysis.is_bearish:
            if self._is_futures:
                self._execute_short(symbol, trend_analysis, df['close'].iloc[-1])
            else:
                self.logger.debug("Bearish signal in SPOT mode - no short available")

    def _execute_long(self, symbol: str, trend_analysis: TrendAnalysis, price: float):
        """Execute LONG entry"""
        self.logger.info("=" * 40)
        self.logger.info(f"SIGNAL: LONG {symbol}")
        self.logger.info(f"Price: {price}")
        self.logger.info(f"Confidence: {trend_analysis.system_confidence}%")
        self.logger.info(f"Trend Strength: {trend_analysis.trend_strength_raw}/7")
        self.logger.info("=" * 40)

        # Get coin objects for trade execution
        coin_symbol = symbol.replace(self.config.BRIDGE_SYMBOL, "")
        origin_coin = Coin(coin_symbol)
        target_coin = self.config.BRIDGE

        # Execute via manager (routes to FuturesClient or SpotClient)
        try:
            result = self.manager.buy_alt(origin_coin, target_coin)

            if result:
                self._current_position = "LONG"
                self._position_entry_price = price

                # Record signal for filter state
                self._record_signal("BUY", trend_analysis)

                self.logger.info(f"LONG position opened at {self._position_entry_price}")
            else:
                self.logger.error("Failed to execute LONG entry - no result")
        except Exception as e:
            self.logger.error(f"Failed to execute LONG entry: {e}")

    def _execute_short(self, symbol: str, trend_analysis: TrendAnalysis, price: float):
        """Execute SHORT entry (futures mode only)"""
        self.logger.info("=" * 40)
        self.logger.info(f"SIGNAL: SHORT {symbol}")
        self.logger.info(f"Price: {price}")
        self.logger.info(f"Confidence: {trend_analysis.system_confidence}%")
        self.logger.info(f"Trend Strength: {trend_analysis.trend_strength_raw}/7")
        self.logger.info("=" * 40)

        # Get coin objects for trade execution
        coin_symbol = symbol.replace(self.config.BRIDGE_SYMBOL, "")
        origin_coin = Coin(coin_symbol)
        target_coin = self.config.BRIDGE

        # Execute via manager (sell_alt opens SHORT in futures mode)
        try:
            result = self.manager.sell_alt(origin_coin, target_coin)

            if result:
                self._current_position = "SHORT"
                self._position_entry_price = price

                # Record signal for filter state
                self._record_signal("SELL", trend_analysis)

                self.logger.info(f"SHORT position opened at {self._position_entry_price}")
            else:
                self.logger.error("Failed to execute SHORT entry - no result")
        except Exception as e:
            self.logger.error(f"Failed to execute SHORT entry: {e}")

    def _record_signal(self, signal: str, trend_analysis: TrendAnalysis):
        """Record signal in filter state"""
        tf = TF_MAP.get(self.filter_config.restrict_tf.upper())
        current_trend = 0
        if tf and tf in trend_analysis.trends:
            current_trend = trend_analysis.trends[tf].trend

        self.signal_filters.record_signal(signal, self._bar_index, current_trend)

    def _manage_position(self, symbol: str, current_price: float):
        """Manage existing position - check TP/SL"""
        if self._position_entry_price <= 0:
            return

        if self._current_position == "LONG":
            pnl_percent = ((current_price - self._position_entry_price) /
                          self._position_entry_price) * 100

            # Take Profit
            if pnl_percent >= self._tp_percent:
                self.logger.info(f"LONG TP hit: +{pnl_percent:.2f}%")
                self._close_position(symbol, "TP")

            # Stop Loss
            elif pnl_percent <= -self._sl_percent:
                self.logger.info(f"LONG SL hit: {pnl_percent:.2f}%")
                self._close_position(symbol, "SL")

        elif self._current_position == "SHORT":
            pnl_percent = ((self._position_entry_price - current_price) /
                          self._position_entry_price) * 100

            # Take Profit
            if pnl_percent >= self._tp_percent:
                self.logger.info(f"SHORT TP hit: +{pnl_percent:.2f}%")
                self._close_position(symbol, "TP")

            # Stop Loss
            elif pnl_percent <= -self._sl_percent:
                self.logger.info(f"SHORT SL hit: {pnl_percent:.2f}%")
                self._close_position(symbol, "SL")

    def _close_position(self, symbol: str, reason: str):
        """Close current position"""
        self.logger.info(f"Closing {self._current_position} position ({reason})")

        coin_symbol = symbol.replace(self.config.BRIDGE_SYMBOL, "")
        origin_coin = Coin(coin_symbol)
        target_coin = self.config.BRIDGE

        try:
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

        except Exception as e:
            self.logger.error(f"Failed to close position: {e}")

    def bridge_scout(self):
        """Override bridge_scout - not used in Chipt strategy"""
        pass
