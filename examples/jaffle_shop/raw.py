from blueno import Blueprint, blueprint, DataFrameType
import polars as pl


base_url = "https://dbt-tutorial-public.s3.us-west-2.amazonaws.com/long_term_dataset"

lakehouse_base_url = "lakehouse/raw/"


@blueprint(
    table_uri=lakehouse_base_url + "customers",
    format="delta",
)
def raw_customers() -> DataFrameType:
    return pl.scan_csv(base_url + "/raw_customers.csv")


@blueprint(
    table_uri=lakehouse_base_url + "items",
    format="delta",
)
def raw_order_items() -> DataFrameType:
    return pl.scan_csv(base_url + "/raw_order_items.csv")


@blueprint(
    table_uri=lakehouse_base_url + "orders",
    format="delta",
)
def raw_orders() -> DataFrameType:
    return pl.scan_csv(base_url + "/raw_orders.csv")


@blueprint(
    table_uri=lakehouse_base_url + "products",
    format="delta",
)
def raw_products() -> DataFrameType:
    return pl.scan_csv(base_url + "/raw_products.csv")


@blueprint(
    table_uri=lakehouse_base_url + "stores",
    format="delta",
)
def raw_stores() -> DataFrameType:
    return pl.scan_csv(base_url + "/raw_stores.csv")


@blueprint(
    table_uri=lakehouse_base_url + "supplies",
    format="delta",
)
def raw_supplies() -> DataFrameType:
    return pl.scan_csv(base_url + "/raw_supplies.csv")
