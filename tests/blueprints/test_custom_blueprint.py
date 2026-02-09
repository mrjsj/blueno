from dataclasses import dataclass
from datetime import datetime
from typing import Callable, Dict, List, Optional

import polars as pl
from deltalake import write_deltalake

from blueno import Blueprint, job_registry


def test_custom_blueprint():
    @dataclass(kw_only=True)
    class CustomBlueprint(Blueprint):
        date_partition_column: Optional[str]

        @property
        def _extend_input_validations(self) -> List[tuple[bool, str]]:
            """Additional input validations."""
            return [
                (
                    "add_time_partitions" in self._post_transforms
                    and not isinstance(self.date_partition_column, str),
                    "date_partition_column must be provided, when add_time_partitions post_transformation is set",
                )
            ]

        def _add_date_partition(self) -> pl.DataFrame:
            self._dataframe = self._dataframe.with_columns(
                pl.col(self.date_partition_column).dt.date().alias("date"),
            )

        @property
        def _extend_post_transforms(self) -> Dict[str, Callable]:
            return {"add_date_partition": self._add_date_partition}

        def _write_mode_overwrite_partition(self) -> None:
            partitions = (
                self._dataframe.select("date").unique().to_dict(as_series=False).get("date", [])
            )

            partitions_str = [partition.strftime("%Y-%m-%d") for partition in partitions]

            partition_predicate = (
                f"""date in ('{"','".join(partitions_str)}')""" if partitions_str else None
            )

            write_deltalake(
                table_or_uri=self.table_uri,
                data=self._dataframe,
                mode="overwrite",
                predicate=partition_predicate,
            )

        @property
        def _extend_write_modes(self) -> Dict[str, Callable]:
            """Additional or override write methods."""
            return {"overwrite_partition": self._write_mode_overwrite_partition}

    # Create an instance of the custom blueprint
    @CustomBlueprint.register(
        table_uri="/tmp/test_delta",
        date_partition_column="ts",
        post_transforms=["add_date_partition"],
        write_mode="overwrite_partition",
        format="delta",
    )
    def my_blueprint_func() -> pl.DataFrame:
        df = pl.DataFrame(
            {
                "a": [
                    1,
                    2,
                    3
                ],
                "ts": [
                    datetime(2023, 10, 1),
                    datetime(2023, 10, 2),
                    datetime(2023, 10, 3),
                ],
            }
        )
        return df

    bp = job_registry.jobs.get("my_blueprint_func")

    assert isinstance(bp, CustomBlueprint)
    assert bp.table_uri == "/tmp/test_delta"
    assert bp.date_partition_column == "ts"
    assert "add_date_partition" in bp._post_transforms

    bp.run()
