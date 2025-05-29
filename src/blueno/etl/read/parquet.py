import polars as pl

from blueno.auth import get_storage_options
from blueno.types import DataFrameType


def read_parquet(table_uri: str, eager: bool = False) -> DataFrameType:
    """Reads a Parquet file from the specified abfss URI. Automatically handles the authentication with OneLake.

    Args:
        table_uri: The abfss URI of the Parquet file to read. Supports globbing.
        eager: If True, reads the file eagerly; otherwise, returns a lazy frame. Defaults to False.

    Returns:
        The data from the Parquet file.

    Example:
        Reading a single file
        ```{.python notest}
        from blueno.etl import read_parquet

        workspace_id = "12345678-1234-1234-1234-123456789012"
        lakehouse_id = "beefbeef-beef-beef-beef-beefbeefbeef"

        file_path = "my-parquet-file.parquet"
        folder_uri = f"abfss://{workspace_id}@onelake.dfs.fabric.microsoft.com/{lakehouse_id}/Files/"

        df = read_parquet(folder_uri + file_path, eager=True)
        ```

        Reading all Parquet files in a folder
        ```{.python notest}
        from blueno.etl import read_parquet

        workspace_id = "12345678-1234-1234-1234-123456789012"
        lakehouse_id = "beefbeef-beef-beef-beef-beefbeefbeef"

        folder_uri = f"abfss://{workspace_id}@onelake.dfs.fabric.microsoft.com/{lakehouse_id}/Files/"
        glob_df = read_parquet(folder_uri + "**/*.parquet", eager=True)
        ```
    """
    storage_options = get_storage_options(table_uri)

    if eager:
        return pl.read_parquet(
            source=table_uri, hive_partitioning=True, storage_options=storage_options
        )

    return pl.scan_parquet(
        source=table_uri, hive_partitioning=True, storage_options=storage_options
    )
