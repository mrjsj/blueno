from blueno import Blueprint, DataFrameType
import polars as pl


@Blueprint.register(
    table_uri="lakehouse/mart/products",
    format="delta"
)
def mart_products(stage_products: DataFrameType):
    
    return stage_products
