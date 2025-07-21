from __future__ import annotations

import importlib
import inspect
import logging
import pathlib
import sys
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from tempfile import TemporaryDirectory
from typing import Callable, Dict, List, Optional

# from blueno.blueprints.blueprint import Blueprint
from blueno.exceptions import BluenoUserError, DuplicateJobError, JobNotFoundError
from blueno.types import DataFrameType

logger = logging.getLogger(__name__)


def track_step(func):
    """A wrapper which logs when a function was called, and when a function call ended.

    Also sets the current step.
    """

    def wrapper(self, *args, **kwargs):
        logger.debug("started step %s for %s %s", func.__name__, self.type, self.name)
        if self._current_step:
            self._current_step += " -> " + func.__name__
        else:
            self._current_step = func.__name__
        result = func(self, *args, **kwargs)
        logger.debug("completed step %s for %s %s", func.__name__, self.type, self.name)
        return result

    return wrapper


@dataclass(kw_only=True)
class BaseJob(ABC):
    """The base class for a Job."""

    name: str
    priority: int
    tags: Dict[str, str]
    max_concurrency: Optional[int] = None
    _current_step: Optional[str] = None
    _fn: Callable[..., DataFrameType]
    _depends_on: Optional[List[BaseJob]] = None

    @track_step
    def _register(self, registry: JobRegistry) -> None:
        if self.name in registry.jobs:
            msg = f"A {type(self).__base__} with name {self.name} already exists!"
            logger.error(msg)
            raise DuplicateJobError(msg)

        registry.jobs[self.name] = self

    @property
    def current_step(self) -> str:
        """The current step which the job is executing."""
        return self._current_step

    @property
    def type(self) -> str:
        """The type of the job."""
        return type(self).__name__

    @property
    def depends_on(self) -> list[BaseJob]:
        """The other jobs which the job depends on."""
        if self._depends_on is not None:
            return self._depends_on

        sig = inspect.signature(self._fn)

        dependencies = list(sig.parameters.keys())

        inputs = []
        for dependency in dependencies:
            if dependency in ("self"):
                continue

            job = job_registry.jobs.get(dependency)
            if job is None:
                msg = "the dependency in %s %s with name %s does not exist"

                from difflib import get_close_matches

                close_matches = get_close_matches(dependency, job_registry.jobs.keys(), n=1)

                if len(close_matches) > 0:
                    msg += " - did you mean %s?" % close_matches[0]

                logger.error(msg, self.type, self.name, dependency)
                raise JobNotFoundError(msg % (self.type, self.name, dependency))

            logger.debug("found dependency %s for job %s", dependency, job.name)
            inputs.append(job)

        self._depends_on = inputs
        return self._depends_on

    @classmethod
    @abstractmethod
    def register(cls, *args, **kwargs) -> BaseJob:
        """A class method to create a decorator for the job.

        This method should be implemented by concrete job classes to define their decorator logic.
        """
        raise NotImplementedError("This method should be implemented by subclasses.")

    @abstractmethod
    def run(self) -> None:
        """What to do when job is run.

        This method should be implemented by concrete job classes to define their execution logic.
        """
        pass

    @abstractmethod
    def free_memory(self) -> None:
        """Method to free up memory, e.g. deleting dataframe.

        This will be called when the jobs dependents have completed.
        """
        pass


@dataclass
class JobRegistry:
    """JobRegistry."""

    _instance: Optional[JobRegistry] = None
    jobs: dict[str, BaseJob] = field(default_factory=dict)

    def __new__(cls):
        """Singleton method."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def discover_py_blueprints(self, path: str | pathlib.Path) -> None:
        """Discovers jobs from all .py files in the provided path."""
        base_dir = pathlib.Path(path).absolute()

        import os

        cwd = os.getcwd()
        logger.debug("discovering jobs in %s", base_dir)

        if not os.path.exists(base_dir):
            logger.error(
                "the provided path %s does not exist in the current working directory %s",
                base_dir,
                cwd,
            )
            raise BluenoUserError(
                "the provided path %s does not exist in the current working directory %s"
                % (base_dir, cwd)
            )

        files_found = False
        for py_file in base_dir.rglob("**/*.py"):
            # Skip __init__.py or hidden files
            if py_file.name.startswith("__"):
                continue

            files_found = True

            module_path = py_file.with_suffix("")

            # Make module path relative to cwd
            module_path = module_path.relative_to(cwd)

            module_name = ".".join(module_path.parts)

            logger.debug("importing %s from %s", module_name, module_path)
            # TODO: Find a better way to do this
            if "." not in sys.path:
                sys.path.append(".")
                importlib.import_module(module_name)
                sys.path.remove(".")
            else:
                importlib.import_module(module_name)

        if not files_found:
            logger.warning("no .py files exists in %s", cwd + str(base_dir))

        logger.debug("done discovering jobs")

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
        """Discover jobs from with possible discovery methods."""
        self.discover_py_blueprints(path)
        # self.discover_sql_blueprints(path)

    # def register(self, job: BaseJob) -> None:
    #     if job.name in self.jobs:
    #         msg = f"A blueprint with name {job.name} already exists!"
    #         logger.error(msg)
    #         raise DuplicateJobError(msg)

    #     logger.debug("adding job %s to jobs registry", job.name)
    #     self.jobs[job.name] = job

    def render_dag(self):
        """Builds a DAG for the currently registered jobs, and shows it.

        Requires graphviz.
        """
        from collections import defaultdict

        try:
            import graphviz
        except ImportError as e:
            msg = "graphviz is not installed - install it to render the dag"
            logger.error(msg)
            raise ImportError(msg) from e

        dot = graphviz.Digraph()
        dot.attr(rankdir="LR")  # Alternatively: TB for horizontal layout.

        levels = defaultdict(list)
        for step in self.jobs.values():
            levels[step.name.split("_")[0]].append(
                step.name
            )  # Maybe introduce "layer" prop on BaseJob to include this? Or pick from tags?

        for _, node_names in levels.items():
            with dot.subgraph() as s:
                s.attr(rank="same")
                for name in node_names:
                    s.node(name)

        for step in self.jobs.values():
            for dep in step.depends_on:
                dot.edge(dep.name, step.name)

        with TemporaryDirectory() as tmpdirname:  # ty: ignore[no-matching-overload]
            dot.render(tmpdirname + "_dag", view=True, cleanup=True, format="png")


job_registry = JobRegistry()
