from blueno import Blueprint, blueprint, DataFrameType
import polars as pl


@blueprint(
    table_uri="lakehouse/mart/products",
    format="delta"
)
def mart_products(stage_products: DataFrameType):
    
    return stage_products
