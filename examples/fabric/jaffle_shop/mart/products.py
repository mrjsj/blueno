from blueno import Blueprint, DataFrameType
import polars as pl


@Blueprint.register(
    table_uri="abfss://<WORKSPACE_ID>@onelake.dfs.fabric.microsoft.com/<LAKEHOUSE_ID>/Tables/mart_products",
    format="delta"
)
def mart_products(stage_products: DataFrameType):
    
    return stage_products
