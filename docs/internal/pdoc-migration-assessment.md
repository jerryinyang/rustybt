# pdoc Migration Assessment for RustyBT

**Date:** 2025-11-07
**Author:** Claude AI Assistant
**Status:** Assessment Complete

## Executive Summary

This document assesses the feasibility of migrating RustyBT's documentation system from **MkDocs + mkdocstrings** to **pdoc**. Based on comprehensive analysis of the codebase (943 classes across 244 Python files), current documentation infrastructure, and pdoc capabilities, this report provides detailed findings and recommendations.

### Key Findings

- **Current System:** Well-established MkDocs setup with Google-style docstrings configured via mkdocstrings
- **Codebase Split:** ~40% modern RustyBT code (excellent docstrings), ~40% legacy Zipline code (variable quality), ~20% utilities
- **Migration Feasibility:** Technically feasible but requires significant preparation work
- **Recommended Approach:** Hybrid system (MkDocs for guides + pdoc for API reference) OR continue with current MkDocs setup

---

## 1. Current Documentation System Analysis

### 1.1 MkDocs Configuration

**Tool Stack:**
- **MkDocs Material** (≥9.5.0) - Premium theme with extensive features
- **mkdocstrings[python]** (≥0.24.0) - API documentation from docstrings
- **mkdocs-jupyter** (≥0.24.0) - Jupyter notebook integration

**Key Configuration:**
```yaml
# From mkdocs.yml (326 lines total)
plugins:
  - mkdocstrings:
      handlers:
        python:
          options:
            docstring_style: google  # Standardized on Google-style
            show_root_heading: true
            show_source: true
            members_order: source
```

**Documentation Structure:**
- **100+ documentation pages** across 7 main sections
- **Getting Started** guides (installation, quickstart, configuration)
- **User Guides** (20+ guides covering all major features)
- **Examples** (40+ Python scripts + 11 Jupyter notebooks)
- **API Reference** (comprehensive, organized by functional area)
- **Migration Guides** (cash validation, etc.)

**Strengths:**
1. ✅ Extensive hand-written documentation
2. ✅ Integrated Jupyter notebooks
3. ✅ Well-organized navigation hierarchy
4. ✅ Material theme features (search, tabs, dark mode, code copy)
5. ✅ ReadTheDocs integration configured
6. ✅ Consistent Google-style docstring standard

**Dependencies:**
- Python 3.12+ requirement
- Markdown extensions (admonition, superfences, tabbed content, etc.)
- Auto-generated cross-references via autorefs plugin

### 1.2 Documentation Quality Metrics

| Category | % of Code | Docstring Quality | Style | Examples | Type Hints |
|----------|-----------|-------------------|-------|----------|------------|
| **Modern RustyBT** | 30% | Excellent (9/10) | Google | Rich | Complete |
| **Modern Data Layer** | 10% | Excellent (9/10) | Google | Rich | Complete |
| **Mixed Modules** | 20% | Good-Fair (6/10) | Mixed | Some | Partial |
| **Legacy Zipline** | 30% | Fair-Poor (4/10) | NumPy/None | Rare | Minimal |
| **Utilities** | 10% | Variable (5/10) | Mixed | Some | Partial |

**Overall Assessment:** 40% migration-ready, 60% needs improvement

---

## 2. pdoc Tool Analysis

### 2.1 pdoc vs pdoc3

**History:**
- **pdoc** (original): Paused development 2014-2021, resumed by mitmproxy team
- **pdoc3** (fork): Created during pause period, AGPL-3.0 licensed
- **Current Status:** Both actively maintained but diverged significantly

**Recommendation:** Use modern **pdoc** (not pdoc3) from mitmproxy team
- PyPI: `pdoc` (https://pdoc.dev/)
- License: Unlicense (more permissive than pdoc3's AGPL)
- Better Python 3.12+ support

### 2.2 pdoc Key Features

**Strengths:**
1. ✅ **Zero configuration required** - works out of the box
2. ✅ **Google-style docstrings** - native support (matches current standard)
3. ✅ **NumPy-style docstrings** - also supported (helpful for legacy code)
4. ✅ **Type annotations** - first-class support for PEP 484/526
5. ✅ **Live reload server** - instant preview during development
6. ✅ **Cross-linking** - automatic identifier cross-references
7. ✅ **Customizable templates** - HTML/CSS can be customized
8. ✅ **Markdown support** - docstrings rendered as Markdown
9. ✅ **Math support** - LaTeX math rendering
10. ✅ **Auto-inheritance** - inherited docstrings shown (greyed out)

**Limitations:**
1. ⚠️ **Cython support uncertain** - no explicit documentation on .pyx files
2. ⚠️ **No built-in guide integration** - API docs only (no tutorials/guides)
3. ⚠️ **Limited navigation customization** - auto-generated structure
4. ⚠️ **No Jupyter integration** - cannot embed notebooks like mkdocs-jupyter
5. ⚠️ **Simpler than Sphinx** - fewer advanced features for large projects

### 2.3 pdoc vs MkDocs Comparison

| Feature | MkDocs + mkdocstrings | pdoc | Winner |
|---------|----------------------|------|--------|
| **Configuration** | YAML config required | Zero config | pdoc |
| **API Docs** | Via mkdocstrings plugin | Native | Tie |
| **Hand-written guides** | Excellent support | No support | MkDocs |
| **Jupyter notebooks** | mkdocs-jupyter plugin | No support | MkDocs |
| **Navigation control** | Full YAML control | Auto-generated | MkDocs |
| **Theme customization** | Material theme (rich) | Basic HTML/CSS | MkDocs |
| **Docstring formats** | Google (via config) | Google + NumPy | Tie |
| **Type hints** | Good support | Excellent support | pdoc |
| **Live reload** | Built-in | Built-in | Tie |
| **Search** | Material theme search | Basic search | MkDocs |
| **Learning curve** | Moderate | Minimal | pdoc |
| **Large projects** | Excellent | Good | MkDocs |

**Verdict:** MkDocs is better suited for comprehensive documentation (guides + API), pdoc is better for pure API documentation

---

## 3. Codebase Docstring Assessment

### 3.1 Module Categories

**A. Modern RustyBT Modules (Migration-Ready)**

**Modules:**
- `rustybt/analytics/` - Jupyter integration, visualization
- `rustybt/live/` - Live trading engine
- `rustybt/optimization/` - Strategy optimization
- `rustybt/portfolio/` - Multi-strategy management
- `rustybt/backtest/` - Artifact management
- `rustybt/data/polars/` - Modern data engine
- `rustybt/data/adapters/` - Data source adapters
- `rustybt/finance/decimal/` - Financial precision

**Example Quality (Excellent):**
```python
"""Polars-based Data Portal with Decimal precision.

This module provides a simplified data portal interface using Polars DataFrames
with Decimal types for financial-grade precision.
"""

class PolarsDataPortal:
    """Data portal with Polars backend and Decimal precision.

    This class provides a simplified interface for accessing OHLCV data
    with Decimal precision. It supports both daily and minute-frequency data.

    Attributes:
        daily_reader: Reader for daily OHLCV data
        minute_reader: Reader for minute OHLCV data
        data_source: Unified data source interface

    Example:
        >>> from rustybt.data.polars import PolarsParquetDailyReader, PolarsDataPortal
        >>> reader = PolarsParquetDailyReader("/path/to/bundle")
        >>> portal = PolarsDataPortal(daily_reader=reader)
        >>> data = portal.get_history_window(
        ...     assets=[asset],
        ...     end_dt=pd.Timestamp("2024-01-31"),
        ...     bar_count=30,
        ...     frequency="1d",
        ...     field="close"
        ... )
    """

    def get_history_window(
        self,
        assets: list[Asset],
        end_dt: pd.Timestamp,
        bar_count: int,
        frequency: str,
        field: str,
    ) -> pl.DataFrame:
        """Retrieve historical data window.

        Args:
            assets: List of assets to retrieve data for
            end_dt: End timestamp for the window
            bar_count: Number of bars to retrieve
            frequency: Data frequency ("1d" or "1m")
            field: OHLCV field to retrieve

        Returns:
            Polars DataFrame with requested data

        Raises:
            ValueError: If invalid frequency or field specified

        Example:
            >>> data = portal.get_history_window(
            ...     assets=[Asset(1)],
            ...     end_dt=pd.Timestamp("2024-01-31"),
            ...     bar_count=30,
            ...     frequency="1d",
            ...     field="close"
            ... )
        """
```

**Characteristics:**
- ✅ Module-level docstring with clear summary
- ✅ Class docstring with description, attributes, examples
- ✅ Method docstrings with Args/Returns/Raises/Examples
- ✅ Full type hints (Python 3.12+ features)
- ✅ Rich examples with code blocks
- ✅ Consistent Google-style formatting

**B. Legacy Zipline Modules (Needs Work)**

**Modules:**
- `rustybt/assets/` - Asset database
- `rustybt/pipeline/` - Pipeline API
- `rustybt/gens/` - Simulation generators
- `rustybt/finance/` (core) - Order/Position/Transaction
- `rustybt/data/` (core) - Legacy data bundles

**Example Quality (Variable):**

**NumPy-style (needs conversion):**
```python
def fill_price_worse_than_limit_price(fill_price, order):
    """Checks whether the fill price is worse than the order's limit price.

    Parameters
    ----------
    fill_price: float
        The price to check.

    order: zipline.finance.order.Order
        The order whose limit price to check.

    Returns
    -------
    bool: Whether the fill price is above the limit price (for a buy) or below
    the limit price (for a sell).
    """
```

**Minimal/Missing (needs writing):**
```python
class Order:
    # using __slots__ to save on memory usage. Simulations can create many
    # Order objects and we keep them all in memory, so it's worthwhile trying
    # to cut down on the memory footprint of this object.
    __slots__ = [
        "id",
        "dt",
        "created",
        # ... many more
    ]
    # No class docstring!
    # No __init__ docstring!
```

**No module docstring:**
```python
# rustybt/finance/__init__.py
from . import execution, trading

__all__ = ["execution", "trading"]
# Just imports, no module-level documentation
```

**Issues:**
- ❌ Many classes lack docstrings entirely
- ❌ NumPy-style format (incompatible with current Google standard)
- ❌ Missing module-level docstrings
- ❌ No examples in most functions
- ❌ Minimal or no type hints
- ❌ Incomplete parameter documentation

### 3.2 Cython Extensions

**Files Identified:**
```
rustybt/lib/adjusted_array.pyx
rustybt/lib/adjustment.pyx
rustybt/lib/rank.pyx
rustybt/finance/slippage.pyx (if exists)
... approximately 10 .pyx files
```

**pdoc Compatibility:** ⚠️ **UNCLEAR**
- pdoc documentation does not explicitly mention Cython support
- May require `.pyi` stub files for proper documentation
- Need to test with actual Cython extensions
- Fallback: Document only the Python API, exclude .pyx internals

**Recommendation:** Create `.pyi` stub files for Cython extensions if migrating to pdoc

### 3.3 Docstring Standardization Work Required

**Estimated Effort:**

| Task | Files | Classes/Functions | Effort (hours) |
|------|-------|-------------------|----------------|
| Convert NumPy → Google style | ~80 | ~300 | 40-60 |
| Add missing class docstrings | ~60 | ~200 | 30-40 |
| Add missing function docstrings | ~100 | ~400 | 50-70 |
| Add module-level docstrings | ~80 | N/A | 20-30 |
| Add examples to key functions | ~150 | ~150 | 30-40 |
| Create .pyi stubs for Cython | ~10 | ~50 | 10-15 |
| **TOTAL** | **~244** | **~1100** | **180-255 hours** |

**Priority Levels:**

1. **High Priority** (Core API - 60 hours):
   - `rustybt/algorithm.py` - Main algorithm class
   - `rustybt/assets/` - Asset management
   - `rustybt/data/` (core) - Data access
   - `rustybt/finance/` (core) - Order/Position/Transaction

2. **Medium Priority** (Extended API - 80 hours):
   - `rustybt/pipeline/` - Pipeline API
   - `rustybt/gens/` - Simulation engine
   - `rustybt/utils/` - Utility functions

3. **Low Priority** (Internal - 60 hours):
   - Internal implementation details
   - Deprecated modules
   - Test utilities

---

## 4. Migration Options & Recommendations

### Option 1: Full Migration to pdoc (Not Recommended)

**Approach:**
- Replace MkDocs entirely with pdoc for all documentation
- Move hand-written guides to separate static site or wiki
- Use pdoc exclusively for API reference

**Pros:**
- ✅ Simpler toolchain (one tool instead of two)
- ✅ Automatic API documentation generation
- ✅ Better type hint integration
- ✅ Zero configuration maintenance

**Cons:**
- ❌ **Lose 100+ pages of hand-written documentation** (guides, tutorials, examples)
- ❌ **Cannot embed Jupyter notebooks** (11 tutorial notebooks)
- ❌ **Limited navigation control** (auto-generated only)
- ❌ **Less rich theming** (compared to Material)
- ❌ **No admonitions, tabs, or advanced Markdown** extensions
- ❌ **Search functionality downgrade** from Material theme
- ❌ **Requires 180-255 hours** of docstring improvement work

**Verdict:** ❌ **NOT RECOMMENDED** - Too much valuable content would be lost

---

### Option 2: Hybrid System (Conditionally Recommended)

**Approach:**
- **Keep MkDocs** for guides, tutorials, getting started, examples
- **Add pdoc** for auto-generated API reference
- Link between the two systems
- Phased migration starting with modern modules

**Pros:**
- ✅ Preserve existing 100+ documentation pages
- ✅ Keep Jupyter notebook integration
- ✅ Auto-generate API docs with pdoc (less manual maintenance)
- ✅ Better API docs for modern modules (already have good docstrings)
- ✅ Can migrate incrementally (phase by phase)

**Cons:**
- ⚠️ **Two documentation systems** to maintain (MkDocs + pdoc)
- ⚠️ **Complexity** of linking between systems
- ⚠️ **Deployment complexity** (two build processes)
- ⚠️ Still requires **180-255 hours** of docstring work for full coverage
- ⚠️ Potential for documentation drift between systems

**Implementation:**
```yaml
# MkDocs nav structure (simplified)
nav:
  - Home: index.md
  - Getting Started: [...]
  - User Guides: [...]
  - Examples: [...]
  - API Reference:
      - Overview: api/README.md
      - Modern API (pdoc): [link to pdoc site]
      - Legacy API (mkdocstrings): [current structure]
```

**Phased Approach:**
1. **Phase 1** (20 hours): Set up pdoc for modern modules only
   - `analytics/`, `live/`, `optimization/`, `portfolio/`, `backtest/`
   - Link from MkDocs to pdoc site
2. **Phase 2** (40 hours): Add data layer
   - `data/polars/`, `data/adapters/`
3. **Phase 3** (100+ hours): Improve legacy docstrings, add to pdoc
   - Convert NumPy → Google style
   - Add missing docstrings
   - Migrate to pdoc

**Verdict:** ⚠️ **CONDITIONALLY RECOMMENDED** - Only if team wants auto-generated API docs and can maintain two systems

---

### Option 3: Continue with MkDocs (Recommended)

**Approach:**
- **Keep current MkDocs + mkdocstrings** setup
- **Improve docstrings** incrementally (Google-style)
- **Enhance mkdocstrings configuration** if needed
- Focus on content quality rather than tool migration

**Pros:**
- ✅ **No migration effort** - focus on content improvement
- ✅ **Proven system** - currently working well
- ✅ **Unified documentation** - guides + API in one place
- ✅ **Rich features** - Material theme, Jupyter notebooks, search
- ✅ **Incremental improvement** - improve docstrings as modules are touched
- ✅ **Lower total effort** - avoid migration overhead

**Cons:**
- ⚠️ Manual maintenance of API reference pages (though mkdocstrings auto-generates from docstrings)
- ⚠️ Still need to improve legacy docstrings (but can do incrementally)

**Improvement Plan:**
1. **Short-term (0-3 months):**
   - Create docstring style guide for contributors
   - Add pre-commit hook to check docstring presence
   - Document high-priority modules (algorithm.py, core APIs)

2. **Medium-term (3-6 months):**
   - Convert NumPy-style docstrings to Google-style (automated tool)
   - Add missing docstrings to frequently-used APIs
   - Expand examples in key modules

3. **Long-term (6-12 months):**
   - Comprehensive docstring coverage for all public APIs
   - Rich examples throughout
   - Consider automated docstring quality checks in CI

**Verdict:** ✅ **RECOMMENDED** - Best balance of effort vs. value

---

## 5. Final Recommendations

### Primary Recommendation: Continue with MkDocs + Incremental Improvement

**Rationale:**
1. **Current system works well** - MkDocs + mkdocstrings is production-ready
2. **Preserves valuable content** - 100+ documentation pages, 11 Jupyter notebooks
3. **Lower total effort** - avoid migration overhead, focus on content
4. **Incremental improvement** - improve docstrings as code evolves
5. **Future-proof** - can still migrate to pdoc later if needed

**Action Items:**

**Immediate (Next 2 weeks):**
1. ✅ Create `docs/contributing/docstring-style-guide.md`
   - Document Google-style standard
   - Provide templates for classes, functions, modules
   - Include examples from modern modules
2. ✅ Add docstring linter to pre-commit hooks
   - Use `pydocstyle` or `darglint` to enforce Google-style
   - Check for missing docstrings on public APIs
3. ✅ Document top 10 most-used APIs
   - Identify via usage analytics or manual review
   - Ensure comprehensive docstrings with examples

**Short-term (1-3 months):**
4. ✅ Convert NumPy-style docstrings to Google-style
   - Use automated tool (e.g., `pyment` or custom script)
   - Focus on high-priority modules first
   - Review and test after conversion
5. ✅ Add module-level docstrings to all packages
   - Brief description of module purpose
   - List key classes/functions
   - Usage examples where appropriate
6. ✅ Enhance mkdocstrings configuration
   - Enable additional options (show_signature_annotations, etc.)
   - Customize template if needed

**Medium-term (3-6 months):**
7. ✅ Achieve 80% docstring coverage on public APIs
   - Add missing class/function docstrings
   - Prioritize user-facing APIs
8. ✅ Add comprehensive examples
   - At least one example per major API
   - Real-world usage patterns
9. ✅ Create automated docstring quality reports
   - Track coverage metrics
   - Identify gaps
   - Include in CI pipeline

**Long-term (6-12 months):**
10. ✅ 100% docstring coverage on all public APIs
11. ✅ Rich examples throughout codebase
12. ✅ Interactive API documentation (if desired)
    - Consider tools like `mkdocs-gallery` or `sphinx-gallery`
    - Generate example gallery from scripts

### Alternative Recommendation: Hybrid System (If Auto-Generation Desired)

**If the team strongly prefers auto-generated API docs**, consider hybrid approach:

**Setup:**
1. Keep MkDocs for guides/tutorials/examples
2. Add pdoc for modern modules (analytics, live, optimization, portfolio)
3. Link from MkDocs nav to pdoc site
4. Gradually migrate legacy modules as docstrings improve

**Deployment:**
```bash
# Build both systems
mkdocs build --site-dir site/docs
pdoc rustybt.analytics rustybt.live rustybt.optimization rustybt.portfolio \
     --output-dir site/api
```

**Pros:**
- Auto-generated API docs stay in sync with code
- Better type hint display
- Reduced manual maintenance for API pages

**Cons:**
- Two systems to maintain
- More complex deployment
- Linking between systems requires care

---

## 6. Cython Extension Handling

### Current Status
- ~10 Cython extensions (.pyx files) in `rustybt/lib/` and `rustybt/finance/`
- pdoc's support for Cython is unclear/undocumented

### Recommendations

**Option A: Create .pyi Stub Files (Preferred)**
```python
# rustybt/lib/adjusted_array.pyi
from typing import Any
import numpy as np

class AdjustedArray:
    """Array with adjustment metadata.

    This class wraps NumPy arrays and applies adjustments
    (splits, dividends) on access.

    Attributes:
        data: Underlying NumPy array
        adjustments: List of adjustments to apply
    """

    def __init__(self, data: np.ndarray, adjustments: list[Any]) -> None:
        """Initialize adjusted array.

        Args:
            data: NumPy array with raw data
            adjustments: List of adjustments
        """
        ...

    def get_value(self, idx: int) -> float:
        """Get adjusted value at index.

        Args:
            idx: Index to retrieve

        Returns:
            Adjusted value
        """
        ...
```

**Benefits:**
- pdoc (and other tools) can document the API
- Type checkers can validate usage
- Clear separation of interface and implementation

**Option B: Document Python API Only**
- Exclude .pyx files from documentation
- Document only the Python wrapper modules
- Use comments in .pyx files for internal documentation

**Option C: Test pdoc with Cython**
- Install pdoc and test with existing .pyx files
- If it works, use as-is
- If not, fall back to Option A or B

**Recommended:** **Option A** (stub files) - provides best documentation and type checking

---

## 7. Migration Risk Assessment

### Technical Risks

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| pdoc cannot handle Cython | Medium | High | Create .pyi stub files |
| Loss of hand-written docs | High (if full migration) | Critical | Use hybrid approach or keep MkDocs |
| Docstring quality insufficient | High | Medium | Improve incrementally before/during migration |
| Broken cross-references | Medium | Medium | Test thoroughly, use pdoc's auto-linking |
| Deployment complexity | Medium | Medium | Automate with scripts, document process |
| Search functionality degraded | High (pdoc only) | Medium | Keep MkDocs or enhance pdoc templates |

### Resource Risks

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Insufficient time for docstring improvement (180-255 hrs) | High | High | Prioritize modules, phase migration |
| Team unfamiliar with pdoc | Medium | Low | pdoc has minimal learning curve |
| Two systems to maintain | High (hybrid) | Medium | Automate builds, clear documentation |
| Documentation drift | Medium (hybrid) | Medium | Single source of truth for API docs |

### Business Risks

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Downtime during migration | Low | Medium | Use staging environment, test thoroughly |
| User confusion (hybrid system) | Medium | Low | Clear navigation, explain dual structure |
| ROI unclear | Medium | Medium | Define success metrics before migrating |

---

## 8. Success Metrics

### If Continuing with MkDocs (Recommended)

**Documentation Quality:**
- [ ] 80% docstring coverage on public APIs (3 months)
- [ ] 100% docstring coverage on public APIs (12 months)
- [ ] 100% of high-priority modules have examples (6 months)
- [ ] All docstrings follow Google-style (6 months)

**User Satisfaction:**
- [ ] Documentation feedback survey score > 4.0/5.0
- [ ] Reduce "documentation needed" issues by 50%
- [ ] Increase time on docs site (indicates better content)

**Developer Productivity:**
- [ ] Reduce time to understand API (survey developers)
- [ ] Fewer questions in Slack/Discord about API usage
- [ ] Faster onboarding for new contributors

### If Migrating to pdoc (Hybrid or Full)

**Migration Progress:**
- [ ] Phase 1: Modern modules migrated (1 month)
- [ ] Phase 2: Data layer migrated (2 months)
- [ ] Phase 3: Legacy modules migrated (6 months)

**Technical Metrics:**
- [ ] Build time < 5 minutes (both systems combined)
- [ ] Zero broken cross-references
- [ ] All Cython extensions documented (via stubs or exclusion)

**Quality Metrics:**
- [ ] Same as MkDocs option above
- [ ] Plus: Auto-generated API docs updated on every commit

---

## 9. Conclusion

### Summary

**Current State:**
- MkDocs + mkdocstrings is production-ready and working well
- 40% of codebase has excellent docstrings (modern modules)
- 60% needs improvement (legacy Zipline code)
- 100+ pages of hand-written documentation
- 11 Jupyter tutorial notebooks

**pdoc Evaluation:**
- Excellent tool for pure API documentation
- Simpler than MkDocs, but limited for comprehensive docs
- Unclear Cython support (needs testing)
- Would require 180-255 hours of docstring work for full coverage

**Recommendation:**
✅ **Continue with MkDocs + Incremental Improvement**

**Rationale:**
1. Current system meets all requirements
2. Preserves valuable hand-written content
3. Lower total effort (no migration overhead)
4. Can still migrate to pdoc later if needed
5. Incremental improvement aligns with agile development

**Alternative:**
⚠️ **Hybrid system** (MkDocs for guides + pdoc for API) if auto-generated API docs are strongly desired, but adds complexity

**Not Recommended:**
❌ **Full migration to pdoc** - loses too much valuable content

### Next Steps

**If continuing with MkDocs (recommended):**
1. Create docstring style guide (this week)
2. Add docstring linter to pre-commit hooks (this week)
3. Convert NumPy-style docstrings to Google-style (automated, 1-2 weeks)
4. Add module-level docstrings (2-4 weeks)
5. Improve high-priority APIs (ongoing)

**If pursuing hybrid approach:**
1. Set up pdoc for modern modules (1 week)
2. Configure deployment pipeline (1 week)
3. Test linking between MkDocs and pdoc (1 week)
4. Document the hybrid system for contributors (1 week)
5. Phase in legacy modules as docstrings improve (3-6 months)

**If testing pdoc with Cython:**
1. Install pdoc (`pip install pdoc`)
2. Test with one Cython extension
3. Evaluate output quality
4. Decide on stub files or exclusion
5. Document findings

---

## Appendix A: Docstring Conversion Tool

### Automated NumPy → Google Style Conversion

**Tool Options:**
1. **pyment** - Python docstring converter
   ```bash
   pip install pyment
   pyment -w -o google rustybt/finance/slippage.py
   ```

2. **docconvert** - Another converter
   ```bash
   pip install docconvert
   docconvert --input-style numpy --output-style google rustybt/
   ```

3. **Custom script** using `docstring_parser` library
   ```python
   from docstring_parser import parse, Docstring
   from docstring_parser.google import compose

   # Read NumPy-style docstring
   numpy_doc = parse(original_docstring, style=DocstringStyle.NUMPYDOC)

   # Convert to Google-style
   google_doc = compose(numpy_doc)
   ```

**Recommendation:** Test with `pyment` on a few files first, review output, then batch convert

---

## Appendix B: pdoc Configuration Example

### Basic pdoc Setup

```bash
# Install
pip install pdoc

# Generate docs for modern modules
pdoc rustybt.analytics \
     rustybt.live \
     rustybt.optimization \
     rustybt.portfolio \
     rustybt.backtest \
     --output-dir docs/api

# Serve locally with live reload
pdoc rustybt.analytics --http localhost:8080
```

### Custom Template (Optional)

```html
<!-- pdoc_template.html -->
<!doctype html>
<html>
<head>
    <title>{{ module.name }} - RustyBT API</title>
    <link rel="stylesheet" href="custom.css">
</head>
<body>
    <!-- pdoc will inject module content here -->
    {{ content }}
</body>
</html>
```

### Exclude Patterns

```python
# In module docstring or __init__.py
__pdoc__ = {
    'internal': False,  # Exclude 'internal' submodule
    'MyClass.private_method': False,  # Exclude specific method
}
```

---

## Appendix C: Resources

### Documentation Tools
- **MkDocs:** https://www.mkdocs.org/
- **MkDocs Material:** https://squidfunk.github.io/mkdocs-material/
- **mkdocstrings:** https://mkdocstrings.github.io/
- **pdoc:** https://pdoc.dev/
- **pdoc3:** https://pdoc3.github.io/pdoc/

### Docstring Guides
- **Google Style Guide:** https://google.github.io/styleguide/pyguide.html#38-comments-and-docstrings
- **NumPy Style Guide:** https://numpydoc.readthedocs.io/en/latest/format.html
- **PEP 257 - Docstring Conventions:** https://peps.python.org/pep-0257/

### Docstring Tools
- **pydocstyle:** https://www.pydocstyle.org/
- **darglint:** https://github.com/terrencepreilly/darglint
- **pyment:** https://github.com/dadadel/pyment
- **interrogate:** https://interrogate.readthedocs.io/ (coverage tool)

### Type Hinting
- **PEP 484 - Type Hints:** https://peps.python.org/pep-0484/
- **PEP 526 - Variable Annotations:** https://peps.python.org/pep-0526/
- **typing module:** https://docs.python.org/3/library/typing.html

---

**End of Assessment**
