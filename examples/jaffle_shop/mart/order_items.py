from blueno import Blueprint, blueprint, DataFrameType
import polars as pl
import polars.selectors as cs

@Blueprint.register(
    table_uri="lakehouse/mart/order_items",
    format="delta"
)
def mart_order_items(
    stage_order_items: DataFrameType,
    stage_orders: DataFrameType,
    stage_products: DataFrameType,
    stage_supplies: DataFrameType,
) -> DataFrameType:

    order_supplies_summary = (
        stage_supplies
        .group_by("product_id")
        .agg(
            pl.col("supply_cost").sum()
        )
    )
    print(order_supplies_summary)
    joined = (
        stage_order_items
        .join(
            stage_orders,
            on="order_id",
            how="left",
        )
        .join(
            stage_products,
            on="product_id",
            how="left",
        )
        .join(
            order_supplies_summary,
            on="product_id",
            how="left",
        )
        .select(
            *stage_order_items.columns,            
            "product_name",
            "product_price",
            "is_food_item",
            "is_drink_item",
            "supply_cost"
        )
    )
    print(joined)

    return joined
