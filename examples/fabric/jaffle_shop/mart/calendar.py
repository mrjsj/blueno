from blueno import Blueprint, DataFrameType
import polars as pl
from datetime import date


@Blueprint.register(
    table_uri="abfss://<WORKSPACE_ID>@onelake.dfs.fabric.microsoft.com/<LAKEHOUSE_ID>/Tables/mart_calendar",
    format="delta"
)
def mart_calendar():
    # Define start and end dates
    start_date = date(2015, 1, 1)
    end_date = date(2030, 12, 31)

    dates = pl.date_range(
        start=start_date,
        end=end_date,
        interval="1d",
        eager=True
    )

    df = (
        pl.LazyFrame(
            {
                "date": dates,
            }
        ).with_columns(
            pl.col("date").dt.year().alias("year"),
            pl.col("date").dt.month().alias("month"),
            pl.col("date").dt.day().alias("day"),
            pl.col("date").dt.weekday().alias("weekday"),
        )
    )
    
    return df
