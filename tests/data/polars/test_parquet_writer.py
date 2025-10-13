"""Tests for Parquet writer with Decimal precision.

Tests cover:
- Daily bars writing with compression
- Minute bars writing with partitioning
- Decimal precision preservation
- Compression statistics
- Metadata catalog integration
- Atomic write operations
"""

import tempfile
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

import polars as pl
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from rustybt.data.polars.parquet_schema import DAILY_BARS_SCHEMA, MINUTE_BARS_SCHEMA
from rustybt.data.polars.parquet_writer import (
    ParquetWriter,
    get_compression_stats,
)


@pytest.fixture
def temp_bundle_path():
    """Create temporary bundle directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def sample_daily_df():
    """Create sample daily bars DataFrame."""
    return pl.DataFrame(
        {
            "date": [date(2023, 1, 1), date(2023, 1, 2), date(2023, 1, 3)],
            "sid": [1, 1, 1],
            "open": [Decimal("100.12345678"), Decimal("101.12345678"), Decimal("102.12345678")],
            "high": [Decimal("101.12345678"), Decimal("102.12345678"), Decimal("103.12345678")],
            "low": [Decimal("99.12345678"), Decimal("100.12345678"), Decimal("101.12345678")],
            "close": [Decimal("100.50000000"), Decimal("101.50000000"), Decimal("102.50000000")],
            "volume": [Decimal("1000000"), Decimal("1100000"), Decimal("1200000")],
        },
        schema=DAILY_BARS_SCHEMA,
    )


@pytest.fixture
def sample_minute_df():
    """Create sample minute bars DataFrame."""
    return pl.DataFrame(
        {
            "timestamp": [
                datetime(2023, 1, 1, 9, 30),
                datetime(2023, 1, 1, 9, 31),
                datetime(2023, 1, 1, 9, 32),
            ],
            "sid": [1, 1, 1],
            "open": [Decimal("100.12345678"), Decimal("100.22345678"), Decimal("100.32345678")],
            "high": [Decimal("100.22345678"), Decimal("100.32345678"), Decimal("100.42345678")],
            "low": [Decimal("100.02345678"), Decimal("100.12345678"), Decimal("100.22345678")],
            "close": [Decimal("100.15000000"), Decimal("100.25000000"), Decimal("100.35000000")],
            "volume": [Decimal("10000"), Decimal("11000"), Decimal("12000")],
        },
        schema=MINUTE_BARS_SCHEMA,
    )


class TestDailyBarsWriting:
    """Test writing daily bars to Parquet."""

    def test_write_daily_bars(self, temp_bundle_path, sample_daily_df):
        """Test basic daily bars writing."""
        writer = ParquetWriter(str(temp_bundle_path), enable_metadata_catalog=False)

        output_path = writer.write_daily_bars(sample_daily_df, compression="zstd")

        assert output_path.exists()
        assert output_path.suffix == ".parquet"

    def test_write_daily_bars_with_compression(self, temp_bundle_path, sample_daily_df):
        """Test writing with different compression algorithms."""
        writer = ParquetWriter(str(temp_bundle_path), enable_metadata_catalog=False)

        # Test ZSTD
        path_zstd = writer.write_daily_bars(sample_daily_df, compression="zstd")
        assert path_zstd.exists()

        # Test Snappy
        path_snappy = writer.write_daily_bars(sample_daily_df, compression="snappy")
        assert path_snappy.exists()

    def test_write_daily_bars_preserves_decimal_precision(self, temp_bundle_path, sample_daily_df):
        """Test Decimal precision is preserved in roundtrip."""
        writer = ParquetWriter(str(temp_bundle_path), enable_metadata_catalog=False)

        output_path = writer.write_daily_bars(sample_daily_df, compression="zstd")

        # Read back
        df_read = pl.read_parquet(output_path)

        # Verify precision preserved
        assert df_read["open"][0] == Decimal("100.12345678")
        assert df_read["high"][0] == Decimal("101.12345678")
        assert df_read["low"][0] == Decimal("99.12345678")
        assert df_read["close"][0] == Decimal("100.50000000")

    def test_write_daily_bars_partitioning(self, temp_bundle_path, sample_daily_df):
        """Test Hive-style partitioning by year/month."""
        writer = ParquetWriter(str(temp_bundle_path), enable_metadata_catalog=False)

        output_path = writer.write_daily_bars(sample_daily_df, compression="zstd")

        # Verify partition structure
        assert "year=2023" in str(output_path)
        assert "month=1" in str(output_path)


class TestMinuteBarsWriting:
    """Test writing minute bars to Parquet."""

    def test_write_minute_bars(self, temp_bundle_path, sample_minute_df):
        """Test basic minute bars writing."""
        writer = ParquetWriter(str(temp_bundle_path), enable_metadata_catalog=False)

        output_path = writer.write_minute_bars(sample_minute_df, compression="zstd")

        assert output_path.exists()
        assert output_path.suffix == ".parquet"

    def test_write_minute_bars_preserves_decimal_precision(
        self, temp_bundle_path, sample_minute_df
    ):
        """Test Decimal precision is preserved for minute data."""
        writer = ParquetWriter(str(temp_bundle_path), enable_metadata_catalog=False)

        output_path = writer.write_minute_bars(sample_minute_df, compression="zstd")

        # Read back
        df_read = pl.read_parquet(output_path)

        # Verify precision preserved
        assert df_read["open"][0] == Decimal("100.12345678")
        assert df_read["close"][0] == Decimal("100.15000000")

    def test_write_minute_bars_partitioning(self, temp_bundle_path, sample_minute_df):
        """Test Hive-style partitioning by year/month/day."""
        writer = ParquetWriter(str(temp_bundle_path), enable_metadata_catalog=False)

        output_path = writer.write_minute_bars(sample_minute_df, compression="zstd")

        # Verify partition structure
        assert "year=2023" in str(output_path)
        assert "month=1" in str(output_path)
        assert "day=1" in str(output_path)


class TestMetadataCatalogIntegration:
    """Test metadata catalog integration during writes."""

    def test_write_updates_metadata_catalog(self, temp_bundle_path, sample_daily_df):
        """Test writing updates metadata catalog."""
        writer = ParquetWriter(str(temp_bundle_path), enable_metadata_catalog=True)

        # Create dataset first
        dataset_id = writer.metadata_catalog.create_dataset(
            source="test",
            resolution="1d",
        )

        # Write with dataset_id
        writer.write_daily_bars(
            sample_daily_df,
            compression="zstd",
            dataset_id=dataset_id,
        )

        # Verify metadata was updated
        date_range = writer.metadata_catalog.get_date_range(dataset_id)
        assert date_range is not None
        assert date_range["start_date"] == date(2023, 1, 1)
        assert date_range["end_date"] == date(2023, 1, 3)

        # Verify checksum was added
        parquet_paths = writer.metadata_catalog.find_parquet_files(dataset_id)
        assert len(parquet_paths) > 0


class TestBatchWriting:
    """Test batch writing operations."""

    def test_write_batch_daily(self, temp_bundle_path):
        """Test writing batch of daily DataFrames."""
        writer = ParquetWriter(str(temp_bundle_path), enable_metadata_catalog=False)

        # Create multiple DataFrames for different months
        dfs = []
        for month in range(1, 4):
            df = pl.DataFrame(
                {
                    "date": [date(2023, month, 1)],
                    "sid": [1],
                    "open": [Decimal("100.00000000")],
                    "high": [Decimal("101.00000000")],
                    "low": [Decimal("99.00000000")],
                    "close": [Decimal("100.50000000")],
                    "volume": [Decimal("1000000")],
                },
                schema=DAILY_BARS_SCHEMA,
            )
            dfs.append(df)

        # Write batch
        paths = writer.write_batch(dfs, resolution="daily", compression="zstd")

        assert len(paths) == 3
        for path in paths:
            assert path.exists()


class TestCompressionStatistics:
    """Test compression statistics calculation."""

    def test_get_compression_stats(self):
        """Test calculating compression statistics with realistic dataset size.

        Uses 100+ rows to ensure Parquet metadata overhead doesn't exceed
        compression benefits (which happens with tiny datasets).
        """
        # Create realistic dataset (100 rows) for compression testing
        dates = [date(2023, 1, 1)] * 100
        sids = list(range(1, 101))  # 100 different assets

        # Generate varied data to test compression
        import random

        random.seed(42)  # Deterministic for reproducibility

        large_df = pl.DataFrame(
            {
                "date": dates,
                "sid": sids,
                "open": [Decimal(str(random.uniform(100, 200))) for _ in range(100)],
                "high": [Decimal(str(random.uniform(200, 300))) for _ in range(100)],
                "low": [Decimal(str(random.uniform(50, 100))) for _ in range(100)],
                "close": [Decimal(str(random.uniform(100, 200))) for _ in range(100)],
                "volume": [Decimal(str(random.randint(100000, 10000000))) for _ in range(100)],
            },
            schema=DAILY_BARS_SCHEMA,
        )

        stats = get_compression_stats(large_df, compression="zstd")

        assert "uncompressed_size_mb" in stats
        assert "compressed_size_mb" in stats
        assert "compression_ratio" in stats
        assert "space_saved_percent" in stats

        # ZSTD should achieve good compression on realistic dataset
        assert (
            stats["compression_ratio"] < 1.0
        ), f"Expected compression ratio < 1.0, got {stats['compression_ratio']}"
        assert (
            stats["space_saved_percent"] > 0
        ), f"Expected space saved > 0%, got {stats['space_saved_percent']}%"

        # With 100 rows, should achieve at least 10% compression
        assert (
            stats["space_saved_percent"] > 10
        ), f"Expected at least 10% compression, got {stats['space_saved_percent']}%"

    def test_compression_ratio_calculation(self, sample_daily_df):
        """Test compression ratio is calculated correctly."""
        stats = get_compression_stats(sample_daily_df, compression="zstd")

        calculated_ratio = stats["compressed_size_mb"] / stats["uncompressed_size_mb"]

        # Should match reported ratio (allow small floating point error)
        assert abs(calculated_ratio - stats["compression_ratio"]) < 0.01


class TestAtomicWrites:
    """Test atomic write operations."""

    def test_atomic_write_success(self, temp_bundle_path, sample_daily_df):
        """Test successful atomic write leaves no temp files."""
        writer = ParquetWriter(str(temp_bundle_path), enable_metadata_catalog=False)

        output_path = writer.write_daily_bars(sample_daily_df, compression="zstd")

        # No temp files should exist
        parent_dir = output_path.parent
        temp_files = list(parent_dir.glob(".*.tmp.*"))
        assert len(temp_files) == 0

    def test_atomic_write_creates_final_file(self, temp_bundle_path, sample_daily_df):
        """Test atomic write creates final data.parquet file."""
        writer = ParquetWriter(str(temp_bundle_path), enable_metadata_catalog=False)

        output_path = writer.write_daily_bars(sample_daily_df, compression="zstd")

        assert output_path.name == "data.parquet"
        assert output_path.exists()


class TestSchemaValidation:
    """Test schema validation during writes."""

    def test_write_invalid_schema_raises_error(self, temp_bundle_path):
        """Test writing DataFrame with invalid schema raises error."""
        writer = ParquetWriter(str(temp_bundle_path), enable_metadata_catalog=False)

        # Create DataFrame with wrong schema
        invalid_df = pl.DataFrame(
            {
                "date": [date(2023, 1, 1)],
                "sid": [1],
                # Missing required OHLCV columns
            }
        )

        with pytest.raises(ValueError, match="Missing required columns"):
            writer.write_daily_bars(invalid_df, compression="zstd")

    def test_write_wrong_decimal_type_raises_error(self, temp_bundle_path):
        """Test writing with wrong Decimal type raises error."""
        writer = ParquetWriter(str(temp_bundle_path), enable_metadata_catalog=False)

        # Create DataFrame with float instead of Decimal
        invalid_df = pl.DataFrame(
            {
                "date": [date(2023, 1, 1)],
                "sid": [1],
                "open": [100.123],  # Float instead of Decimal
                "high": [101.123],
                "low": [99.123],
                "close": [100.5],
                "volume": [1000000],
            }
        )

        with pytest.raises(ValueError, match="incorrect type"):
            writer.write_daily_bars(invalid_df, compression="zstd")


class TestPropertyBasedOHLCVRoundtrip:
    """Property-based tests for OHLCV data roundtrip validation.

    Uses Hypothesis to generate 1000+ test cases with random OHLCV data
    to validate that all valid inputs survive Parquet roundtrip exactly.
    """

    @given(
        st.lists(
            st.tuples(
                # Generate valid OHLCV prices as Decimal strings
                st.decimals(
                    min_value=Decimal("0.00000001"),
                    max_value=Decimal("1000000.00000000"),
                    places=8,
                    allow_nan=False,
                    allow_infinity=False,
                ).map(
                    str
                ),  # Convert to string for Decimal construction
                st.decimals(
                    min_value=Decimal("0.00000001"),
                    max_value=Decimal("1000000.00000000"),
                    places=8,
                    allow_nan=False,
                    allow_infinity=False,
                ).map(str),
                st.decimals(
                    min_value=Decimal("0.00000001"),
                    max_value=Decimal("1000000.00000000"),
                    places=8,
                    allow_nan=False,
                    allow_infinity=False,
                ).map(str),
                st.decimals(
                    min_value=Decimal("0.00000001"),
                    max_value=Decimal("1000000.00000000"),
                    places=8,
                    allow_nan=False,
                    allow_infinity=False,
                ).map(str),
                st.decimals(
                    min_value=Decimal("0.00000000"),
                    max_value=Decimal(
                        "9999999999.99999999"
                    ),  # Max for Decimal(18,8): 10 digits before decimal
                    places=8,
                    allow_nan=False,
                    allow_infinity=False,
                ).map(str),
            ),
            min_size=10,
            max_size=100,
        )
    )
    @settings(max_examples=1000, deadline=None)
    def test_daily_bars_roundtrip_preserves_all_decimal_values(self, ohlcv_data):
        """Property test: Any valid OHLCV data survives daily bars Parquet roundtrip exactly.

        Tests with 1000+ randomly generated examples to validate Decimal precision
        is preserved for all possible valid inputs.
        """
        if not ohlcv_data:
            return  # Skip empty lists

        # Create DataFrame from generated data
        dates = [date(2023, 1, 1)] * len(ohlcv_data)
        sids = [1] * len(ohlcv_data)
        opens = [Decimal(o) for o, h, l, c, v in ohlcv_data]
        highs = [Decimal(h) for o, h, l, c, v in ohlcv_data]
        lows = [Decimal(l) for o, h, l, c, v in ohlcv_data]
        closes = [Decimal(c) for o, h, l, c, v in ohlcv_data]
        volumes = [Decimal(v) for o, h, l, c, v in ohlcv_data]

        # Ensure OHLCV relationships are valid (high >= all, low <= all)
        valid_data = []
        for i in range(len(ohlcv_data)):
            o, h, l, c, v = opens[i], highs[i], lows[i], closes[i], volumes[i]
            # Adjust to ensure valid OHLCV relationships
            max_price = max(o, h, l, c)
            min_price = min(o, h, l, c)
            valid_data.append((o, max_price, min_price, c, v))

        df = pl.DataFrame(
            {
                "date": dates,
                "sid": sids,
                "open": [d[0] for d in valid_data],
                "high": [d[1] for d in valid_data],
                "low": [d[2] for d in valid_data],
                "close": [d[3] for d in valid_data],
                "volume": [d[4] for d in valid_data],
            },
            schema=DAILY_BARS_SCHEMA,
        )

        # Write to Parquet
        with tempfile.TemporaryDirectory() as tmpdir:
            writer = ParquetWriter(tmpdir, enable_metadata_catalog=False)
            output_path = writer.write_daily_bars(df, compression="zstd")

            # Read back
            df_read = pl.read_parquet(output_path)

            # Validate exact Decimal equality for all rows
            for i in range(len(df)):
                assert df_read["open"][i] == df["open"][i], f"Open mismatch at row {i}"
                assert df_read["high"][i] == df["high"][i], f"High mismatch at row {i}"
                assert df_read["low"][i] == df["low"][i], f"Low mismatch at row {i}"
                assert df_read["close"][i] == df["close"][i], f"Close mismatch at row {i}"
                assert df_read["volume"][i] == df["volume"][i], f"Volume mismatch at row {i}"

    @given(
        st.lists(
            st.tuples(
                st.decimals(
                    min_value=Decimal("0.00000001"),
                    max_value=Decimal("100000.00000000"),
                    places=8,
                    allow_nan=False,
                    allow_infinity=False,
                ).map(str),
                st.decimals(
                    min_value=Decimal("0.00000001"),
                    max_value=Decimal("100000.00000000"),
                    places=8,
                    allow_nan=False,
                    allow_infinity=False,
                ).map(str),
                st.decimals(
                    min_value=Decimal("0.00000001"),
                    max_value=Decimal("100000.00000000"),
                    places=8,
                    allow_nan=False,
                    allow_infinity=False,
                ).map(str),
                st.decimals(
                    min_value=Decimal("0.00000001"),
                    max_value=Decimal("100000.00000000"),
                    places=8,
                    allow_nan=False,
                    allow_infinity=False,
                ).map(str),
                st.decimals(
                    min_value=Decimal("0.00000000"),
                    max_value=Decimal("1000000000.00000000"),
                    places=8,
                    allow_nan=False,
                    allow_infinity=False,
                ).map(str),
            ),
            min_size=10,
            max_size=100,
        )
    )
    @settings(max_examples=1000, deadline=None)
    def test_minute_bars_roundtrip_preserves_all_decimal_values(self, ohlcv_data):
        """Property test: Any valid OHLCV data survives minute bars Parquet roundtrip exactly.

        Tests with 1000+ randomly generated examples to validate Decimal precision
        for minute-resolution data.
        """
        if not ohlcv_data:
            return  # Skip empty lists

        # Create DataFrame from generated data
        # Generate timestamps for trading day (9:30 AM to 4:00 PM = 390 minutes)
        base_time = datetime(2023, 1, 1, 9, 30)
        from datetime import timedelta

        timestamps = [base_time + timedelta(minutes=i % 390) for i in range(len(ohlcv_data))]
        sids = [1] * len(ohlcv_data)
        opens = [Decimal(o) for o, h, l, c, v in ohlcv_data]
        highs = [Decimal(h) for o, h, l, c, v in ohlcv_data]
        lows = [Decimal(l) for o, h, l, c, v in ohlcv_data]
        closes = [Decimal(c) for o, h, l, c, v in ohlcv_data]
        volumes = [Decimal(v) for o, h, l, c, v in ohlcv_data]

        # Ensure valid OHLCV relationships
        valid_data = []
        for i in range(len(ohlcv_data)):
            o, h, l, c, v = opens[i], highs[i], lows[i], closes[i], volumes[i]
            max_price = max(o, h, l, c)
            min_price = min(o, h, l, c)
            valid_data.append((o, max_price, min_price, c, v))

        df = pl.DataFrame(
            {
                "timestamp": timestamps,
                "sid": sids,
                "open": [d[0] for d in valid_data],
                "high": [d[1] for d in valid_data],
                "low": [d[2] for d in valid_data],
                "close": [d[3] for d in valid_data],
                "volume": [d[4] for d in valid_data],
            },
            schema=MINUTE_BARS_SCHEMA,
        )

        # Write to Parquet
        with tempfile.TemporaryDirectory() as tmpdir:
            writer = ParquetWriter(tmpdir, enable_metadata_catalog=False)
            output_path = writer.write_minute_bars(df, compression="zstd")

            # Read back
            df_read = pl.read_parquet(output_path)

            # Validate exact Decimal equality for all rows
            for i in range(len(df)):
                assert df_read["open"][i] == df["open"][i], f"Open mismatch at row {i}"
                assert df_read["high"][i] == df["high"][i], f"High mismatch at row {i}"
                assert df_read["low"][i] == df["low"][i], f"Low mismatch at row {i}"
                assert df_read["close"][i] == df["close"][i], f"Close mismatch at row {i}"
                assert df_read["volume"][i] == df["volume"][i], f"Volume mismatch at row {i}"


@pytest.mark.benchmark
class TestPerformanceBenchmarks:
    """Performance benchmark tests for lazy loading and write operations."""

    def test_large_dataset_write_performance(self, benchmark, temp_bundle_path):
        """Benchmark writing large dataset (1000 rows) to Parquet."""
        # Create large dataset
        import random

        random.seed(42)

        dates = [date(2023, 1, 1)] * 1000
        sids = list(range(1, 1001))

        large_df = pl.DataFrame(
            {
                "date": dates,
                "sid": sids,
                "open": [Decimal(str(random.uniform(100, 200))) for _ in range(1000)],
                "high": [Decimal(str(random.uniform(200, 300))) for _ in range(1000)],
                "low": [Decimal(str(random.uniform(50, 100))) for _ in range(1000)],
                "close": [Decimal(str(random.uniform(100, 200))) for _ in range(1000)],
                "volume": [Decimal(str(random.randint(100000, 10000000))) for _ in range(1000)],
            },
            schema=DAILY_BARS_SCHEMA,
        )

        writer = ParquetWriter(str(temp_bundle_path), enable_metadata_catalog=False)

        # Benchmark write operation
        result = benchmark(writer.write_daily_bars, large_df, "zstd")

        # Validate result
        assert result.exists()

    def test_lazy_loading_read_performance(self, benchmark, temp_bundle_path):
        """Benchmark lazy loading read with partition pruning."""
        # First, write a large partitioned dataset
        import random

        random.seed(42)

        # Create multi-month dataset
        all_dfs = []
        for month in range(1, 4):  # 3 months of data
            dates = [date(2023, month, 1)] * 500
            sids = list(range(1, 501))

            month_df = pl.DataFrame(
                {
                    "date": dates,
                    "sid": sids,
                    "open": [Decimal(str(random.uniform(100, 200))) for _ in range(500)],
                    "high": [Decimal(str(random.uniform(200, 300))) for _ in range(500)],
                    "low": [Decimal(str(random.uniform(50, 100))) for _ in range(500)],
                    "close": [Decimal(str(random.uniform(100, 200))) for _ in range(500)],
                    "volume": [Decimal(str(random.randint(100000, 10000000))) for _ in range(500)],
                },
                schema=DAILY_BARS_SCHEMA,
            )
            all_dfs.append(month_df)

        # Write all data
        writer = ParquetWriter(str(temp_bundle_path), enable_metadata_catalog=False)
        paths = []
        for df in all_dfs:
            path = writer.write_daily_bars(df, "zstd")
            paths.append(path)

        # Benchmark reading with lazy loading
        def read_lazy():
            # Read with partition pruning (should only load one partition)
            return pl.read_parquet(paths[0])

        result = benchmark(read_lazy)

        # Validate we got data back
        assert len(result) == 500

    def test_batch_write_performance(self, benchmark, temp_bundle_path):
        """Benchmark batch write operations."""
        import random

        random.seed(42)

        # Create multiple DataFrames
        dfs = []
        for i in range(10):
            dates = [date(2023, 1, i + 1)] * 100
            sids = list(range(1, 101))

            df = pl.DataFrame(
                {
                    "date": dates,
                    "sid": sids,
                    "open": [Decimal(str(random.uniform(100, 200))) for _ in range(100)],
                    "high": [Decimal(str(random.uniform(200, 300))) for _ in range(100)],
                    "low": [Decimal(str(random.uniform(50, 100))) for _ in range(100)],
                    "close": [Decimal(str(random.uniform(100, 200))) for _ in range(100)],
                    "volume": [Decimal(str(random.randint(100000, 10000000))) for _ in range(100)],
                },
                schema=DAILY_BARS_SCHEMA,
            )
            dfs.append(df)

        writer = ParquetWriter(str(temp_bundle_path), enable_metadata_catalog=False)

        # Benchmark batch write
        result = benchmark(writer.write_batch, dfs, "daily", "zstd")

        # Validate all files written
        assert len(result) == 10


@pytest.mark.integration
class TestConcurrentWrites:
    """Integration tests for concurrent atomic write operations."""

    def test_concurrent_writes_no_corruption(self, temp_bundle_path):
        """Test that concurrent writes to different partitions dont corrupt data."""
        import threading

        writer = ParquetWriter(str(temp_bundle_path), enable_metadata_catalog=False)
        errors = []

        def write_data(month, thread_id):
            try:
                dates = [date(2023, month, 1)] * 100
                sids = list(range(thread_id * 100, (thread_id + 1) * 100))

                df = pl.DataFrame(
                    {
                        "date": dates,
                        "sid": sids,
                        "open": [Decimal(str(100 + thread_id)) for _ in range(100)],
                        "high": [Decimal(str(200 + thread_id)) for _ in range(100)],
                        "low": [Decimal(str(50 + thread_id)) for _ in range(100)],
                        "close": [Decimal(str(150 + thread_id)) for _ in range(100)],
                        "volume": [Decimal(str(1000000 + thread_id * 1000)) for _ in range(100)],
                    },
                    schema=DAILY_BARS_SCHEMA,
                )

                output_path = writer.write_daily_bars(df, "zstd")
                assert output_path.exists()

            except Exception as e:
                errors.append((thread_id, str(e)))

        # Create 4 threads writing to different months
        threads = []
        for i in range(4):
            thread = threading.Thread(target=write_data, args=(i + 1, i))
            threads.append(thread)
            thread.start()

        # Wait for all threads
        for thread in threads:
            thread.join()

        # Verify no errors occurred
        assert len(errors) == 0, f"Errors during concurrent writes: {errors}"

        # Verify all files were written
        daily_bars_path = temp_bundle_path / "daily_bars"
        parquet_files = list(daily_bars_path.rglob("*.parquet"))
        assert len(parquet_files) == 4, f"Expected 4 parquet files, found {len(parquet_files)}"

    def test_atomic_write_no_partial_files_on_error(self, temp_bundle_path):
        """Test that atomic writes dont leave partial files on error."""
        writer = ParquetWriter(str(temp_bundle_path), enable_metadata_catalog=False)

        # Create invalid DataFrame to trigger error during write
        invalid_df = pl.DataFrame(
            {
                "date": [date(2023, 1, 1)],
                "sid": [1],
                # Missing required columns to trigger error
            }
        )

        # Attempt write (should fail)
        try:
            writer.write_daily_bars(invalid_df, "zstd")
            assert False, "Expected write to fail"
        except ValueError:
            pass  # Expected error

        # Verify no temp files left behind
        daily_bars_path = temp_bundle_path / "daily_bars"
        if daily_bars_path.exists():
            temp_files = list(daily_bars_path.rglob(".*.tmp.*"))
            assert len(temp_files) == 0, f"Found {len(temp_files)} temp files after failed write"
