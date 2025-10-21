# Test Strategy with YAML Configuration

This is a test strategy that uses `strategy.yaml` to explicitly specify which files to capture.

## Files

- `main.py` - Main entry point
- `custom_helpers.py` - Custom helper functions
- `config/params.json` - Strategy parameters
- `README.md` - This documentation

## Purpose

This fixture tests that YAML configuration takes precedence over automatic entry point detection (100% backward compatibility - CR-003).
