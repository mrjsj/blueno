from __future__ import annotations

import logging
import types
from dataclasses import dataclass

from blueno.orchestration.job import BaseJob, job_registry

logger = logging.getLogger(__name__)


@dataclass(kw_only=True)
class Task(BaseJob):
    def run(self):
        logger.debug("Ran a task!!")
        self._transform_fn(*self.depends_on)


def task(
    _func=None,
    *,
    name: str | None = None,
    priority: int = 100,
):
    # TODO: Input validation
    def decorator(func: types.FunctionType):
        _name = name or func.__name__

        logger.warning("task decorator ran")
        task = Task(
            name=_name,
            _transform_fn=func,
            priority=priority,
        )

        task._register(job_registry)

        return task

    # If used as @task
    if _func is not None and callable(_func):
        return decorator(_func)

    # If used as @task(...)
    return decorator
