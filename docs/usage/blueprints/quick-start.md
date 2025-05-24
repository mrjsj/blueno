# Quick start

If you just want to get started, you can download the download an example and run it.

First install the tool

```
pip install blueno
```

Copy the example and save it to a folder, e.g. `blueprints/example.py`

```python
import random
import time

import polars as pl

from blueno import Blueprint, DataFrameType, blueprint

RAND_SIZE = 10


@blueprint(table_uri="lakehouse/bronze/product")
def bronze_product() -> DataFrameType:
    df = pl.DataFrame(
        {
            "product_id": [1, 2, 3],
            "product_name": ["ball", "bat", "tent"],
            "price": [4.99, 9.99, 29.99],
        }
    )

    time.sleep(random.random() * 2)

    return df


@blueprint(table_uri="lakehouse/bronze/transaction")
def bronze_transaction() -> DataFrameType:
    df = pl.DataFrame(
        {
            "product_id": [3, 2, 1, 1],
            "transaction_date": ["2025-01-01", "2025-01-02", "2025-01-03", "2025-01-04"],
            "quantity": [2, 1, 1, 0],
        }
    )
    time.sleep(random.random() * RAND_SIZE)

    return df


@blueprint(
    table_uri="lakehouse/silver/product",
    primary_keys=["product_id"],
)
def silver_product(self: Blueprint, bronze_product: DataFrameType) -> DataFrameType:
    df = bronze_product.unique(subset=self.primary_keys)
    time.sleep(random.random() * RAND_SIZE)

    return df


@blueprint(
    table_uri="lakehouse/silver/transaction",
    primary_keys=["product_id"],
)
def silver_transaction(bronze_transaction: DataFrameType) -> DataFrameType:
    df = bronze_transaction.filter(pl.col("quantity") > 0)
    time.sleep(random.random() * RAND_SIZE)

    return df


@blueprint(
    table_uri="lakehouse/gold/sales_metric",
    write_mode="incremental",
    incremental_column="transaction_date",
)
def gold_sales_metric(
    silver_transaction: DataFrameType,
    silver_product: DataFrameType,
) -> DataFrameType:
    df = (
        silver_transactions
        .join(silver_products, on="product_id", how="left")
        .group_by(
            "transaction_date",
            "product_id",
        )
        .agg(
            pl.sum("quantity").alias("total_quantity"),
            (pl.col("quantity") * pl.col("price")).sum().alias("total_sales"),
        )
    )
    time.sleep(random.random() * RAND_SIZE)

    return df

```

Then run the CLI command:

```sh
blueno run ./blueprints --concurrency 2
```