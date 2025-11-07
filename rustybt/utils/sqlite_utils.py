# Copyright 2016 Quantopian, Inc.
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
"""SQLite database utilities and connection management.

This module provides utilities for working with SQLite databases, including
connection management, query optimization, and handling SQLite limitations
such as maximum variable counts.
"""

import os
import sqlite3
from functools import partial

import sqlalchemy as sa
from sqlalchemy.pool import NullPool

from .input_validation import coerce_string

SQLITE_MAX_VARIABLE_NUMBER = 998


def group_into_chunks(items, chunk_size=SQLITE_MAX_VARIABLE_NUMBER):
    """Split items into chunks to work around SQLite variable limits.

    SQLite has a maximum number of variables (typically 999) that can be
    used in a single query. This function splits large lists into smaller
    chunks that fit within this limit.

    Args:
        items: An iterable of items to split into chunks.
        chunk_size: Maximum size of each chunk. Defaults to SQLITE_MAX_VARIABLE_NUMBER.

    Returns:
        A list of lists, where each inner list contains at most chunk_size items.
    """
    items = list(items)
    return [items[x : x + chunk_size] for x in range(0, len(items), chunk_size)]


def verify_sqlite_path_exists(path):
    """Verify that a SQLite database file exists.

    Args:
        path: Path to the SQLite database file.

    Raises:
        ValueError: If the path doesn't exist (unless it's ":memory:").
    """
    if path != ":memory:" and not os.path.exists(path):
        raise ValueError(f"SQLite file {path!r} doesn't exist.")


def check_and_create_connection(path, require_exists):
    """Create a SQLite connection, optionally verifying the file exists.

    Args:
        path: Path to the SQLite database file.
        require_exists: If True, verify the file exists before connecting.

    Returns:
        A sqlite3.Connection object.

    Raises:
        ValueError: If require_exists is True and the path doesn't exist.
    """
    if require_exists:
        verify_sqlite_path_exists(path)
    return sqlite3.connect(path)


def check_and_create_engine(path, require_exists):
    """Create a SQLAlchemy engine, optionally verifying the file exists.

    Args:
        path: Path to the SQLite database file.
        require_exists: If True, verify the file exists before creating the engine.

    Returns:
        A SQLAlchemy Engine object configured for SQLite.

    Raises:
        ValueError: If require_exists is True and the path doesn't exist.
    """
    if require_exists:
        verify_sqlite_path_exists(path)
    return sa.create_engine("sqlite:///" + path, poolclass=NullPool)


def coerce_string_to_conn(require_exists):
    """Create a coercion function for string-to-connection conversion.

    Args:
        require_exists: If True, the returned function will verify file existence.

    Returns:
        A function that coerces strings to SQLite connections.
    """
    return coerce_string(partial(check_and_create_connection, require_exists=require_exists))


def coerce_string_to_eng(require_exists):
    """Create a coercion function for string-to-engine conversion.

    Args:
        require_exists: If True, the returned function will verify file existence.

    Returns:
        A function that coerces strings to SQLAlchemy engines.
    """
    return coerce_string(partial(check_and_create_engine, require_exists=require_exists))
