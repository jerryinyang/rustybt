# Rust Setup and Development Guide

This guide explains how to set up, build, and develop Rust extensions for RustyBT.

## Table of Contents

- [Prerequisites](#prerequisites)
- [Building Rust Extensions](#building-rust-extensions)
- [Development Workflow](#development-workflow)
- [Debugging Rust Code](#debugging-rust-code)
- [Adding New Rust Functions](#adding-new-rust-functions)
- [Common Errors and Solutions](#common-errors-and-solutions)
- [Resources](#resources)

## Prerequisites

### Install Rust Toolchain

**macOS / Linux:**
```bash
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
```

**Windows:**
Download and run [rustup-init.exe](https://rustup.rs/)

**Verify Installation:**
```bash
rustc --version  # Should be 1.90+
cargo --version
```

### Python Requirements

- **Python 3.12+** required (PyO3 0.26 supports Python 3.12-3.14)
- `setuptools-rust` for building Rust extensions alongside Cython

The build system uses `setuptools-rust` to integrate Rust extensions with the existing Python/Cython build process. When you run `pip install -e .` from the project root, both Cython and Rust extensions are built automatically.

## Building Rust Extensions

### Integrated Build (Recommended)

The Rust extensions are automatically built as part of the standard Python package installation:

```bash
# From project root
pip install -e .
```

This uses `setuptools-rust` to build both Cython and Rust extensions in one step.

**Verify the build:**
```bash
python -c "from rustybt import rust_sum; print(rust_sum(2, 3))"
# Output: 5
```

### Manual Build (Development)

For faster iteration during Rust development, you can build just the Rust extension using maturin:

```bash
cd rust/
maturin develop
```

This rebuilds only the Rust extension without reinstalling the entire Python package.

### Release Build

For production builds with optimizations:

```bash
# Full package with all extensions
pip install --no-build-isolation .

# Or just Rust extension
cd rust/
maturin build --release
```

### Using Make Targets

Convenient make targets are available from the project root:

```bash
# Build Rust extension (development)
make rust-dev

# Build Rust extension (release)
make rust-build

# Run Rust tests
make rust-test
```

## Development Workflow

The typical workflow for developing Rust extensions:

1. **Edit Rust code** in `rust/src/`

2. **Rebuild the extension:**
   ```bash
   cd rust/
   maturin develop
   ```

   Or from project root:
   ```bash
   make rust-dev
   ```

3. **Test from Python:**
   ```bash
   pytest tests/rust/ -v
   ```

4. **Iterate:** Repeat steps 1-3 until complete

### Hot Reload Tips

- `maturin develop` is fast for incremental builds (~1-5 seconds)
- Use `cargo check` for faster syntax/type checking without linking:
  ```bash
  cd rust/
  cargo check
  ```

## Debugging Rust Code

### Logging

Use the `log` crate in Rust and integrate with Python's `structlog`:

```rust
use log::{debug, info, warn, error};

#[pyfunction]
fn my_function() -> PyResult<()> {
    info!("Starting computation");
    debug!("Debug details: {}", value);
    Ok(())
}
```

### Panic Handling

Rust panics are converted to Python exceptions by PyO3:

```rust
#[pyfunction]
fn checked_divide(a: i64, b: i64) -> PyResult<i64> {
    if b == 0 {
        return Err(PyErr::new::<pyo3::exceptions::PyValueError, _>(
            "Division by zero"
        ));
    }
    Ok(a / b)
}
```

### Rust Unit Tests

Write tests directly in Rust:

```rust
#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_rust_sum() {
        assert_eq!(rust_sum(2, 3).unwrap(), 5);
    }
}
```

Run Rust tests (note: `cargo test` doesn't work with `extension-module` feature):
```bash
cargo check  # Check compilation only
```

Instead, test via Python:
```bash
pytest tests/rust/ -v
```

## Adding New Rust Functions

### Basic Function Pattern

```rust
use pyo3::prelude::*;

/// Multiply two numbers.
///
/// # Arguments
///
/// * `a` - First number
/// * `b` - Second number
///
/// # Returns
///
/// Product of a and b
#[pyfunction]
fn multiply(a: i64, b: i64) -> PyResult<i64> {
    Ok(a * b)
}
```

### Register in Module

Add to `_rustybt` module in `rust/src/lib.rs`:

```rust
#[pymodule]
fn _rustybt(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(rust_sum, m)?)?;
    m.add_function(wrap_pyfunction!(multiply, m)?)?;  // Add new function
    Ok(())
}
```

### Expose in Python Package

Update `rustybt/__init__.py`:

```python
try:
    from rustybt._rustybt import rust_sum, multiply
    _RUST_AVAILABLE = True
except ImportError:
    _RUST_AVAILABLE = False
    rust_sum = None
    multiply = None

__all__ = [
    # ... existing exports ...
    "rust_sum",
    "multiply",  # Add new export
]
```

### Function with Decimal

```rust
use pyo3::prelude::*;
use pyo3::types::PyString;

#[pyfunction]
fn decimal_sum(py: Python, a: &PyAny, b: &PyAny) -> PyResult<PyObject> {
    // Import Python's Decimal
    let decimal_module = py.import_bound("decimal")?;
    let decimal_class = decimal_module.getattr("Decimal")?;

    // Convert to Decimal if not already
    let a_dec = decimal_class.call1((a,))?;
    let b_dec = decimal_class.call1((b,))?;

    // Perform addition
    let result = a_dec.call_method1("__add__", (b_dec,))?;

    Ok(result.into())
}
```

### Function Returning Result

```rust
#[pyfunction]
fn safe_divide(a: f64, b: f64) -> PyResult<f64> {
    if b == 0.0 {
        Err(PyErr::new::<pyo3::exceptions::PyValueError, _>(
            "Cannot divide by zero"
        ))
    } else {
        Ok(a / b)
    }
}
```

## Common Errors and Solutions

### Error: `extension-module` feature causes linking errors in tests

**Problem:** `cargo test` fails with undefined symbols.

**Solution:** Don't use `cargo test` with PyO3 extensions. Test via Python instead:
```bash
pytest tests/rust/ -v
```

### Error: `cannot find module _rustybt`

**Problem:** Rust extension not built or not installed.

**Solution:**
```bash
cd rust/
maturin develop
```

### Error: `pyo3` version mismatch

**Problem:** Incompatible PyO3 version.

**Solution:** Keep the workspace dependency on PyO3 0.26 with abi3 support. From the repository root:
```toml
[workspace.dependencies]
pyo3 = { version = "0.26", features = ["extension-module", "abi3-py312"] }
```

If a crate overrides this dependency, sync it back to the workspace version. After updating, rebuild:
```bash
cd rust/
cargo clean
maturin develop
```

### Error: Python version not supported

**Problem:** PyO3 0.26 with the `abi3-py312` feature targets Python 3.12+.

**Solution:** Upgrade to a supported Python version or, if you must support an older interpreter, rebuild with the appropriate abi3 feature flag (for example, `abi3-py311`) in `Cargo.toml`—but note that the project baseline is Python 3.12 and newer.

## Platform-Specific Notes

### macOS

- Rust toolchain installs to `~/.cargo/bin/`
- Add to PATH: `export PATH="$HOME/.cargo/bin:$PATH"`
- Apple Silicon (M1/M2): Builds target `aarch64-apple-darwin`
- Intel: Builds target `x86_64-apple-darwin`

### Linux

- Ubuntu/Debian: `sudo apt install build-essential`
- May need: `sudo apt install python3-dev`
- Target: `x86_64-unknown-linux-gnu`

### Windows

- Install Visual Studio Build Tools or Visual C++ Build Tools
- maturin will auto-detect and use the MSVC toolchain
- Target: `x86_64-pc-windows-msvc`

## Performance Tips

1. **Use `--release` for benchmarks:**
   ```bash
   maturin build --release
   ```

2. **Profile Rust code** with `cargo flamegraph`:
   ```bash
   cargo install flamegraph
   cargo flamegraph
   ```

3. **Check assembly** to verify optimizations:
   ```bash
   cargo rustc --release -- --emit asm
   ```

## Workspace Structure

The Rust code is organized as a Cargo workspace for scalability:

```
rust/
├── Cargo.toml              # Workspace root configuration
├── pyproject.toml          # Maturin build configuration
├── crates/
│   └── rustybt/            # Main extension crate
│       ├── Cargo.toml      # Crate-specific dependencies
│       └── src/
│           └── lib.rs      # PyO3 module entry point
└── target/                 # Build artifacts
```

**Key Points:**
- Workspace allows adding future crates (e.g., `rustybt-indicators`, `rustybt-data`)
- Shared dependencies defined in workspace root `Cargo.toml`
- Each crate can have its own dependencies in `crates/*/Cargo.toml`

## Technical Details

### PyO3 Version

- **PyO3 0.26+** with `abi3-py312` feature
- Supports Python 3.12, 3.13, and 3.14
- Stable ABI for forward compatibility
- Built as `cdylib` (C dynamic library) for Python import

### Cross-Platform Support

The build system supports:
- **Linux**: x86_64, aarch64
- **macOS**: Intel (x86_64), Apple Silicon (arm64), Universal2
- **Windows**: x86_64

Maturin automatically detects the platform and builds appropriate wheels.

## Resources

### Official Documentation

- [PyO3 User Guide](https://pyo3.rs/)
- [maturin Documentation](https://www.maturin.rs/)
- [The Rust Book](https://doc.rust-lang.org/book/)
- [Rust by Example](https://doc.rust-lang.org/rust-by-example/)

### RustyBT-Specific

- [Tech Stack Documentation](../architecture/tech-stack.md)
- [Coding Standards](../architecture/coding-standards.md)
- [Epic 7: Performance Optimization](../prd/epic-7-performance-optimization-rust-integration.md)

### PyO3 Examples

- [PyO3 Examples Repository](https://github.com/PyO3/pyo3/tree/main/examples)
- [rust-numpy](https://github.com/PyO3/rust-numpy) - NumPy integration
- [polars](https://github.com/pola-rs/polars) - Real-world example of Rust DataFrame library with Python bindings

---

**Questions or Issues?** Open an issue on the RustyBT GitHub repository.
