"""Asset database schema migration utilities.

This module provides infrastructure for upgrading and downgrading the asset database
schema between different versions. It uses Alembic for migration operations and maintains
a registry of downgrade functions for each schema version.

Key Features:
    - Automated schema versioning and validation
    - Forward and backward migration support
    - SQLite and PostgreSQL compatibility
    - Foreign key constraint handling during migrations
    - Safe DDL operations with validation

Migration Workflow:
    1. Schema changes are made in asset_db_schema.py
    2. ASSET_DB_VERSION is incremented
    3. A downgrade function is added here using the @downgrades decorator
    4. The function implements the inverse operation to revert the schema change

Version Control:
    The module maintains a _downgrade_methods dictionary that maps version numbers
    to downgrade functions. Each function knows how to downgrade from version N to
    version N-1.

Safety Features:
    - Input validation for SQL identifiers
    - Foreign key handling for batch operations
    - Version checking to prevent invalid migrations
    - Automatic cleanup of temporary tables

Examples:
    Downgrade a database to an earlier version:
        >>> from rustybt.assets.asset_db_migrations import downgrade
        >>> from sqlalchemy import create_engine
        >>> engine = create_engine("sqlite:///assets.db")
        >>> downgrade(engine, desired_version=8)  # Downgrade to v8

    Check if migration is needed:
        >>> # AssetFinder automatically checks version on initialization
        >>> from rustybt.assets import AssetFinder
        >>> finder = AssetFinder("sqlite:///assets.db")  # Raises if version mismatch

Warning:
    Migrations can be destructive operations, especially downgrades which may lose
    data. Always backup your database before performing migrations.

See Also:
    rustybt.assets.asset_db_schema: Schema definitions and ASSET_DB_VERSION
    rustybt.assets.asset_writer: Database writing and version management
    rustybt.errors.AssetDBVersionError: Version mismatch errors

Notes:
    - Downgrade functions are registered with @downgrades(source_version)
    - The decorator automatically handles version table updates
    - Foreign keys are temporarily disabled during complex migrations
    - SQL identifier validation prevents injection in migration code
"""

import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations
from toolz.curried import do, operator

from rustybt.assets.asset_writer import write_version_info
from rustybt.errors import AssetDBImpossibleDowngrade
from rustybt.utils.compat import wraps
from rustybt.utils.preprocess import preprocess
from rustybt.utils.sqlite_utils import coerce_string_to_eng


def alter_columns(op, name, *columns, **kwargs):
    """Alter table columns during migrations.

    Performs a table column alteration by creating a new table with the desired
    schema, copying data from the old table, and replacing the old table. This
    is necessary because SQLite doesn't support ALTER COLUMN directly.

    The function validates all identifiers (table and column names) to prevent
    SQL injection and ensures safe migrations.

    Args:
        op: Alembic Operations object for DDL operations.
        name: Name of the table to alter. Must be a valid SQL identifier.
        *columns: SQLAlchemy Column objects defining the new schema.
        **kwargs: Optional keyword arguments:
            selection_string: Custom SQL SELECT expression for copying data.
                If not provided, selects all columns from the new schema.

    Raises:
        ValueError: If table or column names are not valid SQL identifiers.

    Notes:
        - Columns must be passed explicitly for safety in downgrades
        - Temporary tables are used and automatically cleaned up
        - Indexes are dropped and recreated as needed
        - PostgreSQL uses CASCADE for table drops

    Examples:
        Alter table to change column types:
            >>> alter_columns(
            ...     op,
            ...     "equities",
            ...     sa.Column("sid", sa.BigInteger, primary_key=True),
            ...     sa.Column("symbol", sa.Text),
            ...     sa.Column("exchange", sa.Text)
            ... )

        Alter with custom selection (e.g., dropping a column):
            >>> alter_columns(
            ...     op,
            ...     "equities",
            ...     sa.Column("sid", sa.BigInteger, primary_key=True),
            ...     sa.Column("symbol", sa.Text),
            ...     selection_string="sid, symbol"  # Exclude other columns
            ... )
    """
    # SECURITY: SQL f-strings in migration code
    # THREAT MODEL:
    # - Input source: Database migration code (internal, not user input)
    # - Trust level: Trusted (migration-defined table/column names)
    # - Use case: Alembic database schema migrations
    # GUARDRAILS:
    # - Table and column names come from migration definitions, not external input
    # - Alembic Operations API provides DDL abstraction
    # - Identifier validation below ensures SQL-safe names
    # SQL INJECTION RISK: Low (controlled identifiers only)
    # MITIGATION: Whitelist validation of identifiers

    # Validate table name is SQL-safe identifier
    if not name.replace("_", "").isalnum():
        raise ValueError(f"Invalid table name for migration: {name!r}")

    selection_string = kwargs.pop("selection_string", None)
    if kwargs:
        raise TypeError(
            "alter_columns received extra arguments: %r" % sorted(kwargs),
        )
    if selection_string is None:
        selection_string = ", ".join(column.name for column in columns)

    # Validate column names are SQL-safe identifiers
    for column in columns:
        if not column.name.replace("_", "").isalnum():
            raise ValueError(f"Invalid column name for migration: {column.name!r}")

    tmp_name = "_alter_columns_" + name
    op.rename_table(name, tmp_name)

    for column in columns:
        # Clear any indices that already exist on this table, otherwise we will
        # fail to create the table because the indices will already be present.
        # When we create the table below, the indices that we want to preserve
        # will just get recreated.
        for table in (name, tmp_name):
            try:
                # nosec B608 - table and column names validated as SQL identifiers above
                op.execute(f"DROP INDEX IF EXISTS ix_{table}_{column.name}")
            except sa.exc.OperationalError:
                pass

    op.create_table(name, *columns)
    # nosec B608 - table name validated, selection_string from internal column names
    # Table and column names are from trusted internal framework preprocessing
    op.execute(
        f"INSERT INTO {name} SELECT {selection_string} FROM {tmp_name}",  # nosec B608
    )

    if op.impl.dialect.name == "postgresql":
        # nosec B608 - tmp_name is internally generated with validated base name
        op.execute(f"ALTER TABLE {tmp_name} DISABLE TRIGGER ALL;")
        op.execute(f"DROP TABLE {tmp_name} CASCADE;")
    else:
        op.drop_table(tmp_name)


@preprocess(engine=coerce_string_to_eng(require_exists=True))
def downgrade(engine, desired_version):
    """Downgrade the asset database to a specific schema version.

    Executes a series of downgrade operations to migrate the database from its
    current version to the specified target version. Each downgrade step is
    executed sequentially with foreign keys disabled for safe schema modifications.

    Warning:
        Downgrades may result in data loss. Always backup your database before
        performing downgrades, especially when downgrading multiple versions.

    Args:
        engine: SQLAlchemy engine connection to the assets database, or a string
            URI that can be parsed by SQLAlchemy. The database must exist.
        desired_version: Target schema version to downgrade to. Must be less than
            or equal to the current database version.

    Raises:
        AssetDBImpossibleDowngrade: If desired_version is greater than the current
            database version (would require upgrade, not downgrade).

    Examples:
        Downgrade from v10 to v8:
            >>> from sqlalchemy import create_engine
            >>> engine = create_engine("sqlite:///assets.db")
            >>> downgrade(engine, desired_version=8)

        Downgrade using a connection string:
            >>> downgrade("sqlite:///assets.db", desired_version=7)

    Notes:
        - If the database is already at the desired version, no operations are performed
        - Foreign keys are disabled during the migration and re-enabled afterward
        - The version_info table is updated after each successful downgrade step
        - Migration operations are wrapped in a transaction
    """
    # Check the version of the db at the engine
    with engine.begin() as conn:
        metadata_obj = sa.MetaData()
        metadata_obj.reflect(conn)
        version_info_table = metadata_obj.tables["version_info"]
        # starting_version = sa.select((version_info_table.c.version,)).scalar()
        starting_version = conn.execute(sa.select(version_info_table.c.version)).scalar()

        # Check for accidental upgrade
        if starting_version < desired_version:
            raise AssetDBImpossibleDowngrade(
                db_version=starting_version, desired_version=desired_version
            )

        # Check if the desired version is already the db version
        if starting_version == desired_version:
            # No downgrade needed
            return

        # Create alembic context
        ctx = MigrationContext.configure(conn)
        op = Operations(ctx)

        # Integer keys of downgrades to run
        # E.g.: [5, 4, 3, 2] would downgrade v6 to v2
        downgrade_keys = range(desired_version, starting_version)[::-1]

        # Disable foreign keys until all downgrades are complete
        _pragma_foreign_keys(conn, False)

        # Execute the downgrades in order
        for downgrade_key in downgrade_keys:
            _downgrade_methods[downgrade_key](op, conn, version_info_table)

        # Re-enable foreign keys
        _pragma_foreign_keys(conn, True)


def _pragma_foreign_keys(connection, on):
    """Enable or disable foreign key constraint checking.

    Temporarily disables foreign key constraints to allow batch table modifications
    that would otherwise violate referential integrity during intermediate migration
    steps. Only affects SQLite databases.

    Args:
        connection: SQLAlchemy database connection.
        on: If True, enables foreign key constraints (PRAGMA foreign_keys=ON).
            If False, disables foreign key constraints (PRAGMA foreign_keys=OFF).

    Notes:
        - Only executes for SQLite databases; PostgreSQL is not affected
        - Should always be re-enabled after migration operations complete
        - Foreign key constraints are NOT enforced while disabled
        - Use with caution as this can allow invalid data states temporarily

    Examples:
        Disable foreign keys before migration:
            >>> _pragma_foreign_keys(conn, False)
            >>> # Perform migration operations
            >>> _pragma_foreign_keys(conn, True)  # Re-enable
    """
    if connection.engine.name == "sqlite":
        connection.execute(sa.text(f"PRAGMA foreign_keys={'ON' if on else 'OFF'}"))
    # elif connection.engine.name == "postgresql":
    #     connection.execute(
    #         f"SET session_replication_role  = {'origin' if on else 'replica'};"
    #     )


# This dict contains references to downgrade methods that can be applied to an
# assets db. The resulting db's version is the key.
# e.g. The method at key '0' is the downgrade method from v1 to v0
_downgrade_methods = {}


def downgrades(src):
    """Decorator for registering schema downgrade functions.

    Marks a function as a downgrade operation from a specific source version to
    the previous version (src - 1). The decorated function is automatically
    registered in the _downgrade_methods dictionary and wrapped to handle
    version table updates.

    Args:
        src: The source schema version this function downgrades FROM.
            The function will downgrade from version `src` to version `src-1`.

    Returns:
        callable: A decorator function that wraps the downgrade implementation.

    Examples:
        Register a downgrade from v10 to v9:
            >>> @downgrades(10)
            ... def _downgrade_v10(op):
            ...     '''Downgrade from v10 to v9 by removing new table.'''
            ...     op.drop_table("new_table_added_in_v10")

        The decorator handles:
            - Clearing the current version from version_info table
            - Executing the downgrade function
            - Writing the new version (src-1) to version_info table

    Notes:
        - Downgrade functions receive an Alembic Operations object as `op`
        - They also receive `conn` (connection) and `version_info_table`
        - The function is registered at `_downgrade_methods[src-1]`
        - Version table updates are automatic
    """

    def _(f):
        destination = src - 1

        @do(operator.setitem(_downgrade_methods, destination))
        @wraps(f)
        def wrapper(op, conn, version_info_table):
            conn.execute(version_info_table.delete())  # clear the version
            f(op)
            write_version_info(conn, version_info_table, destination)

        return wrapper

    return _


@downgrades(1)
def _downgrade_v1(op):
    """
    Downgrade assets db by removing the 'tick_size' column and renaming the
    'multiplier' column.
    """
    # Drop indices before batch
    # This is to prevent index collision when creating the temp table
    op.drop_index("ix_futures_contracts_root_symbol")
    op.drop_index("ix_futures_contracts_symbol")

    # Execute batch op to allow column modification in SQLite
    with op.batch_alter_table("futures_contracts") as batch_op:
        # Rename 'multiplier'
        batch_op.alter_column(column_name="multiplier", new_column_name="contract_multiplier")

        # Delete 'tick_size'
        batch_op.drop_column("tick_size")

    # Recreate indices after batch
    op.create_index(
        "ix_futures_contracts_root_symbol",
        table_name="futures_contracts",
        columns=["root_symbol"],
    )
    op.create_index(
        "ix_futures_contracts_symbol",
        table_name="futures_contracts",
        columns=["symbol"],
        unique=True,
    )


@downgrades(2)
def _downgrade_v2(op):
    """
    Downgrade assets db by removing the 'auto_close_date' column.
    """
    # Drop indices before batch
    # This is to prevent index collision when creating the temp table
    op.drop_index("ix_equities_fuzzy_symbol")
    op.drop_index("ix_equities_company_symbol")

    # Execute batch op to allow column modification in SQLite
    with op.batch_alter_table("equities") as batch_op:
        batch_op.drop_column("auto_close_date")

    # Recreate indices after batch
    op.create_index("ix_equities_fuzzy_symbol", table_name="equities", columns=["fuzzy_symbol"])
    op.create_index("ix_equities_company_symbol", table_name="equities", columns=["company_symbol"])


@downgrades(3)
def _downgrade_v3(op):
    """
    Downgrade assets db by adding a not null constraint on
    ``equities.first_traded``
    """
    op.create_table(
        "_new_equities",
        sa.Column(
            "sid",
            sa.BigInteger,
            unique=True,
            nullable=False,
            primary_key=True,
        ),
        sa.Column("symbol", sa.Text),
        sa.Column("company_symbol", sa.Text),
        sa.Column("share_class_symbol", sa.Text),
        sa.Column("fuzzy_symbol", sa.Text),
        sa.Column("asset_name", sa.Text),
        sa.Column("start_date", sa.BigInteger, default=0, nullable=False),
        sa.Column("end_date", sa.BigInteger, nullable=False),
        sa.Column("first_traded", sa.BigInteger, nullable=False),
        sa.Column("auto_close_date", sa.BigInteger),
        sa.Column("exchange", sa.Text),
    )
    op.execute(
        """
        insert into _new_equities
        select * from equities
        where equities.first_traded is not null
        """,
    )
    op.drop_table("equities")
    op.rename_table("_new_equities", "equities")
    # we need to make sure the indices have the proper names after the rename
    op.create_index(
        "ix_equities_company_symbol",
        "equities",
        ["company_symbol"],
    )
    op.create_index(
        "ix_equities_fuzzy_symbol",
        "equities",
        ["fuzzy_symbol"],
    )


@downgrades(4)
def _downgrade_v4(op):
    """
    Downgrades assets db by copying the `exchange_full` column to `exchange`,
    then dropping the `exchange_full` column.
    """
    op.drop_index("ix_equities_fuzzy_symbol")
    op.drop_index("ix_equities_company_symbol")

    op.execute("UPDATE equities SET exchange = exchange_full")

    with op.batch_alter_table("equities") as batch_op:
        batch_op.drop_column("exchange_full")

    op.create_index("ix_equities_fuzzy_symbol", table_name="equities", columns=["fuzzy_symbol"])
    op.create_index("ix_equities_company_symbol", table_name="equities", columns=["company_symbol"])


@downgrades(5)
def _downgrade_v5(op):
    op.create_table(
        "_new_equities",
        sa.Column(
            "sid",
            sa.BigInteger,
            unique=True,
            nullable=False,
            primary_key=True,
        ),
        sa.Column("symbol", sa.Text),
        sa.Column("company_symbol", sa.Text),
        sa.Column("share_class_symbol", sa.Text),
        sa.Column("fuzzy_symbol", sa.Text),
        sa.Column("asset_name", sa.Text),
        sa.Column("start_date", sa.BigInteger, default=0, nullable=False),
        sa.Column("end_date", sa.BigInteger, nullable=False),
        sa.Column("first_traded", sa.BigInteger),
        sa.Column("auto_close_date", sa.BigInteger),
        sa.Column("exchange", sa.Text),
        sa.Column("exchange_full", sa.Text),
    )

    op.execute(
        """
        INSERT INTO _new_equities
        SELECT
            equities.sid as sid,
            sym.symbol as symbol,
            sym.company_symbol as company_symbol,
            sym.share_class_symbol as share_class_symbol,
            sym.company_symbol || sym.share_class_symbol as fuzzy_symbol,
            equities.asset_name as asset_name,
            equities.start_date as start_date,
            equities.end_date as end_date,
            equities.first_traded as first_traded,
            equities.auto_close_date as auto_close_date,
            equities.exchange as exchange,
            equities.exchange_full as exchange_full
        FROM
            equities
        INNER JOIN
            -- Select the last held symbol (end_date) for each equity sid from the
            (SELECT
                sid, symbol, company_symbol, share_class_symbol, end_date
                FROM (SELECT *, RANK() OVER (PARTITION BY sid ORDER BY end_date DESC) max_end_date
                FROM equity_symbol_mappings) ranked WHERE max_end_date=1
            ) as sym
        on
            equities.sid = sym.sid
        """,
    )
    op.drop_table("equity_symbol_mappings")
    op.drop_table("equities")
    op.rename_table("_new_equities", "equities")
    # we need to make sure the indices have the proper names after the rename
    op.create_index(
        "ix_equities_company_symbol",
        "equities",
        ["company_symbol"],
    )
    op.create_index(
        "ix_equities_fuzzy_symbol",
        "equities",
        ["fuzzy_symbol"],
    )


@downgrades(6)
def _downgrade_v6(op):
    op.drop_table("equity_supplementary_mappings")


@downgrades(7)
def _downgrade_v7(op):
    tmp_name = "_new_equities"
    op.create_table(
        tmp_name,
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
        # remove foreign key to exchange
        sa.Column("exchange", sa.Text),
        # add back exchange full column
        sa.Column("exchange_full", sa.Text),
    )
    # nosec B608 - tmp_name is internally generated from trusted migration code
    # Table name is not from user input - it's from internal migration framework
    op.execute(
        f"""
        insert into
            {tmp_name}
        select
            eq.sid,
            eq.asset_name,
            eq.start_date,
            eq.end_date,
            eq.first_traded,
            eq.auto_close_date,
            ex.canonical_name,
            ex.exchange
        from
            equities eq
        inner join
            exchanges ex
        on
            eq.exchange = ex.exchange
        where
            ex.country_code in ('US', '??')
        """,  # nosec B608
    )
    # if op.impl.dialect.name == "postgresql":
    #     for table_name, col_name in [
    #         ("equities", "exchange"),
    #         ("equity_symbol_mappings", "sid"),
    #         ("equity_supplementary_mappings", "sid"),
    #     ]:
    #         op.drop_constraint(
    #             f"{table_name}_{col_name}_fkey",
    #             f"{table_name}",
    #             type_="foreignkey",
    #         )
    if op.impl.dialect.name == "postgresql":
        op.execute("ALTER TABLE equities DISABLE TRIGGER ALL;")
        op.execute("DROP TABLE equities CASCADE;")
    else:
        op.drop_table("equities")
    op.rename_table(tmp_name, "equities")

    # rebuild all tables without a foreign key to ``exchanges``
    alter_columns(
        op,
        "futures_root_symbols",
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
        sa.Column("exchange", sa.Text),
    )
    alter_columns(
        op,
        "futures_contracts",
        sa.Column(
            "sid",
            sa.BigInteger,
            unique=True,
            nullable=False,
            primary_key=True,
        ),
        sa.Column("symbol", sa.Text, unique=True, index=True),
        sa.Column("root_symbol", sa.Text, index=True),
        sa.Column("asset_name", sa.Text),
        sa.Column("start_date", sa.BigInteger, default=0, nullable=False),
        sa.Column("end_date", sa.BigInteger, nullable=False),
        sa.Column("first_traded", sa.BigInteger),
        sa.Column("exchange", sa.Text),
        sa.Column("notice_date", sa.BigInteger, nullable=False),
        sa.Column("expiration_date", sa.BigInteger, nullable=False),
        sa.Column("auto_close_date", sa.BigInteger, nullable=False),
        sa.Column("multiplier", sa.Float),
        sa.Column("tick_size", sa.Float),
    )

    # drop the ``country_code`` and ``canonical_name`` columns
    alter_columns(
        op,
        "exchanges",
        sa.Column(
            "exchange",
            sa.Text,
            unique=True,
            nullable=False,
            primary_key=True,
        ),
        sa.Column("timezone", sa.Text),
        # Set the timezone to NULL because we don't know what it was before.
        # Nothing in zipline reads the timezone so it doesn't matter.
        selection_string="exchange, NULL",
    )
    op.rename_table("exchanges", "futures_exchanges")

    # add back the foreign keys that previously existed
    alter_columns(
        op,
        "futures_root_symbols",
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
            sa.ForeignKey("futures_exchanges.exchange"),
        ),
    )
    alter_columns(
        op,
        "futures_contracts",
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
            sa.ForeignKey("futures_root_symbols.root_symbol"),
            index=True,
        ),
        sa.Column("asset_name", sa.Text),
        sa.Column("start_date", sa.BigInteger, default=0, nullable=False),
        sa.Column("end_date", sa.BigInteger, nullable=False),
        sa.Column("first_traded", sa.BigInteger),
        sa.Column(
            "exchange",
            sa.Text,
            sa.ForeignKey("futures_exchanges.exchange"),
        ),
        sa.Column("notice_date", sa.BigInteger, nullable=False),
        sa.Column("expiration_date", sa.BigInteger, nullable=False),
        sa.Column("auto_close_date", sa.BigInteger, nullable=False),
        sa.Column("multiplier", sa.Float),
        sa.Column("tick_size", sa.Float),
    )

    # Delete equity_symbol_mappings records that no longer refer to valid sids.
    op.execute(
        """
        DELETE FROM
            equity_symbol_mappings
        WHERE
            sid NOT IN (SELECT sid FROM equities);
        """
    )

    # Delete asset_router records that no longer refer to valid sids.
    op.execute(
        """
        DELETE FROM
            asset_router
        WHERE
            sid
            NOT IN (
                SELECT sid FROM equities
                UNION
                SELECT sid FROM futures_contracts
            );
        """
    )


@downgrades(8)
def _downgrade_v8(op):
    """
    Downgrade assets db by removing bundle metadata and data quality tables.
    """
    op.drop_table("data_quality_metrics")
    op.drop_table("bundle_metadata")


@downgrades(9)
def _downgrade_v9(op):
    """Downgrade assets db by restoring legacy bundle metadata schema."""
    # Backup unified quality fields prior to altering table structure
    op.execute(
        """
        CREATE TABLE _bundle_quality_backup AS
        SELECT
            bundle_name,
            row_count,
            start_date,
            end_date,
            missing_days_count,
            missing_days_list,
            outlier_count,
            ohlcv_violations,
            validation_timestamp,
            validation_passed
        FROM bundle_metadata
        """
    )

    # Drop unified validation index added in v9
    op.drop_index("idx_bundle_metadata_validation", table_name="bundle_metadata")

    # Legacy schema for bundle_metadata (version 8)
    legacy_bundle_metadata = sa.Table(
        "bundle_metadata_legacy",
        sa.MetaData(),
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("bundle_name", sa.Text, nullable=False, unique=True),
        sa.Column("source_type", sa.Text, nullable=False),
        sa.Column("source_url", sa.Text),
        sa.Column("api_version", sa.Text),
        sa.Column("fetch_timestamp", sa.Integer, nullable=False),
        sa.Column("data_version", sa.Text),
        sa.Column("checksum", sa.Text, nullable=False),
        sa.Column("timezone", sa.Text, nullable=False, server_default="UTC"),
        sa.Column("created_at", sa.Integer, nullable=False),
        sa.Column("updated_at", sa.Integer, nullable=False),
    )

    selection = (
        "id, bundle_name, source_type, source_url, api_version, "
        "fetch_timestamp, data_version, "
        "COALESCE(checksum, file_checksum, 'legacy-missing-checksum') AS checksum, "
        "timezone, created_at, updated_at"
    )

    alter_columns(
        op,
        "bundle_metadata",
        *legacy_bundle_metadata.c,
        selection_string=selection,
    )

    # Recreate legacy indexes
    op.create_index("idx_bundle_metadata_name", "bundle_metadata", ["bundle_name"], unique=False)
    op.create_index(
        "idx_bundle_metadata_fetch", "bundle_metadata", ["fetch_timestamp"], unique=False
    )

    # Restore legacy data_quality_metrics table
    op.create_table(
        "data_quality_metrics",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "bundle_name",
            sa.Text,
            sa.ForeignKey("bundle_metadata.bundle_name"),
            nullable=False,
        ),
        sa.Column("row_count", sa.Integer, nullable=False),
        sa.Column("start_date", sa.Integer, nullable=False),
        sa.Column("end_date", sa.Integer, nullable=False),
        sa.Column("missing_days_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("missing_days_list", sa.Text),
        sa.Column("outlier_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("ohlcv_violations", sa.Integer, nullable=False, server_default="0"),
        sa.Column("validation_timestamp", sa.Integer, nullable=False),
        sa.Column(
            "validation_passed", sa.Boolean, nullable=False, server_default=sa.sql.expression.true()
        ),
    )

    # Populate legacy quality metrics table from backup (skip rows without row_count)
    op.execute(
        """
        INSERT INTO data_quality_metrics (
            bundle_name,
            row_count,
            start_date,
            end_date,
            missing_days_count,
            missing_days_list,
            outlier_count,
            ohlcv_violations,
            validation_timestamp,
            validation_passed
        )
        SELECT
            bundle_name,
            row_count,
            start_date,
            end_date,
            COALESCE(missing_days_count, 0),
            missing_days_list,
            COALESCE(outlier_count, 0),
            COALESCE(ohlcv_violations, 0),
            validation_timestamp,
            COALESCE(validation_passed, 1)
        FROM _bundle_quality_backup
        WHERE row_count IS NOT NULL AND validation_timestamp IS NOT NULL
        """
    )

    # Drop backup table
    op.execute("DROP TABLE _bundle_quality_backup")

    # Recreate legacy indexes for quality metrics
    op.create_index(
        "idx_quality_metrics_bundle", "data_quality_metrics", ["bundle_name"], unique=False
    )
    op.create_index(
        "idx_quality_metrics_validation",
        "data_quality_metrics",
        ["validation_timestamp"],
        unique=False,
    )
