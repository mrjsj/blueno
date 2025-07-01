from __future__ import annotations

import logging
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
        self._fn(*self.depends_on)

    @classmethod
    def register(
        cls,
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
            from blueno import blueprint, Blueprint, Task
            import logging

            logger = logging.getLogger(__name__)


            @Task.register()
            def notify_end(gold_metrics: Blueprint) -> None:
                logger.info("Gold metrics ran successfully")

                # Send message on Slack
            ```
        """

        def decorator(func):
            _name = name or func.__name__
            print(_name)
            task = cls(
                name=_name,
                _fn=func,
                priority=priority,
            )
            task._register(job_registry)
            return task

        return decorator

