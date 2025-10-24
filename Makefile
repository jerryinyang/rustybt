.PHONY: help profile profile-daily profile-hourly profile-minute profile-all profile-compare test lint format clean docs docs-serve docs-build build

# Default target
help:
	@echo "RustyBT Development Makefile"
	@echo ""
	@echo "Available targets:"
	@echo "  help            - Show this help message"
	@echo "  test            - Run test suite"
	@echo "  lint            - Run linting checks"
	@echo "  format          - Format code with black and ruff"
	@echo "  build           - Build Python package (wheel + source dist)"
	@echo "  clean           - Clean generated files"
	@echo ""
	@echo "Documentation targets:"
	@echo "  docs            - Build documentation locally"
	@echo "  docs-serve      - Serve documentation locally with hot reload"
	@echo "  docs-build      - Build documentation for deployment"
	@echo ""
	@echo "Profiling targets:"
	@echo "  profile         - Run all profiling scenarios (daily, hourly, minute)"
	@echo "  profile-daily   - Run daily data profiling scenario"
	@echo "  profile-hourly  - Run hourly data profiling scenario"
	@echo "  profile-minute  - Run minute data profiling scenario"
	@echo "  profile-all     - Run all profiling with all profilers (cprofile + memory)"
	@echo "  profile-compare - Compare baseline vs optimized profiling results"
	@echo ""

# Profiling targets
profile: profile-daily profile-hourly profile-minute

profile-daily:
	@echo "Running daily data profiling scenario..."
	python scripts/profiling/run_profiler.py --scenario daily --profiler cprofile

profile-hourly:
	@echo "Running hourly data profiling scenario..."
	python scripts/profiling/run_profiler.py --scenario hourly --profiler cprofile

profile-minute:
	@echo "Running minute data profiling scenario..."
	python scripts/profiling/run_profiler.py --scenario minute --profiler cprofile

profile-all:
	@echo "Running all profiling scenarios with all profilers..."
	python scripts/profiling/run_profiler.py --scenario all --profiler all

profile-compare:
	@echo "Comparing baseline vs optimized profiling results..."
	python scripts/profiling/compare_profiles.py \
		docs/performance/profiles/baseline/ \
		docs/performance/profiles/optimized/ \
		--scenario all

# Testing targets
test:
	pytest tests/ -v --tb=short

# Build targets
build:
	@echo "Building Python package..."
	uv build

# Code quality targets
lint:
	ruff check rustybt/ scripts/ tests/
	mypy rustybt/ scripts/

format:
	black rustybt/ scripts/ tests/
	ruff check --fix rustybt/ scripts/ tests/

# Documentation targets
docs: docs-serve

docs-serve:
	@echo "Starting documentation server with hot reload..."
	mkdocs serve

docs-build:
	@echo "Building documentation for deployment..."
	mkdocs build --strict

# Clean targets
clean:
	@echo "Cleaning generated files..."
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type f -name ".coverage" -delete
	rm -rf .pytest_cache .mypy_cache .ruff_cache htmlcov dist/ build/ site/
