from blueno import Blueprint, DataFrameType


@Blueprint.register(
    table_uri="jaffle_shop/mart/locations",
    format="delta"
)
def mart_locations(stage_locations: DataFrameType):
    
    return stage_locations
