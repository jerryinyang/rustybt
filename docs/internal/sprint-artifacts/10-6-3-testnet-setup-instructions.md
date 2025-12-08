# Story 10.6.3: Testnet Setup Instructions

Status: done

## Story

As a **user**,
I want **testnet setup instructions for all supported platforms**,
So that **I can practice live trading without risking real funds**.

## Acceptance Criteria

1. **AC1:** Binance testnet instructions include:
   - Testnet account registration
   - API key generation on testnet
   - Testnet faucet usage
   - Environment variable configuration

2. **AC2:** Bybit testnet instructions include:
   - Testnet account registration
   - API key generation
   - Test fund acquisition
   - Configuration

3. **AC3:** Hyperliquid testnet instructions include:
   - Testnet wallet setup
   - Test fund acquisition
   - Configuration

4. **AC4:** Lighter.xyz testnet instructions include:
   - Testnet wallet requirements
   - Testnet URL configuration
   - Test fund acquisition (if available)

5. **AC5:** Each platform section includes verification steps to confirm setup

## Tasks / Subtasks

- [x] Task 1: Create testnet guide file (AC: #1-5)
  - [x] Create `docs/live-trading/testnet-setup-guide.md`
  - [x] Set up section structure
  - [x] Add table of contents

- [x] Task 2: Write Binance testnet section (AC: #1)
  - [x] Document registration steps with screenshots/links
  - [x] Document API key generation
  - [x] Document faucet usage
  - [x] Document env vars
  - [x] Document verification steps

- [x] Task 3: Write Bybit testnet section (AC: #2)
  - [x] Document registration
  - [x] Document API setup
  - [x] Document test funds
  - [x] Document verification

- [x] Task 4: Write Hyperliquid testnet section (AC: #3)
  - [x] Document wallet setup
  - [x] Document testnet access
  - [x] Document test funds
  - [x] Document verification

- [x] Task 5: Write Lighter.xyz testnet section (AC: #4)
  - [x] Document wallet requirements
  - [x] Document testnet URL
  - [x] Document test funds (if any)
  - [x] Document verification

- [x] Task 6: Write verification section (AC: #5)
  - [x] Include code snippet for connection test
  - [x] Include expected output
  - [x] Include troubleshooting tips

## Dev Notes

### Document Structure

```markdown
# Testnet Setup Guide

## Why Use Testnets?
- Risk-free testing
- Same API behavior as mainnet
- Free test funds

## Binance Testnet

### 1. Create Testnet Account
1. Go to https://testnet.binance.vision/
2. Log in with GitHub account
3. ...

### 2. Generate API Keys
...

### 3. Get Test Funds
Use the testnet faucet at [link]

### 4. Configure Environment
```bash
export BINANCE_TESTNET_API_KEY="your_testnet_key"
export BINANCE_TESTNET_SECRET="your_testnet_secret"
```

### 5. Verify Setup
```python
from rustybt.live.brokers.binance_adapter import BinanceBrokerAdapter

adapter = BinanceBrokerAdapter(testnet=True)
await adapter.connect()
info = await adapter.get_account_info()
print(f"Connected! Balance: {info['balance']}")
```

Expected output:
```
Connected! Balance: 10000.00000000
```

## Bybit Testnet
...

## Hyperliquid Testnet
...

## Lighter.xyz Testnet
...

## Troubleshooting

### "Invalid API key"
Check that you're using testnet keys with testnet=True

### "Insufficient balance"
Request more test funds from the faucet

### "Connection refused"
Verify testnet URL is correct
```

### Testnet URLs and Resources

| Platform | Testnet URL | Faucet |
|----------|-------------|--------|
| Binance | https://testnet.binance.vision/ | Built-in |
| Bybit | https://testnet.bybit.com/ | Account creation |
| Hyperliquid | https://testnet.hyperliquid.xyz/ | Connect wallet |
| Lighter.xyz | https://testnet.zklighter.elliot.ai/ | TBD |

### Verification Code Template

```python
import asyncio
from rustybt.live.brokers.{exchange}_adapter import {Exchange}BrokerAdapter

async def verify_testnet():
    adapter = {Exchange}BrokerAdapter(testnet=True)

    try:
        await adapter.connect()
        print("✓ Connection successful")

        info = await adapter.get_account_info()
        print(f"✓ Account info retrieved: {info}")

        positions = await adapter.get_positions()
        print(f"✓ Position query successful: {len(positions)} positions")

        print("\nTestnet setup verified successfully!")

    except Exception as e:
        print(f"✗ Setup verification failed: {e}")

    finally:
        await adapter.disconnect()

asyncio.run(verify_testnet())
```

### Prerequisites

- Live trading setup guide complete (Story 10.6.1)
- All adapters implement testnet mode

### References

- [Source: docs/internal/sprint-artifacts/epic-10-tech-spec.md#AC-10.6.3]
- [Source: docs/internal/planning/prd-epic-10.md#FR60 - Testnet setup instructions]
- [Source: docs/internal/planning/epics/epic-10-live-trading-production-readiness-lighter-xyz-integration.md#Story 10.6.3]

## Dev Agent Record

### Context Reference

- `docs/internal/sprint-artifacts/10-6-3-testnet-setup-instructions.context.xml`

### Agent Model Used

Claude Opus 4.5 (claude-opus-4-5-20251101)

### Debug Log References

- Found existing comprehensive testnet guide at docs/live-trading/testnet-setup-guide.md
- Enhanced with verification code snippets for each platform
- Added all-in-one verification script for quick testing

### Completion Notes List

1. Enhanced `docs/live-trading/testnet-setup-guide.md` with verification steps
2. Binance section: Complete with GitHub login, API key gen, faucet, env vars, verification code with expected output
3. Bybit section: Complete with registration, API setup, test funds, verification code with expected output
4. Hyperliquid section: Complete with wallet setup, API wallet, testnet access, verification code with expected output
5. Lighter.xyz section: Complete with wallet requirements, testnet URL, verification code with expected output
6. Added comprehensive "Quick Verification Script" that tests all platforms at once
7. Each verification section includes troubleshooting tips for common failures
8. All acceptance criteria met (AC1-AC5)

### File List

| File | Action | Description |
|------|--------|-------------|
| docs/live-trading/testnet-setup-guide.md | Modified | Added verification code for all 4 platforms + all-in-one script |

## Change Log

| Date | Change | Author |
|------|--------|--------|
| 2025-12-05 | Story drafted from Epic 10 breakdown | SM Agent |
| 2025-12-07 | Enhanced testnet guide with verification scripts for all platforms | Dev Agent |
| 2025-12-08 | Senior Developer Review - APPROVED | SM Agent |

---

## Senior Developer Review (AI)

### Reviewer
.smirk

### Date
2025-12-08

### Outcome
**APPROVE** ✅

Comprehensive testnet setup guide with detailed instructions for all 4 platforms plus an all-in-one verification script.

### Summary
The Testnet Setup Guide provides complete step-by-step instructions for obtaining testnet credentials on Hyperliquid, Binance, Bybit, and Lighter.xyz. Each platform section includes verification code with expected output.

### Key Findings
None - documentation is complete and thorough.

### Acceptance Criteria Coverage

| AC# | Description | Status | Evidence |
|-----|-------------|--------|----------|
| AC1 | Binance testnet (registration, API, faucet, env) | ✅ IMPLEMENTED | testnet-setup-guide.md:155-269 |
| AC2 | Bybit testnet (registration, API, funds, config) | ✅ IMPLEMENTED | testnet-setup-guide.md:272-386 |
| AC3 | Hyperliquid testnet (wallet, funds, config) | ✅ IMPLEMENTED | testnet-setup-guide.md:15-154 |
| AC4 | Lighter.xyz testnet (wallet, URL, funds) | ✅ IMPLEMENTED | testnet-setup-guide.md:389-523 |
| AC5 | Verification steps for each platform | ✅ IMPLEMENTED | Each section + all-in-one at 646-761 |

**Summary:** 5/5 acceptance criteria fully implemented

### Task Completion Validation

| Task | Status | Evidence |
|------|--------|----------|
| Task 1: Create testnet guide file | ✅ VERIFIED | File exists with TOC |
| Task 2: Binance testnet section | ✅ VERIFIED | Complete with verification |
| Task 3: Bybit testnet section | ✅ VERIFIED | Complete with verification |
| Task 4: Hyperliquid testnet section | ✅ VERIFIED | Complete with verification |
| Task 5: Lighter.xyz testnet section | ✅ VERIFIED | Complete with verification |
| Task 6: Verification section | ✅ VERIFIED | Per-platform + all-in-one script |

**Summary:** 6/6 completed tasks verified

### Zero-Mock Enforcement
N/A - Documentation story, no code implementation

### Orphaned Files Enforcement
**PASS** - `docs/live-trading/testnet-setup-guide.md` properly placed

### Test Coverage and Gaps
N/A - Documentation story

### Architectural Alignment
Documentation correctly references adapter interfaces and follows security patterns from ADR-003 (testnet first).

### Security Notes
Documentation correctly covers:
- Separate testnet/mainnet credentials
- Key format validation
- IP whitelisting recommendations
- Never committing .env files

### Best-Practices and References
- Step-by-step format with screenshots/links
- Expected output for each verification step
- Troubleshooting tips included

### Action Items
None - story approved for completion
