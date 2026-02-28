# Algo Trading Guide - TWAP & Volume Participation

## Overview

Binance-trade-bot now supports algorithmic order execution via Binance Futures Algo Trading API. This allows splitting large orders into smaller chunks to minimize market impact and achieve better average prices.

### Supported Algorithms

1. **TWAP (Time-Weighted Average Price)**
   - Executes order over specified time period
   - Slices order into smaller chunks
   - Duration: 5 minutes to 24 hours
   - Minimum: 10,000 USDT equivalent

2. **Volume Participation (VP)**
   - Executes based on market volume percentage
   - Urgency levels: LOW (1-10%), MEDIUM (10-30%), HIGH (30-50%)
   - Adaptive to market conditions
   - Minimum: 10,000 USDT equivalent

## Configuration

### Environment Variables

```bash
TRADE_MARKET=futures    # Must be futures for algo trading
ALGO_TYPE=twap          # Options: twap, vp, none
TWAP_DURATION=600       # 300-86400 seconds (default: 300)
VP_URGENCY=MEDIUM       # LOW, MEDIUM, HIGH (default: LOW)
TESTNET=true            # Use testnet for testing
```

### user.cfg

```ini
[binance_user_config]
trade_market = futures
algo_type = twap
twap_duration = 600
vp_urgency = MEDIUM
```

## Usage

### Automatic Integration

When `algo_type` is set, existing trading code automatically uses algo orders:

```python
from binance_trade_bot.binance_api_manager import BinanceAPIManager

manager = BinanceAPIManager(config, db, logger, testnet=True)

# These automatically use TWAP/VP if algo_type != "none"
manager.buy_alt(btc_coin, usdt_coin)
manager.sell_alt(btc_coin, usdt_coin)
```

### Manual Algo Orders

```python
from binance_trade_bot.clients.algo_client import AlgoClient

algo_client = AlgoClient(config, db, logger, testnet=True)

# TWAP order - execute over 10 minutes
response = algo_client.place_twap_order(
    symbol="BTCUSDT",
    side="BUY",
    quantity=0.5,
    duration=600  # seconds
)
algo_id = response.get('algoId')

# VP order - medium urgency
response = algo_client.place_vp_order(
    symbol="ETHUSDT",
    side="SELL",
    quantity=5.0,
    urgency="MEDIUM"
)

# Check status
status = algo_client.get_algo_order_status(algo_id)
print(f"Status: {status.get('algoStatus')}")
print(f"Executed: {status.get('executedQty')} / {status.get('totalQty')}")

# Get sub-orders (execution details)
sub_orders = algo_client.get_sub_orders(algo_id)

# Cancel if needed
algo_client.cancel_algo_order(algo_id)
```

### Query Orders

```python
# Get all open algo orders
open_orders = algo_client.get_open_algo_orders()

for order in open_orders:
    print(f"Algo ID: {order.get('algoId')}")
    print(f"Symbol: {order.get('symbol')}")
    print(f"Status: {order.get('algoStatus')}")
```

## API Methods

### AlgoClient Methods

| Method | Description | Parameters |
|--------|-------------|------------|
| `place_twap_order()` | Place TWAP order | symbol, side, quantity, duration |
| `place_vp_order()` | Place VP order | symbol, side, quantity, urgency |
| `get_algo_order_status()` | Query order status | algo_id |
| `cancel_algo_order()` | Cancel order | algo_id |
| `get_open_algo_orders()` | Get all open orders | - |
| `get_sub_orders()` | Get execution details | algo_id |

### Overridden Methods

When `algo_type != "none"`, these methods automatically use algo orders:

- `buy_alt()` - Uses TWAP/VP instead of market order
- `sell_alt()` - Uses TWAP/VP instead of market order

## Order Parameters

### TWAP Duration

- **Minimum:** 300 seconds (5 minutes)
- **Maximum:** 86,400 seconds (24 hours)
- **Default:** 300 seconds
- **Config:** `TWAP_DURATION` or `twap_duration`

### VP Urgency

- **LOW:** 1-10% of market volume
- **MEDIUM:** 10-30% of market volume
- **HIGH:** 30-50% of market volume
- **Default:** LOW
- **Config:** `VP_URGENCY` or `vp_urgency`

## Limitations

1. **Minimum Order Size:** 10,000 USDT equivalent
2. **Futures Only:** Algo orders only available on USDT-M Futures
3. **No WebSocket:** Must poll for order status updates
4. **Partial Execution:** `success: true` doesn't guarantee full fill

## Monitoring

Algo orders don't have WebSocket notifications. Poll for status:

```python
import time

algo_id = response.get('algoId')

while True:
    status = algo_client.get_algo_order_status(algo_id)
    algo_status = status.get('algoStatus')

    if algo_status in ['FINISHED', 'CANCELLED', 'FAILED']:
        break

    print(f"Status: {algo_status}")
    print(f"Executed: {status.get('executedQty')} / {status.get('totalQty')}")
    time.sleep(30)  # Poll every 30 seconds
```

## Error Handling

```python
try:
    response = algo_client.place_twap_order("BTCUSDT", "BUY", 0.5, 600)

    if response.get('code') == 0:
        print(f"✓ Order placed: {response.get('algoId')}")
    else:
        print(f"✗ Order failed: {response.get('msg')}")

except ValueError as e:
    # Invalid parameters (duration/urgency)
    print(f"✗ Invalid parameters: {e}")

except Exception as e:
    # API error
    print(f"✗ API error: {e}")
```

## Security Considerations

1. **Large Capital:** Minimum 10,000 USDT per order
2. **Testnet First:** Always test on testnet before production
3. **Monitor Execution:** Poll status regularly
4. **Set Limits:** Validate order sizes before placement
5. **Audit Logs:** All orders logged with details

## Examples

See `examples/algo_trading_example.py` for comprehensive usage examples.

## Troubleshooting

### Order Rejected

**Cause:** Order size below 10,000 USDT minimum
**Solution:** Increase quantity or use standard orders

### API Error: Invalid Duration

**Cause:** Duration outside 300-86400 range
**Solution:** Adjust `TWAP_DURATION` or duration parameter

### No Status Updates

**Cause:** No WebSocket support for algo orders
**Solution:** Poll `get_algo_order_status()` periodically

### Wrong Client Type

**Cause:** `TRADE_MARKET != futures`
**Solution:** Set `TRADE_MARKET=futures` in config

## Testing

### Testnet Setup

1. Get testnet API keys from https://testnet.binancefuture.com
2. Configure environment:
   ```bash
   export TESTNET=true
   export TRADE_MARKET=futures
   export ALGO_TYPE=twap
   export API_KEY=your_testnet_key
   export API_SECRET_KEY=your_testnet_secret
   ```
3. Run examples or bot

### Docker Testing

```bash
docker run --rm \
  -e TESTNET=true \
  -e TRADE_MARKET=futures \
  -e ALGO_TYPE=twap \
  -e API_KEY=your_key \
  -e API_SECRET_KEY=your_secret \
  binance-trade-bot
```

## References

- [Binance Algo Trading Introduction](https://developers.binance.com/docs/algo/Introduction)
- [TWAP FAQ](https://www.binance.com/en/support/faq/how-to-use-twap-algorithm-on-binance-futures-093927599fd54fd48857237f6ebec0b0)
- [Volume Participation FAQ](https://www.binance.com/en/support/faq/how-to-use-the-volume-participation-algorithm-on-binance-futures-b0b94dcc8eb64c2585763b8747b60702)
