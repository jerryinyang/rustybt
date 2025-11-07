# Cython Build Check Pre-Commit Hook

## Purpose

This pre-commit hook (`check_cython_build.py`) prevents a critical bug where Cython source files (`.pyx`) are modified but the compiled extensions (`.so`, `.pyd`) are not rebuilt, causing code changes to not take effect.

## The Problem It Solves

**Bug**: RUSTYBT-DATA-001 lookahead bias report (2025-11-07)

The fix for the data alignment bug was merged at 12:22, but the Cython extensions were not recompiled. A benchmark ran at 13:28 using the old compiled code (from 11:45), detecting a bug that was already fixed in the source code.

## How It Works

1. Finds all `.pyx` files in the repository
2. For each `.pyx` file, locates the corresponding compiled extension (`.so` or `.pyd`)
3. Compares file modification timestamps
4. If the `.pyx` is newer than the compiled extension, the hook fails with clear instructions

## Usage

The hook runs automatically on every commit that touches `.pyx` files.

### Manual Testing

```bash
# Test the hook directly
python3 scripts/check_cython_build.py

# Run via pre-commit
pre-commit run check-cython-build --all-files
```

### When the Hook Fails

If you see this error:

```
🚨 CYTHON EXTENSIONS ARE STALE OR MISSING

❌ rustybt/_protocol.pyx
   Source modified: 2025-11-07 13:42:46
   Extension built: 2025-11-07 13:35:48
   Extension is 7.0 minutes older
```

**Fix it by:**

1. Recompile Cython extensions:
   ```bash
   python setup.py build_ext --inplace
   ```

2. Stage the updated `.so` files:
   ```bash
   git add rustybt/**/*.so
   ```

3. Commit again

## Technical Details

### File Patterns

The hook looks for compiled extensions matching these patterns:
- Linux: `<module>.cpython-312-x86_64-linux-gnu.so`
- macOS: `<module>.cpython-312-darwin.so`
- Windows: `<module>.cp312-win_amd64.pyd`

### Exit Codes

- `0`: All Cython extensions are up-to-date
- `1`: Some extensions are stale or missing

## Configuration

In `.pre-commit-config.yaml`:

```yaml
- id: check-cython-build
  name: Check Cython Extensions Are Up-to-Date
  entry: python3 scripts/check_cython_build.py
  language: system
  pass_filenames: false
  description: "Ensures Cython .pyx files have been recompiled after changes"
  files: \.pyx$
```

## Related

- Fix document: `docs/internal/sprint-debug/fixes/completed/2025-11-07-133200-critical-lookahead-bias-data-history.md`
- Original bug: `docs/internal/sprint-debug/fixes/completed/2025-11-07-105919-history-off-by-one-data-shift.md`
