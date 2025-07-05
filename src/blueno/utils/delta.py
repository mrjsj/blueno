from datetime import datetime
from typing import Any

import polars as pl
from deltalake import DeltaTable

from blueno.auth import get_storage_options


def get_or_create_delta_table(table_uri: str, schema: pl.Schema) -> DeltaTable:
    """Retrieves a Delta table or creates a new one if it does not exist.

    Args:
        table_uri: The URI of the Delta table.
        schema: The Polars or PyArrow schema to create the Delta table with.

    Returns:
        The Delta table.
    """
    storage_options = get_storage_options(table_uri)

    if DeltaTable.is_deltatable(table_uri, storage_options=storage_options):
        dt = DeltaTable(table_uri, storage_options=storage_options)
    else:
        if isinstance(schema, pl.Schema):
            arrow_schema = pl.DataFrame(schema=schema).to_arrow().schema
        else:
            arrow_schema = schema

        dt = DeltaTable.create(table_uri, arrow_schema, storage_options=storage_options)

    return dt


def get_last_modified_time(table_uri: str) -> datetime:
    """Retrieves the last modified time of a Delta table.

    Args:
        table_uri: A string URI to a Delta table.

    Returns:
        The last modified time of the table, or None if the table does not exist.

    Example:
    ```python notest
    from blueno.utils import get_last_modified_time

    last_modified = get_last_modified_time("path/to/delta_table")
    ```
    """
    storage_options = get_storage_options(table_uri)

    if isinstance(table_uri, str):
        if not DeltaTable.is_deltatable(table_uri, storage_options=storage_options):
            return datetime(1970, 1, 1)  # Return epoch time if table does not exist

    # Tracked operations
    operation = [
        "CREATE OR REPLACE TABLEWRITE",
        "DELETE",
        "UPDATE",
        "MERGE",
        "STREAMING UPDATE",
    ]

    metadata = DeltaTable(table_uri, storage_options=storage_options).history(50)
    timestamp = next(
        commit.get("timestamp") for commit in metadata if commit.get("operation") in operation
    )

    if timestamp is None:
        return datetime(1970, 1, 1)  # Return epoch time if no timestamp found

    return datetime.fromtimestamp(timestamp / 1000)


def get_max_column_value(table_or_uri: str | DeltaTable, column_name: str) -> Any:
    """Retrieves the maximum value of the specified column from a Delta table.

    Args:
        table_or_uri: A string URI to a Delta table or a DeltaTable instance.
        column_name: The name of the column.

    Returns:
        The maximum value of the column, or None if the table does not exist.

    Example:
    ```python notest
    from blueno.utils import get_max_column_value

    max_value = get_max_column_value("path/to/delta_table", "incremental_id")
    ```
    """
    storage_options = get_storage_options(table_or_uri)

    if isinstance(table_or_uri, str):
        if not DeltaTable.is_deltatable(table_or_uri, storage_options=storage_options):
            return None

    return (
        pl.scan_delta(table_or_uri, storage_options=storage_options)
        .select(pl.col(column_name))
        .max()
        .collect()
        .item()
    )


def get_min_column_value(table_or_uri: str | DeltaTable, column_name: str) -> Any:
    """Retrieves the maximum value of the specified column from a Delta table.

    Args:
        table_or_uri: A string URI to a Delta table or a DeltaTable instance.
        column_name: The name of the column.

    Returns:
        The minimum value of the column, or None if the table does not exist.

    Example:
    ```python notest
    from blueno.utils import get_min_column_value

    min_value = get_min_column_value("path/to/delta_table", "incremental_id")
    ```
    """
    storage_options = get_storage_options(table_or_uri)

    if isinstance(table_or_uri, str):
        if not DeltaTable.is_deltatable(table_or_uri, storage_options=storage_options):
            return None

    return (
        pl.scan_delta(table_or_uri, storage_options=storage_options)
        .select(pl.col(column_name))
        .min()
        .collect()
        .item()
    )
