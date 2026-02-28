# Planner Report: Binance Trade Bot Upgrade

**Date:** 2026-03-01
**Plan Directory:** `/Users/admin/AI/binance-trade-bot/plans/260301-0024-binance-bot-upgrade/`

## Summary

Created comprehensive implementation plan for upgrading the Binance Trade Bot with:
1. Fixed Spot Testnet Support
2. USDS-Margined Futures Trading
3. Algo Trading API (TWAP, Volume Participation)

## Codebase Analysis

### Current Architecture
- Python trading bot using `python-binance==1.0.27`
- WebSocket via `unicorn-binance-websocket-api`
- SQLite database for persistence
- Strategy pattern for trading logic
- Docker deployment support

### Key Files Analyzed
| File | Lines | Purpose |
|------|-------|---------|
| `binance_api_manager.py` | 380 | Core API wrapper, Spot only |
| `binance_stream_manager.py` | 191 | WebSocket management |
| `auto_trader.py` | 193 | Base trading logic |
| `config.py` | 85 | Configuration handling |
| `database.py` | 296 | SQLite persistence |

### Testnet Issues Found
1. WebSocket manager uses `binance.com-testnet` - needs validation
2. Trade fee API emulation exists but incomplete
3. No futures testnet URL configuration
4. Missing environment logging

## Plan Structure

```
plans/260301-0024-binance-bot-upgrade/
├── plan.md                           # Overview (32h total effort)
├── phase-01-fix-testnet-support.md   # 6h - Fix Spot testnet
├── phase-02-refactor-api-manager.md  # 6h - Multi-market factory
├── phase-03-add-futures-trading.md   # 8h - USDS-M Futures
├── phase-04-add-algo-trading.md      # 8h - TWAP/VP strategies
└── phase-05-testing-and-docs.md      # 4h - Tests & docs
```

## Phase Summary

| Phase | Effort | Key Deliverables |
|-------|--------|------------------|
| 1 | 6h | Testnet URLs, WebSocket fix, validation |
| 2 | 6h | BinanceBaseClient, SpotClient, factory pattern |
| 3 | 8h | FuturesClient, position tracking, leverage config |
| 4 | 8h | AlgoClient, TWAP/VP orders, polling service |
| 5 | 4h | Unit tests, integration tests, documentation |

## Architecture Changes

### Before
Single `BinanceAPIManager` tightly coupled to Spot trading.

### After
Factory pattern with market-specific clients:
- `BinanceBaseClient` (abstract)
- `SpotClient` - Spot market
- `FuturesClient` - USDS-M Futures
- `AlgoClient` - TWAP/VP strategies

## New Configuration Options

```ini
trade_market=spot          # spot | futures
testnet=false
futures_leverage=1         # 1-125
futures_margin_type=CROSSED
algo_type=none             # none | twap | vp
twap_duration=300          # seconds
vp_urgency=LOW             # LOW | MEDIUM | HIGH
```

## Risk Mitigation

| Risk | Mitigation |
|------|------------|
| Futures liquidation | Default 1x leverage, position limits |
| Breaking Spot logic | Comprehensive test suite |
| Algo partial fills | Order tracking, polling service |
| Testnet differences | Extensive testnet validation |

## Sources Referenced

- [Binance Spot Testnet](https://developers.binance.com/docs/binance-spot-api-docs/testnet)
- [USDS-Margined Futures API](https://developers.binance.com/docs/derivatives/usds-margined-futures/general-info)
- [Algo Trading API](https://developers.binance.com/docs/algo/Introduction)
- [python-binance docs](https://python-binance.readthedocs.io/en/latest/)

## Unresolved Questions

1. Does `unicorn-binance-websocket-api` fully support futures testnet WebSockets?
2. Algo Trading API minimum order size (10k USDT) - acceptable for bot use case?
3. Should we add risk management features (stop-loss, take-profit) as separate phase?
4. CI/CD pipeline setup - separate plan or include in Phase 5?
