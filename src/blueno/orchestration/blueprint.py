from __future__ import annotations

import inspect
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from functools import cached_property
from typing import Callable, Dict, List, Optional, Tuple

import polars as pl
from croniter import croniter
from deltalake import DeltaTable, WriterProperties
from polars.testing import assert_frame_equal
from typing_extensions import override

from blueno.etl import (
    append,
    apply_scd_type_2,
    apply_soft_delete_flag,
    incremental,
    overwrite,
    read_parquet,
    replace_range,
    upsert,
    write_parquet,
)
from blueno.exceptions import (
    BluenoUserError,
    GenericBluenoError,
    InvalidJobError,
    Unreachable,
)
from blueno.orchestration.job import BaseJob, JobRegistry, job_registry, track_step
from blueno.types import DataFrameType
from blueno.utils import (
    get_delta_table_if_exists,
    get_delta_table_or_raise,
    get_last_modified_time,
    get_max_column_value,
    get_or_create_delta_table,
)

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
    schedule: Optional[str] = None
    maintenance_schedule: Optional[str] = None

    _inputs: list[BaseJob] = field(default_factory=list)
    _dataframe: DataFrameType | None = field(init=False, repr=False, default=None)
    _preview: bool = False
    _max_upstream_timestamp: int = -1

    @override
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
        schedule: Optional[str] = None,
        maintenance_schedule: Optional[str] = None,
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
                E.g., setting this to `timedelta(hours=1)` will ensure this blueprint is only run at most once an hour.
            schedule: Optional cron style for schedule.
                If blueno runs at a time in the intervals of the schedule, it will be run. Otherwise it will be skipped.
                If not provided, blueprint will **always** be executed.
                Still respects freshness. For instance `* * * * 1-5` will run Monday through Friday.
            maintenance_schedule: Optional cron style for table maintenance.
                Table maintenance compacts and vacuums the delta table.
                If not provided, **no maintenance** will be executed.
                Maintenance will only run once during a cron interval. Setting this value to `* 0-8 * * 6` will run maintenance on the **first** run on Saturdays between 0 and 8.
            **kwargs: Additional keyword arguments to pass to the blueprint. This is used when extending the blueprint with custom attributes or methods.

        **Simple example**
        ```python
        from blueno import Blueprint, DataFrameType


        @Blueprint.register(
            table_uri="/path/to/stage/customer",
            format="delta",
            primary_keys=["customer_id"],
            write_mode="overwrite",
        )
        def stage_customer(self: Blueprint, bronze_customer: DataFrameType) -> DataFrameType:
            # Deduplicate customers
            df = bronze_customer.unique(subset=self.primary_keys)

            return df
        ```

        **Full example**
        ```python
        from blueno import Blueprint, DataFrameType
        from datetime import timedelta


        @Blueprint.register(
            name="gold_customer",
            table_uri="/path/to/gold/customer",
            primary_keys=["customer_id", "site_id"],
            partition_by=["year", "month", "day"],
            incremental_column="order_timestamp",
            scd2_column="modified_timestamp",
            write_mode="upsert",
            format="delta",
            tags={
                "owner": "Alice Wonderlands",
                "project": "customer_360",
                "pii": "true",
                "business_unit": "finance",
            },
            post_transforms=[
                "deduplicate",
                "add_audit_columns",
                "apply_scd2_by_column",
            ],
            deduplication_order_columns=["modified_timestamp"],
            priority=110,
            max_concurrency=2,
            # Will only run if last materialization is more than 1 day ago.
            freshness=timedelta(days=1),
            # Runs if blueno runs on Mondays through Fridays - but only once a day at maximum due to `freshness` setting.
            schedule="* * * * 1-5",
            # Runs maintenance if blueno is run between 22 and 23 on Saturdays.
            maintenance_schedule="* 22 * 6 *",
        )
        def gold_customer(self: Blueprint, silver_customer: DataFrameType) -> DataFrameType:
            # Some advanced business logic
            df = silver_customer.with_columns(...)

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
                schedule=schedule,
                maintenance_schedule=maintenance_schedule,
                _fn=func,
                **kwargs,
            )
            blueprint._register(job_registry)
            return blueprint

        return decorator

    @property
    def _input_validations(self) -> List[tuple[bool, str]]:
        def is_valid_cron(expr: str) -> bool:
            try:
                cron = croniter(expr)
                assert len(cron.fields) == 5, "blueno supports 5 column cron expressions only."
                return True
            except Exception:
                return False

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
                    not isinstance(self.freshness, timedelta) or self.freshness.total_seconds() < 0
                ),
                "freshness must be a positive timedelta or 0",
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
                not isinstance(self.tags, Dict)
                or not all(isinstance(k, str) and isinstance(v, str) for k, v in self.tags.items()),
                "tags must be a dictionary, and all keys and values must be of type `str`.",
            ),
            (
                self.schedule is not None and not is_valid_cron(self.schedule),
                "schedule must be valid cron with exactly 5 columns.",
            ),
            (
                self.maintenance_schedule is not None
                and not is_valid_cron(self.maintenance_schedule),
                "maintenance_schedule must be valid cron with exactly 5 columns.",
            ),
            (
                self.table_uri is not None and self.format == "dataframe",
                "cannot use table_uri when format is dataframe!",
            ),
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

    def _post_transform_apply_scd2_by_column(self):
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

        self._dataframe = apply_scd_type_2(
            source_df=source_df,
            target_df=target_df,
            primary_key_columns=self.primary_keys,
            valid_from_column=self._valid_from_column,
            valid_to_column=self._valid_to_column,
        )

        if self._valid_from_column not in self.primary_keys:
            self.primary_keys = self.primary_keys + [self._valid_from_column]

    def _post_transform_apply_soft_delete_flag(self):
        source_df = self._dataframe
        schema = (
            source_df.collect_schema() if isinstance(source_df, pl.LazyFrame) else source_df.schema
        )

        target_dt = get_or_create_delta_table(self.table_uri, schema)
        target_df = pl.scan_delta(target_dt)

        self._dataframe = apply_soft_delete_flag(
            source_df=source_df,
            target_df=target_df,
            primary_key_columns=self.primary_keys,
            soft_delete_column=self._is_deleted_column,
        )

        # This is not pretty, but most convinient way to fix the updated_at column
        if "add_audit_columns" in self.post_transforms:
            self._dataframe = self._dataframe.drop(
                self._updated_at_column,
            )
            self._post_transform_add_audit_columns()
        elif self._updated_at_column in (
            source_df.collect_schema().names()
            if isinstance(source_df, pl.LazyFrame)
            else source_df.schema.names()
        ):
            self._dataframe = self._dataframe.with_columns(
                pl.lit(datetime.now(timezone.utc))
                .cast(pl.Datetime("us"))
                .alias(self._updated_at_column)
            )

    @property
    def _write_modes(self) -> Dict[str, Callable]:
        """Returns a dictionary of available write methods."""
        return {
            "append": lambda: append(self.table_uri, self._dataframe),
            "overwrite": lambda: overwrite(self.table_uri, self._dataframe),
            "upsert": lambda: upsert(
                table_or_uri=self.table_uri,
                df=self._dataframe,
                key_columns=self.primary_keys,
                predicate_exclusion_columns=[self._identity_column, self._created_at_column],
                update_exclusion_columns=[self._identity_column, self._created_at_column],
            ),
            "incremental": lambda: incremental(
                self.table_uri, self._dataframe, self.incremental_column
            ),
            "replace_range": lambda: replace_range(
                self.table_uri,
                self._dataframe,
                self.incremental_column,
            ),
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
        default_valid_from = datetime(1970, 1, 1, tzinfo=timezone.utc)

        audit_columns = {
            self._created_at_column: pl.lit(timestamp)
            .cast(pl.Datetime("us"))
            .alias(self._created_at_column),
            self._updated_at_column: pl.lit(timestamp)
            .cast(pl.Datetime("us"))
            .alias(self._updated_at_column),
            self._valid_from_column: pl.lit(default_valid_from)
            .cast(pl.Datetime("us"))
            .alias(self._valid_from_column),
            self._valid_to_column: pl.lit(None)
            .cast(pl.Datetime("us"))
            .alias(self._valid_to_column),
            self._is_current_column: pl.lit(True).alias(self._is_current_column),
            self._is_deleted_column: pl.lit(False).alias(self._is_deleted_column),
        }
        columns = (
            self._dataframe.columns
            if isinstance(self._dataframe, pl.DataFrame)
            else self._dataframe.collect_schema().names()
        )
        self._dataframe = self._dataframe.with_columns(
            *[
                col_expr if col_name not in columns else pl.col(col_name).alias(col_name)
                for col_name, col_expr in audit_columns.items()
            ]
        )

    @property
    def _post_transforms(self) -> Dict[str, Callable]:
        """Post-transformation methods to be applied after the transformation."""
        return {
            "add_audit_columns": self._post_transform_add_audit_columns,
            "add_identity_column": self._post_transform_add_identity_column,
            "deduplicate": self._post_transform_deduplicate,
            "apply_scd2_by_column": self._post_transform_apply_scd2_by_column,
            "apply_soft_delete_flag": self._post_transform_apply_soft_delete_flag,
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
            return self._dataframe.lazy()

        if self._preview:
            logger.debug("reading %s %s from preview", self.type, self.name)
            self.preview(show_preview=False)
            return self._dataframe

        if self.table_uri is not None and self.format != "dataframe":
            logger.debug("reading %s %s from %s", self.type, self.name, self.table_uri)
            return self.target_df

        msg = "%s %s is not materialized - most likely because it was never materialized, or it's an ephemeral format, i.e. 'dataframe'"
        logger.error(msg, self.type, self.name)
        raise BluenoUserError(msg % (self.type, self.name))

    @property
    def target_df(self) -> DataFrameType:
        """A reference to the target table as a dataframe."""
        match self.format:
            case "delta":
                dt = get_delta_table_if_exists(self.table_uri)
                if dt is None:
                    logger.error(
                        "No table found for %s at %s. Has it not been materialized yet? Ensure this blueprint is ran before using it in downstream jobs",
                        self.name,
                        self.table_uri,
                    )
                    raise BluenoUserError(
                        "No table found for %s at %s. Has it not been materialized yet? Ensure this blueprint is ran before using it in downstream jobs"
                        % (self.name, self.table_uri)
                    )
                return pl.scan_delta(dt)
            case "parquet":
                return read_parquet(self.table_uri)
            case _:
                msg = f"Unsupported format `{self.format}` for blueprint `{self.name}`"
                logger.error(msg)
                raise GenericBluenoError(msg)

    @property
    def delta_table(self) -> DeltaTable:
        """The delta table."""
        return get_delta_table_or_raise(self.table_uri)

    @track_step
    def write(self) -> None:
        """Writes to destination."""
        logger.debug("writing %s %s to %s", self.type, self.name, self.format)

        if self.format == "dataframe":
            self._dataframe = self._dataframe.lazy()
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
        # Currently isn't working properly
        # if self._preview:
        #     logger.debug("reading sources for preview of %s %s", self.type, self.name)
        #     for input in self.depends_on:
        #         if hasattr(input, "preview"):
        #             input.preview(show_preview=False, limit=-1)

        self._inputs = [
            input.read() if hasattr(input, "read") else input for input in self.depends_on
        ]

    @track_step
    def transform(self) -> None:
        """Runs the transformation."""
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

    def _is_schedule_due(self, schedule: str) -> bool:
        """Checks if now is in the interval of the schedule."""
        # If we're not within the schedule we can exit early
        now = datetime.now(timezone.utc)
        start_interval = croniter(schedule, now).get_prev(datetime)
        if (
            start_interval.year == now.year
            and start_interval.month == now.month
            and start_interval.day == now.day
            and start_interval.hour == now.hour
            and start_interval.minute == now.minute
        ):
            return True
        return False

    def _needs_maintenance(self):
        """Checks if a blueprints needs maintenance."""
        from croniter import croniter

        if not self._is_schedule_due(self.maintenance_schedule):
            return

        # Otherwise we check when table was last optimized.
        last_maintained_from_metadata = get_last_modified_time(
            self.delta_table, ["OPTIMIZE", "VACUUM END"]
        ) or datetime(1970, 1, 1, tzinfo=timezone.utc)

        last_maintained_table_property = datetime.fromtimestamp(
            int(self.get_table_property("blueno.lastMaintenanceTimestamp")) / 1000, tz=timezone.utc
        ) or datetime(1970, 1, 1, tzinfo=timezone.utc)

        last_optimized = max(last_maintained_from_metadata, last_maintained_table_property)

        now = datetime.now(timezone.utc)
        start_interval = croniter(self.maintenance_schedule, now).get_prev(datetime)

        if last_optimized > start_interval:
            logger.info(
                "skipping maintenance for blueprint %s: maintanance schedule is %s and last maintenance was %s",
                self.name,
                start_interval,
                last_optimized,
            )
            return False

        return True

    @track_step
    def maintain(self):
        """Maintains the delta table."""
        if self.format != "delta":
            logger.debug(
                "not running maintenance for %s as format for is not delta - got format %s",
                self.name,
                self.format,
            )
            return

        if self.maintenance_schedule is None:
            logger.debug("no maintenance as maintenance_schedule is None")
            return

        if not self._needs_maintenance():
            return

        logger.info("running compaction on table %s", self.name)
        wp = WriterProperties(compression="ZSTD")
        self.delta_table.optimize.compact(writer_properties=wp)

        logger.info("running vacuum on table %s", self.name)
        self.delta_table.vacuum(dry_run=False)

        logger.info("running creating checkpoint on table %s", self.name)
        self.delta_table.create_checkpoint()

        logger.info("running cleanup metadata on table %s", self.name)
        self.delta_table.cleanup_metadata()

        last_optimize = get_last_modified_time(self.delta_table, ["OPTIMIZE", "VACUUM END"])
        logger.debug("last optimize is now %s", last_optimize)

        # If the optimize/vacuum was a no-op, we don't actually write a timestamp, so we save a backup table property
        if last_optimize is None:
            last_optimize = datetime.now(timezone.utc)

        logger.debug("setting new maintenance timestamp to %s", last_optimize)
        self.set_table_property(
            "blueno.lastMaintenanceTimestamp",
            str(int(last_optimize.timestamp() * 1000)),
        )

    def get_table_property(self, name: str) -> str | None:
        """Gets the table property with the given name."""
        dt = get_delta_table_if_exists(self.table_uri)

        if dt is None:
            return None

        prop = dt.metadata().configuration.get(name)

        if prop is None:
            logger.warning(
                "tried to retrieve a table property with name %s from table %s but it does not exist",
                name,
                self.name,
            )

        return prop

    def set_table_property(self, name: str, value: str):
        """Sets the table with the given name to the given value."""
        dt = get_delta_table_if_exists(self.table_uri)

        if dt is None:
            raise BluenoUserError("Can't set table property if table doesn't exist!")

        if not isinstance(value, str):
            raise BluenoUserError("Table property value must be a string!")

        dt.alter.set_table_properties(
            {
                name: value,
            },
            raise_if_not_exists=False,
        )

    def update_upstream_timestamp_table_property(self):
        """Updates the table property with the max upsteam timestamp."""
        if not self.table_uri:
            return
        self.set_table_property("blueno.maxUpstreamTimestamp", str(self._max_upstream_timestamp))

    def get_upstream_timestamp_table_property(self):
        """Updates the table property with the max upsteam timestamp."""
        ts = self.get_table_property("blueno.maxUpstreamTimestamp")
        logger.debug("read maxUpstreamTimestamp table property for %s with value %s", self.name, ts)
        return ts or 0

    @cached_property
    def last_modified_time(self):
        """When the table was last refreshed by any of the operations.

        - `CREATE OR REPLACE TABLE`
        - `WRITE`
        - `DELETE`
        - `UPDATE`
        - `MERGE`
        - `STREAMING UPDATE`
        """
        tracked_operations = [
            "CREATE OR REPLACE TABLE",
            "WRITE",
            "DELETE",
            "UPDATE",
            "MERGE",
            "STREAMING UPDATE",
        ]
        return get_last_modified_time(self.table_uri, tracked_operations)

    def _find_first_upstream_table_and_unresolved_upstream_dependencies(
        self,
    ) -> Tuple[List[Blueprint], List[BaseJob]]:
        """First the first immediate table dependencies and any unresolved upstream dependencies."""
        visited_ids = set()
        resolved = []
        unresolved = []

        def traverse(dep: BaseJob):
            logger.debug("checking %s", dep.name)
            dep_id = id(dep)
            if dep_id in visited_ids:
                return
            visited_ids.add(dep_id)

            # If no dependencies - it's a terminal node (external API, a hardcode DataFrame, external storage, etc.)
            if not dep.depends_on:
                logger.debug("adding unresolved %s", dep.name)
                unresolved.append(dep)
                return

            for upstream in dep.depends_on:
                if isinstance(upstream, Blueprint) and upstream.format == "delta":
                    logger.debug("adding table %s", upstream.name)
                    resolved.append(upstream)
                    # Stop here - this is the first Blueprint with format = delta
                else:
                    traverse(upstream)

        traverse(self)
        return resolved, unresolved

    @track_step
    def needs_refresh(self) -> bool:
        """Checks if the blueprint needs to be refreshed."""
        if not self.table_uri:
            return True

        if self.schedule is not None and not self._is_schedule_due(self.schedule):
            logger.info(
                "blueprint %s is skipped because schedule %s is not due", self.name, self.schedule
            )
            return False

        if self.freshness is not None:
            if self.freshness.total_seconds() == 0:
                logger.info(
                    "blueprint %s will be force refreshed as the freshness timedelta is 0.",
                    self.name,
                )
                return True

            ts = self.last_modified_time or datetime(1970, 1, 1)

            ts = ts.replace(tzinfo=timezone.utc)
            if ts > datetime.now(timezone.utc) - self.freshness:
                logger.debug(
                    "blueprint %s is fresh - last modified time is %s, freshness threshold is %s",
                    self.name,
                    ts,
                    self.freshness,
                )
                return False

            logger.debug(
                "blueprint %s is stale - last modified time is %s, freshness threshold is %s",
                self.name,
                ts,
                self.freshness,
            )

        if len(self.depends_on) == 0:
            logger.info(
                "table for blueprint %s has no dependencies and no freshness schedule, so it will always be refreshed",
                self.name,
            )
            return True

        table_dependencies, non_tables_dependencies = (
            self._find_first_upstream_table_and_unresolved_upstream_dependencies()
        )

        if len(non_tables_dependencies) > 0:
            logger.info(
                "one or more of the blueprint %s dependencies resolves to a non-table so it's not possible to check the last refresh time - the upstream non-table dependencies are %s",
                self.name,
                ", ".join({dep.name for dep in non_tables_dependencies}),
            )
            return True

        if len(table_dependencies) > 0:
            timestamps = []
            for table in table_dependencies:
                ts = table.last_modified_time
                logger.info(
                    "blueprint %s has an (possibly indirect) upstream dependency on %s with a last refresh timestamp of %s",
                    self.name,
                    table.name,
                    ts,
                )
                if ts is not None:
                    timestamps.append(ts)

            max_upstream_timestamp = (
                max(timestamps) if len(timestamps) > 0 else datetime(1970, 1, 1)
            )

            self._max_upstream_timestamp = int(max_upstream_timestamp.timestamp())

            current_upstream_timestamp = self.get_upstream_timestamp_table_property()
            logger.info(
                "upstream was last changed %s and table %s last upstream refresh is %s",
                max_upstream_timestamp.replace(microsecond=0),
                self.name,
                datetime.fromtimestamp(int(current_upstream_timestamp), tz=timezone.utc),
            )

            if self._max_upstream_timestamp == int(current_upstream_timestamp):
                logger.info(
                    "skipped run for %s as its upstream dependents have not changed since last run - if you want to force a refresh you can set the `freshness=timedelta(minutes=0)` on the blueprint.",
                    self.name,
                )
                return False

            logger.info(
                "table for blueprint %s needs to be refreshed as upstream have changed",
                self.name,
            )
            return True

        raise Unreachable("Shouldn't happen.")

    @override
    @track_step
    def free_memory(self):
        """Clears the collected dataframe to free memory."""
        if self.format == "delta":
            self._dataframe = None

    @override
    @track_step
    def run(self):
        """Runs the job."""
        if not self.needs_refresh():
            logger.info("blueprint %s is skipped due to freshness policy", self.name)
            return
        self.read_sources()
        self.transform()
        self.post_transform()
        self.validate_schema()
        self.write()
        self.update_upstream_timestamp_table_property()
        self.maintain()

    @track_step
    def preview(self, show_preview: bool = True, limit: int = 10):
        """Previews the job."""
        logger.debug("preview %s rows", limit if limit >= 0 else "all")
        self._preview = True
        self.read_sources()
        self.transform()
        self.post_transform()

        if limit >= 0:
            self._dataframe = self._dataframe.limit(limit)

        if hasattr(self._dataframe, "pl"):
            self._dataframe = self._dataframe.pl().lazy()

        if show_preview:
            if isinstance(self._dataframe, pl.LazyFrame):
                self._dataframe = self._dataframe.collect()

            with pl.Config() as cfg:
                cfg.set_tbl_cols(-1)
                cfg.set_tbl_rows(-1)

                print(self._dataframe)
