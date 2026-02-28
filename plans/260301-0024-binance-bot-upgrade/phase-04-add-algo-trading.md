# Phase 4: Add Algo Trading API (TWAP, Volume Participation)

## Overview
- **Priority:** P2
- **Status:** Pending
- **Effort:** 8h
- **Dependencies:** Phase 2

## Context Links
- [Algo Trading Introduction](https://developers.binance.com/docs/algo/Introduction)
- [TWAP FAQ](https://www.binance.com/en/support/faq/how-to-use-twap-algorithm-on-binance-futures-093927599fd54fd48857237f6ebec0b0)
- [Volume Participation FAQ](https://www.binance.com/en/support/faq/how-to-use-the-volume-participation-algorithm-on-binance-futures-b0b94dcc8eb64c2585763b8747b60702)

## Key Insights

### Algo Trading Types

#### TWAP (Time-Weighted Average Price)
- Executes order over specified time period
- Slices order into smaller chunks
- Aims for average execution price close to TWAP
- Minimum order size: 10,000 USDT equivalent
- Duration: 5 minutes to 24 hours

#### Volume Participation (VP)
- Executes based on market volume
- Target percentage of market volume (1%-100%)
- Minimizes market impact
- Adaptive to market conditions
- Minimum order size: 10,000 USDT equivalent

### API Endpoints
| Operation | Endpoint | Method |
|-----------|----------|--------|
| TWAP New Order | /sapi/v1/algo/futures/newOrderTwap | POST |
| VP New Order | /sapi/v1/algo/futures/newOrderVp | POST |
| Cancel Order | /sapi/v1/algo/futures/order | DELETE |
| Query Open Orders | /sapi/v1/algo/futures/openOrders | GET |
| Query Historical | /sapi/v1/algo/futures/historicalOrders | GET |
| Query Sub Orders | /sapi/v1/algo/futures/subOrders | GET |

### Limitations
- No WebSocket notifications for algo orders
- Must poll for order status
- Only available on USDS-M Futures
- Minimum 10,000 USDT order size
- `success: true` does not guarantee execution

## Requirements

### Functional
- F1: Create TWAP orders with configurable duration
- F2: Create Volume Participation orders with target percentage
- F3: Query algo order status
- F4: Cancel active algo orders
- F5: Track sub-orders (child orders)
- F6: Support all USDS-M Futures symbols

### Non-Functional
- NF1: Polling mechanism for order status
- NF2: Order tracking in database
- NF3: Clear logging of algo execution progress

## Architecture

### AlgoClient Class
```python
class AlgoClient:
    def __init__(self, config, db, logger, testnet=False):
        self.config = config
        self.db = db
        self.logger = logger
        # Uses same client as Futures
        self.binance_client = Client(...)

    # TWAP methods
    def create_twap_order(self, symbol, side, quantity, duration)
    def cancel_twap_order(self, algo_id)

    # Volume Participation methods
    def create_vp_order(self, symbol, side, quantity, urgency)
    def cancel_vp_order(self, algo_id)

    # Query methods
    def get_open_algo_orders(self)
    def get_historical_algo_orders(self, symbol=None)
    def get_sub_orders(self, algo_id)
```

### Database Model
```python
class AlgoOrder(Base):
    __tablename__ = "algo_orders"
    id = Column(Integer, primary_key=True)
    algo_id = Column(Integer, unique=True)
    algo_type = Column(String)  # TWAP / VP
    symbol = Column(String)
    side = Column(String)
    quantity = Column(Float)
    executed_qty = Column(Float)
    avg_price = Column(Float)
    status = Column(String)
    duration = Column(Integer, nullable=True)  # TWAP
    urgency = Column(String, nullable=True)    # VP
    created_at = Column(DateTime)
    completed_at = Column(DateTime, nullable=True)
```

### Polling Service
```python
class AlgoOrderPoller:
    def __init__(self, algo_client, db, interval=30):
        self.client = algo_client
        self.db = db
        self.interval = interval

    def poll(self):
        """Check status of open algo orders"""
        open_orders = self.db.get_open_algo_orders()
        for order in open_orders:
            status = self.client.get_order_status(order.algo_id)
            self.db.update_algo_order(order.algo_id, status)
```

## Related Code Files

### Files to Create
1. `/binance_trade_bot/clients/algo_client.py`
2. `/binance_trade_bot/models/algo_order.py`
3. `/binance_trade_bot/algo_order_poller.py`
4. `/binance_trade_bot/strategies/algo_strategy.py`

### Files to Modify
1. `/binance_trade_bot/config.py` - Add algo config
2. `/binance_trade_bot/binance_api_manager.py` - Add algo support
3. `/binance_trade_bot/database.py` - Add algo order methods
4. `/binance_trade_bot/crypto_trading.py` - Add poller scheduling

## Implementation Steps

### Step 1: Add Algo Config Options (30 min)
```python
# In config.py
self.ALGO_TYPE = os.environ.get("ALGO_TYPE") or config.get(
    USER_CFG_SECTION, "algo_type", fallback="none")
self.TWAP_DURATION = int(os.environ.get("TWAP_DURATION") or
    config.get(USER_CFG_SECTION, "twap_duration", fallback="300"))  # 5 min
self.VP_URGENCY = os.environ.get("VP_URGENCY") or config.get(
    USER_CFG_SECTION, "vp_urgency", fallback="LOW")  # LOW/MEDIUM/HIGH
```

### Step 2: Create AlgoOrder Model (30 min)
Database model for tracking algo orders and their execution.

### Step 3: Implement AlgoClient (3h)
```python
class AlgoClient:
    def create_twap_order(self, symbol, side, quantity, duration):
        """
        Create TWAP order.
        Args:
            symbol: Trading pair (e.g., BTCUSDT)
            side: BUY or SELL
            quantity: Order quantity
            duration: Duration in seconds (300-86400)
        """
        return self.binance_client._request(
            method="POST",
            path="/sapi/v1/algo/futures/newOrderTwap",
            signed=True,
            data={
                "symbol": symbol,
                "side": side,
                "quantity": quantity,
                "duration": duration,
            }
        )

    def create_vp_order(self, symbol, side, quantity, urgency="LOW"):
        """
        Create Volume Participation order.
        Args:
            symbol: Trading pair
            side: BUY or SELL
            quantity: Order quantity
            urgency: LOW (1-10%), MEDIUM (10-30%), HIGH (30-50%)
        """
        return self.binance_client._request(
            method="POST",
            path="/sapi/v1/algo/futures/newOrderVp",
            signed=True,
            data={
                "symbol": symbol,
                "side": side,
                "quantity": quantity,
                "urgency": urgency,
            }
        )

    def get_open_orders(self):
        return self.binance_client._request(
            method="GET",
            path="/sapi/v1/algo/futures/openOrders",
            signed=True,
        )

    def get_historical_orders(self, symbol=None, start_time=None, end_time=None):
        params = {}
        if symbol:
            params["symbol"] = symbol
        if start_time:
            params["startTime"] = start_time
        if end_time:
            params["endTime"] = end_time
        return self.binance_client._request(
            method="GET",
            path="/sapi/v1/algo/futures/historicalOrders",
            signed=True,
            data=params,
        )

    def cancel_order(self, algo_id):
        return self.binance_client._request(
            method="DELETE",
            path="/sapi/v1/algo/futures/order",
            signed=True,
            data={"algoId": algo_id},
        )

    def get_sub_orders(self, algo_id):
        return self.binance_client._request(
            method="GET",
            path="/sapi/v1/algo/futures/subOrders",
            signed=True,
            data={"algoId": algo_id},
        )
```

### Step 4: Implement AlgoOrderPoller (1h)
Background service to poll algo order status since no WebSocket available.

### Step 5: Create Algo Strategy (1.5h)
Strategy that uses algo orders instead of direct market orders:
```python
class AlgoStrategy(AutoTrader):
    def __init__(self, manager, db, logger, config):
        super().__init__(manager, db, logger, config)
        self.algo_client = AlgoClient(config, db, logger, config.TESTNET)
        self.algo_type = config.ALGO_TYPE

    def execute_trade(self, symbol, side, quantity):
        if self.algo_type == "twap":
            return self.algo_client.create_twap_order(
                symbol, side, quantity, self.config.TWAP_DURATION
            )
        elif self.algo_type == "vp":
            return self.algo_client.create_vp_order(
                symbol, side, quantity, self.config.VP_URGENCY
            )
```

### Step 6: Integration (1h)
- Add poller to scheduler in `crypto_trading.py`
- Update database with algo order methods
- Add algo order tracking to UI (optional)

### Step 7: Testing (30 min)
- Test on futures testnet with minimum viable orders
- Verify order status polling
- Test cancellation

## Todo List

- [x] Add algo config options to `config.py`
- [ ] Create `AlgoOrder` database model (deferred - not needed for core functionality)
- [x] Implement `AlgoClient` with TWAP/VP methods
- [x] Implement order status queries
- [x] Implement order cancellation
- [ ] Create `AlgoOrderPoller` service (deferred - can poll manually in strategy)
- [ ] Create `AlgoStrategy` (not needed - AlgoClient overrides buy_alt/sell_alt)
- [ ] Add poller to main scheduler (deferred)
- [ ] Add algo order database methods (deferred - not needed for core functionality)
- [ ] Test on futures testnet (requires testnet credentials)

## Success Criteria

- [x] Create TWAP order successfully (implemented)
- [x] Create VP order successfully (implemented)
- [x] Query open algo orders (implemented)
- [x] Query historical algo orders (implemented via get_algo_order_status)
- [x] Cancel active algo order (implemented)
- [ ] Poller updates order status correctly (deferred - manual polling available)
- [ ] Orders tracked in database (deferred - not critical for MVP)
- [x] Sub-orders visible for each algo order (implemented)

## Risk Assessment

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Minimum order size not met | High | Medium | Validate before submission |
| Partial execution | Medium | Low | Track executed qty |
| API polling rate limits | Low | Low | Reasonable poll interval |
| Order not filling | Medium | Medium | Timeout and notification |

## Security Considerations

- Algo orders commit significant capital (min 10k USDT)
- Require confirmation for large orders
- Log all algo order activity
- Monitor execution progress
- Alert on stalled orders

## Next Steps

After completion:
1. Phase 5: Testing and Documentation
2. Create advanced algo strategies
3. Add algo order analytics
