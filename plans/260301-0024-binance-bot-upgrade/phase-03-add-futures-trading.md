# Phase 3: Add USDS-Margined Futures Trading

## Overview
- **Priority:** P1
- **Status:** Completed
- **Effort:** 8h
- **Dependencies:** Phase 2

## Context Links
- [USDS-Margined Futures General Info](https://developers.binance.com/docs/derivatives/usds-margined-futures/general-info)
- [Futures Trading Endpoints](https://developers.binance.com/docs/derivatives/usds-margined-futures/trade/rest-api)
- [binance-futures-connector-python](https://github.com/binance/binance-futures-connector-python)

## Key Insights

### Futures vs Spot Differences
| Aspect | Spot | Futures |
|--------|------|---------|
| API Base URL | api.binance.com | fapi.binance.com |
| Testnet URL | testnet.binance.vision | testnet.binancefuture.com |
| Leverage | N/A | 1x-125x |
| Margin Type | N/A | CROSSED / ISOLATED |
| Position Side | N/A | LONG / SHORT / BOTH |
| Order Types | LIMIT, MARKET | + STOP, TAKE_PROFIT, etc. |
| Liquidation | N/A | Yes (position risk) |

### python-binance Futures Support
The `python-binance` library supports futures via:
```python
# Futures-specific methods
client.futures_account()
client.futures_position_information()
client.futures_create_order()
client.futures_cancel_order()
client.futures_get_order()
```

### API Endpoints Used
| Operation | Endpoint | Method |
|-----------|----------|--------|
| Account Info | /fapi/v3/account | GET |
| Position Risk | /fapi/v3/positionRisk | GET |
| New Order | /fapi/v1/order | POST |
| Cancel Order | /fapi/v1/order | DELETE |
| Change Leverage | /fapi/v1/leverage | POST |
| Change Margin Type | /fapi/v1/marginType | POST |

## Requirements

### Functional
- F1: Connect to Futures API (production and testnet)
- F2: Set leverage and margin type per symbol
- F3: Open long/short positions
- F4: Close positions (market or limit)
- F5: Monitor position risk and unrealized PnL
- F6: Cancel open orders
- F7: Support USDT-margined futures contracts

### Non-Functional
- NF1: Position size limits to manage risk
- NF2: Automatic stop-loss support
- NF3: Clear position state logging

## Architecture

### FuturesClient Class
```python
class FuturesClient(BinanceBaseClient):
    def __init__(self, config, db, logger, testnet=False):
        super().__init__(config, logger, testnet)
        self.leverage = config.FUTURES_LEVERAGE
        self.margin_type = config.FUTURES_MARGIN_TYPE

    # Core methods
    def get_account(self)
    def get_position(self, symbol: str)
    def get_positions(self)
    def open_position(self, symbol, side, quantity, price=None)
    def close_position(self, symbol, side, quantity=None)
    def set_leverage(self, symbol, leverage)
    def set_margin_type(self, symbol, margin_type)
```

### Futures Stream Manager
```python
class FuturesStreamManager:
    # Subscribe to:
    # - markPrice@arr - Mark prices for all symbols
    # - !userData - Account updates, order updates, position changes
```

### Database Changes
New model for tracking futures positions:
```python
class FuturesPosition(Base):
    __tablename__ = "futures_positions"
    id = Column(Integer, primary_key=True)
    symbol = Column(String)
    side = Column(String)  # LONG/SHORT
    entry_price = Column(Float)
    quantity = Column(Float)
    leverage = Column(Integer)
    unrealized_pnl = Column(Float)
    liquidation_price = Column(Float)
    created_at = Column(DateTime)
    closed_at = Column(DateTime, nullable=True)
```

## Related Code Files

### Files to Create
1. `/binance_trade_bot/clients/futures_client.py`
2. `/binance_trade_bot/futures_stream_manager.py`
3. `/binance_trade_bot/models/futures_position.py`
4. `/binance_trade_bot/strategies/futures_strategy.py`

### Files to Modify
1. `/binance_trade_bot/config.py` - Add futures config
2. `/binance_trade_bot/binance_api_manager.py` - Add futures factory
3. `/binance_trade_bot/database.py` - Add futures position methods
4. `/binance_trade_bot/constants.py` - Add futures URLs

## Implementation Steps

### Step 1: Add Futures Constants (30 min)
```python
# In constants.py
FUTURES_API_URL = "https://fapi.binance.com"
FUTURES_TESTNET_API_URL = "https://testnet.binancefuture.com"
FUTURES_WS_URL = "wss://fstream.binance.com"
FUTURES_TESTNET_WS_URL = "wss://stream.binancefuture.com"
```

### Step 2: Add Futures Config Options (30 min)
```python
# In config.py
self.FUTURES_LEVERAGE = int(os.environ.get("FUTURES_LEVERAGE") or
    config.get(USER_CFG_SECTION, "futures_leverage", fallback="1"))
self.FUTURES_MARGIN_TYPE = os.environ.get("FUTURES_MARGIN_TYPE") or
    config.get(USER_CFG_SECTION, "futures_margin_type", fallback="CROSSED")
```

### Step 3: Create FuturesPosition Model (30 min)
Add to models package for position tracking.

### Step 4: Implement FuturesClient (3h)
Core implementation with:
- Account and position queries
- Order placement (market, limit)
- Leverage and margin type management
- Position closing logic

```python
class FuturesClient(BinanceBaseClient):
    def __init__(self, config, db, logger, testnet=False):
        super().__init__(config, logger, testnet)
        self.binance_client = Client(
            config.BINANCE_API_KEY,
            config.BINANCE_API_SECRET_KEY,
            testnet=testnet,
        )
        # Configure for futures
        self._setup_futures()

    def _setup_futures(self):
        """Configure leverage and margin for tracked symbols"""
        pass

    def get_account(self):
        return self.binance_client.futures_account()

    def get_position(self, symbol: str):
        positions = self.binance_client.futures_position_information(symbol=symbol)
        return positions[0] if positions else None

    def open_long(self, symbol, quantity, price=None):
        order_type = "LIMIT" if price else "MARKET"
        return self.binance_client.futures_create_order(
            symbol=symbol,
            side="BUY",
            type=order_type,
            quantity=quantity,
            price=price,
            timeInForce="GTC" if price else None,
        )

    def open_short(self, symbol, quantity, price=None):
        order_type = "LIMIT" if price else "MARKET"
        return self.binance_client.futures_create_order(
            symbol=symbol,
            side="SELL",
            type=order_type,
            quantity=quantity,
            price=price,
            timeInForce="GTC" if price else None,
        )

    def close_position(self, symbol):
        position = self.get_position(symbol)
        if not position or float(position["positionAmt"]) == 0:
            return None
        quantity = abs(float(position["positionAmt"]))
        side = "SELL" if float(position["positionAmt"]) > 0 else "BUY"
        return self.binance_client.futures_create_order(
            symbol=symbol,
            side=side,
            type="MARKET",
            quantity=quantity,
            reduceOnly=True,
        )
```

### Step 5: Implement FuturesStreamManager (1.5h)
WebSocket streams for futures:
- Mark price updates
- Account/position updates
- Order execution reports

### Step 6: Create Futures Strategy (1h)
Basic strategy that trades futures instead of spot:
```python
class FuturesStrategy(AutoTrader):
    def scout(self):
        # Similar logic but using futures positions
        pass
```

### Step 7: Integration and Testing (1h)
- Test on futures testnet
- Verify position tracking
- Test order execution

## Todo List

- [x] Add futures constants to `constants.py` (Phase 1)
- [x] Add futures config options (Phase 1)
- [ ] Create `FuturesPosition` model (Future phase)
- [x] Implement `FuturesClient` with core methods
- [x] Implement leverage/margin type configuration
- [ ] Create `FuturesStreamManager` (Future phase)
- [ ] Create basic `FuturesStrategy` (Future phase)
- [x] Update `BinanceAPIManager` factory
- [ ] Add futures position tracking to database (Future phase)
- [x] Test on futures testnet

## Success Criteria

- [x] Connect to Futures API (testnet and production)
- [x] Query account balance and positions
- [x] Open long position successfully (implemented)
- [x] Open short position successfully (implemented)
- [x] Close position with market order (implemented)
- [x] Set leverage per symbol
- [x] Set margin type per symbol
- [ ] WebSocket streams receive position updates (Future phase)
- [ ] Position tracking persisted to database (Future phase)

## Risk Assessment

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Liquidation from high leverage | High | Critical | Default 1x leverage, validation |
| Incorrect position sizing | Medium | High | Position size limits |
| API rate limits | Low | Medium | Request throttling |
| Order rejection | Medium | Low | Proper error handling |

## Security Considerations

- Futures trading has liquidation risk
- Implement maximum leverage limits (suggest 5x max)
- Add position size limits as percentage of account
- Log all position changes for audit
- Consider adding stop-loss as default

## Next Steps

After completion:
1. Phase 4: Add Algo Trading API
2. Create futures-specific strategies
3. Add risk management features
