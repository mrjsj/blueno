from blueno import Blueprint, DataFrameType


@Blueprint.register(
    table_uri="abfss://<WORKSPACE_ID>@onelake.dfs.fabric.microsoft.com/<LAKEHOUSE_ID>/Tables/mart_locations",
    format="delta"
)
def mart_locations(stage_locations: DataFrameType):
    
    return stage_locations
