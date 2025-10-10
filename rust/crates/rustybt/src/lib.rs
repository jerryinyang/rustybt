use pyo3::prelude::*;

// Declare submodules
mod indicators;
mod data_ops;
mod decimal_ops;

/// RustyBT Rust Extensions Module
///
/// This module provides performance-critical functions implemented in Rust
/// for use in the RustyBT backtesting engine.
///
/// Modules:
/// - indicators: Technical indicators (SMA, EMA, RSI, etc.)
/// - data_ops: Data operations (windowing, slicing, array operations)
#[pymodule]
fn _rustybt(m: &Bound<'_, PyModule>) -> PyResult<()> {
    // Register indicator functions
    m.add_function(wrap_pyfunction!(indicators::rust_sum, m)?)?;  // Legacy two-arg sum
    m.add_function(wrap_pyfunction!(indicators::rust_array_sum, m)?)?;
    m.add_function(wrap_pyfunction!(indicators::rust_sma, m)?)?;
    m.add_function(wrap_pyfunction!(indicators::rust_ema, m)?)?;
    m.add_function(wrap_pyfunction!(indicators::rust_mean, m)?)?;
    m.add_function(wrap_pyfunction!(indicators::rust_rolling_sum, m)?)?;

    // Register data operation functions
    m.add_function(wrap_pyfunction!(data_ops::rust_window_slice, m)?)?;
    m.add_function(wrap_pyfunction!(data_ops::rust_create_columns, m)?)?;
    m.add_function(wrap_pyfunction!(data_ops::rust_index_select, m)?)?;
    m.add_function(wrap_pyfunction!(data_ops::rust_fillna, m)?)?;
    m.add_function(wrap_pyfunction!(data_ops::rust_pairwise_op, m)?)?;

    // Register decimal operation functions
    m.add_function(wrap_pyfunction!(decimal_ops::rust_decimal_window_slice, m)?)?;
    m.add_function(wrap_pyfunction!(decimal_ops::rust_decimal_index_select, m)?)?;
    m.add_function(wrap_pyfunction!(decimal_ops::rust_decimal_sum, m)?)?;
    m.add_function(wrap_pyfunction!(decimal_ops::rust_decimal_mean, m)?)?;
    m.add_function(wrap_pyfunction!(decimal_ops::rust_decimal_sma, m)?)?;
    m.add_function(wrap_pyfunction!(decimal_ops::rust_decimal_ema, m)?)?;
    m.add_function(wrap_pyfunction!(decimal_ops::rust_decimal_rolling_sum, m)?)?;
    m.add_function(wrap_pyfunction!(decimal_ops::rust_decimal_pairwise_op, m)?)?;
    m.add_function(wrap_pyfunction!(decimal_ops::rust_decimal_fillna, m)?)?;

    Ok(())
}
