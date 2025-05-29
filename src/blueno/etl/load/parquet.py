from typing import List, Optional

import polars as pl

from blueno.auth import get_storage_options
from blueno.types import DataFrameType


def write_parquet(uri: str, df: DataFrameType, partition_by: Optional[List[str]] = None) -> None:
    """Overwrites the entire parquet file or directory (if using `partition_by`) with the provided dataframe.

    Args:
        uri: The file or directory URI to write to. This should be a path if using `partition_by`
        df: The dataframe to write
        partition_by: Column(s) to partition by

    Example:
        ```python
        from blueno.etl import write_parquet
        import polars as pl

        # Create sample data with dates
        data = pl.DataFrame(
            {"year": [2024, 2024, 2024], "month": [1, 2, 3], "value": [100, 200, 300]}
        )

        # Write data partitioned by year and month
        write_parquet(uri="path/to/parquet", df=data, partition_by=["year", "month"])
        ```
    """
    storage_options = get_storage_options(uri)

    if isinstance(df, pl.LazyFrame):
        df = df.collect()

    df.write_parquet(file=uri, partition_by=partition_by, storage_options=storage_options)
