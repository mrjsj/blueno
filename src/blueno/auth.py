import logging
import os
import sys
from functools import lru_cache

from deltalake import DeltaTable

from blueno.exceptions import BluenoUserError

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def get_access_token(audience: str) -> str:
    """Retrieves an access token for a given audience.

    This function attempts to obtain an access token for a given audience.
    It first checks if the code is running in a Microsoft Fabric notebook environment
    and attempts to use the `notebookutils` library to get the token. If the library
    is not available, it falls back to using the `DefaultAzureCredential` from the Azure SDK
    to fetch the token.
    """
    if "notebookutils" in sys.modules:
        logger.debug("trying to get token using notebookutils")
        import notebookutils  # type: ignore

        token = notebookutils.credentials.getToken(audience)
        return token

    logger.debug("notebookutils not found, falling back to azure-identity")

    try:
        logger.debug("trying to get token using azure-identity")
        from azure.core.exceptions import ClientAuthenticationError
        from azure.identity import DefaultAzureCredential
    except ModuleNotFoundError as e:
        msg = (
            "the `azure-identity` package is required to when using ADLS or OneLake protocols.\n"
            'please install the required dependencies: `pip install "blueno[azure]"`'
        )
        logger.error(msg)
        raise ModuleNotFoundError(msg) from e

    try:
        token = DefaultAzureCredential().get_token(f"{audience}/.default").token
    except ClientAuthenticationError as e:
        msg = (
            "failed to get token using azure-identity. "
            "please check your Azure credentials and permissions."
        )
        logger.error(msg)
        raise ClientAuthenticationError(msg) from e

    return token


def get_onelake_access_token() -> str:
    """Alias for `get_azure_storage_access_token`."""
    return get_azure_storage_access_token()


def get_azure_storage_access_token() -> str:
    """Retrieves an access token for Azure Storage.

    This function attempts to obtain an access token for accessing Azure storage.
    It first checks if the `AZURE_STORAGE_TOKEN` environment variable is set.
    Otherwise, it tries to get the token using `notebookutils.credentials.getToken`.
    Lastly, it falls back to using the `DefaultAzureCredential`.

    Returns:
        The access token used for authenticating requests to Azure Storage.
    """
    logger.debug("trying to get token using AZURE_STORAGE_TOKEN environment variable")
    token = os.environ.get("AZURE_STORAGE_TOKEN")
    if token:
        logger.debug("using AZURE_STORAGE_TOKEN from environment variable")
        return token

    logger.debug("AZURE_STORAGE_TOKEN not found.")

    audience = "https://storage.azure.com"

    token = get_access_token(audience)

    return token


def get_fabric_bearer_token() -> str:
    """Retrieves a bearer token for Fabric (Power BI) API.

    This function attempts to obtain a bearer token for authenticating requests to the
    Power BI API. It first checks if the code is running in a Microsoft Fabric
    notebook environment and tries to use the `notebookutils` library to get the token.
    If the library is not available, it falls back to using the `DefaultAzureCredential`
    from the Azure SDK to fetch the token.

    Returns:
        The bearer token used for authenticating requests to the Fabric (Power BI) API.
    """
    audience = "https://analysis.windows.net/powerbi/api"
    return get_access_token(audience)


def get_azure_devops_access_token() -> str:
    """Retrieves a bearer token for Azure DevOps.

    This function attempts to obtain a bearer token for authenticating requests to Azure DevOps.

    Returns:
        The bearer token used for authenticating requests to Azure DevOps.
    """
    audience = "499b84ac-1321-427f-aa17-267ca6975798"
    return get_access_token(audience)


def get_storage_options(table_or_uri: str | DeltaTable) -> dict[str, str]:
    """Retrieves storage options including a bearer token for Azure Storage.

    This function calls `get_azure_storage_access_token` to obtain a bearer token
    and returns a dictionary containing the token.

    Args:
        table_or_uri: The URI of the Delta table.

    Returns:
        A dictionary containing the storage options for Azure Storage.

    Example:
    **Retrieve storage options**
    ```python notest
    from blueno.auth import get_storage_options

    options = get_storage_options("abfss://path/to/delta_table")
    options
    {"bearer_token": "your_token_here"}
    ```
    """
    if isinstance(table_or_uri, DeltaTable):
        table_or_uri = table_or_uri.table_uri

    logger.debug("getting storage options for table_or_uri: %s", table_or_uri)

    protocol = table_or_uri.split("://")[0]

    match protocol:
        case "abfss":
            tenant_id = os.getenv("AZURE_TENANT_ID")
            client_id = os.getenv("AZURE_CLIENT_ID")
            client_secret = os.getenv("AZURE_CLIENT_SECRET")
            if tenant_id is not None and client_id is not None and client_secret is not None:
                logger.debug(
                    "getting storage options from environment variables AZURE_TENANT_ID, AZURE_CLIENT_ID, AZURE_CLIENT_SECRET."
                )
                storage_options = {
                    tenant_id: tenant_id,
                    client_id: client_id,
                    client_secret: client_secret,
                }
            else:
                storage_options = {
                    "bearer_token": get_azure_storage_access_token(),
                }
            # TODO: `allow_invalid_certificates` is set due to: https://github.com/delta-io/delta-rs/issues/3243
            # This is specifically an issue in the Microsoft Fabric Python runtime.
            if "notebookutils" in sys.modules:
                storage_options["allow_invalid_certificates"] = "true"

            # Timeout some issues related to delta-rs: https://github.com/delta-io/delta-rs/issues/2639
            storage_options["timeout"] = "120s"

            return storage_options

        case "r2":
            msg = "r2 is supported, but you must use the s3 protocol."
            logger.error("r2 is supported, but you must use the s3 protocol.")
            raise BluenoUserError(msg)
        case "s3" | "s3a":
            storage_options = {}
            s3_env_vars = [
                "AWS_ACCESS_KEY_ID",
                "AWS_SECRET_ACCESS_KEY",
                "AWS_SESSION_TOKEN",
                "AWS_REGION",
                "AWS_ENDPOINT_URL",
            ]
            for env_var in s3_env_vars:
                var = os.getenv(env_var)
                if var is not None:
                    storage_options[env_var] = var

            return storage_options
        case "http" | "https" | "gcs":
            logger.warning(
                "protocol %s is not supported yet - you can provide your own storage options."
                % protocol
            )
        case _:
            if protocol == table_or_uri:
                logger.debug("no object store protocol found in table_uri - assuming file system.")
            else:
                logger.warning("protocol %s not known", protocol)

    return {}
