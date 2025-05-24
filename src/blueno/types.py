from typing import TypeAlias, Union

import polars as pl

DataFrameType: TypeAlias = Union[pl.DataFrame, pl.LazyFrame]
