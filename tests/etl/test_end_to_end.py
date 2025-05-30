from datetime import datetime, timezone

import polars as pl
from freezegun import freeze_time
from polars.testing import assert_frame_equal

from blueno.etl import (
    add_audit_columns,
    deduplicate,
    get_default_config,
    normalize_column_names,
    read_delta,
    upsert,
)
from blueno.utils import get_max_column_value


@freeze_time("2024-01-01")
def test_end_to_end(tmp_path):
    source_table_path = str(tmp_path / "source_table")
    target_table_path = str(tmp_path / "target_table")

    # Create a source table
    source_df = pl.DataFrame(
        {
            "ID": [1, 2, 3, 1, 2],
            "FirstName": ["Alice", "Bob", "Charlie", "AliceS", "BobB"],
            "batch_id": [1, 1, 1, 2, 2],
        }
    )
    source_df.write_delta(source_table_path)

    # Get the default config
    config = get_default_config()

    # Read the source delta table
    source_df = read_delta(source_table_path)

    # Get the incremental column value
    incremental_column_value = get_max_column_value(target_table_path, "batch_id")

    # Filter the source dataframe to only get the rows with a modified_at greater than the incremental column value
    filtered_df = source_df.filter(pl.col("batch_id") > (incremental_column_value or 0))

    # Deduplicate the source dataframe
    deduped_df = deduplicate(filtered_df, key_columns="ID", deduplication_order_columns="batch_id")

    # Normalize the column names

    strategy = config.normalization_strategy
    normalized_df = normalize_column_names(deduped_df, strategy)

    # Add audit columns
    audit_df = add_audit_columns(normalized_df, config.get_audit_columns())

    # Upsert to a target table
    upsert(
        target_table_path,
        audit_df,
        key_columns=["id"],
        update_exclusion_columns=config.get_static_audit_columns(),
        predicate_exclusion_columns=config.get_dynamic_audit_columns(),
    )

    # Read the target table
    target_df = pl.read_delta(target_table_path)

    # Test that the target table is as expected
    datetime_now = datetime(2024, 1, 1, 0, 0, tzinfo=timezone.utc)

    expected_df = pl.DataFrame(
        {
            "id": [3, 1, 2],
            "first_name": ["Charlie", "AliceS", "BobB"],
            "batch_id": [1, 2, 2],
            "__created_at": [datetime_now, datetime_now, datetime_now],
            "__modified_at": [datetime_now, datetime_now, datetime_now],
            "__deleted_at": [None, None, None],
            "__valid_from": [datetime_now, datetime_now, datetime_now],
            "__valid_to": [None, None, None],
        },
        schema_overrides={
            "__created_at": pl.Datetime(time_zone="UTC"),
            "__modified_at": pl.Datetime(time_zone="UTC"),
            "__deleted_at": pl.Datetime(time_zone="UTC"),
            "__valid_to": pl.Datetime(time_zone="UTC"),
            "__valid_from": pl.Datetime(time_zone="UTC"),
        },
    )

    assert_frame_equal(target_df, expected_df, check_row_order=False)
