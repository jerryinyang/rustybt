# Epic 8: User-Facing Documentation & Usage Guide

**Goal:** Enable users to effectively use the rustybt validation framework through comprehensive, accessible documentation that guides them from first-time setup through advanced usage patterns, while properly separating internal development artifacts from public documentation.

**Value Delivered:** Users (individual traders, researchers, institutions, community contributors) can:
- Access clean, organized documentation without internal development noise
- Start using the validation framework immediately with step-by-step guidance
- Implement and validate their own strategies
- Investigate and classify discrepancies effectively
- Troubleshoot common issues independently
- Extend the framework with new strategies or layers

**Stories:** 9

**FRs Covered:** Extends FR65 (user-facing documentation) and addresses documentation gaps not covered by automated reporting in Epic 7

---

## Story 8.1: Reorganize Documentation Structure (Internal vs User-Facing)

As a **project maintainer**,
I want a **clear separation between internal development documentation and user-facing documentation**,
So that I can **protect confidential information, maintain documentation quality, and provide users with a clean experience**.

**Acceptance Criteria:**

**Given** the current mixed documentation structure in `/docs`
**When** the reorganization is complete
**Then**:
- Internal documents are in a dedicated `docs/internal/` directory (or similar protected location)
- User-facing documents are in the main `docs/` directory with clear structure
- Documentation generation configs (YAML files) are updated to reflect the new structure
- No internal/confidential content is exposed in user-facing docs
- All internal cross-references are updated and functional
- All user-facing cross-references are updated and functional

**And** the following are classified as **INTERNAL** (moved to protected location):
- PRD documents (`prd.md`, sharded PRD folders)
- Architecture documents (`architecture.md`, architecture decision records)
- Epic breakdown files (`epics/` folder with all stories)
- Sprint artifacts (`sprint-artifacts/` folder)
- Implementation readiness reports
- BMM workflow status and index files (`bmm-*.yaml`, `bmm-*.md`)
- Project scan reports (`project-scan-report.json`)
- Test design system documents
- Any files containing business strategy, timelines, or internal discussions

**And** the following remain/become **USER-FACING**:
- Getting started guides
- API reference documentation
- User guides and tutorials
- Examples and cookbook
- Contributing guidelines
- Migration guides
- Performance documentation (user-relevant portions)
- Validation framework usage documentation

**And** the documentation generation is updated:
- MkDocs/pdoc/Sphinx config files updated for new paths
- `.gitignore` updated if internal docs should not be in public repo
- CI/CD documentation build pipelines updated
- Links from README and other entry points updated

**Prerequisites:** Epics 1-7 complete (framework built)

**Technical Notes:**
- Proposed structure:
  ```
  docs/
  ├── internal/                    # INTERNAL (protected)
  │   ├── planning/               # PRD, architecture, epics
  │   │   ├── prd.md
  │   │   ├── architecture.md
  │   │   └── epics/
  │   ├── sprint-artifacts/       # Sprint tracking
  │   ├── reports/                # Implementation reports, audits
  │   └── design/                 # Test design, system design
  ├── about/                      # USER-FACING
  ├── api/                        # USER-FACING
  ├── getting-started/            # USER-FACING
  ├── guides/                     # USER-FACING
  ├── validation/                 # USER-FACING (new validation docs)
  ├── examples/                   # USER-FACING
  ├── contributing/               # USER-FACING
  └── index.md                    # USER-FACING entry point
  ```
- Consider whether `docs/internal/` should be:
  - In `.gitignore` (not in public repo at all)
  - In a separate branch
  - In the repo but excluded from doc generation
- Update all relative links after move
- Run link checker after reorganization
- Preserve git history with `git mv` where possible

---

## Story 8.2: Create Getting Started Tutorial

As a **new user**,
I want a **step-by-step getting started tutorial**,
So that I can **run my first validation session within 15 minutes**.

**Acceptance Criteria:**

**Given** a developer with Python 3.12+ installed and no prior rustybt-validation experience
**When** they follow the getting started guide
**Then** they can:
- Install the validation framework and dependencies
- Create their first validation session
- Execute a simple validation (SMA Crossover strategy)
- View validation results
- Understand next steps

**And** the guide includes:
- Prerequisites checklist (Python version, git, pip/uv)
- Installation commands (including Backtrader setup)
- Verification commands to confirm successful installation
- Quick start example with expected output
- Common installation troubleshooting

**Prerequisites:** Story 8.1 (docs reorganized)

**Technical Notes:**
- Located at `docs/validation/getting-started.md`
- Include copy-pasteable commands
- Show expected terminal output for each step
- Link to deeper documentation for each topic
- Test the guide on a fresh environment before shipping

---

## Story 8.3: Create Strategy Implementation Guide

As a **validation framework user**,
I want a **comprehensive strategy implementation guide**,
So that I can **add my own strategies to the validation suite**.

**Acceptance Criteria:**

**Given** a user who wants to validate a custom strategy
**When** they follow the strategy implementation guide
**Then** they can:
- Understand the dual-implementation requirement (rustybt + Backtrader)
- Create a new strategy using ValidatedStrategy base classes
- Implement identical logic in both frameworks
- Audit their implementations for logical equivalence
- Run validation and interpret results

**And** the guide includes:
- Template files for both rustybt and Backtrader strategies
- Step-by-step walkthrough of implementing a strategy (with a concrete example)
- Strategy audit checklist with pass/fail criteria
- Common pitfalls and how to avoid them (timing differences, indicator libraries)
- Testing your strategy before adding to validation suite

**Prerequisites:** Story 8.2

**Technical Notes:**
- Located at `docs/validation/strategy-implementation-guide.md`
- Include complete working examples (not just snippets)
- Reference the log schema and required events
- Link to ValidatedStrategy API reference
- Show before/after for common mistakes

---

## Story 8.4: Create Investigation Workflow User Guide

As a **validation framework user**,
I want an **investigation workflow user guide**,
So that I can **properly investigate and classify discrepancies**.

**Acceptance Criteria:**

**Given** a user who has run validation and discovered discrepancies
**When** they follow the investigation workflow guide
**Then** they understand:
- How to read discrepancy reports
- How to use the investigation CLI commands
- When to classify as BUG vs DESIGN
- How to document their investigation rationale
- How to verify bug fixes and mark findings as resolved

**And** the guide includes:
- Decision tree for BUG vs DESIGN classification
- Real examples of BUG findings (with investigation walkthrough)
- Real examples of DESIGN findings (with documentation approach)
- Investigation best practices (reproducibility, evidence gathering)
- Tips for source code linking and root cause analysis

**Prerequisites:** Story 8.2

**Technical Notes:**
- Located at `docs/validation/investigation-guide.md`
- Include screenshots/examples of CLI investigation interface
- Reference actual findings from Epic 6 strategy validation (if available)
- Provide templates for investigation notes
- Cross-reference with DESIGN differences documentation

---

## Story 8.5: Create CLI Reference Documentation

As a **validation framework user**,
I want **complete CLI reference documentation**,
So that I can **use all available commands effectively**.

**Acceptance Criteria:**

**Given** a user who needs to perform any validation task via CLI
**When** they consult the CLI reference
**Then** they find:
- Complete list of all commands and subcommands
- Syntax and options for each command
- Examples of common usage patterns
- Output format descriptions

**And** the documentation includes:
- `rustybt-validate session` commands (create, list, show, resume, delete)
- `rustybt-validate run` commands (execute validation)
- `rustybt-validate investigate` commands (review findings, classify)
- `rustybt-validate report` commands (generate reports)
- `rustybt-validate status` commands (overall validation status)
- Global options and environment variables

**Prerequisites:** Story 8.2

**Technical Notes:**
- Located at `docs/validation/cli-reference.md`
- Generated from Click command decorators where possible
- Include exit codes and error messages
- Show common command sequences (pipelines)
- Keep in sync with actual CLI implementation

---

## Story 8.6: Create Python API Reference

As a **developer integrating validation programmatically**,
I want **complete Python API reference documentation**,
So that I can **use the validation framework in scripts and CI/CD pipelines**.

**Acceptance Criteria:**

**Given** a developer who wants to integrate validation into their workflow
**When** they consult the Python API reference
**Then** they find:
- All public classes and functions documented
- Type signatures and parameter descriptions
- Return value descriptions
- Usage examples for common patterns

**And** the documentation covers:
- `SessionManager` API (create, load, query sessions)
- `run_validation()` and execution APIs
- `Comparator` classes (per-layer comparison)
- `Finding` and `Discrepancy` data models
- `ReportGenerator` API (programmatic report generation)
- Configuration loading and tolerance APIs

**Prerequisites:** Story 8.2

**Technical Notes:**
- Located at `docs/validation/api-reference.md`
- Use docstrings as source of truth (ensure docstrings are complete)
- Include type annotations in documentation
- Show integration examples (pytest fixtures, CI pipelines)
- Cross-reference with CLI for equivalent operations

---

## Story 8.7: Create Troubleshooting Guide

As a **validation framework user encountering issues**,
I want a **troubleshooting guide**,
So that I can **resolve common problems independently**.

**Acceptance Criteria:**

**Given** a user who encounters an error or unexpected behavior
**When** they consult the troubleshooting guide
**Then** they find:
- Description of the problem
- Likely causes
- Step-by-step resolution
- When to escalate or report a bug

**And** the guide covers:
- Installation issues (dependency conflicts, version mismatches)
- Strategy execution failures (subprocess errors, log generation issues)
- Log parsing errors (schema violations, incomplete logs)
- Comparison failures (tolerance configuration, missing data)
- Session management issues (corrupted sessions, resume failures)
- Common error messages and their meanings

**Prerequisites:** Stories 8.2-8.6

**Technical Notes:**
- Located at `docs/validation/troubleshooting.md`
- Organize by symptom (what the user sees) not by cause
- Include error message text for searchability
- Provide diagnostic commands users can run
- Keep updated as new issues are discovered

---

## Story 8.8: Create Examples & Recipes Cookbook

As a **validation framework user**,
I want an **examples and recipes cookbook**,
So that I can **learn from real-world usage patterns**.

**Acceptance Criteria:**

**Given** a user who wants to accomplish a specific validation task
**When** they consult the cookbook
**Then** they find:
- Complete, runnable examples for common use cases
- Copy-paste ready code and commands
- Explanation of what each example demonstrates

**And** the cookbook includes:
- Recipe: Validating a new strategy from scratch
- Recipe: Resuming an interrupted validation session
- Recipe: Investigating a specific layer's discrepancies
- Recipe: Adding a new validation tolerance configuration
- Recipe: Generating a validation report for stakeholders
- Recipe: Running validation in CI/CD pipeline
- Recipe: Comparing results across rustybt versions

**Prerequisites:** Stories 8.2-8.7

**Technical Notes:**
- Located at `docs/validation/cookbook.md`
- Each recipe should be independently useful
- Include expected output for validation
- Test all examples before publishing
- Use consistent formatting (problem → solution → explanation)

---

## Story 8.9: Create Documentation Index and Navigation

As a **validation framework user**,
I want a **well-organized documentation index**,
So that I can **find the right documentation quickly**.

**Acceptance Criteria:**

**Given** a user looking for validation framework documentation
**When** they access the documentation entry point
**Then** they find:
- Clear navigation to all documentation sections
- Appropriate starting points based on user type/goal
- Cross-references between related documents
- Search-friendly structure

**And** the index includes:
- Quick links for common tasks (getting started, add strategy, investigate findings)
- User journey paths (new user → experienced user → contributor)
- Table of contents for each major section
- Links to related rustybt documentation (main framework docs)

**Prerequisites:** Stories 8.1-8.8

**Technical Notes:**
- Located at `docs/validation/index.md`
- Ensure consistent navigation across all validation docs
- Include breadcrumbs or clear hierarchy indicators
- Test all internal links
- Consider different entry points (GitHub, installed package, website)

---

## Summary

| Story | Title | Prerequisites |
|-------|-------|---------------|
| 8.1 | Reorganize Documentation Structure (Internal vs User-Facing) | Epics 1-7 |
| 8.2 | Getting Started Tutorial | 8.1 |
| 8.3 | Strategy Implementation Guide | 8.2 |
| 8.4 | Investigation Workflow Guide | 8.2 |
| 8.5 | CLI Reference | 8.2 |
| 8.6 | Python API Reference | 8.2 |
| 8.7 | Troubleshooting Guide | 8.2-8.6 |
| 8.8 | Examples & Recipes Cookbook | 8.2-8.7 |
| 8.9 | Documentation Index | 8.1-8.8 |

**Total Stories:** 9
**Value:** Clean separation of internal/external docs + complete user-facing documentation enabling self-service adoption of the validation framework

---

_Epic 8 created as extension to rustybt validation framework epic breakdown_
_Date: 2025-11-29_
_For: .smirk_
