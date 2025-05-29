from __future__ import annotations

import logging
import types
from dataclasses import dataclass
from typing import Optional

from blueno.orchestration.job import BaseJob, job_registry, track_step

logger = logging.getLogger(__name__)


@dataclass(kw_only=True)
class Task(BaseJob):
    """Class for the task decorator."""

    @track_step
    def run(self):
        """Running the task."""
        self._transform_fn(*self.depends_on)


def task(
    _func=None,
    *,
    name: Optional[str] = None,
    priority: int = 100,
):
    """Create a definition for task.

    A task can be anything and doesn't need to provide an output.

    Args:
        name: The name of the blueprint. If not provided, the name of the function will be used. The name must be unique across all blueprints.
        priority: Determines the execution order among activities ready to run. Higher values indicate higher scheduling preference, but dependencies and concurrency limits are still respected.

    Example:
        **Creates a task for the `notify_end`, which is depends on a gold blueprint.**

        ```python
        from blueno import blueprint, Blueprint, task
        import logging

        logger = logging.getLogger(__name__)


        @task
        def notify_end(gold_metrics: Blueprint) -> None:
            logger.info("Gold metrics ran successfully")

            # Send message on Slack
        ```
    """

    # TODO: Input validation
    def decorator(func: types.FunctionType):
        _name = name or func.__name__

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
