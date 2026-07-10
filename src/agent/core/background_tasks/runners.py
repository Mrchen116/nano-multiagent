"""Common lifecycle template for background task runners.

Runners are platform-provided; core only defines the lifecycle protocol
so that registry, notifications, and queue logic stay testable.
"""

from __future__ import annotations


from agent.core.background_tasks.interfaces import (
    BackgroundBashRunner,
    BackgroundSubagentHandle,
    BackgroundSubagentRunner,
    BackgroundTaskOutput,
    BackgroundTaskStopper,
    TaskCompletionCallback,
    TaskFailureCallback,
    TaskKillCallback,
)
from agent.core.background_tasks.models import BackgroundTaskRecord


def run_subagent_lifecycle(
    *,
    runner: BackgroundSubagentRunner,
    record: BackgroundTaskRecord,
    on_complete: TaskCompletionCallback,
    on_fail: TaskFailureCallback,
    on_kill: TaskKillCallback,
    llm_session_id: str | None = None,
) -> BackgroundSubagentHandle:
    """Start a subagent worker and wire completion/failure/kill callbacks.

    The caller (platform adapter) is responsible for:
      - Updating registry state to RUNNING before/after this call.
      - Delivering the notification to the parent session when complete.

    bugfix-422 (#129): ``llm_session_id`` lets the caller reuse the parent's
    session id at the LLM request layer so the subagent's provider calls group
    under the parent in the LLM proxy session-inspector, while the subagent keeps
    its own local session id for JSONL storage, resumption, and agent_id lookup.
    """
    if record.agent_session_id is None:
        raise ValueError("subagent record must have agent_session_id")
    return runner.start(
        agent_session_id=record.agent_session_id,
        parent_session_id=record.parent_session_id,
        prompt=record.prompt or "",
        on_complete=on_complete,
        on_fail=on_fail,
        on_kill=on_kill,
        llm_session_id=llm_session_id,
    )


def run_bash_lifecycle(
    *,
    runner: BackgroundBashRunner,
    record: BackgroundTaskRecord,
    output: BackgroundTaskOutput,
    cwd: str,
    timeout: float | None,
    on_complete: TaskCompletionCallback,
    on_fail: TaskFailureCallback,
) -> BackgroundTaskStopper:
    """Start a background shell process and wire callbacks.

    The caller (platform adapter) is responsible for:
      - Updating registry state to RUNNING before/after this call.
      - Pumping stdout/stderr into ``output`` if the runner does not do so itself.
      - Delivering the notification to the parent session when complete.
    """
    if record.command is None:
        raise ValueError("bash record must have command")
    from pathlib import Path

    return runner.start(
        command=record.command,
        cwd=Path(cwd),
        output=output,
        task_id=record.task_id,
        timeout=timeout,
        on_complete=on_complete,
        on_fail=on_fail,
    )
