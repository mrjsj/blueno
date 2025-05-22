from __future__ import annotations

import inspect
import json
import logging
import types
from dataclasses import dataclass, field
from typing import Callable

import polars as pl
from polars.testing import assert_frame_equal

from blueno.etl import (
    append,
    apply_scd_type_2,
    incremental,
    overwrite,
    read_delta,
    read_parquet,
    replace_range,
    upsert,
    write_parquet,
)
from blueno.etl.types import DataFrameType
from blueno.orchestration.exceptions import (
    GenericBluenoError,
    InvalidJobError,
)
from blueno.orchestration.job import BaseJob, Job, JobRegistry, job_registry, track_step

logger = logging.getLogger(__name__)


@dataclass(kw_only=True)
class Blueprint(BaseJob):
    name: str
    table_uri: str | None
    schema: pl.Schema | None
    format: str
    write_mode: str
    _transform_fn: Callable
    primary_keys: list[str] = field(default_factory=list)
    partition_by: list[str] = field(default_factory=list)
    incremental_column: str | None = None
    valid_from_column: str | None = None
    valid_to_column: str | None = None
    priority: int = 100

    _inputs: list[Job] = field(default_factory=list)
    _dataframe: DataFrameType | None = field(init=False, repr=False, default=None)
    _current_step: str = ""

    def _register(self, registry: JobRegistry) -> None:
        super()._register(job_registry)

        if self.table_uri:
            blueprints = [
                b
                for b in registry.jobs.values()
                if isinstance(b, Blueprint) and b.name != self.name
            ]

            table_uris = [b.table_uri.strip("/") for b in blueprints if b.table_uri is not None]

            if self.table_uri.rstrip("/") in table_uris:
                msg = f"A blueprint with table_uri {self.table_uri} already exists!"
                logger.error(msg)
                raise InvalidJobError(msg)

        registry.jobs[self.name] = self

    @property
    def current_step(self) -> str:
        return self._current_step

    def __str__(self):
        return json.dumps(
            {
                "name": self.table_uri,
                # "depends_on": self.depends_on,
                "primary_keys": self.primary_keys,
                "format": self.format,
                "write_method": self.write_mode,
                "transform_fn": self._transform_fn.__name__,
            }
        )

    def read(self) -> DataFrameType:
        if self._dataframe is not None:
            logger.debug(f"Reading blueprint `{self.name}` from `self._dataframe`")
            return self._dataframe

        if self.table_uri is not None and self.format != "dataframe":
            logger.debug(f"Reading blueprint `{self.name}` from `self.table_uri`")
            return self.target_df

        logger.debug(f"Reading blueprint `{self.name}` from `self.transform()`")
        self.transform()

        return self._dataframe

    @property
    def target_df(self) -> DataFrameType:
        match self.format:
            case "delta":
                return read_delta(self.table_uri)
            case "parquet":
                return read_parquet(self.table_uri)
            case _:
                msg = f"Unsupported format `{self.format}` for blueprint `{self.name}`"
                logger.error(msg)
                raise GenericBluenoError(msg)

    @track_step
    def write(self) -> None:
        logger.debug(
            f"Writing blueprint `{self.name}` to `{self.table_uri}` with mode `{self.write_mode}`"
        )
        if self.format == "dataframe":
            logger.debug(f"Writing blueprint `{self.name}` to memory")
            self._dataframe = self._dataframe.lazy().collect()
            return

        if self.format == "parquet":
            logger.debug(f"Writing blueprint `{self.name}` to parquet")
            write_parquet(self.table_uri, self._dataframe, partition_by=self.partition_by)
            return

        if self.format == "delta":
            match self.write_mode:
                case "append":
                    append(
                        table_or_uri=self.table_uri,
                        df=self._dataframe,
                    )
                case "incremental":
                    incremental(
                        table_or_uri=self.table_uri,
                        df=self._dataframe,
                        incremental_column=self.incremental_column,
                    )
                case "replace_range":
                    replace_range(
                        table_or_uri=self.table_uri,
                        df=self._dataframe,
                        range_column=self.incremental_column,
                    )
                case "overwrite":
                    overwrite(
                        table_or_uri=self.table_uri,
                        df=self._dataframe,
                    )
                case "upsert":
                    upsert(
                        table_or_uri=self.table_uri,
                        df=self._dataframe,
                        primary_key_columns=self.primary_keys,
                    )
                case "scd2":
                    upsert_df = apply_scd_type_2(
                        source_df=self._dataframe,
                        target_df=self.target_df,
                        primary_key_columns=self.primary_keys,
                        valid_from_column=self.valid_from_column,
                        valid_to_column=self.valid_to_column,
                    )
                    upsert(
                        table_or_uri=self.table_uri,
                        df=upsert_df,
                        primary_key_columns=self.primary_keys + [self.valid_from_column],
                    )
                case _:
                    msg = f"Invalid write mode `{self.write_mode}` for `{self.format}` for blueprint `{self.name}`"
                    logger.error(msg)
                    raise GenericBluenoError(msg)

        logger.debug(f"Successfully wrote blueprint `{self.name}` to `{self.table_uri}`")

    @track_step
    def read_sources(self):
        self._inputs = [
            input.read() if hasattr(input, "read") else input for input in self.depends_on
        ]

    @track_step
    def transform(self) -> None:
        logger.debug(f"Transforming blueprint {self.name}")

        sig = inspect.signature(self._transform_fn)
        if "self" in sig.parameters.keys():
            self._dataframe: DataFrameType = self._transform_fn(self, *self._inputs)
        else:
            self._dataframe: DataFrameType = self._transform_fn(*self._inputs)

        if not isinstance(self._dataframe, DataFrameType):
            msg = (
                f"Transform function `{self._transform_fn.__name__}` must return a `DataFrameType`!"
            )
            logger.error(msg)
            raise TypeError(msg)

    @track_step
    def validate_schema(self) -> None:
        if self.schema is None:
            logger.debug(f"Schema is not set for blueprint `{self.name}`. Skipping validation.")
            return

        if self._dataframe is None:
            msg = f"Blueprint `{self.name}` has no dataframe to validate against the schema. Run the `transform` method first!"
            logger.error(msg)
            raise GenericBluenoError(msg)

        logger.debug(f"Validating schema for blueprint `{self.name}`")

        schema_frame = pl.DataFrame(schema=self.schema)
        assert_frame_equal(self._dataframe.limit(0), schema_frame, check_column_order=False)
        logger.debug(f"Schema validation passed for blueprint `{self.name}`")

    def run(self):
        logger.debug(f"Running blueprint: {self.name}")
        self.read_sources()
        self.transform()
        self.validate_schema()
        self.write()

        logger.debug(f"Succesfully ran blueprint: {self.table_uri}")


def blueprint(
    _func=None,
    *,
    name: str | None = None,
    table_uri: str | None = None,
    schema: pl.Schema | None = None,
    primary_keys: list[str] | None = None,
    partition_by: list[str] | None = None,
    incremental_column: str | None = None,
    valid_from_column: str | None = None,
    valid_to_column: str | None = None,
    write_mode: str = "overwrite",
    format: str = "delta",
    priority: int = 100,
):
    """Create a definition for how to compute a blueprint.

    A blueprint is a function that takes any number of blueprints (or zero) and returns a dataframe.
    In addition, blueprint-information registered to know how to write the dataframe to a target table.

    Args:
        name (str): The name of the blueprint. If not provided, the name of the function will be used. The name must be unique across all blueprints.
        table_uri (str): The URI of the target table. If not provided, the blueprint will not be stored as a table.
        schema (pl.Schema, optional): The schema of the output dataframe. If provided, transformation function will be validated against this schema.
        primary_keys (list[str], optional): The primary keys of the target table. Is required for `upsert` and `scd2` write_mode.
        partition_by (list[str], optional): The columns to partition the of the target table by.
        incremental_column (str, optional): The incremental column for the target table. Is required for `incremental` write mode.
        valid_from_column (str, optional): The name of the valid from column. Is required for `scd2` write mode.
        valid_to_column (str, optional): The name of the valid to column. Is required for `scd2` write mode.
        write_mode (str): The write method to use. Defaults to `overwrite`. Options are: `append`, `overwrite`, `upsert`, `incremental`, `replace_range`, and `scd2`.
        format (str): The format to use. Defaults to `delta`. Options are: `delta`, `parquet`, and `dataframe`. If `dataframe` is used, the blueprint will be stored in memory and not written to a target table.
        priority (int): Determines the execution order among activities ready to run. Higher values indicate higher scheduling preference, but dependencies and concurrency limits are still respected.

    Example:
        Creates a blueprint for the `silver_customer` table, which is derived from the `bronze_customer` table.
        The `bronze_customer` must be another blueprint.

        ```python
        from blueno import blueprint, Blueprint, DataFrameType

        @blueprint(
            table_uri="/path/to/silver/customer",
            primary_keys=["customer_id"],
            write_mode="overwrite",
        )
        def silver_customer(self: Blueprint, bronze_customer: DataFrameType) -> DataFrameType

            # Deduplicate customers
            df = bronze_customers.unique(subset=self.primary_keys)

            return df
        ```
    """
    _primary_keys = primary_keys or []

    if schema is not None and not isinstance(schema, pl.Schema):
        msg = "`schema` must be a polars schema (`pl.Schema`)."
        logger.error(msg)
        raise GenericBluenoError(msg)

    if write_mode not in ["append", "overwrite", "upsert", "incremental", "replace_range", "scd2"]:
        msg = "`write_method` must be one of: 'append', 'overwrite', 'upsert', 'incremental', 'replace_range', 'scd2'."
        logger.error(msg)
        raise GenericBluenoError(msg)

    if format not in ["delta", "parquet", "dataframe"]:
        msg = f"`format` must be one of: 'delta', 'parquet', 'dataframe'. Got {format}."
        logger.error(msg)
        raise GenericBluenoError(msg)

    if write_mode == "upsert" and not primary_keys:
        msg = "`primary_keys` must be provided for `upsert` write mode."
        logger.error(msg)
        raise GenericBluenoError(msg)

    if write_mode in ("incremental", "replace_range") and not incremental_column:
        msg = "`incremental_column` must be provided for `incremental` and `replace_range` write mode."
        logger.error(msg)
        raise GenericBluenoError(msg)

    if write_mode == "scd2" and (not valid_from_column or not valid_to_column):
        msg = "`valid_from_column` and `valid_to_column` must be provided for `scd2` write mode."
        logger.error(msg)
        raise GenericBluenoError(msg)

    if write_mode == "scd2" and not primary_keys:
        msg = "`primary_keys` must be provided for `scd2` write mode."
        logger.error(msg)
        raise GenericBluenoError(msg)

    def decorator(func: types.FunctionType):
        _name = name or func.__name__
        logger.warning("blueprint decorator ran")

        blueprint = Blueprint(
            table_uri=table_uri,
            schema=schema,
            name=_name,
            primary_keys=_primary_keys,
            incremental_column=incremental_column,
            valid_from_column=valid_from_column,
            valid_to_column=valid_to_column,
            write_mode=write_mode,
            _transform_fn=func,
            format=format,
            priority=priority,
        )
        blueprint._register(job_registry)

        return lambda: blueprint

    if _func is not None and callable(_func):
        return decorator(_func)

    return decorator
