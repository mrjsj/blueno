from typing import TypeAlias, Union

import polars as pl

try:
    import duckdb

    DataFrameType: TypeAlias = Union[pl.DataFrame, pl.LazyFrame, duckdb.DuckDBPyRelation]
except ImportError:
    DataFrameType: TypeAlias = Union[pl.DataFrame, pl.LazyFrame]
