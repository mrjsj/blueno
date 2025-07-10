import logging
from typing import Annotated, Dict, List, Literal, Optional

from cyclopts import App, Group, Parameter

from blueno import create_pipeline, job_registry
from blueno.display import _task_display
from blueno.exceptions import BluenoUserError

logger = logging.getLogger(__name__)




class _CustomFormatter(logging.Formatter):
    grey = "\x1b[38;20m"
    yellow = "\x1b[33;20m"
    red = "\x1b[31;20m"
    bold_red = "\x1b[31;1m"
    reset = "\x1b[0m"
    _format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s (%(filename)s:%(lineno)d)"
    # format = "%(asctime)s - %(levelname)s - %(message)s (%(filename)s:%(lineno)d)"

    # # FORMATS = {
    # #     logging.DEBUG: grey + format + reset,
    # #     logging.INFO: grey + format + reset,
    # #     logging.WARNING: yellow + format + reset,
    # #     logging.ERROR: red + format + reset,
    # #     logging.CRITICAL: bold_red + format + reset,
    # # }

    def format(self, record):
        # log_fmt = self.FORMATS.get(record.levelno)
        formatter = logging.Formatter(self._format)
        return formatter.format(record)


app = App(default_parameter=Parameter(negative=()))
global_args = Group(
    name="Global arguments",  # type: ignore[call-arg] # False positive
    default_parameter=Parameter(show_default=False, negative=()),
)


def _setup_logging(log_level: str, display_mode: Optional[str] = None) -> None:
    handlers = [logging.FileHandler("blueno.log")]

    if display_mode == "log" or display_mode is None:
        stream_handler = logging.StreamHandler()  # ty: ignore[no-matching-overload]
        handlers.append(stream_handler)

    for handler in handlers:
        handler.setLevel(log_level)
        handler.setFormatter(_CustomFormatter())

    logging.basicConfig(level=log_level, handlers=handlers)


def _prepare_blueprints(project_dir: str) -> None:
    job_registry.discover_jobs(project_dir)


@app.command
def run(
    project_dir: str,
    select: Annotated[Optional[list[str]], Parameter(consume_multiple=True)] = None,
    select_tags: Annotated[Optional[list[str]], Parameter(consume_multiple=True)] = None,    
    display_mode: Annotated[
        Literal["live", "log", "none"],
        Parameter(help="Show live updates, log output, or no output"),
    ] = "live",
    show_dag: bool = False,
    concurrency: int = 1,
    help: Annotated[bool, Parameter(group=global_args, help="Show this help and exit")] = False,
    log_level: Annotated[
        Literal["DEBUG", "INFO", "WARNING", "ERROR"],
        Parameter(group=global_args, help="Log level to use"),
    ] = "INFO",
):
    """Run the blueprints.

    Args:
        project_dir: Path to the blueprints
        concurrency: Number of concurrent tasks to run
        select: List of blueprints to run. If not provided, all blueprints will be run
        select_tags: List of tags to filter on. Should be in the format: `mytag=value`. Same name tags will be treated as OR, and different named tags will be treated as AND. I.e. "color=blue color=red shape=circle" filters on "(color=blue OR color=red) AND shape=circle".
        show_dag: Whether to show the DAG of the blueprints
        display_mode: Show live updates, log output, or no output
        help: Show this help and exit
        log_level: Log level to use
    """
    _setup_logging(log_level, display_mode)
    _prepare_blueprints(project_dir)

    if show_dag:
        job_registry.render_dag()

    blueprints = list(job_registry.jobs.values())

    tag_filters: Dict[str, List[str]] = {}
    for tag in select_tags or []:
        key, val = tag.split('=', 1)
        if key in tag_filters:
            tag_filters[key].append(val.split())    
        else:
            tag_filters[key] = [val.strip()]

    pipeline = create_pipeline(blueprints, name_filters=select, tag_filters=tag_filters)

    if display_mode == "live":
        with _task_display(pipeline, 10):
            pipeline.run(concurrency=concurrency)
    else:
        pipeline.run(concurrency=concurrency)


@app.command
def preview(
    project_dir: str,
    transformation_name: str,
    help: Annotated[bool, Parameter(group=global_args, help="Show this help and exit")] = False,
    log_level: Annotated[
        Literal["DEBUG", "INFO", "WARNING", "ERROR"],
        Parameter(group=global_args, help="Log level to use"),
    ] = "INFO",
):
    """Previews a transformation.

    Args:
        project_dir: Path to the blueprints
        transformation_name: The name of the transformation to preview
        help: Show this help and exit
        log_level: Log level to use

    """
    _setup_logging(log_level, display_mode=None)
    _prepare_blueprints(project_dir)

    blueprint = job_registry.jobs.get(transformation_name)
    if not blueprint:
        msg = "Transformation '%s' not found in the project directory '%s'." % (
            transformation_name,
            project_dir,
        )
        logger.error(msg)
        raise BluenoUserError(msg)

    blueprint.preview()


@app.command
def run_remote(
    project_dir: str,
    workspace_id: str,
    lakehouse_id: str,
    notebook_id: str,
    select: Optional[list[str]] = None,
    concurrency: int = 1,
    v_cores: int = 2,
    help: Annotated[bool, Parameter(group=global_args, help="Show this help and exit")] = False,
    log_level: Annotated[
        Literal["DEBUG", "INFO", "WARNING", "ERROR"],
        Parameter(group=global_args, help="Log level to use"),
    ] = "INFO",
):
    """Run the blueprints in a Microsoft Fabric remote environment.

    It uploads the blueprints to the target lakehouse in a temporary folder, and runs the blueprints from a notebook.

    Args:
        project_dir: Path to the blueprints
        workspace_id: The workspace id to use
        lakehouse_id: The lakehouse id to use
        notebook_id: The notebook id to use
        concurrency: Number of concurrent tasks to run
        v_cores: Number of vCores to use
        select: List of blueprints to run. If not provided, all blueprints will be run
        help: Show this help and exit
        log_level: Log level to use

    """
    import uuid

    from blueno.fabric import (
        run_notebook,
        upload_folder_contents,
    )

    _setup_logging(log_level, display_mode=None)

    _prepare_blueprints(project_dir)

    destination_folder = f"{project_dir.split('/')[-1]}_{str(uuid.uuid4()).split('-')[0]}"

    upload_folder_contents(
        source_folder=project_dir,
        workspace_name=workspace_id,
        lakehouse_name=lakehouse_id,
        destination_folder=destination_folder,
    )

    execution_data = {
        "parameters": {
            "concurrency": {"value": concurrency, "type": "int"},
            "project_dir": {"value": destination_folder, "type": "string"},
            "log_level": {"value": log_level, "type": "string"},
            "select": {"value": ";".join(select) if select else "", "type": "string"},
        },
        "configuration": {
            "vCores": v_cores,
        },
    }

    run_notebook(workspace_id=workspace_id, notebook_id=notebook_id, execution_data=execution_data)


def main():
    """Entrypoint."""
    app()


if __name__ == "__main__":
    main()
