"""Blueno."""

from importlib.metadata import PackageNotFoundError, version

from blueno.auth import (
    get_azure_storage_access_token,
    get_fabric_bearer_token,
    get_onelake_access_token,
)
from blueno.orchestration.blueprint import Blueprint
from blueno.orchestration.job import BaseJob, job_registry
from blueno.orchestration.pipeline import create_pipeline
from blueno.orchestration.task import Task
from blueno.types import DataFrameType

__all__ = (
    "get_fabric_bearer_token",
    "get_azure_storage_access_token",
    "get_onelake_access_token",
    "DataFrameType",
    "Blueprint",
    "BaseJob",
    "Task",
    "create_pipeline",
    "job_registry",
)


try:
    __version__ = version("blueno")
except PackageNotFoundError:
    # package is not installed
    __version__ = "0.0.0"
