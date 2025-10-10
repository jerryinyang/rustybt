use pyo3::exceptions::{PyIndexError, PyValueError};
use pyo3::prelude::*;
use pyo3::types::{PyAny, PyList, PyString};
use pyo3::{Bound, Py};
use rust_decimal::prelude::FromPrimitive;
use rust_decimal::Decimal as RustDecimal;
use rust_decimal::RoundingStrategy;
use std::str::FromStr;

fn parse_rounding_strategy(name: &str) -> PyResult<RoundingStrategy> {
    match name {
        "ROUND_HALF_EVEN" => Ok(RoundingStrategy::MidpointNearestEven),
        "ROUND_HALF_UP" => Ok(RoundingStrategy::MidpointAwayFromZero),
        "ROUND_HALF_DOWN" => Ok(RoundingStrategy::MidpointTowardZero),
        "ROUND_UP" => Ok(RoundingStrategy::AwayFromZero),
        "ROUND_DOWN" => Ok(RoundingStrategy::ToZero),
        "ROUND_CEILING" => Ok(RoundingStrategy::ToPositiveInfinity),
        "ROUND_FLOOR" => Ok(RoundingStrategy::ToNegativeInfinity),
        "ROUND_05UP" => Ok(RoundingStrategy::AwayFromZero),
        other => Err(PyValueError::new_err(format!(
            "Unsupported rounding mode '{}'",
            other
        ))),
    }
}

fn clamp_scale(scale: u32) -> u32 {
    if scale > 28 { 28 } else { scale }
}

fn round_decimal(value: RustDecimal, scale: u32, strategy: RoundingStrategy) -> RustDecimal {
    value.round_dp_with_strategy(clamp_scale(scale), strategy)
}

fn rust_decimal_to_py(py: Python<'_>, value: RustDecimal) -> PyResult<Py<PyAny>> {
    let decimal_module = py.import("decimal")?;
    let decimal_class = decimal_module.getattr("Decimal")?;
    let as_string = value.normalize().to_string();
    Ok(decimal_class.call1((as_string,))?.unbind())
}

fn py_decimal_to_rust(value: &Bound<'_, PyAny>) -> PyResult<RustDecimal> {
    let string_repr: Bound<'_, PyString> = value.str()?;
    let as_str = string_repr.to_str()?;
    // Normalize scientific notation: Python uses 'E', rust-decimal expects 'e'
    let normalized = as_str.replace('E', "e");
    RustDecimal::from_str(&normalized).map_err(|err| PyValueError::new_err(format!(
        "Invalid Decimal '{}': {}",
        as_str, err
    )))
}

fn pylist_to_rust(values: &Bound<'_, PyList>) -> PyResult<Vec<RustDecimal>> {
    values
        .iter()
        .map(|item| py_decimal_to_rust(&item))
        .collect::<PyResult<Vec<RustDecimal>>>()
}

#[pyfunction]
pub fn rust_decimal_window_slice(values: &Bound<'_, PyList>, start: usize, end: usize) -> PyResult<Vec<Py<PyAny>>> {
    let len = values.len();
    if start >= len || end > len || start >= end {
        return Err(PyIndexError::new_err(format!(
            "Invalid window bounds: start={}, end={}, len={}",
            start, end, len
        )));
    }

    let mut result = Vec::with_capacity(end - start);
    for idx in start..end {
        result.push(values.get_item(idx)?.unbind());
    }
    Ok(result)
}

#[pyfunction]
pub fn rust_decimal_index_select(values: &Bound<'_, PyList>, indices: Vec<usize>) -> PyResult<Vec<Py<PyAny>>> {
    let len = values.len();
    let mut result = Vec::with_capacity(indices.len());

    for idx in indices {
        if idx >= len {
            return Err(PyIndexError::new_err(format!(
                "Index {} out of bounds for array of length {}",
                idx, len
            )));
        }
        result.push(values.get_item(idx)?.unbind());
    }

    Ok(result)
}

#[pyfunction]
pub fn rust_decimal_sum(values: &Bound<'_, PyList>, scale: u32, rounding: &str) -> PyResult<Py<PyAny>> {
    if values.is_empty() {
        let py = values.py();
        return rust_decimal_to_py(py, RustDecimal::ZERO);
    }

    let decimals = pylist_to_rust(values)?;
    let total = decimals.iter().fold(RustDecimal::ZERO, |acc, value| acc + *value);
    let strategy = parse_rounding_strategy(rounding)?;
    let rounded = round_decimal(total, scale, strategy);
    rust_decimal_to_py(values.py(), rounded)
}

#[pyfunction]
pub fn rust_decimal_mean(values: &Bound<'_, PyList>, scale: u32, rounding: &str) -> PyResult<Py<PyAny>> {
    let len = values.len();
    if len == 0 {
        let py = values.py();
        let decimal_module = py.import("decimal")?;
        let decimal_class = decimal_module.getattr("Decimal")?;
        return Ok(decimal_class.call1(("NaN",))?.unbind());
    }

    let decimals = pylist_to_rust(values)?;
    let total = decimals.iter().fold(RustDecimal::ZERO, |acc, value| acc + *value);
    let denominator = RustDecimal::from_usize(len).ok_or_else(|| {
        PyValueError::new_err("Unable to convert length to Decimal for mean calculation")
    })?;
    let raw_mean = total / denominator;
    let strategy = parse_rounding_strategy(rounding)?;
    let rounded = round_decimal(raw_mean, scale, strategy);
    rust_decimal_to_py(values.py(), rounded)
}

#[pyfunction]
pub fn rust_decimal_sma(
    values: &Bound<'_, PyList>,
    window: usize,
    scale: u32,
    rounding: &str,
) -> PyResult<Vec<Py<PyAny>>> {
    if window == 0 {
        return Err(PyValueError::new_err("Window size must be greater than 0"));
    }

    let len = values.len();
    let py = values.py();
    if len == 0 {
        return Ok(Vec::new());
    }

    let strategy = parse_rounding_strategy(rounding)?;
    let decimals = pylist_to_rust(values)?;
    let decimal_module = py.import("decimal")?;
    let decimal_class = decimal_module.getattr("Decimal")?;
    let nan_obj: Py<PyAny> = decimal_class.call1(("NaN",))?.unbind();
    let mut output: Vec<Py<PyAny>> = (0..len).map(|_| nan_obj.clone_ref(py)).collect();

    if len < window {
        return Ok(output);
    }

    let divisor = RustDecimal::from_usize(window).ok_or_else(|| {
        PyValueError::new_err("Unable to convert window size to Decimal")
    })?;

    let mut sum = RustDecimal::ZERO;
    for value in decimals.iter().take(window) {
        sum += *value;
    }
    let first_avg = round_decimal(sum / divisor, scale, strategy);
    output[window - 1] = rust_decimal_to_py(py, first_avg)?;

    for idx in window..len {
        sum += decimals[idx];
        sum -= decimals[idx - window];
        let avg = round_decimal(sum / divisor, scale, strategy);
        output[idx] = rust_decimal_to_py(py, avg)?;
    }

    Ok(output)
}

#[pyfunction]
pub fn rust_decimal_ema(
    values: &Bound<'_, PyList>,
    span: usize,
    scale: u32,
    rounding: &str,
) -> PyResult<Vec<Py<PyAny>>> {
    if span == 0 {
        return Err(PyValueError::new_err("Span must be greater than 0"));
    }

    let len = values.len();
    let py = values.py();
    if len == 0 {
        return Ok(Vec::new());
    }

    let strategy = parse_rounding_strategy(rounding)?;
    let decimals = pylist_to_rust(values)?;
    let mut output: Vec<Py<PyAny>> = Vec::with_capacity(len);

    let two = RustDecimal::from_i32(2).unwrap();
    let denom = RustDecimal::from_usize(span + 1).ok_or_else(|| {
        PyValueError::new_err("Unable to convert span to Decimal")
    })?;
    let alpha = two / denom;
    let one_minus_alpha = RustDecimal::ONE - alpha;

    let mut ema = decimals[0];
    ema = round_decimal(ema, scale, strategy);
    output.push(rust_decimal_to_py(py, ema)?);

    for value in decimals.iter().skip(1) {
        let next = alpha * *value + one_minus_alpha * ema;
        ema = round_decimal(next, scale, strategy);
        output.push(rust_decimal_to_py(py, ema)?);
    }

    Ok(output)
}

#[pyfunction]
pub fn rust_decimal_rolling_sum(
    values: &Bound<'_, PyList>,
    window: usize,
    scale: u32,
    rounding: &str,
) -> PyResult<Vec<Py<PyAny>>> {
    if window == 0 {
        return Err(PyValueError::new_err("Window size must be greater than 0"));
    }

    let len = values.len();
    let py = values.py();
    if len == 0 {
        return Ok(Vec::new());
    }

    let strategy = parse_rounding_strategy(rounding)?;
    let decimals = pylist_to_rust(values)?;
    let decimal_module = py.import("decimal")?;
    let decimal_class = decimal_module.getattr("Decimal")?;
    let nan_obj: Py<PyAny> = decimal_class.call1(("NaN",))?.unbind();
    let mut output: Vec<Py<PyAny>> = (0..len).map(|_| nan_obj.clone_ref(py)).collect();

    if len < window {
        return Ok(output);
    }

    let mut sum = RustDecimal::ZERO;
    for value in decimals.iter().take(window) {
        sum += *value;
    }
    output[window - 1] = rust_decimal_to_py(py, round_decimal(sum, scale, strategy))?;

    for idx in window..len {
        sum += decimals[idx];
        sum -= decimals[idx - window];
        output[idx] = rust_decimal_to_py(py, round_decimal(sum, scale, strategy))?;
    }

    Ok(output)
}

#[pyfunction]
pub fn rust_decimal_pairwise_op(
    left: &Bound<'_, PyList>,
    right: &Bound<'_, PyList>,
    op: &str,
    scale: u32,
    rounding: &str,
) -> PyResult<Vec<Py<PyAny>>> {
    let len = left.len();
    if len != right.len() {
        return Err(PyValueError::new_err(format!(
            "Array lengths don't match: {} vs {}",
            len,
            right.len()
        )));
    }

    let strategy = parse_rounding_strategy(rounding)?;
    let left_decimals = pylist_to_rust(left)?;
    let right_decimals = pylist_to_rust(right)?;
    let py = left.py();

    let mut result: Vec<Py<PyAny>> = Vec::with_capacity(len);
    for (lhs, rhs) in left_decimals.iter().zip(right_decimals.iter()) {
        let value = match op {
            "add" | "+" => *lhs + *rhs,
            "sub" | "-" | "subtract" => *lhs - *rhs,
            "mul" | "*" | "multiply" => *lhs * *rhs,
            "div" | "/" | "divide" => {
                if rhs.is_zero() {
                    return Err(PyValueError::new_err("Division by zero"));
                }
                *lhs / *rhs
            }
            other => {
                return Err(PyValueError::new_err(format!(
                    "Unknown operation: {}",
                    other
                )));
            }
        };
        result.push(rust_decimal_to_py(py, round_decimal(value, scale, strategy))?);
    }

    Ok(result)
}

#[pyfunction]
pub fn rust_decimal_fillna(
    values: &Bound<'_, PyList>,
    fill_value: &Bound<'_, PyAny>,
) -> PyResult<Vec<Py<PyAny>>> {
    let py = values.py();
    let fill_decimal = py_decimal_to_rust(fill_value)?;
    let fill_py = rust_decimal_to_py(py, fill_decimal)?;

    let mut result = Vec::with_capacity(values.len());
    for item in values.iter() {
        if item.call_method0("is_nan")?.extract::<bool>()? {
            result.push(fill_py.clone_ref(py));
        } else {
            result.push(item.unbind());
        }
    }

    Ok(result)
}
