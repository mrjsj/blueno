from blueno import Blueprint, DataFrameType
import polars as pl


@Blueprint.register(
    table_uri="lakehouse/mart/orders",
    format="delta"
)
def mart_orders(
    mart_order_items: DataFrameType,
    stage_orders: DataFrameType,
) -> DataFrameType:

    order_items_summary = (
        mart_order_items
        .group_by("order_id")
        .agg(
            pl.col("supply_cost").sum().alias("order_cost"),
            pl.col("product_price").sum().alias("order_items_subtotal"),
            pl.col("order_item_id").count().alias("count_order_items"),
            pl.col("is_food_item").sum().alias("count_food_items"),
            pl.col("is_drink_item").sum().alias("count_drink_items"),
        )
    )

    compute_booleans = (
        stage_orders
        .join(
            order_items_summary,
            on="order_id",
            how="left"
        )
        .select(
            *stage_orders.columns,
            "order_cost",
            "order_items_subtotal",
            "count_food_items",
            "count_drink_items",
            "count_order_items",
            (pl.col("count_food_items") > 0).alias("is_food_order"),
            (pl.col("count_drink_items") > 0).alias("is_drink_order"),
        )
    )
    
    customer_order_count = (
        compute_booleans
        .with_columns(
            pl.col("customer_id")
                .rank(method="ordinal")
                .over(
                    partition_by="customer_id",
                    order_by="ordered_at",
                )
                .alias("customer_order_number")
        )
    )


    return customer_order_count
