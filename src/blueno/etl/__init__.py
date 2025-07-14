"""Collection of ETL functions."""

from .config import Column, Config, IncrementalColumn, create_config, get_default_config
from .load.delta import append, incremental, overwrite, replace_range, upsert
from .load.parquet import write_parquet
from .read.delta import read_delta
from .read.parquet import read_parquet
from .transform.transforms import (
    add_audit_columns,
    apply_scd_type_2,
    apply_soft_delete_flag,
    deduplicate,
    normalize_column_names,
    reorder_columns_by_prefix,
    reorder_columns_by_suffix,
)

__all__ = (
    "get_default_config",
    "create_config",
    "Config",
    "IncrementalColumn",
    "Column",
    "upsert",
    "append",
    "incremental",
    "overwrite",
    "replace_range",
    "upsert",
    "read_parquet",
    "read_delta",
    "deduplicate",
    "apply_scd_type_2",
    "apply_soft_delete_flag",
    "normalize_column_names",
    "add_audit_columns",
    "write_parquet",
    "reorder_columns_by_prefix",
    "reorder_columns_by_suffix",
)
