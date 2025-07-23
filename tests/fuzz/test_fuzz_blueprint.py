import uuid
from datetime import timedelta

import polars as pl
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from blueno.exceptions import BluenoUserError
from blueno.orchestration.blueprint import Blueprint


@settings(max_examples=1000)
@given(
    write_mode=st.sampled_from(
        [
            "append",
            "safe_append",
            "overwrite",
            "upsert",
            "naive_upsert",
            "incremental",
            "replace_range",
            "scd2_by_column",
            "scd2_by_time",
            "write_more_that_does_not_exist",
        ]
    ),
    format=st.sampled_from(["delta", "parquet", "dataframe", "format_that_does_not_exist"]),
    primary_keys=st.one_of(st.none(), st.lists(st.text(min_size=1), max_size=3), st.text()),
    deduplication_order_columns=st.one_of(st.none(), st.lists(st.text(min_size=1), max_size=3), st.text()),
    incremental_column=st.one_of(st.none(), st.text(min_size=1), st.lists(st.text(min_size=1), max_size=3)),
    scd2_column=st.one_of(st.none(), st.text(min_size=1), st.lists(st.text(min_size=1), max_size=3)),
    freshness=st.one_of(st.none(), st.timedeltas(), st.integers(), st.text()),
    schedule=st.one_of(st.just("* * * * *"), st.just("* * * * * *"), st.just("not cron")),
    maintenance_schedule=st.one_of(st.just("* * * * *"), st.just("* * * * * *"), st.just("not cron")),
    schema=st.one_of(st.none(), st.just(pl.Schema({"a": pl.Int64})), st.just(pl.Schema({"a": pl.String}))),
    post_transforms=st.lists(
        st.sampled_from(
            [
                "deduplicate",
                "add_audit_columns",
                "add_identity_column",
                "post_transform_that_does_not_exist",
            ],
        ),
        min_size=0,
        max_size=3,
        unique=True,
    ),
)
def test_blueprint_register_fuzz(
    write_mode, format, primary_keys, incremental_column, scd2_column, freshness, post_transforms, deduplication_order_columns, schema, schedule, maintenance_schedule
):
    # Compose arguments
    kwargs = dict(
        name="fuzz_test",
        table_uri="/tmp/fuzz" if format != "dataframe" else None,
        schema=schema,
        primary_keys=primary_keys,
        partition_by=[],
        incremental_column=incremental_column,
        deduplication_order_columns=deduplication_order_columns,
        scd2_column=scd2_column,
        write_mode=write_mode,
        format=format,
        freshness=freshness,
        post_transforms=post_transforms,
        schedule=schedule,
        maintenance_schedule=maintenance_schedule,
    )

    def dummy(self):
        return pl.DataFrame({"a": [1, 2, 3]})

    try:
        name = kwargs.pop("name") + uuid.uuid4().hex[:8]  # Ensure unique name
        table_uri = kwargs.pop("table_uri", None)
        table_uri = table_uri + uuid.uuid4().hex[:8] if table_uri is not None else f"/tmp/{name}"

        bp = Blueprint.register(name=name, **kwargs)(dummy)

        assert bp is not None

    except BluenoUserError:
        pass

    except Exception as e:
        pytest.fail(f"Unexpected exception: {e}")
