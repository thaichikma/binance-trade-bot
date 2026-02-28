# Binance API URL Constants
# Production and Testnet endpoints for Spot and Futures trading

# ============ SPOT ============
# REST API
SPOT_API_URL = "https://api.binance.com"
SPOT_TESTNET_API_URL = "https://testnet.binance.vision"

# WebSocket Streams
SPOT_WS_URL = "wss://stream.binance.com:9443"
SPOT_TESTNET_WS_URL = "wss://stream.testnet.binance.vision:9443"

# Exchange names for unicorn-binance-websocket-api
SPOT_EXCHANGE = "binance.com"
SPOT_TESTNET_EXCHANGE = "binance.com-testnet"

# ============ FUTURES (USDS-Margined) ============
# REST API
FUTURES_API_URL = "https://fapi.binance.com"
FUTURES_TESTNET_API_URL = "https://testnet.binancefuture.com"

# WebSocket Streams
FUTURES_WS_URL = "wss://fstream.binance.com"
FUTURES_TESTNET_WS_URL = "wss://stream.binancefuture.com"

# Exchange names for unicorn-binance-websocket-api
FUTURES_EXCHANGE = "binance.com-futures"
FUTURES_TESTNET_EXCHANGE = "binance.com-futures-testnet"

# ============ ALGO TRADING ============
# Algo endpoints (uses main API base)
ALGO_FUTURES_TWAP_ENDPOINT = "sapi/v1/algo/futures/newOrderTwap"
ALGO_FUTURES_VP_ENDPOINT = "sapi/v1/algo/futures/newOrderVp"
ALGO_SPOT_TWAP_ENDPOINT = "sapi/v1/algo/spot/newOrderTwap"

# ============ HELPER FUNCTIONS ============

def get_api_url(trade_market: str, testnet: bool) -> str:
    """Get REST API URL based on market type and testnet flag"""
    if trade_market == "futures":
        return FUTURES_TESTNET_API_URL if testnet else FUTURES_API_URL
    return SPOT_TESTNET_API_URL if testnet else SPOT_API_URL


def get_ws_url(trade_market: str, testnet: bool) -> str:
    """Get WebSocket URL based on market type and testnet flag"""
    if trade_market == "futures":
        return FUTURES_TESTNET_WS_URL if testnet else FUTURES_WS_URL
    return SPOT_TESTNET_WS_URL if testnet else SPOT_WS_URL


def get_exchange_name(trade_market: str, testnet: bool, tld: str = "com") -> str:
    """Get exchange name for unicorn-binance-websocket-api"""
    if trade_market == "futures":
        return FUTURES_TESTNET_EXCHANGE if testnet else FUTURES_EXCHANGE

    base = f"binance.{tld}"
    if testnet:
        return f"{base}-testnet"
    return base
