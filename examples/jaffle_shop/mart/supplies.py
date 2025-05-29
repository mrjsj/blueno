from blueno import Blueprint, blueprint, DataFrameType
import polars as pl
import polars.selectors as cs


@blueprint(
    table_uri="lakehouse/mart/supplies",
    format="delta"
)
def mart_supplies(stage_supplies: DataFrameType):
    
    return stage_supplies
