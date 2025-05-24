class BluenoUserError(Exception):
    """An exception for user errors."""

    pass


class GenericBluenoError(Exception):
    """Catch-all exception for generic Blueno orchestration errors."""

    pass


class DuplicateJobError(Exception):
    """Raised when attempting to create a job that already exists."""

    pass


class InvalidJobError(Exception):
    """Raised when attempting to create a job that is invalid."""

    pass


class JobNotFoundError(Exception):
    """Raised when a job is not found."""

    pass


class Unreachable(Exception):
    """Raised when supposedly unreachable code is executed (should never happen)."""

    pass
