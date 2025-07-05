from blueno import Blueprint, DataFrameType
import polars as pl


@Blueprint.register(
    table_uri="jaffle_shop/mart/products",
    format="delta"
)
def mart_products(stage_products: DataFrameType):
    
    return stage_products
