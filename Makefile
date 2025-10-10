.PHONY: help profile profile-daily profile-hourly profile-minute profile-all profile-compare test lint format clean rust-dev rust-build rust-test rust-clean

# Default target
help:
	@echo "RustyBT Development Makefile"
	@echo ""
	@echo "Available targets:"
	@echo "  help            - Show this help message"
	@echo "  profile         - Run all profiling scenarios (daily, hourly, minute)"
	@echo "  profile-daily   - Run daily data profiling scenario"
	@echo "  profile-hourly  - Run hourly data profiling scenario"
	@echo "  profile-minute  - Run minute data profiling scenario"
	@echo "  profile-all     - Run all profiling with all profilers (cprofile + memory)"
	@echo "  profile-compare - Compare baseline vs post-rust profiling results"
	@echo "  test            - Run test suite"
	@echo "  lint            - Run linting checks"
	@echo "  format          - Format code with black and ruff"
	@echo "  clean           - Clean generated files"
	@echo ""
	@echo "Rust targets:"
	@echo "  rust-dev        - Build Rust extension in development mode"
	@echo "  rust-build      - Build Rust extension in release mode"
	@echo "  rust-test       - Run Rust integration tests"
	@echo "  rust-clean      - Clean Rust build artifacts"
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
	@echo "Comparing baseline vs post-rust profiling results..."
	python scripts/profiling/compare_profiles.py \
		docs/performance/profiles/baseline/ \
		docs/performance/profiles/post-rust/ \
		--scenario all

# Testing targets
test:
	pytest tests/ -v --tb=short

# Code quality targets
lint:
	ruff check rustybt/ scripts/ tests/
	mypy rustybt/ scripts/

format:
	black rustybt/ scripts/ tests/
	ruff check --fix rustybt/ scripts/ tests/

# Clean targets
clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type f -name ".coverage" -delete
	rm -rf .pytest_cache .mypy_cache .ruff_cache htmlcov

# Rust targets
rust-dev:
	@echo "Building Rust extension (development mode)..."
	cd rust && maturin develop

rust-build:
	@echo "Building Rust extension (release mode)..."
	cd rust && maturin build --release

rust-test:
	@echo "Running Rust integration tests..."
	pytest tests/rust/ -v

rust-clean:
	@echo "Cleaning Rust build artifacts..."
	cd rust && cargo clean
	rm -rf rust/target/
