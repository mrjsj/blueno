from __future__ import annotations

import inspect
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Callable, Dict, List, Optional

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
from blueno.exceptions import (
    BluenoUserError,
    GenericBluenoError,
    InvalidJobError,
)
from blueno.orchestration.job import BaseJob, JobRegistry, job_registry, track_step
from blueno.types import DataFrameType
from blueno.utils import get_last_modified_time, get_max_column_value, get_or_create_delta_table

logger = logging.getLogger(__name__)


@dataclass(kw_only=True)
class Blueprint(BaseJob):
    """Blueprint."""

    table_uri: Optional[str]
    schema: pl.Schema | None
    format: str
    write_mode: str
    post_transforms: List[str]
    deduplication_order_columns: List[str]
    primary_keys: List[str]
    partition_by: List[str]
    incremental_column: Optional[str] = None
    scd2_column: Optional[str] = None
    freshness: Optional[timedelta] = None

    _inputs: list[BaseJob] = field(default_factory=list)
    _dataframe: DataFrameType | None = field(init=False, repr=False, default=None)
    _preview: bool = False

    @classmethod
    def register(
        cls,
        name: Optional[str] = None,
        table_uri: Optional[str] = None,
        schema: Optional[pl.Schema] = None,
        primary_keys: Optional[List[str]] = None,
        partition_by: Optional[List[str]] = None,
        incremental_column: Optional[str] = None,
        scd2_column: Optional[str] = None,
        write_mode: str = "overwrite",
        format: str = "dataframe",
        tags: Optional[Dict[str, str]] = None,
        post_transforms: Optional[List[str]] = None,
        deduplication_order_columns: Optional[List[str]] = None,
        priority: int = 100,
        max_concurrency: Optional[int] = None,
        freshness: Optional[timedelta] = None,
        **kwargs,
    ):
        """Create a decorator for the Blueprint.

        A blueprint is a function that takes any number of blueprints (or zero) and returns a dataframe.
        In addition, blueprint-information registered to know how to write the dataframe to a target table.

        Args:
            name: The name of the blueprint. If not provided, the name of the function will be used.
                The name must be unique across all blueprints.
            table_uri: The URI of the target table. If not provided, the blueprint will not be stored as a table.
            schema: The schema of the output dataframe. If provided, transformation function will be validated against this schema.
            primary_keys: The primary keys of the target table. Is required for `upsert` and `scd2` write_mode.
            partition_by: The columns to partition the of the target table by.
            incremental_column: The incremental column for the target table. Is required for `incremental` write mode.
            scd2_column: The name of the sequence column used for SCD2. Is required for `scd2_by_column` and `scd2_by_time` write mode.
            write_mode: The write method to use. Defaults to `overwrite`.
                Options are: `append`, `overwrite`, `upsert`, `incremental`, `replace_range`, and `scd2_by_column`.
            format: The format to use. Defaults to `delta`. Options are: `delta`, `parquet`, and `dataframe`. If `dataframe` is used, the blueprint will be stored in memory and not written to a target table.
            tags: A dictionary of tags to apply to the blueprint. This can be used to group related blueprints by tag, and can be used to run a subset of blueprints based on tags.
            post_transforms: Optional list of post-transformation functions to apply after the main transformation. Options are: `deduplicate`, `add_audit_columns`, `add_identity_column`.
                These functions will be applied in the order they are provided.
            deduplication_order_columns: Optional list of columns to use for deduplication when `post_transforms` includes `deduplicate`.
            priority: Determines the execution order among activities ready to run. Higher values indicate higher scheduling preference, but dependencies and concurrency limits are still respected.
            max_concurrency: Maximum number of parallel executions allowed when this job is running.
                When set, limits the global concurrency while this blueprint is running.
                This is useful for blueprints with high CPU or memory requirements. For example, setting max_concurrency=1 ensures this job runs serially, while still allowing other jobs to run in parallel.
                Higher priority jobs will be scheduled first when concurrent limits are reached.
            freshness: Optional freshness threshold for the blueprint.
                Only applicable if the format is `delta`.
                If set, the blueprint will only be processed if the delta table's last modification time is older than the freshness threshold.
            **kwargs: Additional keyword arguments to pass to the blueprint. This is used when extending the blueprint with custom attributes or methods.

        Example:
            ```python
            from blueno import Blueprint, DataFrameType


            @Blueprint.register(
                table_uri="/path/to/stage/customer",
                primary_keys=["customer_id"],
                write_mode="overwrite",
            )
            def stage_customer(self: Blueprint, bronze_customer: DataFrameType) -> DataFrameType:
                # Deduplicate customers
                df = bronze_customers.unique(subset=self.primary_keys)

                return df
            ```
        """

        def decorator(func):
            blueprint = cls(
                name=name or func.__name__,
                table_uri=table_uri,
                schema=schema,
                primary_keys=primary_keys or [],
                partition_by=partition_by or [],
                incremental_column=incremental_column,
                scd2_column=scd2_column,
                write_mode=write_mode,
                format=format,
                tags=tags or {},
                post_transforms=post_transforms or [],
                deduplication_order_columns=deduplication_order_columns or [],
                priority=priority,
                max_concurrency=max_concurrency,
                freshness=freshness,
                _fn=func,
                **kwargs,
            )
            blueprint._register(job_registry)
            return blueprint

        return decorator

    @property
    def _input_validations(self) -> List[tuple[bool, str]]:
        rules = [
            (
                self.schema is not None and not isinstance(self.schema, pl.Schema),
                "schema must be a polars schema (pl.Schema).",
            ),
            (
                self.write_mode not in self._write_modes,
                f"write_mode must be one of: {list(self._write_modes.keys())} - got '{self.write_mode}'",
            ),
            (
                self.format not in ["delta", "parquet", "dataframe"],
                f"format must be one of: 'delta', 'parquet', 'dataframe' - got {self.format}",
            ),
            (
                self.format in ["delta", "parquet"] and self.table_uri is None,
                "table_uri must be supplied when format is 'delta' or 'parquet'",
            ),
            (
                self.write_mode == "upsert" and not self.primary_keys,
                "primary_keys must be provided for upsert write_mode",
            ),
            (
                self.write_mode in ("incremental", "replace_range") and not self.incremental_column,
                "incremental_column must be provided for incremental and replace_range write_mode",
            ),
            (
                self.write_mode == "scd2_by_column"
                and (not self.primary_keys or not self.scd2_column),
                "primary_keys, scd2_column must be provided for scd2_by_column write_mode",
            ),
            (
                self.write_mode == "scd2_by_time" and not self.primary_keys,
                "primary_keys must be provided for scd2_by_time write_mode",
            ),
            (
                self.freshness is not None and self.format != "delta",
                "freshness can only be set for delta format blueprints",
            ),
            (
                self.freshness is not None
                and (
                    not isinstance(self.freshness, timedelta) or self.freshness.total_seconds() <= 0
                ),
                "freshness must be a positive timedelta",
            ),
            (
                "deduplicate" in self.post_transforms
                and (not self.primary_keys or not self.deduplication_order_columns),
                "deduplicate post_transform requires primary_keys and deduplication_order_columns to be set",
            ),
            (
                any(transform not in self._post_transforms for transform in self.post_transforms),
                f"post_transforms must exist in {list(self._post_transforms.keys())} - got {self.post_transforms}",
            ),
            (
                not isinstance(self.tags, Dict) or not all(isinstance(k, str) and isinstance(v, str) for k, v in self.tags.items()),
                "tags must be a dictionary, and all keys and values must be of type `str`."
            )            
        ]

        rules.extend(self._extend_input_validations)
        return rules

    @property
    def _extend_input_validations(self) -> List[tuple[bool, str]]:
        """Additional input validations."""
        return []

    @track_step
    def __post_init__(self):
        """Post-initialization."""
        errors = []

        for cond, msg in self._input_validations:
            if cond:
                errors.append(msg)

        if errors:
            for msg in errors:
                logger.error(msg)
            raise BluenoUserError("\n".join(errors))

    @property
    def _system_columns(self) -> Dict[str, str]:
        """System columns used in the blueprint."""
        return {
            "identity_column": "__id",
            "valid_from_column": "__valid_from",
            "valid_to_column": "__valid_to",
            "created_at_column": "__created_at",
            "updated_at_column": "__updated_at",
            "is_current_column": "__is_current",
            "is_deleted_column": "__is_deleted",
        }

    @property
    def _identity_column(self) -> str:
        return self._system_columns.get("identity_column", "__id")

    @property
    def _valid_from_column(self) -> str:
        return self._system_columns.get("valid_from_column", "__valid_from")

    @property
    def _valid_to_column(self) -> str:
        return self._system_columns.get("valid_to_column", "__valid_to")

    @property
    def _created_at_column(self) -> str:
        return self._system_columns.get("created_at_column", "__created_at")

    @property
    def _updated_at_column(self) -> str:
        return self._system_columns.get("updated_at_column", "__updated_at")

    @property
    def _is_current_column(self) -> str:
        return self._system_columns.get("is_current_column", "__is_current")

    @property
    def _is_deleted_column(self) -> str:
        return self._system_columns.get("is_deleted_column", "__is_deleted")

    def _write_mode_scd2_by_column(self):
        scd2_column_dtype = self._dataframe.select(self.scd2_column).dtypes[0]

        if isinstance(scd2_column_dtype, pl.Datetime):
            time_unit = scd2_column_dtype.time_unit
            time_zone = scd2_column_dtype.time_zone

            source_df = self._dataframe.with_columns(
                pl.col(self.scd2_column).alias(self._valid_from_column),
                pl.datetime(None, None, None, time_unit=time_unit, time_zone=time_zone).alias(
                    self._valid_to_column
                ),
            )

        else:
            logger.warning(
                "using scd2_column on a string column - defaulting to time_unit 'us' and time_zone 'UTC'. consider manually casting %s to a pl.Datetime",
                self.scd2_column,
            )
            time_unit = "us"
            time_zone = "UTC"

            source_df = self._dataframe.with_columns(
                pl.col(self.scd2_column)
                .str.to_datetime(time_unit=time_unit, time_zone=time_zone)
                .alias(self._valid_from_column),
                pl.datetime(None, None, None, time_unit=time_unit, time_zone=time_zone).alias(
                    self._valid_to_column
                ),
            )

        schema = (
            source_df.collect_schema() if isinstance(source_df, pl.LazyFrame) else source_df.schema
        )

        target_dt = get_or_create_delta_table(self.table_uri, schema)
        target_df = pl.scan_delta(target_dt)

        upsert_df = apply_scd_type_2(
            source_df=source_df,
            target_df=target_df,
            primary_key_columns=self.primary_keys,
            valid_from_column=self._valid_from_column,
            valid_to_column=self._valid_to_column,
        )

        upsert(
            table_or_uri=self.table_uri,
            df=upsert_df,
            key_columns=self.primary_keys + [self._valid_from_column],
            predicate_exclusion_columns=[self._identity_column, self._created_at_column],
            update_exclusion_columns=[self._identity_column, self._created_at_column],
        )

    def _write_mode_scd2_by_time(self):
        """Write mode for Slowly Changing Dimension Type 2 by time."""
        raise NotImplementedError()

    @property
    def _write_modes(self) -> Dict[str, Callable]:
        """Returns a dictionary of available write methods."""
        return {
            "append": lambda: append(self.table_uri, self._dataframe),
            "overwrite": lambda: overwrite(self.table_uri, self._dataframe),
            "upsert": lambda: upsert(
                self.table_uri,
                self._dataframe,
                self.primary_keys,
            ),
            "incremental": lambda: incremental(
                self.table_uri, self._dataframe, self.incremental_column
            ),
            "replace_range": lambda: replace_range(
                self.table_uri,
                self._dataframe,
                self.incremental_column,
            ),
            "scd2_by_column": self._write_mode_scd2_by_column,
            "scd2_by_time": self._write_mode_scd2_by_time,
            **self._extend_write_modes,
        }

    @property
    def _extend_write_modes(self) -> Dict[str, Callable]:
        """Additional or override write methods."""
        return {}

    def _post_transform_add_identity_column(self):
        next_identity_value = (get_max_column_value(self.table_uri, self._identity_column) or 0) + 1
        self._dataframe = self._dataframe.with_row_index(self._identity_column, next_identity_value)

    def _post_transform_deduplicate(self):
        self._dataframe = self._dataframe.sort(self.deduplication_order_columns, descending=True)
        self._dataframe = self._dataframe.unique(
            subset=self.primary_keys,
            keep="first",
        )

    def _post_transform_add_audit_columns(self):
        """Adds audit columns to the dataframe."""
        timestamp = datetime.now(timezone.utc)

        self._dataframe = self._dataframe.with_columns(
            pl.lit(timestamp).cast(pl.Datetime("us", "UTC")).alias(self._created_at_column),
            pl.lit(timestamp).cast(pl.Datetime("us", "UTC")).alias(self._updated_at_column),
            pl.lit(True).alias(self._is_current_column),
            pl.lit(False).alias(self._is_deleted_column),
        )

    @property
    def _post_transforms(self) -> Dict[str, Callable]:
        """Post-transformation methods to be applied after the transformation."""
        return {
            "add_audit_columns": self._post_transform_add_audit_columns,
            "add_identity_column": self._post_transform_add_identity_column,
            "deduplicate": self._post_transform_deduplicate,
            **self._extend_post_transforms,
        }

    @property
    def _extend_post_transforms(self) -> Dict[str, Callable]:
        """Additional or override post-transformation methods."""
        return {}

    @track_step
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
                msg = "a job with table_uri %s already exists"
                logger.error(msg, self.table_uri)
                raise InvalidJobError(msg % self.table_uri)

        registry.jobs[self.name] = self

    def __str__(self):
        """String representation."""
        return json.dumps(
            {
                "name": self.table_uri,
                "primary_keys": self.primary_keys,
                "format": self.format,
                "write_method": self.write_mode,
                "transform_fn": self._fn.__name__,
            }
        )

    @track_step
    def read(self) -> DataFrameType:
        """Reads from the blueprint and returns a dataframe."""
        if self._dataframe is not None:
            logger.debug("reading %s %s from %s", self.type, self.name, "dataframe")
            return self._dataframe

        if self._preview:
            logger.debug("reading %s %s from preview", self.type, self.name)
            self.preview(show_preview=False)
            return self._dataframe

        if self.table_uri is not None and self.format != "dataframe":
            logger.debug("reading %s %s from %s", self.type, self.name, self.table_uri)
            return self.target_df

        msg = "%s %s is not materialized - most likely because it was never materialized, or it's an ephemeral format, i.e. 'dataframe'"
        logger.error(msg, self.type, self.name, self.name)
        raise BluenoUserError(msg % (self.type, self.name, self.name))

    @property
    def target_df(self) -> DataFrameType:
        """A reference to the target table as a dataframe."""
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
        """Writes to destination."""
        logger.debug("writing %s %s to %s", self.type, self.name, self.format)

        if self.format == "dataframe":
            self._dataframe = self._dataframe.lazy().collect()
            return

        if self.format == "parquet":
            write_parquet(self.table_uri, self._dataframe, partition_by=self.partition_by)
            return

        self._write_modes.get(self.write_mode)()

        logger.debug(
            "wrote %s %s to %s with mode %s", self.type, self.name, self.table_uri, self.write_mode
        )

    @track_step
    def read_sources(self):
        """Reads from sources."""
        if self._preview:
            logger.debug("reading sources for preview of %s %s", self.type, self.name)
            for input in self.depends_on:
                if hasattr(input, "preview"):
                    input.preview(show_preview=False)

        self._inputs = [
            input.read() if hasattr(input, "read") else input for input in self.depends_on
        ]

    @track_step
    def transform(self) -> None:
        """Runs the transformation."""
        if self.freshness:
            ts = get_last_modified_time(self.table_uri)
            if ts < datetime.now(timezone.utc) - self.freshness:
                logger.debug(
                    "blueprint %s is stale - last modified time is %s, freshness threshold is %s",
                    self.name,
                    ts,
                    self.freshness,
                )
            else:
                logger.debug(
                    "blueprint %s is fresh - last modified time is %s, freshness threshold is %s",
                    self.name,
                    ts,
                    self.freshness,
                )
                self._dataframe = self.target_df
                return

        sig = inspect.signature(self._fn)
        if "self" in sig.parameters.keys():
            self._dataframe: DataFrameType = self._fn(self, *self._inputs)
        else:
            self._dataframe: DataFrameType = self._fn(*self._inputs)

        if isinstance(self._dataframe, DataFrameType):
            return

        if hasattr(self._dataframe, "pl"):
            self._dataframe = self._dataframe.pl()
            return

        msg = "%s %s must return a Polars LazyFrame, DataFrame or a DuckDBPyConnection - got %s"
        logger.error(msg, self.type, self.name, type(self._dataframe))
        raise TypeError(msg % (self.type, self.name, type(self._dataframe)))

    @track_step
    def post_transform(self) -> None:
        """Applies post-transformation functions."""
        for transform in self.post_transforms:
            logger.debug("applying post_transform %s to %s %s", transform, self.type, self.name)
            self._post_transforms[transform]()

    @track_step
    def validate_schema(self) -> None:
        """Validates the schema."""
        if self.schema is None:
            logger.debug("schema is not set for %s %s - skipping validation", self.type, self.name)
            return

        if self._dataframe is None:
            msg = "%s %s has no dataframe to validate against the schema - `transform` must be run first"
            logger.error(msg, self.type, self.name)
            raise GenericBluenoError(msg % (self.type, self.name))

        logger.debug("validating schema for %s %s", self.type, self.name)

        if isinstance(self._dataframe, pl.LazyFrame):
            schema_frame = pl.LazyFrame(schema=self.schema)
        else:
            schema_frame = pl.DataFrame(schema=self.schema)

        try:
            assert_frame_equal(self._dataframe.limit(0), schema_frame, check_column_order=False)
        except AssertionError as e:
            msg = f"Schema validation failed for {self.type} {self.name}: {str(e)}"
            logger.error(msg)
            raise BluenoUserError(msg)

        logger.debug("schema validation passed for %s %s", self.type, self.name)

    @track_step
    def free_memory(self):
        """Clears the collected dataframe to free memory."""
        self._dataframe = None

    @track_step
    def run(self):
        """Runs the job."""
        self.read_sources()
        self.transform()
        self.post_transform()
        self.validate_schema()
        self.write()

    @track_step
    def preview(self, show_preview: bool = True):
        """Previews the job."""
        self._preview = True
        self.read_sources()
        self.transform()
        self.post_transform()

        if hasattr(self._dataframe, "pl"):
            self._dataframe = self._dataframe.pl().lazy()

        if show_preview:
            if isinstance(self._dataframe, pl.LazyFrame):
                self._dataframe = self._dataframe.collect()

            print(self._dataframe)
