from blueno import Blueprint, DataFrameType
import polars as pl


@Blueprint.register(
    format="dataframe"
)
def stage_customers(raw_customers: DataFrameType) -> DataFrameType:
    
    df = raw_customers.rename(
        {
            "id": "customer_id",
            "name": "customer_name",
        }
    )

    return df


@Blueprint.register(
    format="dataframe",
    schema=pl.Schema(
        {
            "location_id": pl.String,
            "location_name": pl.String,
            "tax_rate": pl.Float64,
            "opened_date": pl.Date,
        }
    ),
)
def stage_locations(raw_stores: DataFrameType) -> DataFrameType:

    df = (
        raw_stores
        .select(
            pl.col("id").alias("location_id"),
            pl.col("name").alias("location_name"),
            pl.col("tax_rate"),
            pl.col("opened_at").str.to_date("%Y-%m-%d %H:%M:%S").alias("opened_date"),
        )
    )

    return df

@Blueprint.register(
    format="dataframe",
)
def stage_order_items(raw_order_items: DataFrameType) -> DataFrameType:

    df = (
        raw_order_items
        .select(
            pl.col("id").alias("order_item_id"),
            pl.col("order_id"),
            pl.col("sku").alias("product_id"),
        )
    )

    return df

def cents_to_dollars(expr: pl.Expr) -> pl.Expr:
    return expr.truediv(100)

@Blueprint.register(
    format="dataframe",
)
def stage_orders(raw_orders: DataFrameType) -> DataFrameType:

    df = (
        raw_orders
        .select(
            # ids
            pl.col("id").alias("order_id"),
            pl.col("store_id").alias("location_id"),
            pl.col("customer").alias("customer_id"),

            # numerics
            pl.col("subtotal").alias("subtotal_cents"),
            pl.col("tax_paid").alias("tax_paid_cents"),
            pl.col("order_total").alias("order_total_cents"),
            cents_to_dollars(pl.col("subtotal")).alias("subtotal"),
            cents_to_dollars(pl.col("tax_paid")).alias("tax_paid"),
            cents_to_dollars(pl.col("order_total")).alias("order_total"),

            # timestamps
            pl.col("ordered_at").str.to_date("%Y-%m-%d %H:%M:%S").alias("ordered_at"),
        )
    )

    return df


@Blueprint.register(
    format="dataframe",
)
def stage_products(raw_products: DataFrameType) -> DataFrameType:

    df = (
        raw_products
        .select(
            # ids
            pl.col("sku").alias("product_id"),

            # text
            pl.col("name").alias("product_name"),
            pl.col("type").alias("product_type"),
            pl.col("description").alias("product_description"),

            # numerics
            cents_to_dollars(pl.col("price")).alias("product_price"),

            # boolean
            (pl.col("type") == "jaffle").alias("is_food_item"),
            (pl.col("type") == "beverage").alias("is_drink_item"),
        )
    )

    return df


@Blueprint.register(
    format="dataframe",
)
def stage_supplies(raw_supplies: DataFrameType) -> DataFrameType:

    df = (
        raw_supplies
        .select(
            # ids
            pl.col("id").alias("supply_id"),
            pl.col("sku").alias("product_id"),

            # text
            pl.col("name").alias("supply_name"),

            # numerics
            cents_to_dollars(pl.col("cost")).alias("supply_cost"),

            # boolean
            pl.col("perishable").alias("is_perishable_supply"),
        )
    )
    return df
