from blueno import Blueprint, blueprint, DataFrameType


@blueprint(
    table_uri="lakehouse/mart/locations",
    format="delta"
)
def mart_locations(stage_locations: DataFrameType):
    
    return stage_locations
