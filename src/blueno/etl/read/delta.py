import polars as pl

from blueno.auth import get_storage_options
from blueno.types import DataFrameType


def read_delta(table_uri: str, eager: bool = False) -> DataFrameType:
    """Reads a Delta table from the specified abfss URI. Automatically handles the authentication with OneLake.

    Args:
        table_uri: The abfss URI of the Delta table to read.
        eager: If True, reads the table eagerly; otherwise, returns a lazy frame. Defaults to False.

    Returns:
        DataFrameType: The data from the Delta table.

    Example:
        ```{.python notest}
        from blueno.etl import read_delta

        workspace_id = "12345678-1234-1234-1234-123456789012"
        lakehouse_id = "beefbeef-beef-beef-beef-beefbeefbeef"
        table_name = "my-delta-table"
        table_uri = f"abfss://{workspace_id}@onelake.dfs.fabric.microsoft.com/{lakehouse_id}/Tables/{table_name}"

        df = read_delta(table_uri, eager=True)
        lazy_df = read_delta(table_uri, eager=False)
        ```
    """
    storage_options = get_storage_options(table_uri)

    if eager:
        return pl.read_delta(source=table_uri, storage_options=storage_options)

    return pl.scan_delta(source=table_uri, storage_options=storage_options)
