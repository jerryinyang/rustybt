"""Asset database schema definitions for RustyBT.

This module defines the complete SQLAlchemy schema for the assets database, providing
the foundation for storing and managing asset metadata, pricing data bundles, and
related information.

Schema Components:
    Core Asset Tables:
        - equities: Equity securities metadata
        - futures_contracts: Futures contract specifications
        - futures_root_symbols: Root symbol definitions for futures
        - exchanges: Exchange information
        - asset_router: Maps sids to asset types

    Symbol Mapping Tables:
        - equity_symbol_mappings: Historical equity symbol changes
        - equity_supplementary_mappings: Additional equity identifier mappings

    Bundle Management Tables:
        - bundle_metadata: Pricing data bundle metadata and quality metrics
        - bundle_cache: Smart caching layer for bundle data
        - cache_statistics: Cache performance monitoring
        - bundle_symbols: Symbol inventory per bundle
        - backtest_data_links: Backtest-to-bundle provenance tracking

    Version Control:
        - version_info: Database schema version tracking

Database Versioning:
    The schema uses a version number (ASSET_DB_VERSION) to track schema changes and
    enable proper migration handling. When modifying the schema:

    1. Increment ASSET_DB_VERSION
    2. Add corresponding upgrade/downgrade logic in asset_db_migrations.py
    3. Test migration both forward and backward

Schema Evolution:
    - v1-7: Legacy asset and symbol tracking
    - v8: Added bundle metadata and quality metrics
    - v9: Unified quality metrics into bundle_metadata
    - v10: Current version with full bundle management

Examples:
    Create a new assets database:
        >>> from rustybt.assets.asset_db_schema import metadata
        >>> from sqlalchemy import create_engine
        >>> engine = create_engine("sqlite:///assets.db")
        >>> metadata.create_all(engine)

    Query the version:
        >>> from rustybt.assets.asset_db_schema import ASSET_DB_VERSION
        >>> print(f"Schema version: {ASSET_DB_VERSION}")
        Schema version: 10

See Also:
    rustybt.assets.asset_writer: AssetDBWriter for populating the schema
    rustybt.assets.asset_db_migrations: Schema migration utilities
    rustybt.assets.assets: AssetFinder for querying the database

Notes:
    - All date/time fields are stored as Unix epoch nanoseconds (BigInteger)
    - The schema supports both SQLite and PostgreSQL backends
    - Foreign key constraints are enforced where appropriate
    - Indexes are created for common query patterns
"""

import sqlalchemy as sa

# Database schema version number
# Increment this whenever the schema changes and add migration logic to asset_db_migrations.py
ASSET_DB_VERSION = 10

# A frozenset of the names of all tables in the assets db
# NOTE: When modifying this schema, update the ASSET_DB_VERSION value
asset_db_table_names = frozenset(
    {
        "asset_router",
        "equities",
        "equity_symbol_mappings",
        "equity_supplementary_mappings",
        "futures_contracts",
        "exchanges",
        "futures_root_symbols",
        "version_info",
        "bundle_metadata",
        "bundle_cache",
        "cache_statistics",
        "bundle_symbols",
        "backtest_data_links",
    }
)

metadata = sa.MetaData()

exchanges = sa.Table(
    "exchanges",
    metadata,
    sa.Column(
        "exchange",
        sa.Text,
        unique=True,
        nullable=False,
        primary_key=True,
    ),
    sa.Column("canonical_name", sa.Text, nullable=False),
    sa.Column("country_code", sa.Text, nullable=False),
)

equities = sa.Table(
    "equities",
    metadata,
    sa.Column(
        "sid",
        sa.BigInteger,
        unique=True,
        nullable=False,
        primary_key=True,
    ),
    sa.Column("asset_name", sa.Text),
    sa.Column("start_date", sa.BigInteger, default=0, nullable=False),
    sa.Column("end_date", sa.BigInteger, nullable=False),
    sa.Column("first_traded", sa.BigInteger),
    sa.Column("auto_close_date", sa.BigInteger),
    sa.Column("exchange", sa.Text, sa.ForeignKey(exchanges.c.exchange)),
)

equity_symbol_mappings = sa.Table(
    "equity_symbol_mappings",
    metadata,
    sa.Column(
        "id",
        sa.BigInteger,
        unique=True,
        nullable=False,
        primary_key=True,
    ),
    sa.Column(
        "sid",
        sa.BigInteger,
        sa.ForeignKey(equities.c.sid),
        nullable=False,
        index=True,
    ),
    sa.Column(
        "symbol",
        sa.Text,
        nullable=False,
    ),
    sa.Column(
        "company_symbol",
        sa.Text,
        index=True,
    ),
    sa.Column(
        "share_class_symbol",
        sa.Text,
    ),
    sa.Column(
        "start_date",
        sa.BigInteger,
        nullable=False,
    ),
    sa.Column(
        "end_date",
        sa.BigInteger,
        nullable=False,
    ),
)

equity_supplementary_mappings = sa.Table(
    "equity_supplementary_mappings",
    metadata,
    sa.Column(
        "sid",
        sa.BigInteger,
        sa.ForeignKey(equities.c.sid),
        nullable=False,
        primary_key=True,
    ),
    sa.Column("field", sa.Text, nullable=False, primary_key=True),
    sa.Column("start_date", sa.BigInteger, nullable=False, primary_key=True),
    sa.Column("end_date", sa.BigInteger, nullable=False),
    sa.Column("value", sa.Text, nullable=False),
)

futures_root_symbols = sa.Table(
    "futures_root_symbols",
    metadata,
    sa.Column(
        "root_symbol",
        sa.Text,
        unique=True,
        nullable=False,
        primary_key=True,
    ),
    sa.Column("root_symbol_id", sa.BigInteger),
    sa.Column("sector", sa.Text),
    sa.Column("description", sa.Text),
    sa.Column(
        "exchange",
        sa.Text,
        sa.ForeignKey(exchanges.c.exchange),
    ),
)

futures_contracts = sa.Table(
    "futures_contracts",
    metadata,
    sa.Column(
        "sid",
        sa.BigInteger,
        unique=True,
        nullable=False,
        primary_key=True,
    ),
    sa.Column("symbol", sa.Text, unique=True, index=True),
    sa.Column(
        "root_symbol",
        sa.Text,
        sa.ForeignKey(futures_root_symbols.c.root_symbol),
        index=True,
    ),
    sa.Column("asset_name", sa.Text),
    sa.Column("start_date", sa.BigInteger, default=0, nullable=False),
    sa.Column("end_date", sa.BigInteger, nullable=False),
    sa.Column("first_traded", sa.BigInteger),
    sa.Column(
        "exchange",
        sa.Text,
        sa.ForeignKey(exchanges.c.exchange),
    ),
    sa.Column("notice_date", sa.BigInteger, nullable=False),
    sa.Column("expiration_date", sa.BigInteger, nullable=False),
    sa.Column("auto_close_date", sa.BigInteger, nullable=False),
    sa.Column("multiplier", sa.Float),
    sa.Column("tick_size", sa.Float),
)

asset_router = sa.Table(
    "asset_router",
    metadata,
    sa.Column("sid", sa.BigInteger, unique=True, nullable=False, primary_key=True),
    sa.Column("asset_type", sa.Text),
)

version_info = sa.Table(
    "version_info",
    metadata,
    sa.Column(
        "id",
        sa.Integer,
        unique=True,
        nullable=False,
        primary_key=True,
    ),
    sa.Column(
        "version",
        sa.Integer,
        unique=True,
        nullable=False,
    ),
    # This constraint ensures a single entry in this table
    sa.CheckConstraint("id <= 1"),
)

bundle_metadata = sa.Table(
    "bundle_metadata",
    metadata,
    sa.Column(
        "id",
        sa.Integer,
        primary_key=True,
        autoincrement=True,
    ),
    sa.Column(
        "bundle_name",
        sa.Text,
        nullable=False,
        unique=True,
    ),
    sa.Column(
        "source_type",
        sa.Text,
        nullable=False,
    ),
    sa.Column("source_url", sa.Text),
    sa.Column("api_version", sa.Text),
    sa.Column("fetch_timestamp", sa.Integer, nullable=False),
    sa.Column("data_version", sa.Text),
    sa.Column("timezone", sa.Text, nullable=False, server_default="UTC"),
    sa.Column("row_count", sa.Integer, nullable=True),
    sa.Column("start_date", sa.Integer, nullable=True),
    sa.Column("end_date", sa.Integer, nullable=True),
    sa.Column("missing_days_count", sa.Integer, nullable=False, server_default="0"),
    sa.Column("missing_days_list", sa.Text, nullable=False, server_default="[]"),
    sa.Column("outlier_count", sa.Integer, nullable=False, server_default="0"),
    sa.Column("ohlcv_violations", sa.Integer, nullable=False, server_default="0"),
    sa.Column(
        "validation_passed", sa.Boolean, nullable=False, server_default=sa.sql.expression.true()
    ),
    sa.Column("validation_timestamp", sa.Integer, nullable=True),
    sa.Column("file_checksum", sa.Text),
    sa.Column("file_size_bytes", sa.Integer),
    sa.Column("checksum", sa.Text),  # Legacy checksum (deprecated)
    sa.Column(
        "calendar",
        sa.Text,
        nullable=True,
    ),  # Trading calendar name (e.g., "24/5" for forex, "XNYS" for equities)
    sa.Column(
        "created_at",
        sa.Integer,
        nullable=False,
    ),
    sa.Column(
        "updated_at",
        sa.Integer,
        nullable=False,
    ),
    # Close bundle_metadata table definition
)

# Create indexes for bundle metadata table
sa.Index("idx_bundle_metadata_name", bundle_metadata.c.bundle_name)
sa.Index("idx_bundle_metadata_fetch", bundle_metadata.c.fetch_timestamp)
sa.Index("idx_bundle_metadata_validation", bundle_metadata.c.validation_timestamp)

# Bundle cache table for Story 8.3 (smart caching layer)
bundle_cache = sa.Table(
    "bundle_cache",
    metadata,
    sa.Column(
        "id",
        sa.Integer,
        primary_key=True,
        autoincrement=True,
    ),
    sa.Column(
        "cache_key",
        sa.Text,
        nullable=False,
        unique=True,
        index=True,
    ),
    sa.Column(
        "bundle_name",
        sa.Text,
        nullable=False,
    ),
    sa.Column(
        "bundle_path",
        sa.Text,
        nullable=False,
    ),
    sa.Column("symbols", sa.Text),  # JSON list
    sa.Column("start", sa.Text),
    sa.Column("end", sa.Text),
    sa.Column("frequency", sa.Text),
    sa.Column(
        "fetch_timestamp",
        sa.Integer,
        nullable=False,
    ),
    sa.Column(
        "size_bytes",
        sa.Integer,
        nullable=False,
    ),
    sa.Column("row_count", sa.Integer),
    sa.Column(
        "last_accessed",
        sa.Integer,
        nullable=False,
        index=True,  # For LRU eviction
    ),
)

# Cache statistics table for monitoring (Story 8.3 Phase 4)
cache_statistics = sa.Table(
    "cache_statistics",
    metadata,
    sa.Column(
        "stat_date",
        sa.Integer,
        primary_key=True,  # Unix timestamp (day granularity)
    ),
    sa.Column("hit_count", sa.Integer, default=0),
    sa.Column("miss_count", sa.Integer, default=0),
    sa.Column("total_size_mb", sa.REAL, default=0.0),
    sa.Column("avg_fetch_latency_ms", sa.REAL, default=0.0),
)

# Indexes for cache tables
sa.Index("idx_bundle_cache_key", bundle_cache.c.cache_key)
sa.Index("idx_bundle_cache_last_accessed", bundle_cache.c.last_accessed)
sa.Index("idx_cache_statistics_date", cache_statistics.c.stat_date)

# Bundle symbols table (Story 8.4: Unified Metadata Management)
# Merged from ParquetMetadataCatalog symbols tracking
bundle_symbols = sa.Table(
    "bundle_symbols",
    metadata,
    sa.Column(
        "id",
        sa.Integer,
        primary_key=True,
        autoincrement=True,
    ),
    sa.Column(
        "bundle_name",
        sa.Text,
        sa.ForeignKey("bundle_metadata.bundle_name"),
        nullable=False,
    ),
    sa.Column(
        "symbol",
        sa.Text,
        nullable=False,
    ),
    sa.Column("asset_type", sa.Text),  # 'equity', 'crypto', 'future'
    sa.Column("exchange", sa.Text),  # 'NYSE', 'binance', etc.
    sa.UniqueConstraint("bundle_name", "symbol", name="unique_bundle_symbol"),
)

# Indexes for bundle_symbols
sa.Index("idx_bundle_symbols_bundle", bundle_symbols.c.bundle_name)
sa.Index("idx_bundle_symbols_symbol", bundle_symbols.c.symbol)

# Backtest data links table (Story X3.7: Integrate Backtest Runs with DataCatalog)
# Links backtests to the datasets (bundles) they used for data provenance tracking
backtest_data_links = sa.Table(
    "backtest_data_links",
    metadata,
    sa.Column(
        "id",
        sa.Integer,
        primary_key=True,
        autoincrement=True,
    ),
    sa.Column(
        "backtest_id",
        sa.Text,
        nullable=False,
    ),
    sa.Column(
        "bundle_name",
        sa.Text,
        sa.ForeignKey("bundle_metadata.bundle_name"),
        nullable=False,
    ),
    sa.Column(
        "accessed_at",
        sa.Integer,
        nullable=False,
    ),
)

# Indexes for backtest_data_links
sa.Index("idx_backtest_data_links_backtest_id", backtest_data_links.c.backtest_id)
sa.Index("idx_backtest_data_links_bundle_name", backtest_data_links.c.bundle_name)
