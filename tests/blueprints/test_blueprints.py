import polars as pl
import pytest

from blueno import (
    Blueprint,
    blueprint,
    create_pipeline,
    job_registry,
)
from blueno.orchestration.exceptions import (
    BluenoUserError,
    DuplicateJobError,
    InvalidJobError,
    JobNotFoundError,
)


@pytest.fixture(autouse=True)
def clear_registry():
    job_registry.jobs.clear()
    yield
    job_registry.jobs.clear()


def test_blueprint_simple_example():
    job_registry.discover_jobs("tests/blueprints/simple")

    pipeline = create_pipeline(job_registry.jobs.values())

    pipeline.run(concurrency=4)


def test_blueprint_registers_and_returns_blueprint():
    @blueprint(table_uri="memory://test")
    def test_func():
        return pl.DataFrame({"a": [1, 2, 3]})

    bp = test_func()
    assert isinstance(bp, Blueprint)
    assert bp.name == "test_func"
    assert bp.table_uri == "memory://test"
    assert callable(bp._transform_fn)
    assert bp in job_registry.jobs.values()


def test_blueprint_custom_name():
    @blueprint(name="custom_name", table_uri="memory://test2")
    def test_func2():
        return pl.DataFrame({"b": [4, 5, 6]})

    bp = test_func2()
    assert bp.name == "custom_name"
    assert job_registry.jobs["custom_name"] == bp


def test_blueprint_duplicate_name_raises():
    @blueprint(name="dup", table_uri="memory://test3")
    def func1():
        return pl.DataFrame({"c": [1]})

    func1()  # Register once

    with pytest.raises(DuplicateJobError):

        @blueprint(name="dup", table_uri="memory://test4")
        def func2():
            return pl.DataFrame({"d": [2]})

        func2()


def test_blueprint_schema_type_check():
    with pytest.raises(BluenoUserError):

        @blueprint(schema={"not": "a polars schema"})
        def func():
            return pl.DataFrame({"a": [1]})


def test_blueprint_write_method_check():
    with pytest.raises(BluenoUserError):

        @blueprint(write_mode="invalid")
        def func():
            return pl.DataFrame({"a": [1]})


def test_blueprint_format_check():
    with pytest.raises(BluenoUserError):

        @blueprint(format="csv")
        def func():
            return pl.DataFrame({"a": [1]})


def test_blueprint_dependency_resolution():
    @blueprint(table_uri="memory://parent")
    def parent():
        return pl.DataFrame({"x": [1, 2]})

    @blueprint(table_uri="memory://child")
    def child(parent: pl.DataFrame):
        return parent.with_columns(pl.col("x") + 1)

    bp_child = child()
    deps = bp_child.depends_on
    assert len(deps) == 1
    assert deps[0].name == "parent"


def test_blueprint_invalid_dependency_raises():
    @blueprint(table_uri="memory://issing_dep")
    def issing_dep():
        return pl.DataFrame({"y": [1]})

    @blueprint(table_uri="memory://child")
    def child(missing_dep: pl.DataFrame):
        return pl.DataFrame({"y": [1]})

    bp_child = child()
    with pytest.raises(JobNotFoundError):
        _ = bp_child.depends_on


def test_blueprint_duplicate_table_uri_raises():
    @blueprint(table_uri="memory://table_uri")
    def parent():
        return pl.DataFrame({"y": [1]})

    with pytest.raises(InvalidJobError):

        @blueprint(table_uri="memory://table_uri")
        def child(parent):
            return pl.DataFrame({"y": [1]})


# InvalidJobError


def test_blueprint_transform_and_valid_schema_validation():
    schema = pl.Schema({"a": pl.Int64})

    @blueprint(table_uri="memory://test", schema=schema)
    def test_func():
        return pl.DataFrame({"a": [1, 2, 3]})

    bp = test_func()
    bp.transform()
    bp.validate_schema()  # Should not raise


def test_blueprint_transform_and_invalid_schema_validation():
    schema = pl.Schema({"a": pl.Int32})

    @blueprint(table_uri="memory://test", schema=schema)
    def test_func():
        return pl.DataFrame({"a": [1, 2, 3]})

    bp = test_func()
    bp.transform()
    with pytest.raises(AssertionError):
        bp.validate_schema()  # Should raise


def test_blueprint_transform_returns_non_dataframe_raises():
    @blueprint(table_uri="memory://test")
    def test_func():
        return "not a dataframe"

    bp = test_func()
    with pytest.raises(TypeError):
        bp.transform()
