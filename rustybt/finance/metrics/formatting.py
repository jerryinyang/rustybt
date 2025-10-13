#
# Copyright 2025 RustyBT Contributors
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Decimal metrics formatting for display.

This module provides formatting utilities for displaying Decimal metrics
with appropriate precision and formatting conventions.
"""

import json
from decimal import Decimal
from typing import Any


def format_percentage(value: Decimal, precision: int = 2, include_sign: bool = False) -> str:
    """Format Decimal as percentage with specified precision.

    Args:
        value: Decimal value (e.g., Decimal("0.1234") = 12.34%)
        precision: Number of decimal places (default: 2)
        include_sign: Whether to include + sign for positive values

    Returns:
        Formatted string (e.g., "12.34%")

    Example:
        >>> format_percentage(Decimal("0.1234"), precision=2)
        "12.34%"
        >>> format_percentage(Decimal("-0.0567"), precision=3)
        "-5.670%"
    """
    if value == Decimal("inf"):
        return "∞%"
    if value == Decimal("-inf"):
        return "-∞%"

    percentage = value * Decimal("100")
    sign = "+" if include_sign and percentage > 0 else ""
    return f"{sign}{percentage:.{precision}f}%"


def format_ratio(value: Decimal, precision: int = 2, include_sign: bool = False) -> str:
    """Format Decimal ratio with specified precision.

    Args:
        value: Decimal ratio (e.g., Decimal("1.567"))
        precision: Number of decimal places (default: 2)
        include_sign: Whether to include + sign for positive values

    Returns:
        Formatted string (e.g., "1.57")

    Example:
        >>> format_ratio(Decimal("1.567"), precision=2)
        "1.57"
        >>> format_ratio(Decimal("-0.234"), precision=3)
        "-0.234"
    """
    if value == Decimal("inf"):
        return "∞"
    if value == Decimal("-inf"):
        return "-∞"

    sign = "+" if include_sign and value > 0 else ""
    return f"{sign}{value:.{precision}f}"


def format_currency(
    value: Decimal, symbol: str = "$", precision: int = 2, thousands_sep: bool = True
) -> str:
    """Format Decimal as currency with thousands separators.

    Args:
        value: Decimal value
        symbol: Currency symbol (default: "$")
        precision: Number of decimal places (default: 2)
        thousands_sep: Whether to include thousands separator

    Returns:
        Formatted string (e.g., "$1,234,567.89")

    Example:
        >>> format_currency(Decimal("1234567.89"))
        "$1,234,567.89"
        >>> format_currency(Decimal("999.50"), symbol="€")
        "€999.50"
    """
    if value == Decimal("inf"):
        return f"{symbol}∞"
    if value == Decimal("-inf"):
        return f"-{symbol}∞"

    if thousands_sep:
        return f"{symbol}{value:,.{precision}f}"
    else:
        return f"{symbol}{value:.{precision}f}"


def format_basis_points(value: Decimal, precision: int = 1) -> str:
    """Format Decimal as basis points (1 bp = 0.01%).

    Args:
        value: Decimal value (e.g., Decimal("0.0001") = 1 bp)
        precision: Number of decimal places (default: 1)

    Returns:
        Formatted string (e.g., "10.5 bps")

    Example:
        >>> format_basis_points(Decimal("0.0025"))
        "25.0 bps"
    """
    if value == Decimal("inf"):
        return "∞ bps"
    if value == Decimal("-inf"):
        return "-∞ bps"

    bps = value * Decimal("10000")
    return f"{bps:.{precision}f} bps"


def format_scientific(value: Decimal, precision: int = 2) -> str:
    """Format Decimal in scientific notation for very small/large values.

    Args:
        value: Decimal value
        precision: Number of decimal places (default: 2)

    Returns:
        Formatted string in scientific notation

    Example:
        >>> format_scientific(Decimal("0.00012345"))
        "1.23e-04"
    """
    if value == Decimal("inf"):
        return "∞"
    if value == Decimal("-inf"):
        return "-∞"
    if value == Decimal("0"):
        return "0.00e+00"

    return f"{value:.{precision}e}"


def create_metrics_summary_table(
    metrics: dict[str, Decimal],
    precision_map: dict[str, int] | None = None,
) -> str:
    """Create formatted summary table of metrics.

    Args:
        metrics: Dictionary of metric name to Decimal value
        precision_map: Optional mapping of metric name to precision override

    Returns:
        Formatted string table with aligned columns

    Example:
        >>> metrics = {
        ...     'sharpe_ratio': Decimal('1.567'),
        ...     'max_drawdown': Decimal('-0.234'),
        ...     'win_rate': Decimal('0.625')
        ... }
        >>> print(create_metrics_summary_table(metrics))
    """
    if not metrics:
        return "No metrics available"

    precision_map = precision_map or {}

    # Default precision by metric type
    default_precision = {
        "sharpe_ratio": 2,
        "sortino_ratio": 2,
        "calmar_ratio": 2,
        "information_ratio": 2,
        "max_drawdown": 2,
        "var": 4,
        "cvar": 4,
        "tracking_error": 4,
        "win_rate": 2,
        "profit_factor": 2,
        "alpha": 4,
        "beta": 3,
    }

    # Format metrics
    formatted_metrics = []
    max_name_len = max(len(name) for name in metrics)

    for name, value in sorted(metrics.items()):
        precision = precision_map.get(name, default_precision.get(name, 4))

        # Determine formatting based on metric name
        if "rate" in name.lower() or "drawdown" in name.lower():
            formatted_value = format_percentage(value, precision)
        elif "ratio" in name.lower() or "alpha" in name.lower() or "beta" in name.lower():
            formatted_value = format_ratio(value, precision)
        elif "var" in name.lower() or "error" in name.lower():
            formatted_value = format_percentage(value, precision)
        else:
            formatted_value = format_ratio(value, precision)

        # Format metric name (convert snake_case to Title Case)
        display_name = name.replace("_", " ").title()
        formatted_metrics.append((display_name, formatted_value))

    # Create aligned table
    lines = []
    lines.append("=" * (max_name_len + 20))
    lines.append("Performance Metrics Summary")
    lines.append("=" * (max_name_len + 20))

    for display_name, formatted_value in formatted_metrics:
        padding = " " * (max_name_len - len(display_name) + 2)
        lines.append(f"{display_name}:{padding}{formatted_value:>12}")

    lines.append("=" * (max_name_len + 20))

    return "\n".join(lines)


def metrics_to_json(metrics: dict[str, Decimal]) -> str:
    """Convert metrics dictionary to JSON with Decimal as string.

    Args:
        metrics: Dictionary of metric name to Decimal value

    Returns:
        JSON string representation

    Example:
        >>> metrics = {'sharpe_ratio': Decimal('1.567')}
        >>> metrics_to_json(metrics)
        '{"sharpe_ratio": "1.567"}'
    """

    def decimal_encoder(obj: Any) -> Any:
        if isinstance(obj, Decimal):
            # Handle infinity
            if obj == Decimal("inf"):
                return "Infinity"
            elif obj == Decimal("-inf"):
                return "-Infinity"
            return str(obj)
        raise TypeError(f"Object of type {type(obj)} is not JSON serializable")

    return json.dumps(metrics, default=decimal_encoder, indent=2)


def metrics_to_csv_row(metrics: dict[str, Decimal], include_header: bool = False) -> str:
    """Convert metrics dictionary to CSV row.

    Args:
        metrics: Dictionary of metric name to Decimal value
        include_header: Whether to include header row

    Returns:
        CSV string (header + data if include_header=True, else just data)

    Example:
        >>> metrics = {'sharpe_ratio': Decimal('1.567'), 'max_drawdown': Decimal('-0.234')}
        >>> print(metrics_to_csv_row(metrics, include_header=True))
    """
    sorted_keys = sorted(metrics.keys())

    csv_lines = []

    if include_header:
        csv_lines.append(",".join(sorted_keys))

    # Convert Decimal to string for CSV
    values = []
    for key in sorted_keys:
        value = metrics[key]
        if value == Decimal("inf"):
            values.append("Infinity")
        elif value == Decimal("-inf"):
            values.append("-Infinity")
        else:
            values.append(str(value))

    csv_lines.append(",".join(values))

    return "\n".join(csv_lines)


def format_metrics_html(metrics: dict[str, Decimal]) -> str:
    """Format metrics as HTML table.

    Args:
        metrics: Dictionary of metric name to Decimal value

    Returns:
        HTML string with styled table

    Example:
        >>> metrics = {'sharpe_ratio': Decimal('1.567')}
        >>> html = format_metrics_html(metrics)
    """
    html_parts = [
        '<table style="border-collapse: collapse; width: 100%;">',
        "  <thead>",
        '    <tr style="background-color: #f2f2f2;">',
        '      <th style="padding: 8px; text-align: left; border: 1px solid #ddd;">Metric</th>',
        '      <th style="padding: 8px; text-align: right; border: 1px solid #ddd;">Value</th>',
        "    </tr>",
        "  </thead>",
        "  <tbody>",
    ]

    for name, value in sorted(metrics.items()):
        display_name = name.replace("_", " ").title()

        # Format value based on type
        if "rate" in name.lower() or "drawdown" in name.lower():
            formatted_value = format_percentage(value, precision=2)
        elif "ratio" in name.lower():
            formatted_value = format_ratio(value, precision=2)
        else:
            formatted_value = str(value)

        # Color code based on value (positive = green, negative = red)
        color = ""
        if value > Decimal("0"):
            color = 'style="color: green;"'
        elif value < Decimal("0"):
            color = 'style="color: red;"'

        html_parts.append("    <tr>")
        html_parts.append(
            f'      <td style="padding: 8px; border: 1px solid #ddd;">{display_name}</td>'
        )
        html_parts.append(
            f'      <td style="padding: 8px; text-align: right; border: 1px solid #ddd;" {color}>{formatted_value}</td>'
        )
        html_parts.append("    </tr>")

    html_parts.extend(["  </tbody>", "</table>"])

    return "\n".join(html_parts)
