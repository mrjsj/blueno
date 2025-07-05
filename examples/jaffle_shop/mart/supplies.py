from blueno import Blueprint, DataFrameType
import polars as pl
import polars.selectors as cs


@Blueprint.register(
    table_uri="lakehouse/mart/supplies",
    format="delta"
)
def mart_supplies(stage_supplies: DataFrameType):
    
    return stage_supplies
