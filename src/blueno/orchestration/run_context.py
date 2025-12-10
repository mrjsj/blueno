from dataclasses import dataclass


@dataclass
class RunContext:
    """Global run context. This might be expanded in the future."""
    full_refresh: bool = False
    force_refresh: bool = False


run_context = RunContext()