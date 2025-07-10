from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Dict, Optional

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
        tags: Optional[Dict[str, str]] = None,
        priority: int = 100,
    ):
        """Create a definition for task.

        A task can be anything and doesn't need to provide an output.

        Args:
            name: The name of the blueprint. If not provided, the name of the function will be used. The name must be unique across all jobs.
            tags: A dictionary of tags to apply to the blueprint. This can be used to group related jobs by tag, and can be used to run a subset of jobs based on tags.
            priority: Determines the execution order among activities ready to run. Higher values indicate higher scheduling preference, but dependencies and concurrency limits are still respected.

        Example:
            **Creates a task for the `notify_end`, which is depends on a gold blueprint.**

            ```python
            from blueno import Blueprint, Task
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
            task = cls(
                name=_name,
                tags=tags or {},
                _fn=func,
                priority=priority,
            )
            task._register(job_registry)
            return task

        return decorator
