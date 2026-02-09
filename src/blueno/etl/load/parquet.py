from typing import List, Optional

import polars as pl

from blueno.auth import get_storage_options
from blueno.types import DataFrameType


def write_parquet(uri: str, df: DataFrameType) -> None:
    """Overwrites the entire parquet file or directory with the provided dataframe.

    Args:
        uri: The file or directory URI to write to.
        df: The dataframe to write

    Example:
        ```python
        from blueno.etl import write_parquet
        import polars as pl

        # Create sample data with dates
        data = pl.DataFrame(
            {"year": [2024, 2024, 2024], "month": [1, 2, 3], "value": [100, 200, 300]}
        )

        # Write data partitioned by year and month
        write_parquet(uri="path/to/parquet", df=data)
        ```
    """
    storage_options = get_storage_options(uri)

    if isinstance(df, pl.LazyFrame):
        df.sink_parquet(path=uri, storage_options=storage_options, engine="streaming", mkdir=True)
    else:
        df.write_parquet(file=uri, storage_options=storage_options, mkdir=True)
