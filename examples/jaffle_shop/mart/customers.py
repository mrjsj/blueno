from blueno import Blueprint, blueprint, DataFrameType
import polars as pl


@Blueprint.register(
    table_uri="lakehouse/mart/customers",
    format="delta"
)
def mart_customers(
    stage_customers: DataFrameType,
    mart_orders: DataFrameType
):
    customer_orders_summary = (
        mart_orders
        .group_by("customer_id")
        .agg(
            pl.col("order_id").n_unique().alias("count_lifetime_orders"),
            pl.col("ordered_at").min().alias("first_ordered_at"),
            pl.col("ordered_at").max().alias("last_ordered_at"),
            pl.col("subtotal").sum().alias("lifetime_spend_pretax"),
            pl.col("tax_paid").sum().alias("lifetime_tax_paid"),
            pl.col("order_total").sum().alias("lifetime_spend"),
        )
    )

    joined = (
        stage_customers
        .join(
            customer_orders_summary,
            on="customer_id",
            how="left"
        )
        .select(
            *stage_customers.columns,
            "count_lifetime_orders",
            "first_ordered_at",
            "last_ordered_at",
            "lifetime_spend_pretax",
            "lifetime_tax_paid",
            "lifetime_spend",
            pl.when(pl.col("count_lifetime_orders") > 1)
                .then(pl.lit("returning"))
                .otherwise(pl.lit("new"))
                .alias("customer_type"),
        )
    )
    return joined
