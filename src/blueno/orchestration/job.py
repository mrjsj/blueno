from __future__ import annotations

import importlib
import inspect
import logging
import pathlib
import sys
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from tempfile import TemporaryDirectory
from typing import Callable, Optional

# from blueno.blueprints.blueprint import Blueprint
from blueno.orchestration.exceptions import DuplicateJobError, JobNotFoundError

logger = logging.getLogger(__name__)


@dataclass(kw_only=True)
class Job(ABC):
    name: str
    priority: int
    _current_step: str | None = None
    _transform_fn: Callable = lambda: None

    @property
    @abstractmethod
    def current_step(self) -> list[Job]: ...

    @property
    @abstractmethod
    def type(self) -> str: ...

    @abstractmethod
    def _register(self, register: JobRegistry) -> None: ...

    @property
    @abstractmethod
    def depends_on(self) -> list[Job]: ...

    @abstractmethod
    def run(self) -> None:
        """What to do when activity is run."""
        pass


def track_step(func):
    def wrapper(self, *args, **kwargs):
        if self._current_step:
            self._current_step += " -> " + func.__name__
        else:
            self._current_step = func.__name__
        return func(self, *args, **kwargs)

    return wrapper


@dataclass(kw_only=True)
class BaseJob(Job):
    def _register(self, registry: JobRegistry) -> None:
        if self.name in registry.jobs:
            msg = f"A {type(self).__base__} with name {self.name} already exists!"
            logger.error(msg)
            raise DuplicateJobError(msg)

        registry.jobs[self.name] = self

    @property
    def current_step(self) -> str:
        return self._current_step

    @property
    def type(self) -> str:
        return type(self).__name__

    @property
    def depends_on(self) -> list[Job]:
        sig = inspect.signature(self._transform_fn)

        dependencies = list(sig.parameters.keys())

        inputs = []
        for dependency in dependencies:
            if dependency in ("self"):
                continue

            blueprint = job_registry.jobs.get(dependency)
            if blueprint is None:
                msg = f"The dependency in blueprint `{self.name}` with name `{dependency}` does not exist!"

                from difflib import get_close_matches

                close_matches = get_close_matches(dependency, job_registry.jobs.keys(), n=1)

                if len(close_matches) > 0:
                    msg += f" Did you mean `{close_matches[0]}`?"

                logger.error(msg)
                raise JobNotFoundError(msg)

            inputs.append(blueprint)
            logger.debug(f"Found dependency: {dependency}, {blueprint}")

        return inputs


@dataclass
class JobRegistry:
    _instance: Optional[JobRegistry] = None
    jobs: dict[str, Job] = field(default_factory=dict)

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def discover_py_blueprints(self, path: str | pathlib.Path = "blueprints") -> None:
        logger.debug(f"Discovering Python blueprints in {path}")
        base_dir = pathlib.Path(path).absolute()

        logger.debug(f"Base dir: {base_dir}")

        files = base_dir.rglob("**/*.py")
        import os

        cwd = os.getcwd()
        logger.debug(f"Files: {list(files)}")

        for py_file in base_dir.rglob("**/*.py"):
            # Skip __init__.py or hidden files
            if py_file.name.startswith("__"):
                continue

            module_path = py_file.with_suffix("")

            # Make module path relative to cwd
            module_path = module_path.relative_to(cwd)

            module_name = ".".join(module_path.parts)

            # TODO: Find a better way to do this
            if "." not in sys.path:
                sys.path.append(".")
                importlib.import_module(module_name)
                sys.path.remove(".")
            else:
                importlib.import_module(module_name)

    # def discover_sql_blueprints(self, path: str | pathlib.Path = "blueprints") -> None:
    #     def parse_blueprint(sql: str):
    #         import re

    #         blueprint_pattern = re.compile(
    #             r"BLUEPRINT\s*\(\s*(.*?)\s*\);", re.DOTALL | re.IGNORECASE
    #         )
    #         match = blueprint_pattern.search(sql)
    #         if not match:
    #             return None

    #         blueprint_body = match.group(1)

    #         blueprint_params = {}
    #         for line in blueprint_body.strip().splitlines():
    #             line = line.strip()
    #             if not line or "=" not in line:
    #                 continue
    #             key, value = line.split("=", 1)
    #             blueprint_params[key.strip()] = value.strip()

    #         sql = blueprint_pattern.sub("", sql).strip()

    #         df_refs_pattern = r"\b(?:FROM|JOIN)\s+([a-zA-Z0-9_.]+)"

    #         df_refs = re.findall(df_refs_pattern, sql, re.IGNORECASE)

    #         return blueprint_params, df_refs, sql

    #     logger.debug(f"Discovering SQL blueprints in {path}")
    #     base_dir = pathlib.Path(path).absolute()
    #     logger.debug(f"Base dir: {base_dir}")

    #     files = base_dir.rglob("**/*.sql")
    #     # import os

    #     # cwd = os.getcwd()
    #     logger.debug(f"Files: {list(files)}")

    #     for file in base_dir.rglob("**/*.sql"):
    #         with file.open() as f:
    #             content = f.read()

    #         blueprint_config, dependants, sql = parse_blueprint(content)

    #         # local_vars = {}

    #         sql = sql.replace("\n", " ")

    #         def duckdb_func(self: Blueprint, sql: str, **kwargs):
    #             conn = duckdb.connect()
    #             for dep in dependants:
    #                 bp = job_registry.jobs.get(dep)
    #                 if bp:
    #                     conn.register(dep, bp.read())

    #             return conn.sql(sql).pl()

    #         from functools import partial

    #         kwargs = {dep: dep for dep in dependants if dep != "self"}

    #         def wrapped_func():
    #             return partial(duckdb_func, sql=sql, **kwargs)()

    #         # exec(textwrap.dedent(f"""
    #         #     def func(self, {','.join(dependants)}):
    #         #         import duckdb
    #         #         return duckdb.sql('''{sql}''').pl()

    #         #     fn = func"""
    #         # ), {}, local_vars)

    #         blueprint = Blueprint(
    #             name=blueprint_config.get("name", file.with_suffix("").name),
    #             table_uri=blueprint_config.get("table_uri"),
    #             schema=None,
    #             format=blueprint_config.get("format"),
    #             write_mode=blueprint_config.get("write_mode"),
    #             # _transform_fn=local_vars.get("fn"),
    #             _transform_fn=wrapped_func,
    #             primary_keys=blueprint_config.get("primary_keys"),
    #             partition_by=blueprint_config.get("partition_by"),
    #             incremental_column=blueprint_config.get("incremental_column"),
    #             valid_from_column=blueprint_config.get("valid_from_column"),
    #             valid_to_column=blueprint_config.get("valid_to_column"),
    #             # _depends_on=blueprint_config.get("_depends_on"),
    #         )

    #         job_registry.register(blueprint)

    def discover_jobs(self, path: str | pathlib.Path = "blueprints") -> None:
        self.discover_py_blueprints(path)
        # self.discover_sql_blueprints(path)

    def register(self, job: Job) -> None:
        if job.name in self.jobs:
            msg = f"A blueprint with name {job.name} already exists!"
            logger.error(msg)
            raise DuplicateJobError(msg)

        logger.debug(f"Adding job {job} to jobs registry")
        self.jobs[job.name] = job

    def render_dag(self):
        try:
            import graphviz
        except ImportError as e:
            msg = "Graphviz is not installed. Please install it to render the DAG."
            logger.error(msg)
            raise ImportError(msg) from e

        dot = graphviz.Digraph()

        for step in self.jobs.values():
            dot.node(step.name)
            for dep in step.depends_on:
                dot.edge(dep.name, step.name)

        with TemporaryDirectory() as tmpdirname:  # ty: ignore[no-matching-overload]
            dot.render(tmpdirname + "_dag", view=True, format="png")

    # def build_dag(self, )


job_registry = JobRegistry()
