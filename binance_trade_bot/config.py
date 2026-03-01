# Config consts
import configparser
import os

from .models import Coin
from .constants import get_api_url, get_ws_url, get_exchange_name

CFG_FL_NAME = "user.cfg"
USER_CFG_SECTION = "binance_user_config"


class Config:  # pylint: disable=too-few-public-methods,too-many-instance-attributes
    def __init__(self):
        # Init config
        config = configparser.ConfigParser()
        config["DEFAULT"] = {
            "bridge": "USDT",
            "use_margin": "no",
            "scout_multiplier": "5",
            "scout_margin": "0.8",
            "scout_sleep_time": "5",
            "hourToKeepScoutHistory": "1",
            "tld": "com",
            "strategy": "default",
            "sell_timeout": "0",
            "buy_timeout": "0",
            "testnet": False,
            "trade_market": "spot",
            "algo_type": "none",
            "twap_duration": "300",
            "vp_urgency": "LOW",
        }

        if not os.path.exists(CFG_FL_NAME):
            print("No configuration file (user.cfg) found! See README. Assuming default config...")
            config[USER_CFG_SECTION] = {}
        else:
            config.read(CFG_FL_NAME)

        self.BRIDGE_SYMBOL = os.environ.get("BRIDGE_SYMBOL") or config.get(USER_CFG_SECTION, "bridge")
        self.BRIDGE = Coin(self.BRIDGE_SYMBOL, False)
        self.TESTNET = os.environ.get("TESTNET") or config.getboolean(USER_CFG_SECTION, "testnet")

        self.TRADE_MARKET = os.environ.get("TRADE_MARKET") or config.get(USER_CFG_SECTION, "trade_market")
        self.ALGO_TYPE = os.environ.get("ALGO_TYPE") or config.get(USER_CFG_SECTION, "algo_type")
        self.TWAP_DURATION = int(os.environ.get("TWAP_DURATION") or config.get(USER_CFG_SECTION, "twap_duration"))
        self.VP_URGENCY = os.environ.get("VP_URGENCY") or config.get(USER_CFG_SECTION, "vp_urgency")

        # Derived URL configurations (set after TLD is loaded below)
        self._api_url = None
        self._ws_url = None
        self._exchange_name = None

        # Prune settings
        self.SCOUT_HISTORY_PRUNE_TIME = float(
            os.environ.get("HOURS_TO_KEEP_SCOUTING_HISTORY") or config.get(USER_CFG_SECTION, "hourToKeepScoutHistory")
        )

        # Get config for scout
        self.SCOUT_MULTIPLIER = float(
            os.environ.get("SCOUT_MULTIPLIER") or config.get(USER_CFG_SECTION, "scout_multiplier")
        )
        self.SCOUT_SLEEP_TIME = int(
            os.environ.get("SCOUT_SLEEP_TIME") or config.get(USER_CFG_SECTION, "scout_sleep_time")
        )

        # Get config for binance
        self.BINANCE_API_KEY = os.environ.get("API_KEY") or config.get(USER_CFG_SECTION, "api_key")
        self.BINANCE_API_SECRET_KEY = os.environ.get("API_SECRET_KEY") or config.get(USER_CFG_SECTION, "api_secret_key")
        self.BINANCE_TLD = os.environ.get("TLD") or config.get(USER_CFG_SECTION, "tld")

        # Get supported coin list from the environment
        supported_coin_list = [
            coin.strip() for coin in os.environ.get("SUPPORTED_COIN_LIST", "").split() if coin.strip()
        ]
        # Get supported coin list from supported_coin_list file
        if not supported_coin_list and os.path.exists("supported_coin_list"):
            with open("supported_coin_list") as rfh:
                for line in rfh:
                    line = line.strip()
                    if not line or line.startswith("#") or line in supported_coin_list:
                        continue
                    supported_coin_list.append(line)
        self.SUPPORTED_COIN_LIST = supported_coin_list

        self.CURRENT_COIN_SYMBOL = os.environ.get("CURRENT_COIN_SYMBOL") or config.get(USER_CFG_SECTION, "current_coin")

        self.STRATEGY = os.environ.get("STRATEGY") or config.get(USER_CFG_SECTION, "strategy")

        self.SELL_TIMEOUT = os.environ.get("SELL_TIMEOUT") or config.get(USER_CFG_SECTION, "sell_timeout")
        self.BUY_TIMEOUT = os.environ.get("BUY_TIMEOUT") or config.get(USER_CFG_SECTION, "buy_timeout")

        self.USE_MARGIN = os.environ.get("USE_MARGIN") or config.get(USER_CFG_SECTION, "use_margin")
        self.SCOUT_MARGIN = float(os.environ.get("SCOUT_MARGIN") or config.get(USER_CFG_SECTION, "scout_margin"))

        # Chipt Strategy Settings
        self.CHIPT_PIVOT_LENGTH = int(
            os.environ.get("CHIPT_PIVOT_LENGTH") or
            config.get(USER_CFG_SECTION, "chipt_pivot_length", fallback="5")
        )
        self.CHIPT_MOMENTUM_THRESHOLD = float(
            os.environ.get("CHIPT_MOMENTUM_THRESHOLD") or
            config.get(USER_CFG_SECTION, "chipt_momentum_threshold", fallback="0.01")
        )
        self.CHIPT_TP_PERCENT = float(
            os.environ.get("CHIPT_TP_PERCENT") or
            config.get(USER_CFG_SECTION, "chipt_tp_percent", fallback="1.0")
        )
        self.CHIPT_SL_PERCENT = float(
            os.environ.get("CHIPT_SL_PERCENT") or
            config.get(USER_CFG_SECTION, "chipt_sl_percent", fallback="0.5")
        )
        self.CHIPT_MIN_SIGNAL_DISTANCE = int(
            os.environ.get("CHIPT_MIN_SIGNAL_DISTANCE") or
            config.get(USER_CFG_SECTION, "chipt_min_signal_distance", fallback="5")
        )
        self.CHIPT_MIN_CONFIDENCE = float(
            os.environ.get("CHIPT_MIN_CONFIDENCE") or
            config.get(USER_CFG_SECTION, "chipt_min_confidence", fallback="60")
        )
        self.CHIPT_USE_MOMENTUM_FILTER = (
            os.environ.get("CHIPT_USE_MOMENTUM_FILTER", "").lower() == "true" or
            config.getboolean(USER_CFG_SECTION, "chipt_use_momentum_filter", fallback=True)
        )
        self.CHIPT_USE_TREND_FILTER = (
            os.environ.get("CHIPT_USE_TREND_FILTER", "").lower() == "true" or
            config.getboolean(USER_CFG_SECTION, "chipt_use_trend_filter", fallback=True)
        )
        self.CHIPT_USE_VOLUME_FILTER = (
            os.environ.get("CHIPT_USE_VOLUME_FILTER", "").lower() == "true" or
            config.getboolean(USER_CFG_SECTION, "chipt_use_volume_filter", fallback=True)
        )
        self.CHIPT_USE_BREAKOUT_FILTER = (
            os.environ.get("CHIPT_USE_BREAKOUT_FILTER", "").lower() == "true" or
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

        # Initialize derived URL configurations
        self._api_url = get_api_url(self.TRADE_MARKET, self.TESTNET)
        self._ws_url = get_ws_url(self.TRADE_MARKET, self.TESTNET)
        self._exchange_name = get_exchange_name(self.TRADE_MARKET, self.TESTNET, self.BINANCE_TLD)

    @property
    def API_URL(self) -> str:
        """REST API URL based on trade_market and testnet settings"""
        return self._api_url

    @property
    def WS_URL(self) -> str:
        """WebSocket URL based on trade_market and testnet settings"""
        return self._ws_url

    @property
    def EXCHANGE_NAME(self) -> str:
        """Exchange name for unicorn-binance-websocket-api"""
        return self._exchange_name

    def get_environment_info(self) -> str:
        """Return formatted environment info for logging"""
        mode = "TESTNET" if self.TESTNET else "PRODUCTION"
        market = self.TRADE_MARKET.upper()
        algo = self.ALGO_TYPE.upper() if self.ALGO_TYPE != "none" else "DISABLED"
        return f"Mode: {mode} | Market: {market} | Algo: {algo} | API: {self._api_url}"
