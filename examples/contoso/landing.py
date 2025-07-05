from blueno import blueprint, DataFrameType, Blueprint
import polars as pl

contoso_source_base_uri = "data_generator/out/"
lakehouse_base_uri = "contoso/landing/"

@Blueprint.register(
    table_uri=lakehouse_base_uri + "currency_exchange",
    format="delta",
    primary_keys=["Date", "FromCurrency", "ToCurrency"],
    write_mode="upsert",
)
def landing_currency_exchange() -> DataFrameType:
    
    file_path = contoso_source_base_uri + "currencyexchange.csv"

    return pl.scan_csv(file_path)

@Blueprint.register(
    table_uri=lakehouse_base_uri + "customer",
    format="delta",
    primary_keys=["CustomerKey"],
    write_mode="upsert",
)
def landing_customer() -> DataFrameType:
    
    file_path = contoso_source_base_uri + "customer.csv"

    return pl.scan_csv(
        file_path,
        schema_overrides={"ZipCode": pl.String}
    )

@Blueprint.register(
    table_uri=lakehouse_base_uri + "date",
    format="delta",
    primary_keys=["DateKey"],
    write_mode="upsert",
)
def landing_date() -> DataFrameType:
    
    file_path = contoso_source_base_uri + "date.csv"

    return pl.scan_csv(file_path)


@Blueprint.register(
    table_uri=lakehouse_base_uri + "orderrows",
    format="delta",
    primary_keys=["OrderKey", "LineNumber"],
    write_mode="upsert",
)
def landing_orderrows() -> DataFrameType:
    
    file_path = contoso_source_base_uri + "orderrows.csv"

    return pl.scan_csv(file_path)


@Blueprint.register(
    table_uri=lakehouse_base_uri + "orders",
    format="delta",
    primary_keys=["OrderKey"],
    write_mode="upsert",
)
def landing_orders() -> DataFrameType:
    
    file_path = contoso_source_base_uri + "orders.csv"

    return pl.scan_csv(file_path)


@Blueprint.register(
    table_uri=lakehouse_base_uri + "product",
    format="delta",
    primary_keys=["ProductKey"],
    write_mode="upsert",    
)
def landing_product() -> DataFrameType:
    
    file_path = contoso_source_base_uri + "product.csv"

    return pl.scan_csv(file_path)


@Blueprint.register(
    table_uri=lakehouse_base_uri + "sales",
    format="delta",
    primary_keys=["OrderKey", "LineNumber"],
    write_mode="scd2_by_column",
    incremental_column="OrderDate",
    valid_from_column="valid_from",
    valid_to_column="valid_to"
)
def landing_sales(self: Blueprint) -> DataFrameType:
    
    file_path = contoso_source_base_uri + "sales.csv"

    df = pl.scan_csv(file_path)

    # df = df.with_columns(
    #     OrderDate = pl.col("OrderDate").str.to_datetime()
    # )

    return df


@Blueprint.register(
    table_uri=lakehouse_base_uri + "store",
    format="delta",
    primary_keys=["StoreKey"],
    write_mode="upsert",
)
def landing_store() -> DataFrameType:
    
    file_path = contoso_source_base_uri + "store.csv"

    return pl.scan_csv(file_path)