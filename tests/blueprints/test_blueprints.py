import polars as pl
import pytest

from blueno import (
    Blueprint,
    create_pipeline,
    job_registry,
)
from blueno.exceptions import (
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
    @Blueprint.register(table_uri="memory://test")
    def test_func():
        return pl.DataFrame({"a": [1, 2, 3]})

    bp = test_func
    assert isinstance(bp, Blueprint)
    assert bp.name == "test_func"
    assert bp.table_uri == "memory://test"
    assert callable(bp._fn)
    assert bp in job_registry.jobs.values()


def test_blueprint_custom_name():
    @Blueprint.register(name="custom_name", table_uri="memory://test2")
    def test_func2():
        return pl.DataFrame({"b": [4, 5, 6]})

    bp = test_func2
    assert bp.name == "custom_name"
    assert job_registry.jobs["custom_name"] == bp


def test_blueprint_duplicate_name_raises():
    @Blueprint.register(name="dup", table_uri="memory://test3")
    def func1():
        return pl.DataFrame({"c": [1]})

    func1  # Register once

    with pytest.raises(DuplicateJobError):

        @Blueprint.register(name="dup", table_uri="memory://test4")
        def func2():
            return pl.DataFrame({"d": [2]})

        func2


def test_blueprint_schema_type_check():
    with pytest.raises(BluenoUserError):

        @Blueprint.register(schema={"not": "a polars schema"})
        def func():
            return pl.DataFrame({"a": [1]})


def test_blueprint_write_method_check():
    with pytest.raises(BluenoUserError):

        @Blueprint.register(write_mode="invalid")
        def func():
            return pl.DataFrame({"a": [1]})


def test_blueprint_format_check():
    with pytest.raises(BluenoUserError):

        @Blueprint.register(format="csv")
        def func():
            return pl.DataFrame({"a": [1]})


def test_blueprint_dependency_resolution():
    @Blueprint.register(table_uri="memory://parent")
    def parent():
        return pl.DataFrame({"x": [1, 2]})

    @Blueprint.register(table_uri="memory://child")
    def child(parent: pl.DataFrame):
        return parent.with_columns(pl.col("x") + 1)

    bp_child = child
    deps = bp_child.depends_on
    assert len(deps) == 1
    assert deps[0].name == "parent"


def test_blueprint_invalid_dependency_raises():
    @Blueprint.register(table_uri="memory://issing_dep")
    def issing_dep():
        return pl.DataFrame({"y": [1]})

    @Blueprint.register(table_uri="memory://child")
    def child(missing_dep: pl.DataFrame):
        return pl.DataFrame({"y": [1]})

    bp_child = child
    with pytest.raises(JobNotFoundError):
        _ = bp_child.depends_on


def test_blueprint_duplicate_table_uri_raises():
    @Blueprint.register(table_uri="memory://table_uri")
    def parent():
        return pl.DataFrame({"y": [1]})

    with pytest.raises(InvalidJobError):

        @Blueprint.register(table_uri="memory://table_uri")
        def child(parent):
            return pl.DataFrame({"y": [1]})


# InvalidJobError


def test_blueprint_transform_and_valid_schema_validation():
    schema = pl.Schema({"a": pl.Int64})

    @Blueprint.register(table_uri="memory://test", schema=schema)
    def test_func():
        return pl.DataFrame({"a": [1, 2, 3]})

    bp = test_func
    bp.transform()
    bp.validate_schema()  # Should not raise


def test_blueprint_transform_and_invalid_schema_validation():
    schema = pl.Schema({"a": pl.Int32})

    @Blueprint.register(table_uri="memory://test", schema=schema)
    def test_func():
        return pl.DataFrame({"a": [1, 2, 3]})

    bp = test_func
    bp.transform()
    with pytest.raises(BluenoUserError, match="Schema validation failed"):
        bp.validate_schema()  # Should raise


def test_blueprint_transform_returns_non_dataframe_raises():
    @Blueprint.register(table_uri="memory://test")
    def test_func():
        return "not a dataframe"

    bp = test_func
    with pytest.raises(TypeError):
        bp.transform()


def test_blueprint_transform_returns_duckdb_py_relation_passes():
    import duckdb
    @Blueprint.register(table_uri="memory://test")
    def test_func():
        return duckdb.sql("SELECT 1 as 'a'")
    
    bp = test_func
    bp.transform()

def test_blueprint_transform_returns_duckdb_py_connection_passes():
    import duckdb
    @Blueprint.register(table_uri="memory://test")
    def test_func():
        return duckdb.execute("SELECT 1 as 'a'")
    
    bp = test_func
    bp.transform()    


def test_circular_dependencies_raises():

    @Blueprint.register(table_uri="memory://bronze_transform")
    def bronze_transform(gold_transform): # Depends on gold - creating a circular dependency
        return pl.DataFrame()    

    @Blueprint.register(table_uri="memory://silver_transform")
    def silver_transform(bronze_transform):
        return pl.DataFrame()
    
    @Blueprint.register(table_uri="memory://gold_transform")
    def gold_transform(silver_transform):
        return pl.DataFrame()
    
    with pytest.raises(BluenoUserError, match="Cycle detected"):
        pipeline = create_pipeline(job_registry.jobs.values())
        pipeline.run()
