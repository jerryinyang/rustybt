"""Tests for adapter registry and auto-discovery."""

import polars as pl
import pytest

from rustybt.data.adapters.base import BaseDataAdapter
from rustybt.data.adapters.registry import AdapterRegistry


@pytest.fixture(autouse=True)
def clear_registry():
    """Clear registry before each test."""
    AdapterRegistry.clear()
    yield
    AdapterRegistry.clear()


# ============================================================================
# Registration Tests
# ============================================================================


def test_register_adapter():
    """Adapter registration adds adapter to registry."""

    class TestAdapter(BaseDataAdapter):
        async def fetch(self, symbols, start_date, end_date, resolution):
            return pl.DataFrame()

        def validate(self, df):
            return True

        def standardize(self, df):
            return df

    AdapterRegistry.register(TestAdapter)

    assert "TestAdapter" in AdapterRegistry.list_adapters()


def test_register_non_adapter_raises_error():
    """Registering non-adapter class raises TypeError."""

    class NotAnAdapter:
        pass

    with pytest.raises(TypeError, match="must inherit from BaseDataAdapter"):
        AdapterRegistry.register(NotAnAdapter)


def test_register_multiple_adapters():
    """Multiple adapters can be registered."""

    class Adapter1(BaseDataAdapter):
        async def fetch(self, symbols, start_date, end_date, resolution):
            return pl.DataFrame()

        def validate(self, df):
            return True

        def standardize(self, df):
            return df

    class Adapter2(BaseDataAdapter):
        async def fetch(self, symbols, start_date, end_date, resolution):
            return pl.DataFrame()

        def validate(self, df):
            return True

        def standardize(self, df):
            return df

    AdapterRegistry.register(Adapter1)
    AdapterRegistry.register(Adapter2)

    adapters = AdapterRegistry.list_adapters()
    assert "Adapter1" in adapters
    assert "Adapter2" in adapters
    assert len(adapters) == 2


# ============================================================================
# Retrieval Tests
# ============================================================================


def test_get_adapter_returns_class():
    """get_adapter returns registered adapter class."""

    class TestAdapter(BaseDataAdapter):
        async def fetch(self, symbols, start_date, end_date, resolution):
            return pl.DataFrame()

        def validate(self, df):
            return True

        def standardize(self, df):
            return df

    AdapterRegistry.register(TestAdapter)

    adapter_class = AdapterRegistry.get_adapter("TestAdapter")

    assert adapter_class == TestAdapter
    assert issubclass(adapter_class, BaseDataAdapter)


def test_get_adapter_not_found_raises_error():
    """get_adapter raises ValueError for unknown adapter."""

    with pytest.raises(ValueError, match="Adapter 'NonExistent' not found"):
        AdapterRegistry.get_adapter("NonExistent")


def test_get_adapter_error_message_includes_available_adapters():
    """Error message lists available adapters."""

    class TestAdapter(BaseDataAdapter):
        async def fetch(self, symbols, start_date, end_date, resolution):
            return pl.DataFrame()

        def validate(self, df):
            return True

        def standardize(self, df):
            return df

    AdapterRegistry.register(TestAdapter)

    with pytest.raises(ValueError, match="Available adapters: TestAdapter"):
        AdapterRegistry.get_adapter("NonExistent")


# ============================================================================
# List Adapters Tests
# ============================================================================


def test_list_adapters_returns_empty_list_initially():
    """list_adapters returns empty list when no adapters registered."""
    assert AdapterRegistry.list_adapters() == []


def test_list_adapters_returns_all_registered_adapters():
    """list_adapters returns all registered adapter names."""

    class Adapter1(BaseDataAdapter):
        async def fetch(self, symbols, start_date, end_date, resolution):
            return pl.DataFrame()

        def validate(self, df):
            return True

        def standardize(self, df):
            return df

    class Adapter2(BaseDataAdapter):
        async def fetch(self, symbols, start_date, end_date, resolution):
            return pl.DataFrame()

        def validate(self, df):
            return True

        def standardize(self, df):
            return df

    AdapterRegistry.register(Adapter1)
    AdapterRegistry.register(Adapter2)

    adapters = AdapterRegistry.list_adapters()

    assert set(adapters) == {"Adapter1", "Adapter2"}


# ============================================================================
# Clear Registry Tests
# ============================================================================


def test_clear_removes_all_adapters():
    """clear() removes all registered adapters."""

    class TestAdapter(BaseDataAdapter):
        async def fetch(self, symbols, start_date, end_date, resolution):
            return pl.DataFrame()

        def validate(self, df):
            return True

        def standardize(self, df):
            return df

    AdapterRegistry.register(TestAdapter)
    assert len(AdapterRegistry.list_adapters()) == 1

    AdapterRegistry.clear()
    assert len(AdapterRegistry.list_adapters()) == 0


# ============================================================================
# Integration Tests
# ============================================================================


def test_adapter_registration_and_instantiation():
    """Complete workflow: register, retrieve, instantiate adapter."""

    class TestAdapter(BaseDataAdapter):
        async def fetch(self, symbols, start_date, end_date, resolution):
            return pl.DataFrame()

        def validate(self, df):
            return True

        def standardize(self, df):
            return df

    # Register adapter
    AdapterRegistry.register(TestAdapter)

    # Retrieve adapter class
    adapter_class = AdapterRegistry.get_adapter("TestAdapter")

    # Instantiate adapter
    adapter = adapter_class(name="test_instance")

    assert isinstance(adapter, BaseDataAdapter)
    assert adapter.name == "test_instance"


def test_multiple_instances_from_registered_adapter():
    """Multiple instances can be created from registered adapter."""

    class TestAdapter(BaseDataAdapter):
        async def fetch(self, symbols, start_date, end_date, resolution):
            return pl.DataFrame()

        def validate(self, df):
            return True

        def standardize(self, df):
            return df

    AdapterRegistry.register(TestAdapter)
    adapter_class = AdapterRegistry.get_adapter("TestAdapter")

    # Create multiple instances
    instance1 = adapter_class(name="instance1")
    instance2 = adapter_class(name="instance2")

    assert instance1.name == "instance1"
    assert instance2.name == "instance2"
    assert instance1 is not instance2


# ============================================================================
# Auto-Discovery Tests
# ============================================================================


def test_discover_adapters_does_not_fail():
    """discover_adapters completes without errors."""
    # Should not raise any exceptions
    count = AdapterRegistry.discover_adapters()

    # Count should be non-negative integer
    assert isinstance(count, int)
    assert count >= 0


def test_discover_adapters_skips_base_and_registry():
    """discover_adapters skips base and registry modules."""
    AdapterRegistry.discover_adapters()

    # Should not register BaseDataAdapter itself
    adapters = AdapterRegistry.list_adapters()
    assert "BaseDataAdapter" not in adapters
    assert "AdapterRegistry" not in adapters
