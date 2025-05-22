from typing import Any

from blueno.fabric.fabric import paginated_get_request
from blueno.core.workspace import get_workspace


def get_workspace_sql_endpoints(
    workspace_id: str | None = None, workspace_name: str | None = None
) -> list[dict[str, Any]]:
    """
    Retrieves SQL endpoints for a specified workspace by either `workspace_id` or `workspace_name`.

    This function fetches a list of SQL endpoints from a specified workspace

    Args:
        workspace_id (str | None): The ID of the workspace to retrieve SQL endpoints from.
        workspace_name (str | None): The name of the workspace to retrieve SQL endpoints from.

    Returns:
        A list of dictionaries containing SQL endpoint data for the specified workspace.

    Example:
        By `workspace_id`:
        ```python
        from blueno.core import get_workspace_sql_endpoints

        sql_endpoints = get_workspace_sql_endpoints("12345678-1234-1234-1234-123456789012")
        ```

        By `workspace_name`:
        ```python
        from blueno.core import get_workspace_sql_endpoints
        sql_endpoints = get_workspace_sql_endpoints(workspace_name="My Workspace")
        ```
    """
    data_key = "value"

    if workspace_id is None and workspace_name is None:
        raise ValueError("Either `workspace_id` or `workspace_name` must be provided")

    if workspace_id is not None:
        endpoint = f"workspaces/{workspace_id}/sqlEndpoints"
        return paginated_get_request(endpoint, data_key)

    workspace_resp = get_workspace(workspace_name=workspace_name) #.get("id") # ty: ignore[]
    if isinstance(workspace_resp, dict):
        workspace_id = workspace_resp.get("id")
    endpoint = f"workspaces/{workspace_id}/sqlEndpoints"
    return paginated_get_request(endpoint, data_key)

