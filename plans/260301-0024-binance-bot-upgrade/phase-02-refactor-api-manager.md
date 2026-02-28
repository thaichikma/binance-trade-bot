# Phase 2: Refactor API Manager for Multiple Markets

## Overview
- **Priority:** P1
- **Status:** Pending
- **Effort:** 6h
- **Dependencies:** Phase 1

## Context Links
- [Binance Futures API Docs](https://developers.binance.com/docs/derivatives/usds-margined-futures/general-info)
- [Algo Trading API Docs](https://developers.binance.com/docs/algo/Introduction)
- Current: `binance_trade_bot/binance_api_manager.py`

## Key Insights

### Current Design Limitations
- `BinanceAPIManager` tightly coupled to Spot trading
- Single `binance_client` instance for all operations
- Hardcoded Spot-specific logic (order types, endpoints)

### Required Changes
- Support multiple market types: Spot, Futures, Algo
- Each market type has different API endpoints and order types
- Need unified interface with market-specific implementations

## Requirements

### Functional
- F1: Single entry point for all market types
- F2: Market type selection via configuration
- F3: Market-specific client initialization
- F4: Shared utility methods (logging, caching)

### Non-Functional
- NF1: Backward compatible with existing Spot code
- NF2: Easy to extend for new market types
- NF3: Clear separation of concerns

## Architecture

### New Module Structure
```
binance_trade_bot/
├── clients/
│   ├── __init__.py
│   ├── base_client.py        # Abstract base class
│   ├── spot_client.py        # Spot market client
│   ├── futures_client.py     # Futures market client
│   └── algo_client.py        # Algo trading client
├── binance_api_manager.py    # Factory/facade
└── ...
```

### Class Hierarchy
```
BinanceBaseClient (ABC)
├── get_account()
├── get_ticker_price()
├── buy()
├── sell()
├── get_balance()
└── get_trade_fees()

     ┌────────────────┬────────────────┐
     ▼                ▼                ▼
SpotClient     FuturesClient    AlgoClient
```

### Factory Pattern
```python
class BinanceAPIManager:
    def __init__(self, config, db, logger):
        self.client = self._create_client(config.TRADE_MARKET)

    def _create_client(self, market_type):
        if market_type == "spot":
            return SpotClient(...)
        elif market_type == "futures":
            return FuturesClient(...)
        # Delegates all calls to underlying client
```

## Related Code Files

### Files to Create
1. `/binance_trade_bot/clients/__init__.py`
2. `/binance_trade_bot/clients/base_client.py`
3. `/binance_trade_bot/clients/spot_client.py`

### Files to Modify
1. `/binance_trade_bot/binance_api_manager.py` - Refactor to use client factory
2. `/binance_trade_bot/config.py` - Add `trade_market` option

## Implementation Steps

### Step 1: Create Base Client Interface (1h)
```python
# clients/base_client.py
from abc import ABC, abstractmethod

class BinanceBaseClient(ABC):
    def __init__(self, config, logger, testnet=False):
        self.config = config
        self.logger = logger
        self.testnet = testnet

    @abstractmethod
    def get_account(self): pass

    @abstractmethod
    def get_ticker_price(self, symbol: str): pass

    @abstractmethod
    def get_currency_balance(self, symbol: str) -> float: pass

    @abstractmethod
    def buy(self, symbol: str, quantity: float, price: float = None): pass

    @abstractmethod
    def sell(self, symbol: str, quantity: float, price: float = None): pass

    @abstractmethod
    def get_trade_fees(self) -> dict: pass
```

### Step 2: Extract Spot Client (2h)
Move existing Spot logic from `BinanceAPIManager` to `SpotClient`:
- Keep all current functionality
- Implement `BinanceBaseClient` interface
- Move WebSocket setup to Spot-specific code

### Step 3: Update BinanceAPIManager (1.5h)
Convert to factory/facade:
```python
class BinanceAPIManager:
    def __init__(self, config, db, logger):
        self.config = config
        self.db = db
        self.logger = logger
        self.client = self._create_client()

    def _create_client(self):
        market = self.config.TRADE_MARKET
        testnet = self.config.TESTNET

        if market == "spot":
            from .clients.spot_client import SpotClient
            return SpotClient(self.config, self.db, self.logger, testnet)
        elif market == "futures":
            from .clients.futures_client import FuturesClient
            return FuturesClient(self.config, self.db, self.logger, testnet)
        else:
            raise ValueError(f"Unknown market type: {market}")

    # Delegate methods to client
    def get_account(self):
        return self.client.get_account()

    def buy_alt(self, origin_coin, target_coin):
        return self.client.buy_alt(origin_coin, target_coin)
    # ... etc
```

### Step 4: Update Config (30 min)
```python
# In config.py
self.TRADE_MARKET = os.environ.get("TRADE_MARKET") or config.get(
    USER_CFG_SECTION, "trade_market"
)
# Validate
if self.TRADE_MARKET not in ("spot", "futures"):
    raise ValueError(f"Invalid trade_market: {self.TRADE_MARKET}")
```

### Step 5: Update Dependencies (30 min)
- Ensure `auto_trader.py` works with refactored manager
- Update strategy classes if needed
- Verify all imports work

### Step 6: Testing (30 min)
- Unit test factory logic
- Integration test Spot trading unchanged
- Test config validation

## Todo List

- [ ] Create `clients/` package structure
- [ ] Define `BinanceBaseClient` abstract class
- [ ] Extract `SpotClient` from `BinanceAPIManager`
- [ ] Refactor `BinanceAPIManager` to factory pattern
- [ ] Add `trade_market` config option
- [ ] Update `auto_trader.py` for new interface
- [ ] Write unit tests for client factory
- [ ] Verify Spot trading still works

## Success Criteria

- [ ] `trade_market=spot` uses `SpotClient`
- [ ] All existing Spot functionality works
- [ ] Factory pattern creates correct client
- [ ] Config validation catches invalid market type
- [ ] Easy to add `FuturesClient` in Phase 3
- [ ] No breaking changes to existing code

## Risk Assessment

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Regression in Spot trading | Medium | High | Comprehensive testing |
| Interface mismatch | Low | Medium | Clear abstract methods |
| Import cycles | Low | Low | Careful module organization |

## Next Steps

After completion:
1. Phase 3: Implement FuturesClient
2. Phase 4: Implement AlgoClient
