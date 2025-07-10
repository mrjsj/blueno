import logging
from typing import Dict, List, Optional, Union

import polars as pl
from deltalake import DeltaTable, write_deltalake

from blueno.exceptions import GenericBluenoError
from blueno.types import DataFrameType
from blueno.utils import (
    build_merge_predicate,
    build_when_matched_update_columns,
    build_when_matched_update_predicate,
    get_max_column_value,
    get_or_create_delta_table,
    quote_identifier,
)

logger = logging.getLogger(__name__)


def upsert(
    table_or_uri: Union[str, DeltaTable],
    df: DataFrameType,
    key_columns: List[str],
    update_exclusion_columns: Optional[List[str]] = None,
    predicate_exclusion_columns: Optional[List[str]] = None,
) -> Dict[str, str]:
    """Updates existing records and inserts new records into a Delta table.

    Args:
        table_or_uri: Path to the Delta table or a DeltaTable instance
        df: Data to upsert as a Polars DataFrame or LazyFrame
        key_columns: Column(s) that uniquely identify each record
        update_exclusion_columns: Columns that should never be updated (e.g., created_at)
        predicate_exclusion_columns: Columns to ignore when checking for changes

    Returns:
        Dict containing merge operation statistics

    Example:
        ```python
        from blueno.etl import upsert
        import polars as pl

        # Create sample data
        data = pl.DataFrame({"id": [1, 2], "name": ["Alice", "Bob"]})

        # Upsert data using 'id' as the key column
        upsert("path/to/upsert_delta_table", data, key_columns=["id"])
        ```
    """
    if update_exclusion_columns is None:
        update_exclusion_columns = []

    if predicate_exclusion_columns is None:
        predicate_exclusion_columns = []

    if isinstance(table_or_uri, str):
        schema = df.schema if isinstance(df, pl.DataFrame) else df.collect_schema()
        dt = get_or_create_delta_table(table_or_uri, schema)
    else:
        dt = table_or_uri

    target_columns = [field.name for field in dt.schema().fields]

    if isinstance(df, pl.LazyFrame):
        df = df.collect()

    merge_predicate = build_merge_predicate(key_columns)

    predicate_update_columns = [
        column
        for column in df.columns
        if (column not in key_columns + predicate_exclusion_columns + update_exclusion_columns)
        and column in target_columns
    ]

    new_columns = [column for column in df.columns if column not in target_columns]

    when_matched_update_predicates = build_when_matched_update_predicate(
        predicate_update_columns, new_columns
    )

    update_columns = [
        column for column in df.columns if column not in key_columns + update_exclusion_columns
    ]
    when_matched_update_columns = build_when_matched_update_columns(update_columns)

    # TODO: delta-rs doesn't handle duplicates before merging atm, so this check ensure we don't merge with duplicates in the source_df
    # https://github.com/delta-io/delta-rs/issues/2407
    unique_rows = df.select(key_columns).unique().to_arrow().num_rows

    df = df.to_arrow()

    duplicates = df.num_rows - unique_rows
    if duplicates != 0:
        msg = (
            "%s duplicates in source dataframe detected - duplicates are not allowed when upserting"
        )
        logger.error(
            "%s duplicates in source dataframe detected - duplicates are not allowed when upserting",
            duplicates,
        )
        raise GenericBluenoError(msg % duplicates)

    table_merger = (
        dt.merge(
            df,
            source_alias="source",
            target_alias="target",
            merge_schema=True,
            predicate=merge_predicate,
        )
        .when_matched_update(
            predicate=when_matched_update_predicates, updates=when_matched_update_columns
        )
        .when_not_matched_insert_all()
    )

    return table_merger.execute()


def overwrite(table_or_uri: str | DeltaTable, df: DataFrameType) -> None:
    """Replaces all data in a Delta table with new data.

    Args:
        table_or_uri: Path to the Delta table or a DeltaTable instance
        df: Data to write as a Polars DataFrame or LazyFrame

    Example:
        ```python
        from blueno.etl import overwrite
        import polars as pl

        # Create sample data
        data = pl.DataFrame({"id": [1, 2], "name": ["Alice", "Bob"]})

        # Replace entire table with new data
        overwrite("path/to/overwrite_delta_table", data)
        ```
    """
    if isinstance(table_or_uri, str):
        dt = get_or_create_delta_table(table_or_uri, df.schema)
    else:
        dt = table_or_uri

    if isinstance(df, pl.LazyFrame):
        df = df.collect()

    df = df.to_arrow()

    write_deltalake(
        table_or_uri=dt,
        data=df,
        mode="overwrite",
    )


def replace_range(
    table_or_uri: str | DeltaTable,
    df: DataFrameType,
    range_column: str,
) -> None:
    """Replaces data within a specific range in the Delta table.

    Args:
        table_or_uri: Path to the Delta table or a DeltaTable instance
        df: Data to write as a Polars DataFrame or LazyFrame
        range_column: Column used to define the range. Records in the table with
            values between the min and max of this column in df will be replaced

    Example:
        ```python
        from blueno.etl import replace_range
        import polars as pl

        # Create sample data for dates 2024-01-01 to 2024-01-31
        data = pl.DataFrame({"date": ["2024-01-01", "2024-01-31"], "value": [100, 200]})

        # Replace all records between Jan 1-31
        replace_range("path/to/replace_range_delta_table", data, range_column="date")
        ```
    """
    if isinstance(table_or_uri, str):
        dt = get_or_create_delta_table(table_or_uri, df.schema)
    else:
        dt = table_or_uri

    if isinstance(df, pl.LazyFrame):
        min_value, max_value = (
            df.select(
                pl.col(range_column).min().alias("min"),
                pl.col(range_column).max().alias("max"),
            )
            .collect()
            .row(0)
        )

    else:
        min_value, max_value = df.select(
            pl.col(range_column).min().alias("min"),
            pl.col(range_column).max().alias("max"),
        ).row(0)

    predicate = f"{quote_identifier(range_column)} >= '{min_value}' AND {quote_identifier(range_column)} <= '{max_value}'"

    logger.debug("overwriting with predicate: %s" % predicate)

    if isinstance(df, pl.LazyFrame):
        df = df.collect()

    df = df.to_arrow()

    write_deltalake(
        table_or_uri=dt,
        data=df,
        mode="overwrite",
        predicate=predicate,
    )


def append(table_or_uri: str | DeltaTable, df: DataFrameType) -> None:
    """Appends the provided dataframe to the Delta table.

    Args:
        table_or_uri: The URI of the target Delta table
        df: The dataframe to append to the Delta table

    Example:
        ```python
        from blueno.etl import append
        import polars as pl

        # Create sample data
        data = pl.DataFrame({"id": [1, 2], "name": ["Alice", "Bob"]})

        # Append data to table
        append("path/to/append_delta_table", data)
        ```
    """
    if isinstance(table_or_uri, str):
        dt = get_or_create_delta_table(table_or_uri, df.schema)
    else:
        dt = table_or_uri

    if isinstance(df, pl.LazyFrame):
        df = df.collect()

    df = df.to_arrow()

    write_deltalake(
        table_or_uri=dt,
        data=df,
        mode="append",
    )


def incremental(table_or_uri: str | DeltaTable, df: DataFrameType, incremental_column: str) -> None:
    """Appends only new records based on an incremental column value.

    Args:
        table_or_uri: Path to the Delta table or a DeltaTable instance
        df: Data to append as a Polars DataFrame or LazyFrame
        incremental_column: Column used to identify new records. Only records where
            this column's value is greater than the maximum value in the existing
            table will be appended

    Example:
        ```python
        from blueno.etl import incremental
        import polars as pl

        # Create sample data
        data = pl.DataFrame({"timestamp": ["2024-05-24T10:00:00"], "value": [100]})

        # Append only records newer than existing data
        incremental("path/to/incremental_delta_table", data, incremental_column="timestamp")
        ```
    """
    schema = df.schema if isinstance(df, pl.DataFrame) else df.collect_schema()

    if isinstance(table_or_uri, str):
        dt = get_or_create_delta_table(table_or_uri, schema)
    else:
        dt = table_or_uri

    max_value = get_max_column_value(table_or_uri, incremental_column)

    if max_value is not None:
        df = df.filter(pl.col(incremental_column) > max_value)

    if isinstance(df, pl.LazyFrame):
        df = df.collect()

    df = df.to_arrow()

    write_deltalake(
        table_or_uri=dt,
        data=df,
        mode="append",
    )


# def update_outdated_scd2_dimension_keys(
#         table_or_uri: str | DeltaTable,
#         dimension_table_or_uri: str | DeltaTable,
#         foreign_key_column: str,
#         as_of_column: str,
#         valid_from_column: str,
#         modified_time_column: str,
# ):
#     """
#     NOT IMPLEMENTED
#     Updated foreign keys in a fact table if its corresponding dimension key has been updated.
#     This can happen for late arriving dimensions

#     Args:
#         table_or_uri: Of the target fact table
#         dimension_table_or_uri of the dimension
#         foreign_key_column: the name of the key between fact and dim
#         as_of_column: the name in the fact table used for the scd2 key lookup (e.g. transaction date)
#         valid_from_column: the name of the valid from col in the dim
#         valid_to_column: the name of the valid to col in the dim
#         modified_time_column: the name of the col which tracks when a record was last modified. typically the name across all tables as an audit col


#     """

#     raise NotImplementedError()

#     # Pseudo code.
#     # Below code is not complete, because we can't just update one foreign key because the update to "modified time" would break any try to update another foreign key
#     # Two possible solutions
#     #  - Just do a full scan of fact table and not filter on modified time col, however this could be inefficient
#     #  - Check all dimensions one by one before writing back to target table. SOmewhat more complex implementation wise
#     #    However should be more efficient

#     # Find if any keys in the fact tables has been modified
#     # dim_df = pl.LazyFrame(dimension_table_or_uri).select(
#     #     foreign_key_column,
#     #     pl.col(modified_time_column).name.suffix("__dim")
#     # )
#     # # Foreign keys which has been updated
#     # foreign_keys = (
#     #     pl.LazyFrame(table_or_uri)
#     #     .select(
#     #         foreign_key_column,
#     #         pl.col(modified_time_column).name.suffix("__fact")
#     #     )
#     #     .unique()
#     #     .join(
#     #         other=dim_df,
#     #         on=foreign_key_column
#     #     )
#     #     .filter(
#     #         pl.col(f"{modified_time_column}__dim" > f"{modified_time_column}__fact")
#     #     )
#     #     .select(foreign_key_column)
#     # )

#     # Filter fact df on foreign keys which has been updated
#     #fact_df = (
#     #    pl.LazyFrame(table_or_uri)
#     #    .filter(pl.col(foreign_key_column).is_in(foreign_keys))
#     #)

#     # Recheck if foreign keys must be updated
#     #fact_df = (
#     #    fact_df.join(dim).filter(as_of_col between dim valid from and dim valid to)
#     #     .filter(old_foreign_key != new_foreign_key)
#     #)

#     # merge result backinto fact table

#     #dt.merge(
#     #    predicate = "target.foreign_key = source.old_foreign_key AND target.as_of_col = source.as_of_col"
#     #).update(
#     #    updates = {
#     #        "target.foreign_key": "source.new_foreign_key",
#     #        "target.modified_time": "timestamp now"
#     #    }
#     #)
