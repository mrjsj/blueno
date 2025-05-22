from __future__ import annotations

import json
import logging
import time
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass, field
from enum import Enum
from functools import lru_cache
from typing import Optional

from blueno.orchestration.blueprint import Blueprint
from blueno.orchestration.job import Job

# class Trigger(Enum):
#     ON_SUCCESS = "on_success"
#     ON_COMPLETION = "on_completion"
#     ON_FAILURE = "on_failure"
logger = logging.getLogger(__name__)


class ActivityStatus(Enum):
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
    # id: str
    job: Job
    start: float = 0.0
    duration: float = 0.0
    status: ActivityStatus = ActivityStatus.PENDING
    in_degrees: int = 0
    dependents: list[Job] = field(default_factory=list)

    def __str__(self):
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
    activities: list[PipelineActivity] = field(default_factory=list)
    # _ready_activities: list[Activity] = field(default_factory=list)
    # _lock = threading.Lock()

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
        return all(
            dep.status in (ActivityStatus.COMPLETED, ActivityStatus.SKIPPED)
            for dep in dep_activities
        )

    def _update_activities_status(self):
        # with self._lock:
        for activity in self.activities:
            if activity.status is ActivityStatus.PENDING and self._is_ready(activity):
                activity.status = ActivityStatus.READY

            if activity.status in (ActivityStatus.CANCELLED, ActivityStatus.FAILED):
                for dep in activity.dependents:
                    act = [act for act in self.activities if act.job.name == dep][0]
                    if act.status is ActivityStatus.PENDING:
                        act.status = ActivityStatus.CANCELLED

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
        # or all(
        #     activity.status is Status.WAITING for activity in self.activities
        # )

    def run(self, concurrency: int = 1):
        # ready_activities = [activity for activity in self.activities if activity.in_degrees == 0]
        self._update_activities_status()
        self._update_activities()
        running_futures: dict[Future[str], PipelineActivity] = {}

        def run_step(activity: PipelineActivity):
            # with self._lock:
            try:
                if activity.status is ActivityStatus.SKIPPED:
                    logger.info(f"Skipping: {activity.job.name}")
                    return activity.job.name
                logger.info(f"Running: {activity.job.name}")
                activity.start = time.time()
                activity.status = ActivityStatus.RUNNING
                activity.job.run()
                activity.status = ActivityStatus.COMPLETED

            except Exception as e:
                logger.error(f"Error running blueprint {activity.job.name}: {str(e)}")
                print(f"Error running blueprint {activity.job.name}: {str(e)}")
                with self._lock:
                    activity.status = ActivityStatus.FAILED

                raise e
            logger.info(f"Finished: {activity.job.name}")
            return activity.job.name

        def run_activity(activity: PipelineActivity):
            activity.status = ActivityStatus.RUNNING
            activity.start = time.time()
            try:
                activity.job.run()
                activity.status = ActivityStatus.COMPLETED
                activity.duration = time.time() - activity.start
            except Exception as e:
                activity.status = ActivityStatus.FAILED
                activity.duration = time.time() - activity.start
                logger.error(f"Error running blueprint {activity.job.name}: {str(e)}")

        with ThreadPoolExecutor(max_workers=concurrency) as executor:
            try:
                while self._has_ready_activities or running_futures:
                    for activity in self._ready_activities:
                        # if activity.status is not Status.SKIPPED:

                        activity.status = ActivityStatus.QUEUED
                        future = executor.submit(run_activity, activity)
                        running_futures[future] = activity

                    while True:
                        # self.benchmark(self._update_activities)
                        self._update_activities()

                        done = [f for f in running_futures if f.done()]
                        if done:
                            break
                        time.sleep(0.1)

                    for future in done:
                        _ = running_futures.pop(future)

                    self._update_activities_status()

            except KeyboardInterrupt:
                for future, activity in running_futures.items():
                    if not (future.done() or future.running()):
                        activity.status = ActivityStatus.CANCELLED
                        future.cancel()

                executor.shutdown(wait=False, cancel_futures=True)

        # self._update_activities()


def create_pipeline(jobs: list[Blueprint], subset: list[str] | None = None) -> Pipeline:
    pipeline = Pipeline()

    # Step 1: Create all activities
    for job in jobs:
        activity = PipelineActivity(job)
        # for dep in job.depends_on:
        #     activity.in_degrees += 1
        pipeline.activities.append(activity)

    # Step 2: Link dependencies
    name_to_activity = {activity.job.name: activity for activity in pipeline.activities}
    for activity in pipeline.activities:
        for dep in activity.job.depends_on:
            dep_activity = name_to_activity.get(dep.name)
            if dep_activity:
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

    if not subset:
        logger.debug("No subset")
        return pipeline

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

    for item in subset:
        # Parse modifiers (e.g. +silver, silver++, etc.)
        prefix = re.match(r"^(\+*)", item).group(0)  # ty: ignore[possibly-unbound-attribute]

        suffix = re.match(r"^(\+*)", item[::-1]).group(0)  # ty: ignore[possibly-unbound-attribute]

        core = item.strip("+")

        if core not in name_to_activity:
            continue

        selected.add(core)

        if "+" in prefix:
            selected.update(get_ancestors(core, level=len(prefix)))

        if "+" in suffix:
            selected.update(get_descendants(core, level=len(suffix)))

    # Step 4: Filter activities

    for activity in pipeline.activities:
        if activity.job.name not in selected:
            activity.status = ActivityStatus.SKIPPED

    logger.critical(pipeline)

    return pipeline
