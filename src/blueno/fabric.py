import logging
import os
import shlex
import shutil
import subprocess
import sys
import time
from typing import Any, Dict, List, Optional

import requests

from blueno.auth import get_fabric_bearer_token

logger = logging.getLogger(__name__)


def paginated_get_request(endpoint: str, data_key: str) -> list[dict[str, Any]]:
    """Retrieves paginated data from the specified API endpoint.

    This function makes repeated GET requests to the specified endpoint of the
    Fabric REST API, handling pagination automatically. It uses a bearer token
    for authentication and retrieves data from each page, appending the results
    to a list. Pagination continues until no `continuationToken` is returned.

    Args:
        endpoint: The API endpoint to retrieve data from.
        data_key: The key in the response JSON that contains the list of data to be returned.

    Returns:
        A list of dictionaries containing the data from all pages.

    Raises:
        requests.exceptions.RequestException: If the HTTP request fails or returns an error.
    """
    base_url = "https://api.fabric.microsoft.com/v1"
    token = get_fabric_bearer_token()
    headers = {"Authorization": f"Bearer {token}"}

    responses = []
    continuation_token = None
    while True:
        params = {"continuationToken": continuation_token} if continuation_token else {}

        response = requests.get(f"{base_url}/{endpoint}", headers=headers, params=params)
        response.raise_for_status()
        data: dict = response.json()

        responses.extend(data.get(data_key))

        continuation_token = data.get("continuationToken")
        if not continuation_token:
            break

    return responses


def get_item_from_paginated_get_request(
    endpoint: str, data_key: str, item_key: str, item_value: str
) -> dict[str, Any]:
    """Recursively paginates the API endpoint until specified item is found and returns it.

    This function makes repeated GET requests to the specified endpoint of the
    Fabric REST API, handling pagination automatically. It uses a bearer token
    for authentication and retrieves data from each page, appending the results
    to a list. Pagination continues until the specified item is found or no
    `continuationToken` is returned.

    Args:
        endpoint: The API endpoint to retrieve data from.
        data_key: The key in the response JSON that contains the list of data to be returned.
        item_key: The key in the data dictionary that contains the item to be returned.
        item_value: The value of the item to be returned.

    Returns:
        A dictionary containing the item to be returned.

    Raises:
        requests.exceptions.RequestException: If the HTTP request fails or returns an error.
        ValueError: If the item is not found.
    """
    base_url = "https://api.fabric.microsoft.com/v1"
    token = get_fabric_bearer_token()
    headers = {"Authorization": f"Bearer {token}"}

    continuation_token = None
    while True:
        params = {"continuationToken": continuation_token} if continuation_token else {}

        response = requests.get(f"{base_url}/{endpoint}", headers=headers, params=params)
        response.raise_for_status()
        data: dict = response.json()

        for item in data.get(data_key):
            if item.get(item_key) == item_value:
                return item

        continuation_token = data.get("continuationToken")
        if not continuation_token:
            break

    raise ValueError(f"Item with {item_key} {item_value} not found")


def get_request(endpoint: str, content_only: bool = True) -> requests.Response | dict[str, Any]:
    """Retrieves data from a specified API endpoint.

    This function makes a GET request to the specified endpoint of the Azure Fabric API,
    using a bearer token for authentication. It returns the JSON response as a list of
    dictionaries containing the data returned by the API.

    Args:
        endpoint: The API endpoint to send the GET request to.
        content_only: Whether to return the content of the response only.

    Returns:
        A list of dictionaries containing the data returned from the API or the response object.

    Raises:
        requests.exceptions.RequestException: If the HTTP request fails or returns an error.
    """
    base_url = "https://api.fabric.microsoft.com/v1"
    token = get_fabric_bearer_token()
    headers = {"Authorization": f"Bearer {token}"}
    params = {}

    response = requests.get(f"{base_url}/{endpoint}", headers=headers, params=params)

    if content_only:
        if response.status_code >= 400:
            logger.error(
                "request failed with status code %s: %s", response.status_code, response.json()
            )

        response.raise_for_status()
        return response.json()

    return response


def post_request(
    endpoint: str, data: dict[str, str], content_only: bool = True
) -> requests.Response | dict[str, Any]:
    """Sends a POST request to a specified API endpoint.

    This function makes a POST request to the specified endpoint of the Azure Fabric API,
    using a bearer token for authentication. It sends the provided data in JSON format
    and returns either the JSON response or the full response object.

    Args:
        endpoint: The API endpoint to send the POST request to.
        data: The data to be sent in the request body.
        content_only: Whether to return the content of the response only.

    Returns:
        Either the JSON response as a dictionary or the full response object.

    Raises:
        requests.exceptions.RequestException: If the HTTP request fails or returns an error.
    """
    base_url = "https://api.fabric.microsoft.com/v1"
    token = get_fabric_bearer_token()
    headers = {"Authorization": f"Bearer {token}"}

    response = requests.post(f"{base_url}/{endpoint}", headers=headers, json=data)

    if content_only:
        if response.status_code >= 400:
            logger.error(
                "request failed with status code %s: %s", response.status_code, response.json()
            )

        response.raise_for_status()
        return response.json()

    return response


def patch_request(
    endpoint: str, data: dict[str, str], content_only: bool = True
) -> requests.Response | dict[str, Any]:
    """Sends a PATCH request to a specified API endpoint.

    This function makes a PATCH request to the specified endpoint of the Azure Fabric API,
    using a bearer token for authentication. It sends the provided data in JSON format
    and returns either the JSON response or the full response object.

    Args:
        endpoint: The API endpoint to send the PATCH request to.
        data: The data to be sent in the request body.
        content_only: Whether to return the content of the response only.

    Returns:
        Either the JSON response as a dictionary or the full response object.

    Raises:
        requests.exceptions.RequestException: If the HTTP request fails or returns an error.
    """
    base_url = "https://api.fabric.microsoft.com/v1"
    token = get_fabric_bearer_token()
    headers = {"Authorization": f"Bearer {token}"}

    response = requests.patch(f"{base_url}/{endpoint}", headers=headers, json=data)

    if content_only:
        if response.status_code >= 400:
            logger.error(
                "request failed with status code %s: %s", response.status_code, response.json()
            )

        response.raise_for_status()
        return response.json()

    return response


def delete_request(endpoint: str) -> requests.Response:
    """Sends a DELETE request to a specified API endpoint.

    This function makes a DELETE request to the specified endpoint of the Azure Fabric API,
    using a bearer token for authentication.

    Args:
        endpoint: The API endpoint to send the DELETE request to.

    Returns:
        The response object from the DELETE request.

    Raises:
        requests.exceptions.RequestException: If the HTTP request fails or returns an error.
    """
    base_url = "https://api.fabric.microsoft.com/v1"
    token = get_fabric_bearer_token()
    headers = {"Authorization": f"Bearer {token}"}

    response = requests.delete(f"{base_url}/{endpoint}", headers=headers)
    if response.status_code >= 400:
        logger.error(
            "request failed with status code %s: %s", response.status_code, response.json()
        )
    response.raise_for_status()
    return response


# def run_pipeline(
#     workspace_id: str,
#     pipeline_id: str,
#     parameters: dict[str, Any] | None = None,
#     poll_interval: float = 5.0,
#     timeout: float = 5 * 60.0,
# ) -> requests.Response:
#     """
#     Runs a notebook in the specified workspace.

#     Args:
#         workspace_id: The ID of the workspace where the pipeline is located.
#         pipeline_id: The ID of the pipeline to run.
#         parameters: Parameters to pass to the pipeline. Defaults to None.
#         poll_interval: The interval in seconds to poll the pipeline status. Defaults to 5.0.
#         timeout: The maximum time in seconds to wait for the pipeline to complete. Defaults to 300.0.

#     Returns:
#         The response object from the POST request.

#     Raises:
#         requests.exceptions.RequestException: If the HTTP request fails or returns an error.
#     """
#     base_url = "https://api.fabric.microsoft.com/v1"
#     token = get_fabric_bearer_token()
#     headers = {"Authorization": f"Bearer {token}"}

#     data = {
#         "executionData": {
#             "parameters": parameters or {},
#         }
#     }
#     logger.info(
#         f"Running pipeline {pipeline_id} in workspace {workspace_id} with parameters: {parameters}"
#     )

#     response = requests.post(
#         f"{base_url}/workspaces/{workspace_id}/items/{pipeline_id}/jobs/instances?jobType=Pipeline",
#         headers=headers,
#         json=data,
#     )
#     if response.status_code >= 400:
#         logger.error(f"Request failed with status code {response.status_code}: {response.json()}")
#     response.raise_for_status()

#     url = response.headers.get("Location")

#     time_elapsed = 0
#     while True:
#         time.sleep(5)  # Wait for 5 seconds before checking the status
#         response = requests.get(url, headers=headers)

#         if response.status_code >= 400:
#             logger.error(
#                 f"Request failed with status code {response.status_code}: {response.json()}"
#             )
#             break
#         response.raise_for_status()

#         if response.json().get("status") in ("Completed", "Failed"):
#             logger.info(
#                 f"Pipeline {pipeline_id} in workspace {workspace_id} completed successfully."
#             )
#             break

#         time_elapsed += poll_interval
#         if time_elapsed >= timeout:
#             logger.warning(
#                 f"Polling the pipeline status of {pipeline_id} in workspace {workspace_id} exceeded the timeout limit after {timeout} seconds. This does not necessarily mean the pipeline failed."
#             )
#             break

#         # Else we should be InProgress
#         logger.info(
#             f"pipeline {pipeline_id} in workspace {workspace_id} is still running. Status: {response.json().get('status')}"
#         )

#     return response


def run_notebook(
    notebook_id: str,
    workspace_id: str,
    execution_data: Optional[Dict[str, Any]] = None,
    poll_interval: float = 5.0,
    timeout: float = 5 * 60.0,
) -> requests.Response:
    """Runs a notebook in the specified workspace.

    Args:
        notebook_id: The ID of the notebook to run.
        workspace_id: The ID of the workspace where and notebook is located.
        execution_data: Execution data to pass to the notebook. Defaults to None.
        poll_interval: The interval in seconds to poll the pipeline status. Defaults to 5.0.
        timeout: The maximum time in seconds to wait for the pipeline to complete. Defaults to 300.0.

    Returns:
        The response object from the POST request.

    Raises:
        requests.exceptions.RequestException: If the HTTP request fails or returns an error.
    """
    base_url = "https://api.fabric.microsoft.com/v1"
    token = get_fabric_bearer_token()
    headers = {"Authorization": f"Bearer {token}"}

    data = {
        "executionData": execution_data or {},
    }
    logger.info(
        "running notebook %s in workspace %s with parameters: %s",
        notebook_id,
        workspace_id,
        execution_data,
    )

    response = requests.post(
        f"{base_url}/workspaces/{workspace_id}/items/{notebook_id}/jobs/instances?jobType=RunNotebook",
        headers=headers,
        json=data,
    )
    if response.status_code >= 400:
        logger.error(
            "request failed with status code %s: %s", response.status_code, response.json()
        )
    response.raise_for_status()

    url = response.headers.get("Location")

    time_elapsed = 0
    while True:
        time.sleep(5)  # Wait for 5 seconds before checking the status
        response = requests.get(url, headers=headers)

        if response.status_code >= 400:
            logger.error(
                "polling notebook %s in %s failed with status code %s: %s",
                notebook_id,
                workspace_id,
                response.status_code,
                response.json(),
            )
            break
        response.raise_for_status()

        data = response.json()

        if data.get("status") == "Completed":
            logger.info(
                "notebook %s in workspace %s succeeded with output: %s",
                notebook_id,
                workspace_id,
                data,
            )
            break

        if data.get("status") == "Failed":
            logger.error(
                "notebook %s in workspace %s failed with error: %s", notebook_id, workspace_id, data
            )
            break

        time_elapsed += poll_interval
        if time_elapsed >= timeout:
            logger.warning(
                "polling the notebook status of %s in workspace %s exceeded the timeout limit after %s seconds - this does not necessarily mean the pipeline failed.",
                notebook_id,
                workspace_id,
                timeout,
            )
            break

        # Else we should be InProgress
        logger.info(
            "notebook %s in workspace %s is still running with status: %s",
            notebook_id,
            workspace_id,
            response.json().get("status"),
        )

    return response


def upload_folder_contents(
    workspace_name: str, lakehouse_name: str, source_folder: str, destination_folder: str
) -> None:
    """Uploads the contents of a local folder to a specified destination folder in OneLake using AzCopy.

    Based on: https://medium.com/microsoftazure/ingest-data-into-microsoft-onelake-using-azcopy-a6e0e199feee

    Args:
        workspace_name: The workspace name to upload to.
        lakehouse_name: The lakehouse name to upload to.
        source_folder: The path to the local folder to upload.
        destination_folder: The destination folder in OneLake where the contents will be uploaded.

    Raises:
        requests.exceptions.RequestException: If the HTTP request fails or returns an error.
    """
    # Check if AzCopy is installed
    if not shutil.which("azcopy"):
        logger.error(
            "azcopy is not installed - install it from https://learn.microsoft.com/en-us/azure/storage/common/storage-use-azcopy-v10"
        )
        sys.exit(1)

    # Check if the source folder exists
    if not os.path.exists(source_folder):
        logger.error("source folder %s does not exist", source_folder)
        sys.exit(1)

    cmds = [
        "azcopy",
        "copy",
        f"{source_folder}/*",
        f"https://onelake.blob.fabric.microsoft.com/{workspace_name}/{lakehouse_name}/Files/{destination_folder}/",
        # "--overwrite=prompt",
        "--from-to=LocalBlob",
        # "--delete-destination=true",
        "--blob-type=BlockBlob",
        "--follow-symlinks",
        "--check-length=true",
        "--put-md5",
        "--disable-auto-decoding=false",
        "--recursive",
        "--trusted-microsoft-suffixes=onelake.blob.fabric.microsoft.com",
        "--log-level=INFO",
    ]
    logger.info("uploading %s to %s to OneLake", source_folder, destination_folder)

    # Run the AzCopy command
    try:
        cmd = shlex.join(cmds)
        result = subprocess.run(cmd, shell=True, check=True, capture_output=True)
        logger.debug("azcopy copy succeeded with stdout %s", result.stdout.decode())
    except subprocess.CalledProcessError as e:
        logger.error(
            "azcopy copy failed with error:\n%s\n%s}", e.stderr.decode(), e.stdout.decode()
        )
        sys.exit(1)


def run_multiple(
    path: str,
    notebook_name: str,
    select: Optional[List[str]] = None,
    timeout_in_seconds: int = 60 * 60 * 12,
    concurrency: int = 50,
) -> None:
    """Uses Microsoft Fabric notebookutils.notebook.runMultiple to run jobs in the provided path.

    Requires to be run in a Fabric notebook environment.

    Args:
        path: Path to job location. Should be in files in the default lakehouse or a mounted lakehouse.
        notebook_name: The name of the notebook in the same workspace which can run a job by name. Should have `job_name: str` as only parameter.
        select: List of jobs to run. If not provided, all jobs will be run.
        timeout_in_seconds: The total timeout for the entire run. Defaults to 12 hours.
        concurrency: Max number of notebooks to run concurrently. Defaults to 50.

    """
    from blueno import create_pipeline, job_registry

    job_registry.discover_jobs(path)

    jobs = list(job_registry.jobs.values())

    pipeline = create_pipeline(jobs=jobs, name_filters=select)

    pipeline.activities

    activities = []

    for activity in pipeline.activities:
        activity = {
            "name": activity.job.name,
            "path": f"{notebook_name}",
            "timeoutPerCellInSeconds": 300,
            "args": {"job_name": activity.job.name},
            "retry": 1,
            "retryIntervalInSeconds": 10,
            "dependencies": [
                dep.name for dep in activity.job.depends_on
            ],  # list of activity names that this activity depends on
        }
        activities.append(activity)

    DAG = {
        "activities": activities,
        "timeoutInSeconds": timeout_in_seconds,
        "concurrency": concurrency,
    }

    try:
        import notebookutils  # type: ignore

        notebookutils.notebook.runMultiple(DAG, {"displayDAGViaGraphviz": True})
    except ImportError as e:
        msg = "Cannot run notebookutils outside a Fabric context"
        logger.error(msg)
        raise ImportError(msg) from e
