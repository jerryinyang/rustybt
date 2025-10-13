// Data Operations Module
//
// This module provides Rust-optimized implementations for common data operations
// used in backtesting, particularly for windowing and array manipulations.

use pyo3::prelude::*;

/// Extract a window of values from an array
///
/// Efficiently extracts a contiguous window from an array. This is used
/// for historical data window retrieval.
///
/// # Arguments
///
/// * `values` - Source array
/// * `start` - Start index (inclusive)
/// * `end` - End index (exclusive)
///
/// # Returns
///
/// Slice of values from start to end
#[pyfunction]
pub fn rust_window_slice(values: Vec<f64>, start: usize, end: usize) -> PyResult<Vec<f64>> {
    if start >= values.len() || end > values.len() || start >= end {
        return Err(PyErr::new::<pyo3::exceptions::PyIndexError, _>(
            format!("Invalid window bounds: start={}, end={}, len={}", start, end, values.len())
        ));
    }

    Ok(values[start..end].to_vec())
}

/// Create a 2D array from multiple 1D arrays (for DataFrame-like structure)
///
/// This is used to efficiently construct multi-column data structures
/// without Python overhead.
///
/// # Arguments
///
/// * `columns` - Vec of columns, where each column is a Vec<f64>
///
/// # Returns
///
/// Flattened 2D array in column-major order
#[pyfunction]
pub fn rust_create_columns(columns: Vec<Vec<f64>>) -> PyResult<(Vec<f64>, usize, usize)> {
    if columns.is_empty() {
        return Ok((Vec::new(), 0, 0));
    }

    let n_rows = columns[0].len();
    let n_cols = columns.len();

    // Validate all columns have same length
    for (i, col) in columns.iter().enumerate() {
        if col.len() != n_rows {
            return Err(PyErr::new::<pyo3::exceptions::PyValueError, _>(
                format!("Column {} has length {}, expected {}", i, col.len(), n_rows)
            ));
        }
    }

    // Flatten in column-major order
    let mut result = Vec::with_capacity(n_rows * n_cols);
    for col in columns {
        result.extend(col);
    }

    Ok((result, n_rows, n_cols))
}

/// Fast array indexing for multiple indices
///
/// Extracts values at specified indices. More efficient than Python list comprehension
/// for large arrays.
///
/// # Arguments
///
/// * `values` - Source array
/// * `indices` - Indices to extract
///
/// # Returns
///
/// Array of values at the specified indices
#[pyfunction]
pub fn rust_index_select(values: Vec<f64>, indices: Vec<usize>) -> PyResult<Vec<f64>> {
    let mut result = Vec::with_capacity(indices.len());

    for &idx in &indices {
        if idx >= values.len() {
            return Err(PyErr::new::<pyo3::exceptions::PyIndexError, _>(
                format!("Index {} out of bounds for array of length {}", idx, values.len())
            ));
        }
        result.push(values[idx]);
    }

    Ok(result)
}

/// Fill NaN values with a specified value
///
/// # Arguments
///
/// * `values` - Array with potential NaN values
/// * `fill_value` - Value to replace NaN with
///
/// # Returns
///
/// Array with NaN values replaced
#[pyfunction]
pub fn rust_fillna(mut values: Vec<f64>, fill_value: f64) -> PyResult<Vec<f64>> {
    for val in values.iter_mut() {
        if val.is_nan() {
            *val = fill_value;
        }
    }
    Ok(values)
}

/// Fast pairwise operation between two arrays
///
/// Performs element-wise operation (add, subtract, multiply, divide)
///
/// # Arguments
///
/// * `left` - Left operand array
/// * `right` - Right operand array
/// * `op` - Operation: "add", "sub", "mul", "div"
///
/// # Returns
///
/// Result of element-wise operation
#[pyfunction]
pub fn rust_pairwise_op(left: Vec<f64>, right: Vec<f64>, op: &str) -> PyResult<Vec<f64>> {
    if left.len() != right.len() {
        return Err(PyErr::new::<pyo3::exceptions::PyValueError, _>(
            format!("Array lengths don't match: {} vs {}", left.len(), right.len())
        ));
    }

    let result = match op {
        "add" => left.iter().zip(&right).map(|(a, b)| a + b).collect(),
        "sub" => left.iter().zip(&right).map(|(a, b)| a - b).collect(),
        "mul" => left.iter().zip(&right).map(|(a, b)| a * b).collect(),
        "div" => left.iter().zip(&right).map(|(a, b)| a / b).collect(),
        _ => return Err(PyErr::new::<pyo3::exceptions::PyValueError, _>(
            format!("Unknown operation: {}", op)
        )),
    };

    Ok(result)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_window_slice_basic() {
        let values = vec![1.0, 2.0, 3.0, 4.0, 5.0];
        let result = rust_window_slice(values, 1, 4).unwrap();
        assert_eq!(result, vec![2.0, 3.0, 4.0]);
    }

    #[test]
    fn test_window_slice_invalid_bounds() {
        let values = vec![1.0, 2.0, 3.0];
        assert!(rust_window_slice(values.clone(), 5, 10).is_err());
        assert!(rust_window_slice(values.clone(), 2, 1).is_err());
    }

    #[test]
    fn test_create_columns_basic() {
        let col1 = vec![1.0, 2.0, 3.0];
        let col2 = vec![4.0, 5.0, 6.0];
        let (result, rows, cols) = rust_create_columns(vec![col1, col2]).unwrap();

        assert_eq!(rows, 3);
        assert_eq!(cols, 2);
        assert_eq!(result, vec![1.0, 2.0, 3.0, 4.0, 5.0, 6.0]);
    }

    #[test]
    fn test_create_columns_mismatched_lengths() {
        let col1 = vec![1.0, 2.0, 3.0];
        let col2 = vec![4.0, 5.0];
        assert!(rust_create_columns(vec![col1, col2]).is_err());
    }

    #[test]
    fn test_index_select_basic() {
        let values = vec![10.0, 20.0, 30.0, 40.0, 50.0];
        let indices = vec![0, 2, 4];
        let result = rust_index_select(values, indices).unwrap();
        assert_eq!(result, vec![10.0, 30.0, 50.0]);
    }

    #[test]
    fn test_index_select_out_of_bounds() {
        let values = vec![1.0, 2.0, 3.0];
        let indices = vec![5];
        assert!(rust_index_select(values, indices).is_err());
    }

    #[test]
    fn test_fillna_basic() {
        let values = vec![1.0, f64::NAN, 3.0, f64::NAN, 5.0];
        let result = rust_fillna(values, 0.0).unwrap();
        assert_eq!(result, vec![1.0, 0.0, 3.0, 0.0, 5.0]);
    }

    #[test]
    fn test_pairwise_add() {
        let left = vec![1.0, 2.0, 3.0];
        let right = vec![10.0, 20.0, 30.0];
        let result = rust_pairwise_op(left, right, "add").unwrap();
        assert_eq!(result, vec![11.0, 22.0, 33.0]);
    }

    #[test]
    fn test_pairwise_mul() {
        let left = vec![2.0, 3.0, 4.0];
        let right = vec![10.0, 10.0, 10.0];
        let result = rust_pairwise_op(left, right, "mul").unwrap();
        assert_eq!(result, vec![20.0, 30.0, 40.0]);
    }

    #[test]
    fn test_pairwise_mismatched_lengths() {
        let left = vec![1.0, 2.0];
        let right = vec![1.0, 2.0, 3.0];
        assert!(rust_pairwise_op(left, right, "add").is_err());
    }

    #[test]
    fn test_pairwise_invalid_op() {
        let left = vec![1.0, 2.0];
        let right = vec![1.0, 2.0];
        assert!(rust_pairwise_op(left, right, "invalid").is_err());
    }
}
