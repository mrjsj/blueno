import polars as pl
from polars.testing import assert_frame_equal

from blueno.etl import (
    read_delta,
    upsert,
)


def test_upsert(tmp_path):
    target_table_path = str(tmp_path / "target_table")

    source_df = pl.DataFrame(
        {
            "ID": [1, 2, 3],
            "FirstName": ["Alice", "Bob", "Charlie"],
        }
    )
    upsert(target_table_path, source_df, ["ID"])

    expected_df = read_delta(target_table_path).collect()

    assert_frame_equal(source_df, expected_df, check_row_order=False)

    source_df = pl.DataFrame(
        {
            "ID": [3, 4],
            "FirstName": ["Charlie", "Aimee"],
            "LastName": ["Anderson", "Jensen"],
        }
    )

    upsert(target_table_path, source_df, ["ID"])

    actual_df = read_delta(target_table_path).collect()

    expected_df = pl.DataFrame(
        {
            "ID": [1, 2, 3, 4],
            "FirstName": ["Alice", "Bob", "Charlie", "Aimee"],
            "LastName": [None, None, "Anderson", "Jensen"],
        }
    )

    assert_frame_equal(actual_df, expected_df, check_row_order=False)
