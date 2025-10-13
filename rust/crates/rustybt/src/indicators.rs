// Technical Indicators Module
//
// This module provides Rust-optimized implementations of common technical indicators
// for financial data analysis. These functions are designed to be called from Python
// via PyO3 bindings.

use pyo3::prelude::*;
use std::f64;

/// Calculate Simple Moving Average (SMA)
///
/// Computes the simple moving average of a price series over a specified window.
///
/// # Arguments
///
/// * `values` - Slice of price values
/// * `window` - Window size for the moving average
///
/// # Returns
///
/// Array of SMA values. The first (window-1) elements are NaN since there's
/// insufficient data for the calculation.
///
/// # Examples
///
/// ```python
/// from rustybt._rustybt import rust_sma
/// prices = [1.0, 2.0, 3.0, 4.0, 5.0]
/// sma_3 = rust_sma(prices, 3)
/// # Result: [nan, nan, 2.0, 3.0, 4.0]
/// ```
#[pyfunction]
pub fn rust_sma(values: Vec<f64>, window: usize) -> PyResult<Vec<f64>> {
    if window == 0 {
        return Err(PyErr::new::<pyo3::exceptions::PyValueError, _>(
            "Window size must be greater than 0",
        ));
    }

    if values.is_empty() {
        return Ok(Vec::new());
    }

    let len = values.len();
    let mut result = vec![f64::NAN; len];

    if len < window {
        return Ok(result);
    }

    // Calculate first window
    let first_sum: f64 = values.iter().take(window).sum();
    result[window - 1] = first_sum / window as f64;

    // Use sliding window for remaining values
    for i in window..len {
        let prev_sma = result[i - 1];
        let new_val = values[i];
        let old_val = values[i - window];
        result[i] = prev_sma + (new_val - old_val) / window as f64;
    }

    Ok(result)
}

/// Calculate Exponential Moving Average (EMA)
///
/// Computes the exponential moving average of a price series with specified span.
///
/// # Arguments
///
/// * `values` - Slice of price values
/// * `span` - Span for the EMA (higher span = more smoothing)
///
/// # Returns
///
/// Array of EMA values. Uses the first value as the initial EMA.
///
/// # Examples
///
/// ```python
/// from rustybt._rustybt import rust_ema
/// prices = [1.0, 2.0, 3.0, 4.0, 5.0]
/// ema_3 = rust_ema(prices, 3)
/// ```
#[pyfunction]
pub fn rust_ema(values: Vec<f64>, span: usize) -> PyResult<Vec<f64>> {
    if span == 0 {
        return Err(PyErr::new::<pyo3::exceptions::PyValueError, _>(
            "Span must be greater than 0",
        ));
    }

    if values.is_empty() {
        return Ok(Vec::new());
    }

    let len = values.len();
    let mut result = vec![0.0; len];

    // EMA multiplier: 2 / (span + 1)
    let alpha = 2.0 / (span as f64 + 1.0);

    // Initialize with first value
    result[0] = values[0];

    // Calculate EMA for remaining values
    for i in 1..len {
        result[i] = alpha * values[i] + (1.0 - alpha) * result[i - 1];
    }

    Ok(result)
}

/// Calculate sum of two integers (legacy API for backward compatibility)
///
/// # Arguments
///
/// * `a` - First integer
/// * `b` - Second integer
///
/// # Returns
///
/// Sum of a and b
#[pyfunction]
pub fn rust_sum(a: i64, b: i64) -> PyResult<i64> {
    Ok(a + b)
}

/// Calculate array sum (optimized)
///
/// Fast summation of array values using Rust's iterator optimizations.
///
/// # Arguments
///
/// * `values` - Array of numeric values
///
/// # Returns
///
/// Sum of all values
#[pyfunction]
pub fn rust_array_sum(values: Vec<f64>) -> PyResult<f64> {
    Ok(values.iter().sum())
}

/// Calculate array mean (optimized)
///
/// Fast mean calculation.
///
/// # Arguments
///
/// * `values` - Array of numeric values
///
/// # Returns
///
/// Mean of all values, or NaN if array is empty
#[pyfunction]
pub fn rust_mean(values: Vec<f64>) -> PyResult<f64> {
    if values.is_empty() {
        return Ok(f64::NAN);
    }
    Ok(values.iter().sum::<f64>() / values.len() as f64)
}

/// Calculate rolling window sum
///
/// Computes sum over a rolling window efficiently.
///
/// # Arguments
///
/// * `values` - Array of numeric values
/// * `window` - Window size
///
/// # Returns
///
/// Array of rolling sums. First (window-1) elements are NaN.
#[pyfunction]
pub fn rust_rolling_sum(values: Vec<f64>, window: usize) -> PyResult<Vec<f64>> {
    if window == 0 {
        return Err(PyErr::new::<pyo3::exceptions::PyValueError, _>(
            "Window size must be greater than 0",
        ));
    }

    if values.is_empty() {
        return Ok(Vec::new());
    }

    let len = values.len();
    let mut result = vec![f64::NAN; len];

    if len < window {
        return Ok(result);
    }

    // Calculate first window
    let first_sum: f64 = values.iter().take(window).sum();
    result[window - 1] = first_sum;

    // Use sliding window for remaining values
    for i in window..len {
        result[i] = result[i - 1] + values[i] - values[i - window];
    }

    Ok(result)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_sma_basic() {
        let values = vec![1.0, 2.0, 3.0, 4.0, 5.0];
        let result = rust_sma(values, 3).unwrap();

        assert!(result[0].is_nan());
        assert!(result[1].is_nan());
        assert!((result[2] - 2.0).abs() < 1e-10);
        assert!((result[3] - 3.0).abs() < 1e-10);
        assert!((result[4] - 4.0).abs() < 1e-10);
    }

    #[test]
    fn test_sma_window_larger_than_data() {
        let values = vec![1.0, 2.0];
        let result = rust_sma(values, 5).unwrap();
        assert!(result.iter().all(|&x| x.is_nan()));
    }

    #[test]
    fn test_sma_window_one() {
        let values = vec![1.0, 2.0, 3.0];
        let expected = values.clone();
        let result = rust_sma(values, 1).unwrap();
        assert_eq!(result, expected);
    }

    #[test]
    fn test_sma_empty() {
        let values = vec![];
        let result = rust_sma(values, 3).unwrap();
        assert!(result.is_empty());
    }

    #[test]
    fn test_ema_basic() {
        let values = vec![1.0, 2.0, 3.0, 4.0, 5.0];
        let result = rust_ema(values, 3).unwrap();

        // First value should be equal to input
        assert_eq!(result[0], 1.0);

        // EMA should be increasing
        for i in 1..result.len() {
            assert!(result[i] > result[i - 1]);
        }
    }

    #[test]
    fn test_ema_constant_values() {
        let values = vec![5.0; 10];
        let result = rust_ema(values, 3).unwrap();

        // EMA of constant values should converge to that constant
        for i in 0..result.len() {
            assert!((result[i] - 5.0).abs() < 1e-10);
        }
    }

    #[test]
    fn test_sum_legacy() {
        let result = rust_sum(2, 3).unwrap();
        assert_eq!(result, 5);

        let result = rust_sum(-10, 5).unwrap();
        assert_eq!(result, -5);
    }

    #[test]
    fn test_array_sum_basic() {
        let values = vec![1.0, 2.0, 3.0, 4.0, 5.0];
        let result = rust_array_sum(values).unwrap();
        assert_eq!(result, 15.0);
    }

    #[test]
    fn test_array_sum_empty() {
        let values = vec![];
        let result = rust_array_sum(values).unwrap();
        assert_eq!(result, 0.0);
    }

    #[test]
    fn test_mean_basic() {
        let values = vec![1.0, 2.0, 3.0, 4.0, 5.0];
        let result = rust_mean(values).unwrap();
        assert_eq!(result, 3.0);
    }

    #[test]
    fn test_mean_empty() {
        let values = vec![];
        let result = rust_mean(values).unwrap();
        assert!(result.is_nan());
    }

    #[test]
    fn test_rolling_sum_basic() {
        let values = vec![1.0, 2.0, 3.0, 4.0, 5.0];
        let result = rust_rolling_sum(values, 3).unwrap();

        assert!(result[0].is_nan());
        assert!(result[1].is_nan());
        assert_eq!(result[2], 6.0);  // 1+2+3
        assert_eq!(result[3], 9.0);  // 2+3+4
        assert_eq!(result[4], 12.0); // 3+4+5
    }

    #[test]
    fn test_rolling_sum_window_one() {
        let values = vec![1.0, 2.0, 3.0];
        let expected = values.clone();
        let result = rust_rolling_sum(values, 1).unwrap();
        assert_eq!(result, expected);
    }
}
