# Phase 1: Fix Spot Testnet Support

## Overview
- **Priority:** P1 (Critical)
- **Status:** Pending
- **Effort:** 6h
- **Dependencies:** None

## Context Links
- [Binance Spot Testnet Docs](https://developers.binance.com/docs/binance-spot-api-docs/testnet)
- [WebSocket Streams](https://developers.binance.com/docs/binance-spot-api-docs/testnet/web-socket-streams)
- Current implementation: `binance_trade_bot/binance_api_manager.py`

## Key Insights

### Current Issues
1. **WebSocket URL mismatch**: `unicorn-binance-websocket-api` uses `binance.com-testnet` exchange name, which may not resolve to correct testnet endpoints
2. **REST API**: `python-binance` Client with `testnet=True` should work but needs validation
3. **Missing endpoints**: Some testnet endpoints differ from production (e.g., trade fee API)

### Testnet Configuration
| Service | Production | Testnet |
|---------|------------|---------|
| REST API | api.binance.com | testnet.binance.vision |
| WebSocket Streams | stream.binance.com | stream.testnet.binance.vision |
| WebSocket API | ws-api.binance.com | ws-api.testnet.binance.vision |

### Testnet Limitations
- No trade fee API (`/api/v3/tradeFee`) - must emulate
- Limited trading pairs
- Requires separate testnet API keys from [testnet.binance.vision](https://testnet.binance.vision)

## Requirements

### Functional
- F1: Bot must connect to testnet REST API when `testnet=true`
- F2: Bot must connect to testnet WebSocket streams when `testnet=true`
- F3: All Spot trading functions must work on testnet
- F4: Proper error messages for testnet-specific issues

### Non-Functional
- NF1: No breaking changes to production mode
- NF2: Clear logging of which environment is active
- NF3: Configuration validation on startup

## Architecture

### Component Changes
```
binance_api_manager.py
├── Add testnet URL constants
├── Fix Client initialization
└── Add testnet validation

binance_stream_manager.py
├── Fix exchange name for testnet
└── Add explicit WebSocket URLs

config.py
├── Add testnet URL overrides (optional)
└── Add testnet validation
```

## Related Code Files

### Files to Modify
1. `/Users/admin/AI/binance-trade-bot/binance_trade_bot/binance_api_manager.py`
2. `/Users/admin/AI/binance-trade-bot/binance_trade_bot/binance_stream_manager.py`
3. `/Users/admin/AI/binance-trade-bot/binance_trade_bot/config.py`
4. `/Users/admin/AI/binance-trade-bot/binance_trade_bot/crypto_trading.py`

### Files to Create
1. `/Users/admin/AI/binance-trade-bot/binance_trade_bot/constants.py` - URL constants

## Implementation Steps

### Step 1: Create Constants Module (30 min)
Create `constants.py` with testnet/production URLs:
```python
# REST API URLs
SPOT_API_URL = "https://api.binance.com"
SPOT_TESTNET_API_URL = "https://testnet.binance.vision"

# WebSocket URLs
SPOT_WS_URL = "wss://stream.binance.com:9443"
SPOT_TESTNET_WS_URL = "wss://stream.testnet.binance.vision:9443"

# Exchange names for unicorn-binance-websocket-api
SPOT_EXCHANGE = "binance.com"
SPOT_TESTNET_EXCHANGE = "binance.com-testnet"
```

### Step 2: Update Config (45 min)
Add testnet URL override options and validation:
```python
# In config.py
self.TESTNET = config.getboolean(USER_CFG_SECTION, "testnet")
self.SPOT_API_URL = os.environ.get("SPOT_API_URL") or (
    SPOT_TESTNET_API_URL if self.TESTNET else SPOT_API_URL
)
```

### Step 3: Fix BinanceAPIManager (1.5h)
- Add environment logging on init
- Verify testnet parameter is passed correctly to Client
- Add testnet-specific API fallbacks (trade fee emulation exists, verify it works)

### Step 4: Fix BinanceStreamManager (1.5h)
- Ensure correct exchange name is used: `binance.com-testnet`
- Verify WebSocket connections work with testnet
- Add connection validation and retry logic

### Step 5: Add Startup Validation (1h)
In `crypto_trading.py`:
- Log active environment (testnet/production)
- Validate API keys work before starting
- Check testnet connectivity

### Step 6: Testing (1h)
- Test REST API connectivity on testnet
- Test WebSocket stream connectivity on testnet
- Test basic operations (get account, get ticker)

## Todo List

- [ ] Create `constants.py` with URL definitions
- [ ] Update `config.py` with testnet URL options
- [ ] Verify `BinanceAPIManager` testnet parameter handling
- [ ] Fix `BinanceStreamManager` exchange name logic
- [ ] Add environment logging in `crypto_trading.py`
- [ ] Add testnet connectivity validation
- [ ] Write unit tests for testnet configuration
- [ ] Manual testing on Spot testnet

## Success Criteria

- [ ] `testnet=true` connects to `testnet.binance.vision`
- [ ] WebSocket streams receive data from testnet
- [ ] `get_account()` returns testnet balances
- [ ] `get_ticker_price()` returns testnet prices
- [ ] Trade fee fallback works on testnet
- [ ] Clear "TESTNET MODE" log message on startup
- [ ] Production mode unaffected

## Risk Assessment

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| WebSocket library incompatibility | Medium | High | Test with latest version |
| Testnet API rate limits | Low | Low | Implement backoff |
| Missing testnet pairs | Medium | Medium | Validate supported pairs |

## Security Considerations

- Testnet API keys must not be used on production
- Clear logging to prevent confusion about active environment
- Never commit API keys to repository

## Next Steps

After completion:
1. Proceed to Phase 2: Refactor API Manager
2. Document testnet setup in README
