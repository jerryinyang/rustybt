# Story 10.6.1: Live Trading Setup Guide

Status: done

## Story

As a **user**,
I want **a comprehensive live trading setup guide**,
So that **I can configure rustybt for live trading on supported platforms**.

## Acceptance Criteria

1. **AC1:** Setup guide covers all supported platforms:
   - Binance (futures and spot)
   - Bybit (perpetual futures)
   - Hyperliquid (DeFi perps)
   - Lighter.xyz (DeFi perps)
   - Interactive Brokers (traditional broker)

2. **AC2:** Step-by-step setup instructions include:
   - Account creation prerequisites
   - API key generation
   - Environment variable configuration
   - Testnet vs mainnet configuration

3. **AC3:** Security best practices are documented:
   - API key permissions (minimal required)
   - Environment variable usage
   - Encrypted keystore option
   - IP whitelisting recommendations

4. **AC4:** Common troubleshooting issues addressed:
   - Connection errors
   - Authentication failures
   - Rate limit errors
   - Order rejection reasons

## Tasks / Subtasks

- [x] Task 1: Create guide file structure (AC: #1)
  - [x] Create `docs/live-trading/setup-guide.md`
  - [x] Create platform-specific sections
  - [x] Add table of contents

- [x] Task 2: Write Binance setup section (AC: #1, #2)
  - [x] Document API key creation
  - [x] Document testnet registration
  - [x] Document environment variables
  - [x] Document testnet/mainnet switching

- [x] Task 3: Write Bybit setup section (AC: #1, #2)
  - [x] Document API key creation
  - [x] Document testnet registration
  - [x] Document environment variables

- [x] Task 4: Write Hyperliquid setup section (AC: #1, #2)
  - [x] Document wallet creation
  - [x] Document private key setup
  - [x] Document testnet usage

- [x] Task 5: Write Lighter.xyz setup section (AC: #1, #2)
  - [x] Document wallet requirements
  - [x] Document private key configuration
  - [x] Document testnet/mainnet URLs

- [x] Task 6: Write Interactive Brokers setup section (AC: #1, #2)
  - [x] Document TWS/Gateway requirements
  - [x] Document paper trading mode
  - [x] Document API permissions

- [x] Task 7: Write security best practices section (AC: #3)
  - [x] Document API key permissions
  - [x] Document environment variable patterns
  - [x] Document encrypted keystore usage
  - [x] Document IP whitelisting

- [x] Task 8: Write troubleshooting section (AC: #4)
  - [x] Common connection errors and fixes
  - [x] Authentication troubleshooting
  - [x] Rate limit handling
  - [x] Order rejection diagnosis

## Dev Notes

### Document Structure

```markdown
# Live Trading Setup Guide

## Overview
Quick introduction to live trading in rustybt

## Prerequisites
- Python 3.12+
- rustybt installed with live trading extras
- Exchange account(s) with API access

## Platform Setup

### Binance
#### Account Setup
#### API Key Configuration
#### Environment Variables
#### Testnet Configuration

### Bybit
...

### Hyperliquid
...

### Lighter.xyz
...

### Interactive Brokers
...

## Security Best Practices
### API Key Permissions
### Environment Variables
### Encrypted Keystores
### IP Whitelisting

## Configuration File
Example YAML configuration

## Troubleshooting
### Connection Issues
### Authentication Errors
### Rate Limiting
### Order Rejections

## Next Steps
Link to first trade tutorial
```

### Security Documentation Points

From NFRs:
- **NFR13**: Never log API keys or private keys
- **NFR14**: Load credentials from environment variables
- **NFR15**: Clear testnet/mainnet separation

Example security section:

```markdown
## Security Best Practices

### Environment Variables (Recommended)
```bash
# Testnet (safe for testing)
export BINANCE_TESTNET_API_KEY="your_testnet_api_key"
export BINANCE_TESTNET_SECRET="your_testnet_secret"

# Mainnet (use with caution)
export BINANCE_API_KEY="your_api_key"
export BINANCE_SECRET="your_secret"
```

### Minimum API Permissions
Only enable the permissions you need:
- Trading: Enable for order submission
- Read: Enable for position/balance queries
- **Withdrawal: NEVER enable**
```

### Architecture Patterns and Constraints

- Guide should reference existing documentation where available
- Include code examples from actual rustybt usage
- Follow MkDocs structure per NFR22

### Prerequisites

- All adapter implementations complete (Epic 10.4, 10.5)
- Testnet validation stories complete (Epic 10.2)

### References

- [Source: docs/internal/sprint-artifacts/epic-10-tech-spec.md#AC-10.6.1]
- [Source: docs/internal/planning/prd-epic-10.md#FR58 - Live trading setup guide]
- [Source: docs/internal/planning/epics/epic-10-live-trading-production-readiness-lighter-xyz-integration.md#Story 10.6.1]

## Dev Agent Record

### Context Reference

- `docs/internal/sprint-artifacts/10-6-1-live-trading-setup-guide.context.xml`

### Agent Model Used

Claude Opus 4.5 (claude-opus-4-5-20251101)

### Debug Log References

- Created comprehensive setup guide covering all 5 supported platforms
- Followed NFR13/14/15 for security documentation patterns
- Included code examples from actual adapter implementations

### Completion Notes List

1. Created `docs/live-trading/setup-guide.md` with comprehensive documentation for all platforms
2. Binance section covers spot/futures, API key generation, testnet/mainnet switching, rate limits
3. Bybit section covers API key setup, category selection (linear/inverse/spot), rate limits
4. Hyperliquid section covers ETH wallet setup, API wallets, encrypted keystores
5. Lighter.xyz section covers dual-key auth model (ETH + API keys), account/key indices
6. Interactive Brokers section covers TWS/Gateway setup, port configuration, paper trading
7. Security section covers API permissions, env vars, encrypted keystores, IP whitelisting
8. Troubleshooting section covers connection errors, auth failures, rate limits, order rejections
9. All acceptance criteria met (AC1-AC4)

### File List

| File | Action | Description |
|------|--------|-------------|
| docs/live-trading/setup-guide.md | Created | Comprehensive live trading setup guide |

## Change Log

| Date | Change | Author |
|------|--------|--------|
| 2025-12-05 | Story drafted from Epic 10 breakdown | SM Agent |
| 2025-12-06 | Implemented all tasks - created comprehensive setup guide | Dev Agent |
| 2025-12-08 | Senior Developer Review - APPROVED | SM Agent |

---

## Senior Developer Review (AI)

### Reviewer
.smirk

### Date
2025-12-08

### Outcome
**APPROVE** ✅

All acceptance criteria fully implemented with comprehensive documentation covering all 5 supported platforms.

### Summary
The Live Trading Setup Guide is a well-structured, comprehensive document covering all required platforms with consistent formatting, complete code examples, and thorough security guidance.

### Key Findings
None - documentation is complete and well-organized.

### Acceptance Criteria Coverage

| AC# | Description | Status | Evidence |
|-----|-------------|--------|----------|
| AC1 | All 5 platforms covered | ✅ IMPLEMENTED | setup-guide.md:54-476 |
| AC2 | Step-by-step setup instructions | ✅ IMPLEMENTED | Each platform section includes prereqs, API key gen, env vars, testnet/mainnet |
| AC3 | Security best practices | ✅ IMPLEMENTED | setup-guide.md:479-568 |
| AC4 | Troubleshooting section | ✅ IMPLEMENTED | setup-guide.md:630-718 |

**Summary:** 4/4 acceptance criteria fully implemented

### Task Completion Validation

| Task | Status | Evidence |
|------|--------|----------|
| Task 1: Guide file structure | ✅ VERIFIED | File exists with TOC |
| Task 2: Binance section | ✅ VERIFIED | Lines 54-133 |
| Task 3: Bybit section | ✅ VERIFIED | Lines 136-201 |
| Task 4: Hyperliquid section | ✅ VERIFIED | Lines 203-309 |
| Task 5: Lighter.xyz section | ✅ VERIFIED | Lines 312-402 |
| Task 6: IB section | ✅ VERIFIED | Lines 405-476 |
| Task 7: Security practices | ✅ VERIFIED | Lines 479-568 |
| Task 8: Troubleshooting | ✅ VERIFIED | Lines 630-718 |

**Summary:** 8/8 completed tasks verified

### Zero-Mock Enforcement
N/A - Documentation story, no code implementation

### Orphaned Files Enforcement
**PASS** - `docs/live-trading/setup-guide.md` is properly placed in the documentation directory

### Test Coverage and Gaps
N/A - Documentation story

### Architectural Alignment
Documentation follows NFR13/14/15 security patterns from tech spec. Consistent with existing documentation structure.

### Security Notes
Documentation correctly emphasizes:
- Never enabling withdrawal permissions
- Environment variable usage for credentials
- Encrypted keystore option for DEX platforms
- IP whitelisting recommendations

### Best-Practices and References
- [MkDocs Documentation Standards](https://www.mkdocs.org/)
- Security best practices align with industry standards

### Action Items
None - story approved for completion
