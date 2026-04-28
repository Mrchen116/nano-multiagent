"""Run origin enum for identifying who triggered a run."""

from enum import StrEnum


class RunOrigin(StrEnum):
    """Source of run initiation."""

    USER = "user"
    BACKGROUND_TASK = "background_task"
    HEARTBEAT = "heartbeat"
