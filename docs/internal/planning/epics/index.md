# rustybt - Epic Breakdown

## Table of Contents

- [rustybt - Epic Breakdown](#table-of-contents)
  - [Overview](./overview.md)
    - [Epic Summary](./overview.md#epic-summary)
  - [Functional Requirements Inventory](./functional-requirements-inventory.md)
  - [FR Coverage Map](./fr-coverage-map.md)
  - [Epic 1: Foundation - Validation Framework Infrastructure](./epic-1-foundation-validation-framework-infrastructure.md)
    - [Story 1.1: Initialize Validation Framework Directory Structure](./epic-1-foundation-validation-framework-infrastructure.md#story-11-initialize-validation-framework-directory-structure)
    - [Story 1.2: Configure Validation Framework Dependencies](./epic-1-foundation-validation-framework-infrastructure.md#story-12-configure-validation-framework-dependencies)
    - [Story 1.3: Implement Core Data Models](./epic-1-foundation-validation-framework-infrastructure.md#story-13-implement-core-data-models)
    - [Story 1.4: Create Test Data Fixture Generator](./epic-1-foundation-validation-framework-infrastructure.md#story-14-create-test-data-fixture-generator)
    - [Story 1.5: Implement Basic Session Manager](./epic-1-foundation-validation-framework-infrastructure.md#story-15-implement-basic-session-manager)
    - [Story 1.6: Create Basic CLI Structure](./epic-1-foundation-validation-framework-infrastructure.md#story-16-create-basic-cli-structure)
    - [Story 1.7: Add Development Setup Documentation](./epic-1-foundation-validation-framework-infrastructure.md#story-17-add-development-setup-documentation)
    - [Story 1.8: Implement Resilience Patterns](./epic-1-foundation-validation-framework-infrastructure.md#story-18-implement-resilience-patterns)
    - [Story 1.9: Configure CI Pipeline with Quality Gates](./epic-1-foundation-validation-framework-infrastructure.md#story-19-configure-ci-pipeline-with-quality-gates)
  - [Epic 2: Strategy Comparison Infrastructure](./epic-2-strategy-comparison-infrastructure.md)
    - [Story 2.1: Implement ValidatedStrategy Base Class for rustybt](./epic-2-strategy-comparison-infrastructure.md#story-21-implement-validatedstrategy-base-class-for-rustybt)
    - [Story 2.2: Implement ValidatedStrategy Base Class for Backtrader](./epic-2-strategy-comparison-infrastructure.md#story-22-implement-validatedstrategy-base-class-for-backtrader)
    - [Story 2.3: Create Log Event Decorators for Custom Logic](./epic-2-strategy-comparison-infrastructure.md#story-23-create-log-event-decorators-for-custom-logic)
    - [Story 2.4: Implement Subprocess Execution Runner](./epic-2-strategy-comparison-infrastructure.md#story-24-implement-subprocess-execution-runner)
    - [Story 2.5: Create Strategy Execution Wrapper Scripts](./epic-2-strategy-comparison-infrastructure.md#story-25-create-strategy-execution-wrapper-scripts)
    - [Story 2.6: Implement Log Schema Validation](./epic-2-strategy-comparison-infrastructure.md#story-26-implement-log-schema-validation)
    - [Story 2.7: Implement Dual Framework Execution Coordinator](./epic-2-strategy-comparison-infrastructure.md#story-27-implement-dual-framework-execution-coordinator)
  - [Epic 3: Session Management System](./epic-3-session-management-system.md)
    - [Story 3.1: Implement Session Progress Tracking](./epic-3-session-management-system.md#story-31-implement-session-progress-tracking)
    - [Story 3.2: Implement Session Resumability](./epic-3-session-management-system.md#story-32-implement-session-resumability)
    - [Story 3.3: Implement Session Query Commands](./epic-3-session-management-system.md#story-33-implement-session-query-commands)
    - [Story 3.4: Implement Duplicate Prevention](./epic-3-session-management-system.md#story-34-implement-duplicate-prevention)
    - [Story 3.5: Implement Session Deletion and Archival](./epic-3-session-management-system.md#story-35-implement-session-deletion-and-archival)
    - [Story 3.6: Implement Timestamped Activity Log](./epic-3-session-management-system.md#story-36-implement-timestamped-activity-log)
  - [Epic 4: 5-Layer Comparison Test Suite](./epic-4-5-layer-comparison-test-suite.md)
    - [Story 4.1: Implement Log Parser with Parquet Caching](./epic-4-5-layer-comparison-test-suite.md#story-41-implement-log-parser-with-parquet-caching)
    - [Story 4.2: Implement Tolerance Configuration System](./epic-4-5-layer-comparison-test-suite.md#story-42-implement-tolerance-configuration-system)
    - [Story 4.3: Implement Layer 1 Data Handling Comparator](./epic-4-5-layer-comparison-test-suite.md#story-43-implement-layer-1-data-handling-comparator)
    - [Story 4.4: Implement Layer 2 Signal Computation Comparator](./epic-4-5-layer-comparison-test-suite.md#story-44-implement-layer-2-signal-computation-comparator)
    - [Story 4.5: Implement Layer 3 Order Lifecycle Comparator](./epic-4-5-layer-comparison-test-suite.md#story-45-implement-layer-3-order-lifecycle-comparator)
    - [Story 4.6: Implement Layer 4 Broker Transaction Comparator](./epic-4-5-layer-comparison-test-suite.md#story-46-implement-layer-4-broker-transaction-comparator)
    - [Story 4.7: Implement Layer 5 Portfolio Returns Comparator](./epic-4-5-layer-comparison-test-suite.md#story-47-implement-layer-5-portfolio-returns-comparator)
    - [Story 4.8: Implement Master Comparison Orchestrator](./epic-4-5-layer-comparison-test-suite.md#story-48-implement-master-comparison-orchestrator)
  - [Epic 5: Investigation & Classification Workflow](./epic-5-investigation-classification-workflow.md)
    - [Story 5.1: Implement Discrepancy Presentation Interface](./epic-5-investigation-classification-workflow.md#story-51-implement-discrepancy-presentation-interface)
    - [Story 5.2: Implement Source Code Linking](./epic-5-investigation-classification-workflow.md#story-52-implement-source-code-linking)
    - [Story 5.3: Implement BUG Classification Workflow](./epic-5-investigation-classification-workflow.md#story-53-implement-bug-classification-workflow)
    - [Story 5.4: Implement DESIGN Classification Workflow](./epic-5-investigation-classification-workflow.md#story-54-implement-design-classification-workflow)
    - [Story 5.5: Implement Bug Fix Verification](./epic-5-investigation-classification-workflow.md#story-55-implement-bug-fix-verification)
    - [Story 5.6: Implement Regression Test Generation](./epic-5-investigation-classification-workflow.md#story-56-implement-regression-test-generation)
    - [Story 5.7: Implement Regression Detection](./epic-5-investigation-classification-workflow.md#story-57-implement-regression-detection)
  - [Epic 6: Initial Strategy Validation (4 Strategies)](./epic-6-initial-strategy-validation-4-strategies.md)
    - [Story 6.1: Implement SMA Crossover Strategy (Dual)](./epic-6-initial-strategy-validation-4-strategies.md#story-61-implement-sma-crossover-strategy-dual)
    - [Story 6.2: Implement Mean Reversion Strategy (Dual)](./epic-6-initial-strategy-validation-4-strategies.md#story-62-implement-mean-reversion-strategy-dual)
    - [Story 6.3: Implement Momentum Strategy (Dual)](./epic-6-initial-strategy-validation-4-strategies.md#story-63-implement-momentum-strategy-dual)
    - [Story 6.4: Implement Multi-Factor Strategy (Dual)](./epic-6-initial-strategy-validation-4-strategies.md#story-64-implement-multi-factor-strategy-dual)
    - [Story 6.5: Execute Full Validation for All 4 Strategies](./epic-6-initial-strategy-validation-4-strategies.md#story-65-execute-full-validation-for-all-4-strategies)
  - [Epic 7: Reporting & Documentation System](./epic-7-reporting-documentation-system.md)
    - [Story 7.1: Implement Session Report Generator](./epic-7-reporting-documentation-system.md#story-71-implement-session-report-generator)
    - [Story 7.2: Implement Layer Report Generator](./epic-7-reporting-documentation-system.md#story-72-implement-layer-report-generator)
    - [Story 7.3: Implement Strategy Report Generator](./epic-7-reporting-documentation-system.md#story-73-implement-strategy-report-generator)
    - [Story 7.4: Implement Overall Status Dashboard](./epic-7-reporting-documentation-system.md#story-74-implement-overall-status-dashboard)
    - [Story 7.5: Implement DESIGN Differences Documentation](./epic-7-reporting-documentation-system.md#story-75-implement-design-differences-documentation)
    - [Story 7.6: Implement Validation Completion Tracking](./epic-7-reporting-documentation-system.md#story-76-implement-validation-completion-tracking)
    - [Story 7.7: Implement Next Actions Recommender](./epic-7-reporting-documentation-system.md#story-77-implement-next-actions-recommender)
  - [Epic 8: User-Facing Documentation & Usage Guide](./epic-8-user-facing-documentation-usage-guide.md)
    - [Story 8.1: Reorganize Documentation Structure (Internal vs User-Facing)](./epic-8-user-facing-documentation-usage-guide.md#story-81-reorganize-documentation-structure-internal-vs-user-facing)
    - [Story 8.2: Create Getting Started Tutorial](./epic-8-user-facing-documentation-usage-guide.md#story-82-create-getting-started-tutorial)
    - [Story 8.3: Create Strategy Implementation Guide](./epic-8-user-facing-documentation-usage-guide.md#story-83-create-strategy-implementation-guide)
    - [Story 8.4: Create Investigation Workflow User Guide](./epic-8-user-facing-documentation-usage-guide.md#story-84-create-investigation-workflow-user-guide)
    - [Story 8.5: Create CLI Reference Documentation](./epic-8-user-facing-documentation-usage-guide.md#story-85-create-cli-reference-documentation)
    - [Story 8.6: Create Python API Reference](./epic-8-user-facing-documentation-usage-guide.md#story-86-create-python-api-reference)
    - [Story 8.7: Create Troubleshooting Guide](./epic-8-user-facing-documentation-usage-guide.md#story-87-create-troubleshooting-guide)
    - [Story 8.8: Create Examples & Recipes Cookbook](./epic-8-user-facing-documentation-usage-guide.md#story-88-create-examples--recipes-cookbook)
    - [Story 8.9: Create Documentation Index and Navigation](./epic-8-user-facing-documentation-usage-guide.md#story-89-create-documentation-index-and-navigation)
  - [Epic X: Real rustybt Engine Integration (CRITICAL)](./epic-X-real-rustybt-engine-integration.md)
    - [Story X.1: Analyze rustybt Engine Integration Points](./epic-X-real-rustybt-engine-integration.md#story-x1-analyze-rustybt-engine-integration-points)
    - [Story X.2: Design Shared Data Fixture Infrastructure](./epic-X-real-rustybt-engine-integration.md#story-x2-design-shared-data-fixture-infrastructure)
    - [Story X.3: Reimplement ValidatedStrategy Base Class](./epic-X-real-rustybt-engine-integration.md#story-x3-reimplement-validatedstrategy-base-class)
    - [Story X.4: Reimplement rustybt Execution Wrapper](./epic-X-real-rustybt-engine-integration.md#story-x4-reimplement-rustybt-execution-wrapper)
    - [Story X.5: Reimplement SMA Crossover Strategy](./epic-X-real-rustybt-engine-integration.md#story-x5-reimplement-sma-crossover-strategy)
    - [Story X.6: Reimplement Remaining 3 Strategies](./epic-X-real-rustybt-engine-integration.md#story-x6-reimplement-remaining-3-strategies)
    - [Story X.7: Verify 5-Layer Comparison Compatibility](./epic-X-real-rustybt-engine-integration.md#story-x7-verify-5-layer-comparison-compatibility)
    - [Story X.8: Update Documentation](./epic-X-real-rustybt-engine-integration.md#story-x8-update-documentation)
  - [Epic 9: Databento Adapter Definition Integration](./epic-9-databento-adapter-definition-integration.md)
    - [Story 9.1: Exploration & Documentation of Existing Infrastructure](./epic-9-databento-adapter-definition-integration.md#story-91-exploration--documentation-of-existing-infrastructure)
    - [Story 9.2: CME Definition Parsing & Schema Understanding](./epic-9-databento-adapter-definition-integration.md#story-92-cme-definition-parsing--schema-understanding)
    - [Story 9.3: CME Data Ingestion & Bundle Verification](./epic-9-databento-adapter-definition-integration.md#story-93-cme-data-ingestion--bundle-verification)
    - [Story 9.4: NASDAQ Definition Parsing & Schema Understanding](./epic-9-databento-adapter-definition-integration.md#story-94-nasdaq-definition-parsing--schema-understanding)
    - [Story 9.5: NASDAQ Data Ingestion & Bundle Verification](./epic-9-databento-adapter-definition-integration.md#story-95-nasdaq-data-ingestion--bundle-verification)
  - [FR Coverage Matrix](./fr-coverage-matrix.md)
  - [Summary](./summary.md)

## Epic Status

| Epic | Status | Completion Date | Notes |
|------|--------|-----------------|-------|
| Epic 1 | Complete | 2025-11-24 | Foundation infrastructure |
| Epic 2 | Complete | 2025-11-24 | Strategy comparison infrastructure |
| Epic 3 | Complete | 2025-11-25 | Session management system |
| Epic 4 | Complete | 2025-11-25 | 5-layer comparison test suite |
| Epic 5 | Complete | 2025-11-26 | Investigation & classification workflow |
| Epic 6 | Complete | 2025-11-27 | Initial strategy validation |
| Epic 7 | Complete | 2025-11-28 | Reporting & documentation system |
| Epic 8 | Complete | 2025-11-28 | User-facing documentation |
| Epic X | In Review | 2025-12-01 | Real rustybt engine integration - critical fix |
| Epic 9 | Draft | - | Databento adapter Definition integration (5 stories) |

### Epic X: Real rustybt Engine Integration

**Status:** Stories X-6 and X-7 in review, X-8 (this story) in progress

**Purpose:** Replaced homebrew broker simulation with actual rustybt TradingAlgorithm integration. This was a critical fix - the original implementation was comparing a custom mock against Backtrader, not validating rustybt's actual behavior.

**Key Changes:**
- Removed `SimulatedPosition`, `_cash`, `_execute_order()` homebrew code
- `RustyBTValidatedStrategy` now uses mixin pattern with rustybt's real APIs
- Strategies use `data.history()`, `order_target_percent()`, `context.portfolio`
- Added ADR-005 documenting this decision

See [Epic X Technical Specification](../sprint-artifacts/tech-spec-epic-X.md) for details.
