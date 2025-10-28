"""Database schema migrations for bundle metadata.

Handles backward-compatible schema updates for existing databases.
"""

import structlog
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import Session

from rustybt.assets.asset_db_schema import ASSET_DB_VERSION

logger = structlog.get_logger(__name__)


def migrate_bundle_metadata_schema(db_path: str) -> None:
    """Apply migrations to bundle_metadata table if needed.

    Checks for missing columns and adds them with appropriate defaults.
    This ensures backward compatibility with existing databases.

    Args:
        db_path: Path to SQLite database file

    Example:
        >>> migrate_bundle_metadata_schema("~/.zipline/data/assets-8.db")
    """
    engine = create_engine(f"sqlite:///{db_path}")
    inspector = inspect(engine)

    # Check if bundle_metadata table exists
    if "bundle_metadata" not in inspector.get_table_names():
        logger.info("bundle_metadata table does not exist yet, skipping migration")
        return

    # Get existing columns
    existing_columns = {col["name"] for col in inspector.get_columns("bundle_metadata")}

    migrations_applied = []

    with Session(engine) as session:
        # Migration 1: Add calendar column if missing
        if "calendar" not in existing_columns:
            logger.info("Adding 'calendar' column to bundle_metadata table")
            session.execute(
                text("ALTER TABLE bundle_metadata ADD COLUMN calendar TEXT DEFAULT NULL")
            )
            session.commit()
            migrations_applied.append("calendar")
            logger.info("Successfully added 'calendar' column")

    if migrations_applied:
        logger.info(
            "bundle_metadata_migrations_complete",
            db_path=db_path,
            migrations=migrations_applied,
        )
    else:
        logger.debug("bundle_metadata_schema_up_to_date", db_path=db_path)


def auto_migrate_on_load() -> None:
    """Automatically run migrations when BundleMetadata is first accessed.

    Finds the database path and applies any needed schema updates.
    Safe to call multiple times - only applies missing migrations.
    """
    from pathlib import Path

    from rustybt.utils.paths import zipline_root

    db_path = Path(zipline_root()) / f"assets-{ASSET_DB_VERSION}.db"

    if db_path.exists():
        migrate_bundle_metadata_schema(str(db_path))
    else:
        logger.debug(
            "database_does_not_exist_yet",
            db_path=str(db_path),
            message="Will be created with latest schema",
        )
