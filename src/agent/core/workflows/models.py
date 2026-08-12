"""Pure Workflow state and value models."""

from __future__ import annotations

import os
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Mapping


class WorkflowStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    STOPPED = "stopped"


class WorkflowStopped(Exception):
    """Raised at a checkpoint after whole-run stop has been requested."""


@dataclass(frozen=True, slots=True)
class WorkflowPhase:
    title: str
    detail: str = ""


@dataclass(frozen=True, slots=True)
class WorkflowMeta:
    name: str
    description: str
    when_to_use: str | None = None
    phases: tuple[WorkflowPhase, ...] = ()


@dataclass(frozen=True, slots=True)
class WorkflowLimits:
    max_concurrency: int = max(1, min(16, (os.cpu_count() or 1) - 2))
    max_agents: int = 1000
    max_items: int = 4096


@dataclass(frozen=True, slots=True)
class AgentCallSpec:
    prompt: str
    start_ordinal: int
    resume_key: str
    label: str | None = None
    phase: str | None = None
    schema: Mapping[str, Any] | None = None
    model: str | None = None
    effort: str | None = None
    isolation: str | None = None
    agent_type: str | None = None


@dataclass(frozen=True, slots=True)
class ResumeEntry:
    key: str
    result: Any
    terminal_ordinal: int


@dataclass(frozen=True, slots=True)
class AgentCompletion:
    call: AgentCallSpec
    result: Any
    terminal_ordinal: int
    replayed: bool = False


@dataclass(frozen=True, slots=True)
class WorkflowExecutionResult:
    status: WorkflowStatus
    result: Any = None
    error: str | None = None


_ALLOWED_TRANSITIONS = {
    WorkflowStatus.QUEUED: {WorkflowStatus.RUNNING},
    WorkflowStatus.RUNNING: {
        WorkflowStatus.PAUSED,
        WorkflowStatus.COMPLETED,
        WorkflowStatus.FAILED,
        WorkflowStatus.STOPPED,
    },
    WorkflowStatus.PAUSED: {WorkflowStatus.RUNNING, WorkflowStatus.STOPPED},
    WorkflowStatus.COMPLETED: set(),
    WorkflowStatus.FAILED: set(),
    WorkflowStatus.STOPPED: set(),
}


def transition_workflow(
    current: WorkflowStatus, target: WorkflowStatus
) -> WorkflowStatus:
    """Validate and return one Workflow lifecycle transition."""

    if target not in _ALLOWED_TRANSITIONS[current]:
        raise ValueError(f"invalid Workflow transition: {current} -> {target}")
    return target
