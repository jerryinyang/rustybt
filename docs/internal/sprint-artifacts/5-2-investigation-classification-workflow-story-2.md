# Story 5.2: Implement Source Code Linking

Status: review

## Story

As a developer,
I want findings linked to relevant source code,
so that I can investigate the root cause efficiently.

## Acceptance Criteria

1. **locate_source() function implemented**:
   - Maps finding layer to relevant source modules
   - Searches for event-related functions in rustybt codebase
   - Searches for equivalent functions in Backtrader codebase
   - Returns list of SourceLocation objects with file, line, description

2. **Layer-to-module mapping**:
   - data layer → `rustybt/data/`, `zipline/data/`
   - signals layer → `rustybt/algorithm.py`, `rustybt/signals/`
   - orders layer → `rustybt/finance/order.py`, `rustybt/finance/blotter.py`
   - broker layer → `rustybt/finance/broker.py`, `rustybt/finance/commission.py`
   - portfolio layer → `rustybt/finance/portfolio.py`, `rustybt/finance/returns.py`

3. **View source command in investigation**:
   - Press 'v' during investigation to view source locations
   - Display numbered list of locations for both frameworks
   - Allow selection to open file in configured editor

4. **Editor configuration**:
   - `rustybt-validate config set editor "<command>"` configures editor
   - Support placeholders: {file}, {line}
   - Default to `code -g {file}:{line}` for VS Code
   - Support common editors: vim, emacs, sublime, etc.

5. **Source location caching**:
   - Cache grep results for repeated queries
   - Invalidate cache when source files change
   - Store cache in session directory

6. **Unit tests verify**:
   - Layer-to-module mapping correctness
   - locate_source() returns valid paths
   - Editor command formatting
   - Cache behavior

## Tasks / Subtasks

- [x] Task 1: Implement SourceLocation model (AC: #1)
  - [x] Create SourceLocation dataclass with file, line, description fields
  - [x] Add framework field to distinguish rustybt vs backtrader

- [x] Task 2: Implement layer-to-module mapping (AC: #2)
  - [x] Create LAYER_MODULES constant with layer→paths mapping
  - [x] Support both rustybt and Backtrader module patterns

- [x] Task 3: Implement locate_source() function (AC: #1)
  - [x] Search modules using grep/ripgrep for event-related code
  - [x] Parse file:line from search results
  - [x] Return sorted list of SourceLocation objects

- [x] Task 4: Add view source to investigation interface (AC: #3)
  - [x] Handle 'v' action in investigate command
  - [x] Display numbered source locations
  - [x] Prompt for selection and open in editor

- [x] Task 5: Implement editor configuration (AC: #4)
  - [x] Add `config set editor` command to CLI
  - [x] Store editor command in user config
  - [x] Format command with {file}, {line} placeholders

- [x] Task 6: Implement source location caching (AC: #5)
  - [x] Cache grep results keyed by layer+event
  - [x] Store cache in session directory
  - [x] Add cache invalidation on file modification

- [x] Task 7: Write unit tests (AC: #6)
  - [x] Test layer mapping
  - [x] Test locate_source() with mock filesystem
  - [x] Test editor command formatting
  - [x] Test cache storage/retrieval

## Dev Notes

### Architecture Alignment

**Source Code Linking** (Architecture - Investigation Pattern):
```python
def locate_source(finding: Finding, framework: str) -> list[SourceLocation]:
    """Locate relevant source code for finding."""
    locations = []

    # Map layer to source modules
    layer_modules = {
        "data": ["rustybt/data/", "zipline/data/"],
        "signals": ["rustybt/algorithm.py", "rustybt/signals/"],
        "orders": ["rustybt/finance/order.py", "rustybt/finance/blotter.py"],
        "broker": ["rustybt/finance/broker.py", "rustybt/finance/commission.py"],
        "portfolio": ["rustybt/finance/portfolio.py", "rustybt/finance/returns.py"],
    }

    # Search for event-related functions
    for module_pattern in layer_modules.get(finding.layer, []):
        matches = grep_for_event(module_pattern, finding.event)
        locations.extend(matches)

    return locations
```

**View Source CLI Output**:
```
Source code locations for FIND-001:

rustybt locations:
  1. rustybt/finance/order.py:142 - order_quantity calculation
  2. rustybt/finance/blotter.py:89 - create_order()

Backtrader locations (reference):
  3. backtrader/order.py:234 - Order.__init__
  4. backtrader/broker.py:456 - submit()

Open location? [1-4 or n to skip]:
```

### Learnings from Previous Story

**From Story 5-1 (Discrepancy Presentation) - Prerequisites**

- **Investigation Interface**: 'v' action reserved for view source
- **Finding Model**: Has layer, event fields needed for source lookup
- **CLI Pattern**: Click prompts for user input

[Source: docs/sprint-artifacts/5-1-investigation-classification-workflow-story-1.md]

### Implementation Pattern

**SourceLocation model**:
```python
@dataclass
class SourceLocation:
    """Source code location for a finding."""
    file: Path
    line: int
    description: str
    framework: Literal["rustybt", "backtrader"]

    def __str__(self) -> str:
        return f"{self.file}:{self.line} - {self.description}"
```

**locate_source implementation**:
```python
import subprocess
from pathlib import Path

LAYER_MODULES = {
    "data": {
        "rustybt": ["rustybt/data/", "zipline/data/"],
        "backtrader": ["backtrader/feeds/", "backtrader/data/"],
    },
    "signals": {
        "rustybt": ["rustybt/algorithm.py", "rustybt/signals/"],
        "backtrader": ["backtrader/strategy.py", "backtrader/indicator*.py"],
    },
    "orders": {
        "rustybt": ["rustybt/finance/order.py", "rustybt/finance/blotter.py"],
        "backtrader": ["backtrader/order.py", "backtrader/broker*.py"],
    },
    "broker": {
        "rustybt": ["rustybt/finance/broker.py", "rustybt/finance/commission.py"],
        "backtrader": ["backtrader/broker*.py", "backtrader/commission*.py"],
    },
    "portfolio": {
        "rustybt": ["rustybt/finance/portfolio.py", "rustybt/finance/returns.py"],
        "backtrader": ["backtrader/analyzer*.py", "backtrader/cerebro.py"],
    },
}

def locate_source(finding: Finding, project_root: Path) -> list[SourceLocation]:
    """Locate relevant source code for finding."""
    locations = []

    for framework, modules in LAYER_MODULES.get(finding.layer, {}).items():
        for module_pattern in modules:
            search_path = project_root / module_pattern
            results = grep_for_event(search_path, finding.event)
            locations.extend([
                SourceLocation(
                    file=r.file,
                    line=r.line,
                    description=r.context,
                    framework=framework
                )
                for r in results
            ])

    return locations

def grep_for_event(path: Path, event: str) -> list:
    """Search for event-related code using ripgrep."""
    # Extract key terms from event name (e.g., "order_quantity" from "order_quantity_mismatch")
    terms = event.replace("_mismatch", "").replace("_", "|")

    try:
        result = subprocess.run(
            ["rg", "-n", "--no-heading", terms, str(path)],
            capture_output=True,
            text=True
        )
        return parse_grep_results(result.stdout)
    except FileNotFoundError:
        # Fallback to grep if rg not available
        return []
```

**Editor configuration**:
```python
import os
from pathlib import Path

DEFAULT_EDITOR = "code -g {file}:{line}"
CONFIG_FILE = Path.home() / ".config" / "rustybt-validate" / "config.yaml"

def get_editor_command() -> str:
    """Get configured editor command."""
    if CONFIG_FILE.exists():
        config = yaml.safe_load(CONFIG_FILE.read_text())
        return config.get("editor", DEFAULT_EDITOR)
    return DEFAULT_EDITOR

def open_in_editor(location: SourceLocation) -> None:
    """Open source location in configured editor."""
    cmd = get_editor_command()
    cmd = cmd.format(file=location.file, line=location.line)
    os.system(cmd)
```

### Project Structure Notes

**Files to create/modify**:
- `rustybt/validation/source_linking.py` (NEW - source location logic)
- `rustybt/validation/cli.py` (MODIFY - add config command, integrate view source)
- `rustybt/validation/models.py` (MODIFY - add SourceLocation)
- `tests/validation/test_source_linking.py` (NEW - source linking tests)

**Dependencies**:
- ripgrep (rg) for fast code search (optional, falls back to grep)
- PyYAML for config storage (existing)

### Testing Guidance

```python
import pytest
from pathlib import Path
from rustybt.validation.source_linking import (
    locate_source,
    LAYER_MODULES,
    SourceLocation,
    get_editor_command,
)
from rustybt.validation.models import Finding

@pytest.mark.source_linking
class TestSourceLinking:

    def test_layer_modules_complete(self):
        """Test all layers have module mappings."""
        expected_layers = ["data", "signals", "orders", "broker", "portfolio"]
        for layer in expected_layers:
            assert layer in LAYER_MODULES
            assert "rustybt" in LAYER_MODULES[layer]
            assert "backtrader" in LAYER_MODULES[layer]

    def test_locate_source_returns_locations(self, tmp_path):
        """Test locate_source finds relevant code."""
        # Create mock source file
        source_file = tmp_path / "rustybt" / "finance" / "order.py"
        source_file.parent.mkdir(parents=True)
        source_file.write_text("def create_order(quantity):\n    pass\n")

        finding = Finding(
            id="FIND-001",
            layer="orders",
            event="order_quantity_mismatch",
        )

        locations = locate_source(finding, tmp_path)
        # Should find at least the mock file
        assert isinstance(locations, list)

    def test_source_location_str_format(self):
        """Test SourceLocation string representation."""
        loc = SourceLocation(
            file=Path("rustybt/finance/order.py"),
            line=142,
            description="order_quantity calculation",
            framework="rustybt"
        )
        assert "rustybt/finance/order.py:142" in str(loc)
        assert "order_quantity calculation" in str(loc)

    def test_editor_command_default(self):
        """Test default editor command."""
        cmd = get_editor_command()
        assert "{file}" in cmd
        assert "{line}" in cmd

    def test_editor_command_formatting(self):
        """Test editor command placeholder replacement."""
        loc = SourceLocation(
            file=Path("test.py"),
            line=10,
            description="test",
            framework="rustybt"
        )
        cmd = "code -g {file}:{line}"
        formatted = cmd.format(file=loc.file, line=loc.line)
        assert formatted == "code -g test.py:10"
```

### References

- [Source: docs/architecture.md - Investigation Pattern]
- [Source: docs/archive/epics.md - Story 5.2 specification]
- [Source: docs/prd.md - FR44-FR46 (source code linking)]

## Dev Agent Record

### Context Reference

- docs/sprint-artifacts/5-2-investigation-classification-workflow-story-2.context.xml

### Agent Model Used

Claude Opus 4.5 (claude-opus-4-5-20251101)

### Debug Log References

N/A

### Completion Notes List

1. **Source linking module created** (`rustybt/validation/source_linking.py`):
   - `SourceLocation` dataclass with file, line, description, framework fields
   - `LAYER_MODULES` mapping all 5 layers to rustybt and backtrader paths
   - `locate_source()` - searches for event-related code using ripgrep/grep
   - `grep_for_event()` - runs grep/rg with term extraction
   - `format_source_locations()` - formats locations for CLI display
   - `SourceLocationCache` - caches grep results with invalidation
   - Editor configuration: `get_editor_command()`, `set_editor_command()`, `open_in_editor()`

2. **CLI commands updated** (`rustybt/validation/cli.py`):
   - Enhanced 'v' action in investigate command to show real source locations
   - Added `config` command group with `set`, `get`, `list` subcommands
   - Editor command validation warns about missing placeholders

3. **36 unit tests created** (`tests/validation/test_source_linking.py`):
   - TestSourceLocation (2 tests)
   - TestLayerModules (5 tests)
   - TestSearchTermExtraction (4 tests)
   - TestGrepLineParsing (3 tests)
   - TestGrepForEvent (2 tests)
   - TestLocateSource (2 tests)
   - TestEditorConfiguration (3 tests)
   - TestFormatSourceLocations (3 tests)
   - TestSourceLocationCache (5 tests)
   - TestConfigCLICommands (7 tests)

4. All tests pass: `pytest tests/validation/test_source_linking.py -v` (36 passed)

### File List

- `rustybt/validation/source_linking.py` (NEW - 380 lines)
- `rustybt/validation/cli.py` (MODIFIED - enhanced view source, added config command ~100 lines)
- `tests/validation/test_source_linking.py` (NEW - 420 lines)

---

## Change Log

| Date | Change | Author |
|------|--------|--------|
| 2025-11-27 | Story drafted from Epic 5 specification | SM Agent |
| 2025-11-28 | Senior Developer Review notes appended | .smirk |

---

## Senior Developer Review (AI)

**Reviewer:** .smirk
**Date:** 2025-11-28
**Outcome:** APPROVE

### Summary

Story 5-2 implementation is complete and meets all acceptance criteria. The source code linking module provides comprehensive functionality for locating relevant code, configuring editors, and caching results. All 36 unit tests pass. No zero-mock violations or orphaned files detected.

### Key Findings

No blocking issues found.

### Acceptance Criteria Coverage

| AC# | Description | Status | Evidence |
|-----|-------------|--------|----------|
| AC1 | locate_source() function implemented | ✅ IMPLEMENTED | `source_linking.py:252-303` - Full implementation with grep/ripgrep |
| AC2 | Layer-to-module mapping | ✅ IMPLEMENTED | `source_linking.py:44-65` - LAYER_MODULES constant |
| AC3 | View source command in investigation | ✅ IMPLEMENTED | `cli.py:962-996` - 'v' action handler |
| AC4 | Editor configuration | ✅ IMPLEMENTED | `source_linking.py:74-126`, `cli.py:1027-1091` - config commands |
| AC5 | Source location caching | ✅ IMPLEMENTED | `source_linking.py:356-454` - SourceLocationCache class |
| AC6 | Unit tests verify | ✅ IMPLEMENTED | `test_source_linking.py` - 36 tests covering all functionality |

**Summary:** 6 of 6 acceptance criteria fully implemented

### Task Completion Validation

| Task | Marked As | Verified As | Evidence |
|------|-----------|-------------|----------|
| Task 1: Implement SourceLocation model | ✅ Complete | ✅ VERIFIED | `source_linking.py:21-39` - SourceLocation dataclass |
| Task 2: Implement layer-to-module mapping | ✅ Complete | ✅ VERIFIED | `source_linking.py:44-65` - LAYER_MODULES dict |
| Task 3: Implement locate_source() function | ✅ Complete | ✅ VERIFIED | `source_linking.py:252-303` with grep fallback |
| Task 4: Add view source to investigation | ✅ Complete | ✅ VERIFIED | `cli.py:962-996` - view source action |
| Task 5: Implement editor configuration | ✅ Complete | ✅ VERIFIED | `source_linking.py:74-126`, CLI commands |
| Task 6: Implement source location caching | ✅ Complete | ✅ VERIFIED | `source_linking.py:356-454` - SourceLocationCache |
| Task 7: Write unit tests | ✅ Complete | ✅ VERIFIED | 36 tests all passing |

**Summary:** 7 of 7 completed tasks verified, 0 questionable, 0 falsely marked complete

### Zero-Mock Enforcement

| Check Type | File:Line | Status | Details |
|------------|-----------|--------|---------|
| Hardcoded returns | source_linking.py:124,126 | ✅ OK | `return True/False` for success/failure indication |
| Always-succeeding validations | N/A | ✅ OK | No validation functions that always return True |
| Mock patterns in production | N/A | ✅ OK | No mock/fake/stub patterns |
| Empty error handlers | source_linking.py:84-85,101-102 | ✅ OK | Proper exception handling with pass to use defaults |
| Simplified implementations | N/A | ✅ OK | No simplified implementations |
| Test quality | test_source_linking.py | ✅ OK | Real assertions testing actual functionality |

**Summary:** ZERO-MOCK STATUS: PASS - 0 violations found

### Orphaned Files Enforcement

| File Path | Issue Type | Severity | Status |
|-----------|------------|----------|--------|
| rustybt/validation/source_linking.py | N/A | N/A | ✅ OK - Imported by cli.py |
| tests/validation/test_source_linking.py | N/A | N/A | ✅ OK - In correct test directory |

**Summary:** ORPHAN STATUS: PASS - 0 violations found

### Test Coverage and Gaps

- **Tests Present:** 36 tests covering all core functionality
- **Test Categories:**
  - TestSourceLocation: 2 tests
  - TestLayerModules: 5 tests
  - TestSearchTermExtraction: 4 tests
  - TestGrepLineParsing: 3 tests
  - TestGrepForEvent: 2 tests
  - TestLocateSource: 2 tests
  - TestEditorConfiguration: 3 tests
  - TestFormatSourceLocations: 3 tests
  - TestSourceLocationCache: 5 tests
  - TestConfigCLICommands: 7 tests
- **All tests passing:** ✅ Yes (36/36)

### Architectural Alignment

- ✅ Follows architecture pattern for source linking (Architecture - Investigation Pattern)
- ✅ Proper integration with Finding model
- ✅ Correct file placement in rustybt/validation/ directory
- ✅ User config stored in ~/.config/rustybt-validate/

### Security Notes

- Uses subprocess for grep/ripgrep with proper timeout handling
- Editor command stored in user home config directory (not project)
- No security concerns identified

### Best-Practices and References

- Fallback from ripgrep to grep for compatibility
- Proper timeout handling for subprocess calls
- Cache with invalidation support for performance

### Action Items

**Code Changes Required:**
None - all acceptance criteria met.

**Advisory Notes:**
- Note: Consider adding `@pytest.mark.source_linking` to pyproject.toml markers to avoid PytestUnknownMarkWarning
