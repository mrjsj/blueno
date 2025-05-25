import random
import tempfile
import time
import shutil
import polars as pl

from blueno import Blueprint, DataFrameType, blueprint, task

RAND_SIZE = 0.5


tmp_dir = f"{tempfile.gettempdir()}/blueno/blueno-test"

shutil.rmtree(tmp_dir, True)

@task
def notify_begin() -> None:
    import logging

    # _ = 1/0
    logging.warning("I notified u!")


@task
def notify_end(gold_sales_metrics) -> None:
    import logging

    logging.warning("I notified u!")


@blueprint(table_uri=f"{tmp_dir}/bronze/products")
def bronze_products(notify_begin) -> DataFrameType:
    df = pl.DataFrame(
        {
            "product_id": [1, 2, 3],
            "product_name": ["ball", "bat", "tent"],
            "price": [4.99, 9.99, 29.99],
        }
    )

    time.sleep(random.random() * RAND_SIZE)

    return df


@blueprint(format="dataframe")
def landing_customers() -> DataFrameType:
    df = pl.DataFrame(
        {
            "customer_id": ["CUST01", "CUST02", "CUST03", "CUST03"],
            "customer_name": ["Mary", "Bob", "Alice", "Alice"],
        }
    )
    time.sleep(random.random() * RAND_SIZE)

    return df


@blueprint(table_uri=f"{tmp_dir}/bronze/customers")
def bronze_customers(landing_customers) -> DataFrameType:
    df = landing_customers
    time.sleep(random.random() * RAND_SIZE)

    return df


@blueprint(table_uri=f"{tmp_dir}/bronze/transactions")
def bronze_transactions() -> DataFrameType:
    df = pl.DataFrame(
        {
            "customer_id": ["CUST01", "CUST02", "CUST03", "CUST01"],
            "product_id": [3, 2, 1, 1],
            "transaction_date": ["2025-01-01", "2025-01-02", "2025-01-03", "2025-01-04"],
            "quantity": [2, 1, 1, 0],
        }
    )
    time.sleep(random.random() * RAND_SIZE)

    return df


@blueprint(
    table_uri=f"{tmp_dir}/silver/products",
    primary_keys=["product_id"],
)
def silver_products(self: Blueprint, bronze_products: DataFrameType) -> DataFrameType:
    df = bronze_products.unique(subset=self.primary_keys)
    time.sleep(random.random() * RAND_SIZE)

    return df


@blueprint(
    table_uri=f"{tmp_dir}/silver/customers",
    primary_keys=["customer_id"],
)
def silver_customers(self: Blueprint, bronze_customers: DataFrameType) -> DataFrameType:
    df = bronze_customers.unique(subset=self.primary_keys)
    time.sleep(random.random() * RAND_SIZE)

    return df


@blueprint(
    table_uri=f"{tmp_dir}/silver/transactions",
    primary_keys=["product_id"],
)
def silver_transactions(bronze_transactions: DataFrameType) -> DataFrameType:
    df = bronze_transactions.filter(pl.col("quantity") > 0)
    time.sleep(random.random() * RAND_SIZE)

    return df


@blueprint(
    table_uri=f"{tmp_dir}/gold/sales_metrics",
    write_mode="incremental",
    incremental_column="transaction_date",
)
def gold_sales_metrics(
    silver_transactions: DataFrameType,
    silver_customers: DataFrameType,
    silver_products: DataFrameType,
) -> DataFrameType:
    df = (
        silver_transactions.join(silver_customers, on="customer_id", how="left")
        .join(silver_products, on="product_id", how="left")
        .group_by(
            "transaction_date",
            "customer_id",
            "product_id",
        )
        .agg(
            pl.sum("quantity").alias("total_quantity"),
            (pl.col("quantity") * pl.col("price")).sum().alias("total_sales"),
        )
    )
    time.sleep(random.random() * RAND_SIZE)

    return df
