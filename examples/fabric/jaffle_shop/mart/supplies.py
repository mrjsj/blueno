from blueno import Blueprint, DataFrameType
import polars as pl
import polars.selectors as cs


@Blueprint.register(
    table_uri="abfss://<WORKSPACE_ID>@onelake.dfs.fabric.microsoft.com/<LAKEHOUSE_ID>/Tables/mart_supplies",
    format="delta"
)
def mart_supplies(stage_supplies: DataFrameType):
    
    return stage_supplies
