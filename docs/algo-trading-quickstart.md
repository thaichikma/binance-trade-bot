# Algo Trading Quick Start

## 1. Enable Algo Trading

**user.cfg:**
```ini
[binance_user_config]
trade_market = futures
algo_type = twap
twap_duration = 600
```

**Or environment:**
```bash
export TRADE_MARKET=futures
export ALGO_TYPE=twap
export TWAP_DURATION=600
```

## 2. Run

```bash
# Existing bot code automatically uses TWAP
python -m binance_trade_bot
```

**That's it!** No code changes needed.

## 3. Manual Orders (Optional)

```python
from binance_trade_bot.clients.algo_client import AlgoClient

algo = AlgoClient(config, db, logger, testnet=True)

# TWAP
response = algo.place_twap_order("BTCUSDT", "BUY", 0.5, 600)

# VP
response = algo.place_vp_order("ETHUSDT", "SELL", 5.0, "MEDIUM")

# Status
status = algo.get_algo_order_status(response['algoId'])
```

## Config Options

| Setting | Values | Default |
|---------|--------|---------|
| algo_type | twap, vp, none | none |
| twap_duration | 300-86400 | 300 |
| vp_urgency | LOW, MEDIUM, HIGH | LOW |

**Note:** Minimum 10,000 USDT per order.

See [algo-trading-guide.md](./algo-trading-guide.md) for full documentation.
