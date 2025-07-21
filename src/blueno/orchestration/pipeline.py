from __future__ import annotations

import json
import logging
import time
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from fnmatch import fnmatch
from functools import lru_cache
from typing import Dict, List, Optional

from blueno.exceptions import BluenoUserError
from blueno.orchestration.job import BaseJob

# class Trigger(Enum):
#     ON_SUCCESS = "on_success"
#     ON_COMPLETION = "on_completion"
#     ON_FAILURE = "on_failure"
logger = logging.getLogger(__name__)


class ActivityStatus(Enum):
    """The statuses a `PipelineActivity` can be in."""

    PENDING = "pending"
    READY = "ready"
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
    CANCELLED = "cancelled"


@dataclass
class PipelineActivity:
    """PipelineActivity."""

    # id: str
    job: BaseJob
    start: float = 0.0
    duration: float = 0.0
    status: ActivityStatus = ActivityStatus.PENDING
    in_degrees: int = 0
    dependents: list[BaseJob] = field(default_factory=list)
    exception: Optional[Exception] = None

    def __str__(self):
        """String representation."""
        return json.dumps(
            {
                "job": json.loads(str(self.job)),
                "start": self.start,
                "duration": self.duration,
                "status": str(self.status),
                "in_degrees": self.in_degrees,
                "dependants": self.dependents,
            },
            indent=4,
        )


@dataclass
class Pipeline:
    """Pipeline."""

    activities: list[PipelineActivity] = field(default_factory=list)
    # _ready_activities: list[Activity] = field(default_factory=list)
    # _lock = threading.Lock()
    _running_activities: dict[Future[str], PipelineActivity] = field(default_factory=dict)
    failed_jobs: dict[str, Exception] = field(default_factory=dict)

    def _have_all_dependents_completed(self, activity: PipelineActivity) -> bool:
        """Check if all dependents of an activity have completed."""
        dependent_activities = [a for a in self.activities if a.job.name in activity.dependents]
        return all(
            dep.status in (ActivityStatus.COMPLETED, ActivityStatus.SKIPPED)
            for dep in dependent_activities
        )

    def _is_ready(self, activity: PipelineActivity) -> bool:
        dep_activities = [
            a for a in self.activities if a.job.name in [d.name for d in activity.job.depends_on]
        ]
        # if hasattr(activity.job, "trigger"):
        #     trigger = getattr(activity.job, "trigger", Trigger.ON_SUCCESS)
        #     if trigger == Trigger.ON_SUCCESS:
        #         return all(dep.status == Status.COMPLETED for dep in dep_activities)
        #     elif trigger == Trigger.ON_COMPLETION:
        #         return all(
        #             dep.status in (Status.COMPLETED, Status.FAILED, Status.SKIPPED)
        #             for dep in dep_activities
        #         )
        #     elif trigger == Trigger.ON_FAILURE:
        #         return any(dep.status == Status.FAILED for dep in dep_activities)
        is_ready = all(
            dep.status in (ActivityStatus.COMPLETED, ActivityStatus.SKIPPED)
            for dep in dep_activities
        )
        return is_ready

    def _update_activities_status(self):
        # with self._lock:
        for activity in self.activities:
            if activity.status is ActivityStatus.PENDING and self._is_ready(activity):
                logger.debug("setting status for %s to READY", activity.job.name)
                activity.status = ActivityStatus.READY
                continue

            if activity.status in (ActivityStatus.CANCELLED, ActivityStatus.FAILED):
                for dep in activity.dependents:
                    act = [act for act in self.activities if act.job.name == dep][0]
                    if act.status is ActivityStatus.PENDING:
                        logger.debug(
                            "setting status for activity %s to CANCELLED as upstream activity %s has status %s",
                            act.job.name,
                            activity.job.name,
                            activity.status.name,
                        )
                        act.status = ActivityStatus.CANCELLED
                continue

            if (
                activity.status is ActivityStatus.COMPLETED
            ):  # and self._have_all_dependents_completed(activity):
                activity.job.free_memory()

    def _can_schedule_activity(self, activity: PipelineActivity, pipeline_concurrency: int) -> bool:
        """Check if an activity can be schedule considering its max_concurrency and it's priority relative to other activity priorities."""
        # If there are no running we can schedule
        if self._running_activities == {}:
            return True

        # Check if there's a higher prio waiting.
        higher_prio_waiting = any(
            a for a in self._ready_activities if a.job.priority > activity.job.priority
        )
        if higher_prio_waiting:
            return False

        # Check if adding a new activity would exceed the max_concurrency of current running activities
        max_concurrency = min(
            a.job.max_concurrency or pipeline_concurrency for a in self._running_activities.values()
        )
        if len(self._running_activities) + 1 > max_concurrency:
            return False

        # Check if adding a new activity would exceed it's own max_concurrency
        if (
            activity.job.max_concurrency
            and len(self._running_activities) >= activity.job.max_concurrency  # ty: ignore[unsupported-operator]
        ):
            return False

        return True

    def _update_activities(self):
        for activity in self.activities:
            # if activity.status is Status.RUNNING and activity.start == 0:
            #     activity.start = time.time()

            if activity.status is ActivityStatus.RUNNING:
                activity.duration = time.time() - activity.start
            # elif (
            #     activity.status in (Status.COMPLETED, Status.FAILED)
            #     and activity.duration == 0.0
            # ):
            #     activity.duration = time.time() - activity.start

            # if any(
            #     activity for activity in self.activities if activity.status == Status.FAILED
            # ):
            #     logger.warning("Setting skipped")
            #     if activity.status == Status.WAITING:
            #         activity.status = Status.SKIPPED

    @property
    def _ready_activities(self) -> list[PipelineActivity]:
        return [activity for activity in self.activities if activity.status is ActivityStatus.READY]

    @property
    def _has_ready_activities(self) -> bool:
        return any(self._ready_activities)

    def run_sequential(self):
        """Run activities sequentially."""
        while self._has_ready_activities or self._running_activities:
            for activity in self._ready_activities:
                if not self._can_schedule_activity(activity, 1):
                    continue

                logger.debug("setting status for activity %s to QUEUED", activity.job.name)
                activity.status = ActivityStatus.QUEUED
                try:
                    self.run_activity(activity)
                except Exception as e:
                    logger.debug("setting status for activity %s to FAILED", activity.job.name)
                    logger.info("activity %s completed in failure", activity.job.name)
                    activity.status = ActivityStatus.FAILED
                    activity.duration = time.time() - activity.start
                    self.failed_jobs[activity.job.name] = e
                    activity.exception = e
                    logger.error("Error running blueprint %s: %s", activity.job.name, e, exc_info=e)

                self._update_activities()
                self._update_activities_status()

    def run_activity(self, activity: PipelineActivity, **kwargs):
        """Run a single activity."""
        context = kwargs.pop("context", None)
        if context is not None:
            context.thread_local_storage.invocation_id = context.invocation_id

        activity.status = ActivityStatus.RUNNING
        activity.start = time.time()
        logger.debug("setting status for activity %s to RUNNING", activity.job.name)
        logger.info("starting activity %s", activity.job.name)

        activity.job.run()
        activity.duration = time.time() - activity.start
        activity.status = ActivityStatus.COMPLETED
        logger.debug("setting status for activity %s to COMPLETED", activity.job.name)
        logger.info(
            "activity %s completed successfully in %s seconds",
            activity.job.name,
            round(activity.duration, 3),
        )

    def run(self, concurrency: int = 1, **kwargs):
        """Runs the pipeline."""
        self._update_activities_status()
        self._update_activities()

        start = time.time()
        logger.info("pipeline run started %s", datetime.fromtimestamp(start, tz=timezone.utc))
        if concurrency == 1:
            self.run_sequential()
            logger.info(
                "pipeline run ended %s after %s seconds",
                datetime.fromtimestamp(start, tz=timezone.utc),
                round(time.time() - start, 3),
            )
            return

        with ThreadPoolExecutor(max_workers=concurrency) as executor:
            try:
                while self._has_ready_activities or self._running_activities:
                    for activity in self._ready_activities:
                        if not self._can_schedule_activity(activity, concurrency):
                            continue
                        # if activity.job.max_concurrency and len(self._running_futures) >= activity.job.max_concurrency:
                        #     continue

                        logger.debug("setting status for activity %s to QUEUED", activity.job.name)
                        activity.status = ActivityStatus.QUEUED
                        future = executor.submit(
                            self.run_activity, activity, context=kwargs.get("context")
                        )
                        self._running_activities[future] = activity

                    while True:
                        # self.benchmark(self._update_activities)
                        self._update_activities()

                        done = [f for f in self._running_activities if f.done()]
                        if done:
                            break

                    for future in done:
                        activity = self._running_activities.pop(future)
                        maybe_exception = future.exception()
                        if maybe_exception:
                            logger.debug(
                                "setting status for activity %s to FAILED", activity.job.name
                            )
                            activity.status = ActivityStatus.FAILED
                            activity.duration = time.time() - activity.start
                            logger.info(
                                "activity %s completed in failure after %s seconds",
                                activity.job.name,
                                activity.duration,
                            )
                            self.failed_jobs[activity.job.name] = maybe_exception
                            activity.exception = maybe_exception
                            logger.error(
                                "Error running blueprint %s: %s",
                                activity.job.name,
                                maybe_exception,
                                exc_info=maybe_exception,
                            )

                    self._update_activities_status()

            except KeyboardInterrupt:
                for future, activity in self._running_activities.items():
                    if not (future.done() or future.running()):
                        logger.debug(
                            "setting status for activity %s to CANCELLED as KeyboardInterrupt was called",
                            activity.job.name,
                        )
                        activity.status = ActivityStatus.CANCELLED
                        future.cancel()

                executor.shutdown(wait=False, cancel_futures=True)

        logger.info(
            "pipeline run ended %s after %s seconds",
            datetime.fromtimestamp(start, tz=timezone.utc),
            round(time.time() - start, 3),
        )


def create_pipeline(
    jobs: list[BaseJob],
    name_filters: Optional[List[str]] = None,
    tag_filters: Optional[Dict[str, List[str]]] = None,
) -> Pipeline:
    """Creates a pipeline and resolved dependencies given list of Jobs, and optionally a subset of jobs name.

    Args:
        jobs: A list of jobs
        name_filters: A selector-style list of job names. Can be prefixed or suffixed with + to include downstream and/or upstream jobs.
            The number of +'s will denote the number of levels to include.
            I.e. +silver_product will select the silver_product job and its direct upstream dependencies (parents).
            ++silver_product will select the silver_product job and two generates of upstream dependencies (parents + grandparents).
        tag_filters: A tag style filter. Only jobs tagged with the key-value pair provided will be included.

    Returns:
        A pipeline of activities with resolved dependencies.

    """
    pipeline = Pipeline()

    # Step 1: Create all activities
    for job in jobs:
        activity = PipelineActivity(job)
        # for dep in job.depends_on:
        #     activity.in_degrees += 1
        pipeline.activities.append(activity)

    def find_circular_dependencies(jobs):
        visited = set()
        stack = []

        def visit(job):
            if job.name in stack:
                cycle_start = stack.index(job.name)
                cycle = stack[cycle_start:] + [job.name]
                return cycle
            if job.name in visited:
                return None
            stack.append(job.name)
            for dep in job.depends_on:
                result = visit(dep)
                if result:
                    return result
            stack.pop()
            visited.add(job.name)
            return None

        for job in jobs:
            result = visit(job)
            if result:
                return result
        return None

    cycle = find_circular_dependencies(jobs)
    if cycle:
        msg = "Cycle detected in job dependencies %s"
        logger.error(msg % " -> ".join(reversed(cycle)))
        raise BluenoUserError("Cycle detected in job dependencies:", " -> ".join(reversed(cycle)))

    # Step 2: Link dependencies
    name_to_activity = {activity.job.name: activity for activity in pipeline.activities}
    for activity in pipeline.activities:
        for dep in activity.job.depends_on:
            dep_activity = name_to_activity.get(dep.name)
            if dep_activity:
                logger.debug(
                    "setting %s as a dependent of %s", activity.job.name, dep_activity.job.name
                )
                dep_activity.dependents.append(activity.job.name)
                activity.in_degrees += 1

    @lru_cache(maxsize=None)
    def total_upstream_score(name):
        activity = name_to_activity[name]
        score = activity.in_degrees
        for dep in activity.job.depends_on:
            score += total_upstream_score(dep.name)
        return score

    # Step 3: Sort activities
    pipeline.activities = sorted(
        pipeline.activities,
        key=lambda activity: (
            total_upstream_score(activity.job.name),
            -activity.job.priority,
        ),
    )

    if name_filters:
        # Step 3: Build dependency maps
        def get_ancestors(activity_name: str, level: Optional[int] = None) -> set:
            visited, frontier = set(), {activity_name}
            depth = 0
            while frontier and (level is None or depth < level):
                next_frontier = set()
                for name in frontier:
                    for dep in name_to_activity[name].job.depends_on:
                        if dep.name not in visited:
                            next_frontier.add(dep.name)
                visited.update(next_frontier)
                frontier = next_frontier
                depth += 1
            return visited

        def get_descendants(activity_name: str, level: Optional[int] = None) -> set:
            visited, frontier = set(), {activity_name}
            depth = 0
            while frontier and (level is None or depth < level):
                next_frontier = set()
                for name in frontier:
                    for dep_name in name_to_activity[name].dependents:
                        if dep_name not in visited:
                            next_frontier.add(dep_name)
                visited.update(next_frontier)
                frontier = next_frontier
                depth += 1
            return visited

        selected = set()
        import re

        for item in name_filters:
            # Parse modifiers (e.g. +silver, silver++, etc.)
            prefix = re.match(r"^(\+*)", item).group(0)  # ty: ignore[possibly-unbound-attribute]
            suffix = re.match(r"^(\+*)", item[::-1]).group(0)  # ty: ignore[possibly-unbound-attribute]
            core = item.strip("+")

            # Handle wildcards by finding all matching jobs
            matching_jobs = set()
            if "*" in core:
                matching_jobs = {name for name in name_to_activity.keys() if fnmatch(name, core)}
            else:
                if core in name_to_activity:
                    matching_jobs = {core}

            # Process each matching job with its modifiers
            for job_name in matching_jobs:
                selected.add(job_name)
                if "+" in prefix:
                    selected.update(get_ancestors(job_name, level=len(prefix)))
                if "+" in suffix:
                    selected.update(get_descendants(job_name, level=len(suffix)))

        # Step 4: Filter activities
        for activity in pipeline.activities:
            if activity.job.name not in selected:
                logger.debug(
                    "activity %s was skipped as it did not match any of the name filters %s",
                    activity.job.name,
                    name_filters,
                )
                activity.status = ActivityStatus.SKIPPED
                continue

    if tag_filters:
        for activity in pipeline.activities:
            if activity.status == ActivityStatus.SKIPPED:
                logger.debug(
                    "skipping tag filter check for activity %s as it was already skipped due to another filter",
                    activity.job.name,
                )
                continue

            for tag, allowed_values in tag_filters.items():
                tag_value = activity.job.tags.get(tag)
                if tag_value is None or tag_value not in allowed_values:
                    logger.debug(
                        "activity %s was skipped as it did not match the tag filters %s",
                        activity.job.name,
                        tag_filters,
                    )
                    activity.status = ActivityStatus.SKIPPED
                    break

    if all(activity.status is ActivityStatus.SKIPPED for activity in pipeline.activities):
        logger.warning("no jobs matched the provided filters")

    return pipeline
