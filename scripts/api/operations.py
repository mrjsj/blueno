import logging
import time
from typing import Any

import requests

from blueno.fabric.fabric import get_request


def get_long_running_operation(operation_id: str) -> requests.Response | dict[str, Any]:
    endpoint = f"operations/{operation_id}"
    return get_request(endpoint, content_only=False)


def wait_for_long_running_operation(
    operation_id: str, retry_after: str, timeout: float = 60.0 * 5, polling_interval: float = 5.0
) -> requests.Response | dict[str, Any]:
    """Wait for a long running operation to complete within timeout period.

    Args:
        operation_id: The operation ID to check
        retry_after: Initial wait time in seconds
        timeout: Total timeout in seconds (default: 300s/5min)
        polling_interval: Time in seconds between status checks (default: 5.0)

    Returns:
        Response from the operation

    Raises:
        TimeoutError: If the operation does not complete within the timeout period
        Exception: If the operation fails
    """
    logging.info(f"Waiting {retry_after} seconds for operation {operation_id} to complete...")
    time.sleep(float(retry_after))

    start_time = time.time()

    while True:
        response = get_long_running_operation(operation_id)
        

        if isinstance(response, requests.Response):
            response = response.json()

        match response["status"]:
            case "Succeeded":
                logging.info(f"Operation {operation_id} completed successfully")
                break
            case "Failed":
                raise Exception(f"Operation {operation_id} failed: {response.get('error')}")
            case _:
                if (time.time() - start_time) > timeout:
                    raise TimeoutError(
                        f"Operation {operation_id} timed out after {timeout} seconds"
                    )

                logging.info(
                    f"Operation {operation_id} is {response.get('percentComplete')} percent complete, waiting..."
                )
                time.sleep(polling_interval)

    created_item = get_long_running_operation(f"{operation_id}/result")
    return created_item
