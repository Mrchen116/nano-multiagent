"""Run origin enum for identifying who triggered a run."""

from enum import StrEnum


class RunOrigin(StrEnum):
    """Source of run initiation."""

    USER = "user"
    BACKGROUND_TASK = "background_task"
    HEARTBEAT = "heartbeat"
    # feat-394-M7 R5-1 fix: cron runs are unattended isolated executions;
    # mapping origin="cron" → RunOrigin.CRON prevents AttributeError on submit_message.
    CRON = "cron"
