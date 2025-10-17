"""
Test suite for API import functionality.

Ensures that all documented API imports work correctly and that the @api_method
decorator properly registers methods in rustybt.api.__all__.

Part of Story 11.6: User-Facing Documentation Quality Validation
"""

import pytest


class TestAPIImportsFunctionality:
    """Test that API methods can be imported directly from rustybt.api."""

    def test_critical_quickstart_imports(self):
        """Test the exact imports from Quick Start documentation work."""
        from rustybt.api import order_target, record, symbol

        assert callable(order_target), "order_target should be callable"
        assert callable(record), "record should be callable"
        assert callable(symbol), "symbol should be callable"

    def test_order_functions_import(self):
        """Test that all order-related functions can be imported."""
        from rustybt.api import (
            order,
            order_percent,
            order_target,
            order_target_percent,
            order_target_value,
            order_value,
        )

        for func in [
            order,
            order_percent,
            order_target,
            order_target_percent,
            order_target_value,
            order_value,
        ]:
            assert callable(func), f"{func.__name__} should be callable"

    def test_scheduling_functions_import(self):
        """Test that scheduling functions can be imported."""
        from rustybt.api import schedule_function

        assert callable(schedule_function), "schedule_function should be callable"

    def test_asset_lookup_functions_import(self):
        """Test that asset lookup functions can be imported."""
        from rustybt.api import sid, symbol, symbols

        assert callable(sid), "sid should be callable"
        assert callable(symbol), "symbol should be callable"
        assert callable(symbols), "symbols should be callable"

    def test_order_management_functions_import(self):
        """Test that order management functions can be imported."""
        from rustybt.api import cancel_order, get_open_orders, get_order

        assert callable(cancel_order), "cancel_order should be callable"
        assert callable(get_open_orders), "get_open_orders should be callable"
        assert callable(get_order), "get_order should be callable"

    def test_environment_functions_import(self):
        """Test that environment query functions can be imported."""
        from rustybt.api import get_datetime, get_environment

        assert callable(get_datetime), "get_datetime should be callable"
        assert callable(get_environment), "get_environment should be callable"

    def test_pipeline_functions_import(self):
        """Test that pipeline functions can be imported."""
        from rustybt.api import attach_pipeline, pipeline_output

        assert callable(attach_pipeline), "attach_pipeline should be callable"
        assert callable(pipeline_output), "pipeline_output should be callable"

    def test_configuration_functions_import(self):
        """Test that configuration functions can be imported."""
        from rustybt.api import (
            set_benchmark,
            set_cancel_policy,
            set_commission,
            set_slippage,
        )

        assert callable(set_benchmark), "set_benchmark should be callable"
        assert callable(set_cancel_policy), "set_cancel_policy should be callable"
        assert callable(set_commission), "set_commission should be callable"
        assert callable(set_slippage), "set_slippage should be callable"

    def test_trading_controls_import(self):
        """Test that trading control functions can be imported."""
        from rustybt.api import (
            set_do_not_order_list,
            set_long_only,
            set_max_leverage,
            set_max_order_count,
            set_max_order_size,
            set_max_position_size,
        )

        for func in [
            set_do_not_order_list,
            set_long_only,
            set_max_leverage,
            set_max_order_count,
            set_max_order_size,
            set_max_position_size,
        ]:
            assert callable(func), f"{func.__name__} should be callable"


class TestAPIExportsStructure:
    """Test that the API module exports structure is correct."""

    def test_all_contains_dynamic_methods(self):
        """Test that __all__ includes dynamically registered methods."""
        import rustybt.api

        # Critical methods from documentation
        critical_methods = ["order_target", "record", "symbol", "order", "schedule_function"]

        for method in critical_methods:
            assert method in rustybt.api.__all__, f"{method} should be in __all__"

    def test_all_contains_static_exports(self):
        """Test that __all__ still includes original static exports."""
        import rustybt.api

        static_exports = [
            "commission",
            "slippage",
            "events",
            "calendars",
            "date_rules",
            "time_rules",
        ]

        for export in static_exports:
            assert export in rustybt.api.__all__, f"{export} should be in __all__"

    def test_all_has_expected_size(self):
        """Test that __all__ has grown from 14 to include dynamic methods."""
        import rustybt.api

        # Should have 14 static + ~39 dynamic methods
        assert (
            len(rustybt.api.__all__) >= 45
        ), f"__all__ should have at least 45 items, has {len(rustybt.api.__all__)}"


class TestStaticExportsPreserved:
    """Test that original static exports still work after changes."""

    def test_commission_module_import(self):
        """Test that commission module can be imported."""
        from rustybt.api import commission

        assert commission is not None, "commission module should be importable"

    def test_slippage_module_import(self):
        """Test that slippage module can be imported."""
        from rustybt.api import slippage

        assert slippage is not None, "slippage module should be importable"

    def test_slippage_classes_import(self):
        """Test that slippage classes can be imported."""
        from rustybt.api import FixedSlippage, VolumeShareSlippage

        assert FixedSlippage is not None, "FixedSlippage should be importable"
        assert VolumeShareSlippage is not None, "VolumeShareSlippage should be importable"

    def test_events_module_import(self):
        """Test that events module and submodules can be imported."""
        from rustybt.api import calendars, date_rules, events, time_rules

        assert events is not None, "events module should be importable"
        assert calendars is not None, "calendars module should be importable"
        assert date_rules is not None, "date_rules module should be importable"
        assert time_rules is not None, "time_rules module should be importable"


class TestBackwardCompatibility:
    """Test that different import patterns still work."""

    def test_module_import_pattern(self):
        """Test importing api module and accessing attributes."""
        import rustybt.api as api

        # Should be able to access methods as attributes
        assert hasattr(api, "order_target"), "api should have order_target attribute"
        assert hasattr(api, "record"), "api should have record attribute"
        assert hasattr(api, "symbol"), "api should have symbol attribute"
        assert callable(api.order_target), "api.order_target should be callable"

    def test_selective_import_pattern(self):
        """Test importing specific methods from api."""
        from rustybt.api import order_target, record

        assert callable(order_target), "order_target should be callable"
        assert callable(record), "record should be callable"

    def test_wildcard_import_not_recommended(self):
        """Test that wildcard import works (though not recommended)."""
        # Note: Wildcard imports are not recommended but should work
        import rustybt.api

        # Get all exports
        all_exports = rustybt.api.__all__

        # Verify critical methods are included
        assert "order_target" in all_exports, "order_target should be in __all__"
        assert "record" in all_exports, "record should be in __all__"
