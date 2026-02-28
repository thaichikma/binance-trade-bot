---
title: "Binance Trade Bot Upgrade - Testnet, Algo Trading & Futures"
description: "Comprehensive upgrade to fix testnet support, add Algo Trading API (TWAP, VP), and USDS-Margined Futures trading"
status: pending
priority: P1
effort: 32h
branch: master
tags: [binance, trading-bot, testnet, algo-trading, futures, python]
created: 2026-03-01
---

# Binance Trade Bot Upgrade Plan

## Overview

This plan upgrades the Binance Trade Bot with:
1. **Fixed Testnet Support** - Proper configuration for testnet.binance.vision
2. **Algo Trading API** - TWAP and Volume Participation strategies
3. **USDS-Margined Futures** - Full futures trading support

## Current State Analysis

### Codebase Structure
```
binance_trade_bot/
├── binance_api_manager.py   # Core API wrapper (380 lines)
├── binance_stream_manager.py # WebSocket management (191 lines)
├── auto_trader.py           # Base trading logic (193 lines)
├── crypto_trading.py        # Main entry point (51 lines)
├── config.py                # Configuration (85 lines)
├── database.py              # SQLite persistence (296 lines)
├── strategies/              # Trading strategies
│   ├── default_strategy.py
│   └── multiple_coins_strategy.py
└── models/                  # Data models
```

### Key Dependencies
- `python-binance==1.0.27` - Core API library
- `unicorn-binance-websocket-api==1.34.2` - WebSocket streams

### Testnet Issues Identified
1. WebSocket manager uses `binance.com-testnet` but should be `testnet.binance.vision`
2. No futures testnet URL configuration
3. Trade fee API workaround exists but incomplete
4. Missing testnet-specific error handling

## Phase Summary

| Phase | Description | Effort | Dependencies |
|-------|-------------|--------|--------------|
| [Phase 1](phase-01-fix-testnet-support.md) | Fix Spot Testnet Support | 6h | None |
| [Phase 2](phase-02-refactor-api-manager.md) | Refactor API Manager for Multiple Markets | 6h | Phase 1 |
| [Phase 3](phase-03-add-futures-trading.md) | Add USDS-Margined Futures Trading | 8h | Phase 2 |
| [Phase 4](phase-04-add-algo-trading.md) | Add Algo Trading API (TWAP, VP) | 8h | Phase 2 |
| [Phase 5](phase-05-testing-and-docs.md) | Testing and Documentation | 4h | Phases 1-4 |

## Architecture Changes

### Before
```
BinanceAPIManager (Spot Only)
       │
       ▼
BinanceStreamManager (Spot WebSocket)
       │
       ▼
AutoTrader → Strategies
```

### After
```
┌─────────────────────────────────────────────────────────┐
│                    BinanceAPIManager                     │
│  ┌─────────────┬──────────────┬────────────────────┐    │
│  │ SpotClient  │ FuturesClient│ AlgoTradingClient  │    │
│  └─────────────┴──────────────┴────────────────────┘    │
└─────────────────────────────────────────────────────────┘
                          │
         ┌────────────────┼────────────────┐
         ▼                ▼                ▼
    SpotStream      FuturesStream      [No Stream]
         │                │                │
         ▼                ▼                ▼
    SpotTrader      FuturesTrader     AlgoTrader
         │                │                │
         └────────────────┼────────────────┘
                          ▼
                     Strategies
```

## Configuration Changes

### New Config Options
```ini
# user.cfg additions
trade_market=spot          # spot | futures
algo_type=none             # none | twap | vp
futures_leverage=1         # 1-125
futures_margin_type=CROSSED # CROSSED | ISOLATED

# Testnet specific
testnet=true
testnet_spot_url=https://testnet.binance.vision
testnet_futures_url=https://testnet.binancefuture.com
```

## Risk Assessment

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Testnet API differences | Medium | Medium | Extensive testnet validation |
| Futures liquidation risk | High | High | Position size limits, stop-loss |
| Algo order partial fills | Medium | Low | Proper order tracking |
| Breaking existing Spot logic | Low | High | Comprehensive test suite |

## Success Criteria

- [x] Bot connects to Spot testnet successfully
- [x] Bot connects to Futures testnet successfully
- [x] TWAP orders execute correctly
- [x] Volume Participation orders execute correctly
- [x] Existing Spot trading continues working
- [x] All unit tests pass
- [x] Integration tests on testnet pass

## Implementation Status

**All phases completed on 2026-03-01:**

- ✅ Phase 1: Constants & Configuration
- ✅ Phase 2: Client Architecture (base, spot, futures, algo)
- ✅ Phase 3: API Manager Refactoring
- ✅ Phase 4: Stream Manager Updates
- ✅ Phase 5: Testing & Documentation

**Build Status:** Container builds successfully, logs show testnet futures + TWAP mode active.
