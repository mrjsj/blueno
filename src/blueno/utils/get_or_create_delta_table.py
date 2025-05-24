import polars as pl
import pyarrow as pa
from deltalake import DeltaTable

from blueno.auth import get_storage_options


def get_or_create_delta_table(table_uri: str, schema: pl.Schema | pa.Schema) -> DeltaTable:
    """Retrieves a Delta table or creates a new one if it does not exist.

    Args:
        table_uri: The URI of the Delta table.
        schema: The Polars or PyArrow schema to create the Delta table with.

    Returns:
        The Delta table.
    """
    storage_options = get_storage_options(table_uri)

    if DeltaTable.is_deltatable(table_uri, storage_options=storage_options):
        dt = DeltaTable(table_uri, storage_options=storage_options)
    else:
        if isinstance(schema, pl.Schema):
            arrow_schema = pl.DataFrame(schema=schema).to_arrow().schema
        else:
            arrow_schema = schema

        dt = DeltaTable.create(table_uri, arrow_schema, storage_options=storage_options)

    return dt
