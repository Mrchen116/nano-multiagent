"""Background task data models."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Mapping


class BackgroundTaskStatus(StrEnum):
    """Lifecycle states for a background task."""

    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    KILLED = "killed"


class BackgroundTaskType(StrEnum):
    """Kind of background task."""

    SUBAGENT = "subagent"
    BASH = "bash"


@dataclass(frozen=True, slots=True)
class BackgroundTaskRecord:
    """Immutable snapshot of a background task at a point in time.

    The registry mutates state by creating new records via dataclass
    ``replace()``, not by editing fields in place.
    """

    task_id: str
    task_type: BackgroundTaskType
    parent_session_id: str
    agent_id: str | None = None
    agent_session_id: str | None = None
    description: str = ""
    prompt: str | None = None
    agent_type: str | None = None
    command: str | None = None
    status: BackgroundTaskStatus = BackgroundTaskStatus.QUEUED
    created_at: str = ""
    started_at: str | None = None
    ended_at: str | None = None
    output_file: str = ""
    result_text: str | None = None
    error: str | None = None
    exit_code: int | None = None
    pending_messages: tuple[str, ...] = ()
    usage: Mapping[str, Any] | None = None
    tool_use_count: int | None = None
    duration_ms: int | None = None
    notified: bool = False
    # Captured at registration from the parent session's workspace_root so the
    # delivery path can locate the JSONL even when the session is idle (bugfix-404).
    workspace_root: str | None = None
