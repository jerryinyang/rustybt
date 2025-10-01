"""Property-based testing suite using Hypothesis.

This module contains property-based tests for validating Decimal implementations
across wide input ranges. Property-based tests catch edge cases that traditional
unit tests might miss.

Test Organization:
- test_ledger_properties.py: Portfolio value and accounting identities
- test_order_execution_properties.py: Order execution precision
- test_metrics_properties.py: Performance metrics calculations
- test_data_pipeline_properties.py: Data pipeline operations
- test_decimal_precision.py: Decimal arithmetic properties
- strategies.py: Custom Hypothesis strategies for Decimal generation
"""
