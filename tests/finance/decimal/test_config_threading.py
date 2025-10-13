"""Multi-threading tests for DecimalConfig thread safety."""

import threading
import time
from decimal import Decimal, getcontext
from pathlib import Path

from rustybt.finance.decimal import DecimalConfig


class TestDecimalConfigThreadSafety:
    """Test thread safety of DecimalConfig."""

    def test_thread_context_isolation(self):
        """Test Decimal context is isolated per thread."""
        config = DecimalConfig.get_instance()

        default_config_path = (
            Path(__file__).parent.parent.parent.parent
            / "rustybt"
            / "finance"
            / "decimal"
            / "default_config.yaml"
        )
        config.load_from_yaml(str(default_config_path))

        results = {}

        def thread_worker(asset_class: str, thread_id: int):
            """Worker that uses asset-class-specific precision."""
            with config.with_precision(asset_class) as ctx:
                # Verify this thread sees correct precision
                precision = ctx.prec
                rounding_mode_const = ctx.rounding

                # Perform a calculation to ensure context is active
                value = Decimal("1.123456789")
                calc_result = +value

                results[thread_id] = {
                    "asset_class": asset_class,
                    "precision": precision,
                    "rounding": rounding_mode_const,
                    "calc_result": calc_result,
                }

                # Sleep briefly to ensure threads overlap
                time.sleep(0.01)

        # Spawn threads with different asset classes
        threads = [
            threading.Thread(target=thread_worker, args=("crypto", 0)),
            threading.Thread(target=thread_worker, args=("equity", 1)),
            threading.Thread(target=thread_worker, args=("forex", 2)),
        ]

        for t in threads:
            t.start()

        for t in threads:
            t.join()

        # Verify each thread saw its own precision
        assert results[0]["precision"] == config.get_precision("crypto")
        assert results[1]["precision"] == config.get_precision("equity")
        assert results[2]["precision"] == config.get_precision("forex")

        # Verify each thread used its own rounding mode
        assert results[0]["rounding"] == config.get_rounding_constant("crypto")
        assert results[1]["rounding"] == config.get_rounding_constant("equity")
        assert results[2]["rounding"] == config.get_rounding_constant("forex")

    def test_parent_context_does_not_leak(self):
        """Test parent thread context does not affect child threads."""
        config = DecimalConfig.get_instance()

        default_config_path = (
            Path(__file__).parent.parent.parent.parent
            / "rustybt"
            / "finance"
            / "decimal"
            / "default_config.yaml"
        )
        config.load_from_yaml(str(default_config_path))

        child_context_prec = None

        def child_thread():
            nonlocal child_context_prec
            # Child thread should see default context, not parent's modified context
            child_context_prec = getcontext().prec

        # Set parent context to crypto precision
        with config.with_precision("crypto") as ctx:
            parent_prec = ctx.prec

            # Spawn child thread while parent context is active
            thread = threading.Thread(target=child_thread)
            thread.start()
            thread.join()

        # Child should have default precision (28), not parent's 18
        # Note: child threads get fresh default contexts
        assert child_context_prec != parent_prec or child_context_prec == 28

    def test_concurrent_calculations_different_asset_classes(self):
        """Test concurrent calculations with different asset classes produce correct results."""
        config = DecimalConfig.get_instance()

        default_config_path = (
            Path(__file__).parent.parent.parent.parent
            / "rustybt"
            / "finance"
            / "decimal"
            / "default_config.yaml"
        )
        config.load_from_yaml(str(default_config_path))

        results = {}

        def calculate_crypto(thread_id: int):
            """Calculate crypto value with ROUND_DOWN."""
            with config.with_precision("crypto"):
                # Crypto uses ROUND_DOWN
                value = Decimal("1.999999999")
                # Round to 8 decimal places
                rounded = round(value, 8)
                results[thread_id] = rounded

        def calculate_equity(thread_id: int):
            """Calculate equity value with ROUND_HALF_UP."""
            with config.with_precision("equity"):
                # Equity uses ROUND_HALF_UP
                value = Decimal("1.999999999")
                # Round to 2 decimal places
                rounded = round(value, 2)
                results[thread_id] = rounded

        # Spawn threads
        threads = [
            threading.Thread(target=calculate_crypto, args=(0,)),
            threading.Thread(target=calculate_equity, args=(1,)),
            threading.Thread(target=calculate_crypto, args=(2,)),
            threading.Thread(target=calculate_equity, args=(3,)),
        ]

        for t in threads:
            t.start()

        for t in threads:
            t.join()

        # Verify results are consistent within asset class
        assert results[0] == Decimal("1.99999999")  # Crypto: 8 decimals
        assert results[2] == Decimal("1.99999999")  # Crypto: 8 decimals
        assert results[1] == Decimal("2.00")  # Equity: 2 decimals, ROUND_HALF_UP
        assert results[3] == Decimal("2.00")  # Equity: 2 decimals, ROUND_HALF_UP

    def test_singleton_thread_safety(self):
        """Test singleton pattern is thread-safe during initialization."""
        # Clear the singleton instance to test initialization
        DecimalConfig._instance = None

        instances = []

        def get_instance(thread_id: int):
            """Get singleton instance."""
            instance = DecimalConfig.get_instance()
            instances.append((thread_id, id(instance)))

        # Spawn many threads simultaneously
        threads = [threading.Thread(target=get_instance, args=(i,)) for i in range(10)]

        for t in threads:
            t.start()

        for t in threads:
            t.join()

        # All threads should have gotten the same instance
        instance_ids = [instance_id for _, instance_id in instances]
        assert len(set(instance_ids)) == 1, "Multiple singleton instances created!"

    def test_config_modification_thread_safety(self):
        """Test configuration modifications are visible across threads."""
        config = DecimalConfig.get_instance()

        # Reset config to defaults
        default_config_path = (
            Path(__file__).parent.parent.parent.parent
            / "rustybt"
            / "finance"
            / "decimal"
            / "default_config.yaml"
        )
        config.load_from_yaml(str(default_config_path))

        results = {}

        def set_custom_precision():
            """Set custom precision for new asset class."""
            config.set_precision("custom_test", 12, "ROUND_UP", scale=6)

        def read_custom_precision(thread_id: int):
            """Read custom precision."""
            time.sleep(0.05)  # Wait for setter thread
            try:
                precision = config.get_precision("custom_test")
                rounding = config.get_rounding_mode("custom_test")
                scale = config.get_scale("custom_test")
                results[thread_id] = {"precision": precision, "rounding": rounding, "scale": scale}
            except Exception as e:
                results[thread_id] = {"error": str(e)}

        # Spawn setter thread and reader threads
        setter_thread = threading.Thread(target=set_custom_precision)
        reader_threads = [
            threading.Thread(target=read_custom_precision, args=(i,)) for i in range(3)
        ]

        setter_thread.start()
        for t in reader_threads:
            t.start()

        setter_thread.join()
        for t in reader_threads:
            t.join()

        # All reader threads should see the modified config
        for thread_id in range(3):
            assert results[thread_id]["precision"] == 12
            assert results[thread_id]["rounding"] == "ROUND_UP"
            assert results[thread_id]["scale"] == 6

    def test_context_manager_isolation_concurrent(self):
        """Test context managers don't interfere across threads."""
        config = DecimalConfig.get_instance()

        default_config_path = (
            Path(__file__).parent.parent.parent.parent
            / "rustybt"
            / "finance"
            / "decimal"
            / "default_config.yaml"
        )
        config.load_from_yaml(str(default_config_path))

        results = {}
        barrier = threading.Barrier(3)  # Synchronize thread execution

        def worker_with_context(asset_class: str, thread_id: int):
            """Worker that holds context while other threads also hold contexts."""
            barrier.wait()  # Ensure all threads enter context simultaneously

            with config.with_precision(asset_class) as ctx:
                precision = ctx.prec
                rounding = ctx.rounding

                # Hold context for a bit
                time.sleep(0.02)

                # Record context state
                results[thread_id] = {
                    "precision": precision,
                    "rounding": rounding,
                    "asset_class": asset_class,
                }

        # Spawn threads that will hold contexts simultaneously
        threads = [
            threading.Thread(target=worker_with_context, args=("crypto", 0)),
            threading.Thread(target=worker_with_context, args=("equity", 1)),
            threading.Thread(target=worker_with_context, args=("forex", 2)),
        ]

        for t in threads:
            t.start()

        for t in threads:
            t.join()

        # Each thread should have seen its own context, not others'
        assert results[0]["precision"] == config.get_precision("crypto")
        assert results[0]["rounding"] == config.get_rounding_constant("crypto")

        assert results[1]["precision"] == config.get_precision("equity")
        assert results[1]["rounding"] == config.get_rounding_constant("equity")

        assert results[2]["precision"] == config.get_precision("forex")
        assert results[2]["rounding"] == config.get_rounding_constant("forex")
