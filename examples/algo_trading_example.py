#!/usr/bin/env python3
"""
Example usage of Algo Trading (TWAP/VP) with binance-trade-bot

This demonstrates how to:
1. Configure algo trading
2. Place TWAP orders
3. Place Volume Participation orders
4. Monitor order status
5. Cancel orders
"""

import os
import sys
import time
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from binance_trade_bot.config import Config
from binance_trade_bot.database import Database
from binance_trade_bot.logger import Logger
from binance_trade_bot.clients.algo_client import AlgoClient
from binance_trade_bot.models import Coin


def example_twap_order():
    """Example: Place and monitor a TWAP order"""
    print("\n=== TWAP Order Example ===")

    # Initialize components
    logger = Logger()
    db = Database(logger, "data/crypto_trading.db")
    config = Config()

    # Create AlgoClient (requires TESTNET=true in env)
    algo_client = AlgoClient(config, db, logger, testnet=True)

    # Place TWAP order
    # Note: Minimum 10,000 USDT equivalent required
    symbol = "BTCUSDT"
    side = "BUY"
    quantity = 0.5  # BTC
    duration = 600  # 10 minutes

    print(f"Placing TWAP order: {side} {quantity} {symbol} over {duration}s")

    try:
        response = algo_client.place_twap_order(symbol, side, quantity, duration)

        if response.get('code') == 0:
            algo_id = response.get('algoId')
            print(f"✓ TWAP order placed successfully!")
            print(f"  Algo ID: {algo_id}")

            # Monitor order status
            print("\nMonitoring order status...")
            for i in range(3):
                time.sleep(10)
                status = algo_client.get_algo_order_status(algo_id)
                print(f"  Status: {status.get('algoStatus', 'UNKNOWN')}")
                print(f"  Executed: {status.get('executedQty', 0)} / {status.get('totalQty', 0)}")

            # Get sub-orders
            sub_orders = algo_client.get_sub_orders(algo_id)
            print(f"\n  Sub-orders: {len(sub_orders)}")

        else:
            print(f"✗ Order failed: {response}")

    except Exception as e:
        print(f"✗ Error: {e}")


def example_vp_order():
    """Example: Place and monitor a Volume Participation order"""
    print("\n=== Volume Participation Order Example ===")

    # Initialize components
    logger = Logger()
    db = Database(logger, "data/crypto_trading.db")
    config = Config()

    # Create AlgoClient
    algo_client = AlgoClient(config, db, logger, testnet=True)

    # Place VP order
    symbol = "ETHUSDT"
    side = "SELL"
    quantity = 5.0  # ETH
    urgency = "MEDIUM"  # LOW, MEDIUM, or HIGH

    print(f"Placing VP order: {side} {quantity} {symbol} urgency={urgency}")

    try:
        response = algo_client.place_vp_order(symbol, side, quantity, urgency)

        if response.get('code') == 0:
            algo_id = response.get('algoId')
            print(f"✓ VP order placed successfully!")
            print(f"  Algo ID: {algo_id}")

            # Monitor briefly
            time.sleep(5)
            status = algo_client.get_algo_order_status(algo_id)
            print(f"  Status: {status.get('algoStatus', 'UNKNOWN')}")

        else:
            print(f"✗ Order failed: {response}")

    except Exception as e:
        print(f"✗ Error: {e}")


def example_order_management():
    """Example: Query and cancel algo orders"""
    print("\n=== Order Management Example ===")

    logger = Logger()
    db = Database(logger, "data/crypto_trading.db")
    config = Config()
    algo_client = AlgoClient(config, db, logger, testnet=True)

    # Get all open orders
    print("Fetching open algo orders...")
    open_orders = algo_client.get_open_algo_orders()
    print(f"  Found {len(open_orders)} open orders")

    for order in open_orders:
        print(f"  - Algo ID: {order.get('algoId')}")
        print(f"    Symbol: {order.get('symbol')}")
        print(f"    Side: {order.get('side')}")
        print(f"    Status: {order.get('algoStatus')}")

    # Cancel an order (example)
    if open_orders:
        first_order = open_orders[0]
        algo_id = first_order.get('algoId')

        print(f"\nCanceling order {algo_id}...")
        try:
            result = algo_client.cancel_algo_order(algo_id)
            if result.get('code') == 0:
                print("✓ Order canceled successfully")
            else:
                print(f"✗ Cancellation failed: {result}")
        except Exception as e:
            print(f"✗ Error: {e}")


def example_automatic_integration():
    """Example: Automatic algo trading via BinanceAPIManager"""
    print("\n=== Automatic Integration Example ===")

    # When algo_type is set in config, BinanceAPIManager
    # automatically uses AlgoClient instead of FuturesClient

    logger = Logger()
    db = Database(logger, "data/crypto_trading.db")
    config = Config()

    # Check current algo configuration
    print(f"Trade Market: {config.TRADE_MARKET}")
    print(f"Algo Type: {config.ALGO_TYPE}")
    print(f"TWAP Duration: {config.TWAP_DURATION}s")
    print(f"VP Urgency: {config.VP_URGENCY}")

    from binance_trade_bot.binance_api_manager import BinanceAPIManager

    # This will automatically create AlgoClient if:
    # - TRADE_MARKET = futures
    # - ALGO_TYPE != none
    manager = BinanceAPIManager(config, db, logger, testnet=True)

    print(f"\nClient type: {type(manager.client).__name__}")

    # These methods automatically use algo orders when configured
    btc = Coin("BTC", False)
    usdt = Coin("USDT", False)

    print("\nExample: manager.buy_alt(btc, usdt)")
    print("  → Uses TWAP/VP if algo_type != 'none'")
    print("  → Uses standard futures order if algo_type == 'none'")


if __name__ == "__main__":
    print("=" * 60)
    print("Binance Algo Trading Examples")
    print("=" * 60)
    print("\nNOTE: These examples require:")
    print("  - TESTNET=true")
    print("  - TRADE_MARKET=futures")
    print("  - Valid Binance Futures testnet credentials")
    print("  - Minimum 10,000 USDT equivalent order size")
    print("=" * 60)

    # Check environment
    if not os.getenv("TESTNET"):
        print("\n⚠ WARNING: TESTNET not set. Examples may fail or use real funds!")
        print("Set TESTNET=true in environment or user.cfg")

    # Run examples (commented out to prevent accidental execution)
    # Uncomment to test:

    # example_automatic_integration()
    # example_twap_order()
    # example_vp_order()
    # example_order_management()

    print("\n✓ Example script loaded successfully")
    print("Uncomment function calls to run examples")
