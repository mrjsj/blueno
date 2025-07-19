import threading
import time
from contextlib import contextmanager
from threading import Thread

from rich.live import Live
from rich.panel import Panel
from rich.style import Style
from rich.table import Table

from blueno.orchestration.pipeline import (
    ActivityStatus,
    Pipeline,
    PipelineActivity,
)

STATUS_COLOR = {
    ActivityStatus.PENDING: "dim",
    ActivityStatus.SKIPPED: "dim",
    ActivityStatus.CANCELLED: "dim",
    ActivityStatus.READY: "white",
    ActivityStatus.QUEUED: "white",
    ActivityStatus.RUNNING: "cyan",
    ActivityStatus.COMPLETED: "green",
    ActivityStatus.FAILED: "red",
}


def _render_table(activities: list[PipelineActivity]):
    border_style = Style(color=None, bold=True)

    table = Table(expand=False, border_style=border_style)
    table.add_column("Activity")
    table.add_column("Type")
    table.add_column("Status")
    # table.add_column("Step")
    table.add_column("Start Time")
    table.add_column("Duration")
    table.add_column("Error")

    table.columns[2].min_width = 10
    table.columns[3].min_width = 30

    def sort_running_first(activities: list[PipelineActivity]) -> list[PipelineActivity]:
        return sorted(activities, key=lambda a: 0 if a.status == ActivityStatus.RUNNING else 1)

    sorted_activities = sort_running_first(activities)

    for activity in sorted_activities:
        color = STATUS_COLOR.get(activity.status, "white")
        duration = f"{activity.duration:.1f}s" if activity.duration else "-"
        start = time.strftime("%H:%M:%S", time.localtime(activity.start)) if activity.start else "-"

        if activity.exception:
            error = f"{type(activity.exception).__name__}: {str(activity.exception)}"
        else:
            error = "-"

        table.add_row(
            activity.job.name,
            activity.job.type,
            f"[{color}]{activity.status.value}[/{color}]",
            # activity.job.current_step,
            start,
            duration,
            error,
        )

    panel = Panel(table, title="ETL DAG Status", border_style="blue")
    return panel


@contextmanager
def _task_display(pipeline: Pipeline, refresh_per_second: int):
    stop_event = threading.Event()

    def update(live: Live, activities: list[PipelineActivity], stop_event: threading.Event):
        while not stop_event.is_set() and any(
            activity
            for activity in activities
            if activity.status
            in (ActivityStatus.RUNNING, ActivityStatus.PENDING, ActivityStatus.READY)
        ):
            live.update(_render_table(activities))
            time.sleep(1.0 / refresh_per_second)

    with Live(_render_table(pipeline.activities), refresh_per_second=refresh_per_second) as live:
        updater = Thread(target=update, args=(live, pipeline.activities, stop_event), daemon=True)
        updater.start()

        try:
            yield
        finally:
            stop_event.set()
            # updater.join()
            live.update(_render_table(pipeline.activities))
