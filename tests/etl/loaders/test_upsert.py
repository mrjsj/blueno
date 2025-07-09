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
def test_upsert(tmp_path):
    source_table_path = str(tmp_path / "source_table")
    target_table_path = str(tmp_path / "target_table")

    # Create a source table
    source_df = pl.DataFrame(
        {
            "ID": [1, 2, 3],
            "FirstName": ["Alice", "Bob", "Charlie"],
        }
    )
    upsert(target_table_path, source_df, ["ID"])

    source_df = pl.DataFrame(
        {
            "ID": [3, 4],
            "FirstName": ["Charlie", "Aimee"],
            "LastName": ["Anderson", "Jensen"],
        }
    )    

    upsert(target_table_path, source_df, ["ID"])

    df = read_delta(target_table_path).collect()

    print(df)

    # expected_df = pl.DataFrame(
    #     {
    #         "id": [3, 1, 2],
    #         "first_name": ["Charlie", "AliceS", "BobB"],
    #         "batch_id": [1, 2, 2],
    #         "__created_at": [datetime_now, datetime_now, datetime_now],
    #         "__modified_at": [datetime_now, datetime_now, datetime_now],
    #         "__deleted_at": [None, None, None],
    #         "__valid_from": [datetime_now, datetime_now, datetime_now],
    #         "__valid_to": [None, None, None],
    #     },
    #     schema_overrides={
    #         "__created_at": pl.Datetime(time_zone="UTC"),
    #         "__modified_at": pl.Datetime(time_zone="UTC"),
    #         "__deleted_at": pl.Datetime(time_zone="UTC"),
    #         "__valid_to": pl.Datetime(time_zone="UTC"),
    #         "__valid_from": pl.Datetime(time_zone="UTC"),
    #     },
    # )

    #assert_frame_equal(target_df, expected_df, check_row_order=False)