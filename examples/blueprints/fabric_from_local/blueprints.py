import polars as pl

from blueno import Blueprint, DataFrameType, blueprint

from . import config


@blueprint(table_uri=f"{config.storage_base_path}/bronze/products")
def bronze_products() -> DataFrameType:
    df = pl.DataFrame(
        {
            "product_id": [1, 2, 3],
            "product_name": ["ball", "bat", "tent"],
            "price": [4.99, 9.99, 29.99],
        }
    )

    return df


@blueprint(table_uri=f"{config.storage_base_path}/bronze/customers")
def bronze_customers() -> DataFrameType:
    df = pl.DataFrame(
        {
            "customer_id": ["CUST01", "CUST02", "CUST03", "CUST03"],
            "customer_name": ["Mary", "Bob", "Alice", "Alice"],
        }
    )

    return df


@blueprint(table_uri=f"{config.storage_base_path}/bronze/transactions")
def bronze_transactions() -> DataFrameType:
    df = pl.DataFrame(
        {
            "customer_id": ["CUST01", "CUST02", "CUST03", "CUST01"],
            "product_id": [3, 2, 1, 1],
            "transaction_date": ["2025-01-01", "2025-01-02", "2025-01-03", "2025-01-04"],
            "quantity": [2, 1, 1, 0],
        }
    )

    return df


@blueprint(
    table_uri=f"{config.storage_base_path}/silver/products",
    primary_keys=["product_id"],
)
def silver_products(self: Blueprint, bronze_products: DataFrameType) -> DataFrameType:
    df = bronze_products.unique(subset=self.primary_keys)

    return df


@blueprint(
    table_uri=f"{config.storage_base_path}/silver/customers",
    primary_keys=["customer_id"],
)
def silver_customers(self: Blueprint, bronze_customers: DataFrameType) -> DataFrameType:
    df = bronze_customers.unique(subset=self.primary_keys)

    return df


@blueprint(
    table_uri=f"{config.storage_base_path}/silver/transactions",
    primary_keys=["product_id"],
)
def silver_transactions(bronze_transactions: DataFrameType) -> DataFrameType:
    df = bronze_transactions.filter(pl.col("quantity") > 0)

    return df



@blueprint(
    table_uri=f"{config.storage_base_path}/gold/sales_metrics",
    write_mode="incremental",
    incremental_column="transaction_date",
)
def gold_sales_metrics(
    silver_transactions: DataFrameType,
    silver_customers: DataFrameType,
    silver_products: DataFrameType
) -> DataFrameType:
    
    df = (
        silver_transactions
        .join(silver_customers, on="customer_id", how="left")
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

    return df
