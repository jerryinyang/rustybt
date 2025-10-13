"""Pytest configuration for IB integration tests."""

import pytest


def pytest_addoption(parser):
    """Add custom pytest command line options."""
    parser.addoption(
        "--run-ib-integration",
        action="store_true",
        default=False,
        help="Run IB integration tests (requires TWS/Gateway and paper account)",
    )


def pytest_configure(config):
    """Configure pytest markers."""
    config.addinivalue_line(
        "markers",
        "ib_integration: mark test as IB integration test (requires --run-ib-integration)",
    )


def pytest_collection_modifyitems(config, items):
    """Skip IB integration tests unless --run-ib-integration is specified."""
    if config.getoption("--run-ib-integration"):
        return

    skip_ib = pytest.mark.skip(reason="need --run-ib-integration option to run")
    for item in items:
        if "ib_integration" in item.keywords:
            item.add_marker(skip_ib)
