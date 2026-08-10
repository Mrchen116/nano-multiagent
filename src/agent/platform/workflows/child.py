"""Adapter from Workflow Agent effects to the existing subagent runtime."""

from __future__ import annotations

import asyncio
import json
import subprocess
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from agent.core.llm.model_registry import provider_of
from agent.core.session.types import (
    INTERNAL_RUNTIME_KEY,
    PromptSlotSeed,
    PromptSlotText,
)
from agent.core.types import TurnResult
from agent.core.workflows import AgentCallSpec
from agent.platform.tools.subagent_types import apply_tool_deny, resolve_agent_type


_RETURN_VALUE_ADDENDUM = (
    "You are a Workflow child Agent. Your final text is the value returned to the "
    "Python orchestration script, not a human-facing chat reply. Return only the "
    "requested result. Do not spawn Agent or Workflow children."
)
_STRUCTURED_OUTPUT_TOOL = "WorkflowStructuredOutput"


@dataclass(slots=True)
class _ActiveAttempt:
    handle: Any
    restart_requested: bool = False
    stop_requested: bool = False


class WorkflowChildRunner:
    def __init__(
        self,
        *,
        context: Any,
        workflow_run_id: str,
        subagent_runner: Any,
        config_dirname: str,
        model_override: str | None = None,
    ) -> None:
        self._context = context
        self._workflow_run_id = workflow_run_id
        self._runner = subagent_runner
        self._config_dirname = config_dirname
        self._model_override = model_override
        self._active: dict[str, _ActiveAttempt] = {}
        self._usage: dict[str, dict[str, int]] = {}
        self._status: dict[str, str] = {}
        self._warnings: list[str] = []
        self._lock = threading.Lock()

    @property
    def warnings(self) -> tuple[str, ...]:
        with self._lock:
            return tuple(self._warnings)

    def usage_for(self, agent_call_id: str) -> dict[str, int] | None:
        with self._lock:
            usage = self._usage.get(agent_call_id)
            return dict(usage) if usage is not None else None

    def status_for(self, agent_call_id: str) -> str | None:
        with self._lock:
            return self._status.get(agent_call_id)

    def stop_agent(self, agent_call_id: str) -> bool:
        with self._lock:
            attempt = self._active.get(agent_call_id)
            if attempt is None:
                return False
            attempt.stop_requested = True
            attempt.handle.stop()
            return True

    def restart_agent(self, agent_call_id: str) -> bool:
        with self._lock:
            attempt = self._active.get(agent_call_id)
            if attempt is None:
                return False
            attempt.restart_requested = True
            attempt.handle.stop()
            return True

    def stop_all(self) -> None:
        with self._lock:
            attempts = tuple(self._active.values())
            for attempt in attempts:
                attempt.stop_requested = True
        for attempt in attempts:
            attempt.handle.stop()

    async def __call__(self, call: AgentCallSpec) -> Any:
        control = self._context.subagent_control
        if control is None:
            raise RuntimeError("Workflow child control is not configured")
        parent = control.directory.get(control.ref)
        if parent is None:
            raise RuntimeError("Workflow parent session is not available")
        type_definition = resolve_agent_type(call.agent_type)
        if self._context.parent_runtime_captured:
            parent_tools = self._context.parent_enabled_tools or ()
            parent_skills = self._context.parent_skills
        else:
            parent_tools = (
                parent.tool_allowlist
                if parent.tool_allowlist is not None
                else tuple(control.list_parent_enabled_tool_names())
            )
            parent_skills = parent.skills
        effective_tools = apply_tool_deny(
            parent_tools,
            (*type_definition.disallowed_tools, "agent", "Agent", "Workflow"),
        )
        if call.schema is not None:
            effective_tools = (*effective_tools, _STRUCTURED_OUTPUT_TOOL)
        child_workspace = self._context.workspace_root
        cleanup_worktree = False
        if call.isolation == "worktree":
            child_workspace = self._create_worktree(call)
            cleanup_worktree = True
        prompt_tail = type_definition.role_prompt_seed.tail + (
            PromptSlotText(name="workflow.return-value", text=_RETURN_VALUE_ADDENDUM),
        )
        if call.schema is not None:
            prompt_tail += (
                PromptSlotText(
                    name="workflow.structured-output",
                    text=(
                        "Return a JSON value matching this schema exactly:\n"
                        + json.dumps(call.schema, ensure_ascii=False, sort_keys=True)
                        + "\nYou MUST return it by calling WorkflowStructuredOutput. "
                        "Do not put the value in final prose. If validation fails, "
                        "correct the tool arguments and call it again."
                    ),
                ),
            )
        prompt_seed = PromptSlotSeed(
            head=type_definition.role_prompt_seed.head,
            body=type_definition.role_prompt_seed.body,
            custom=type_definition.role_prompt_seed.custom,
            tail=prompt_tail,
        )
        agent_call_id = f"wa_{call.start_ordinal:06d}"
        try:
            while True:
                model = self._resolve_model(call, control)
                if self._context.parent_runtime_captured:
                    effort = call.effort or self._context.parent_effort
                else:
                    effort_resolver = getattr(control, "resolve_reasoning_effort", None)
                    effort = call.effort or (
                        effort_resolver() if callable(effort_resolver) else None
                    )
                ref = control.create_subagent(
                    workspace_root=child_workspace,
                    skills=parent_skills,
                    tool_allowlist=effective_tools,
                    prompt_seed=prompt_seed,
                    metadata={
                        "kind": "workflow_subagent",
                        "agent_id": agent_call_id,
                        "workflow_run_id": self._workflow_run_id,
                        "workflow_parent_session_id": self._context.parent_session_id,
                        "agent_call_id": agent_call_id,
                        "description": call.label or call.prompt[:80],
                        "workspace_root": str(child_workspace),
                        "workflow_output_schema": call.schema,
                        "workflow_unattended": self._context.parent_run_origin
                        != "human",
                        INTERNAL_RUNTIME_KEY: {
                            "model": model,
                            "reasoning_effort": effort,
                        },
                    },
                    parent_session_id=self._context.parent_session_id,
                )
                starter = getattr(self._runner, "start_workflow_agent", None)
                if callable(starter):
                    handle = starter(
                        agent_session_id=ref.session_id,
                        parent_session_id=self._context.parent_session_id,
                        prompt=call.prompt,
                        workspace_root=child_workspace,
                        llm_session_id=self._context.parent_session_id,
                        model=model,
                        workflow_run_id=self._workflow_run_id,
                        agent_call_id=agent_call_id,
                    )
                else:
                    handle = self._runner.start_foreground(
                        agent_session_id=ref.session_id,
                        parent_session_id=self._context.parent_session_id,
                        prompt=call.prompt,
                        workspace_root=child_workspace,
                        llm_session_id=self._context.parent_session_id,
                        model=model,
                    )
                attempt = _ActiveAttempt(handle=handle)
                with self._lock:
                    self._active[agent_call_id] = attempt
                try:
                    turn = await asyncio.to_thread(handle.result)
                except Exception:
                    with self._lock:
                        restart = attempt.restart_requested
                        stopped = attempt.stop_requested
                    if restart:
                        continue
                    if stopped:
                        with self._lock:
                            self._status[agent_call_id] = "stopped"
                        return None
                    raise
                finally:
                    with self._lock:
                        if self._active.get(agent_call_id) is attempt:
                            self._active.pop(agent_call_id, None)
                with self._lock:
                    restart = attempt.restart_requested
                if restart:
                    continue
                usage = _turn_usage(turn)
                if usage is not None:
                    with self._lock:
                        self._usage[agent_call_id] = usage
                        self._status[agent_call_id] = "completed"
                else:
                    with self._lock:
                        self._status[agent_call_id] = "completed"
                return _extract_value(turn, call.schema)
        finally:
            if cleanup_worktree:
                self._cleanup_worktree(child_workspace)

    def _resolve_model(self, call: AgentCallSpec, control: Any) -> str | None:
        parent_model = (
            self._context.parent_model
            if self._context.parent_runtime_captured
            else control.resolve_run_model()
        )
        requested = self._model_override or call.model or parent_model
        if requested is None:
            return None
        try:
            provider_of(requested)
            return requested
        except (RuntimeError, ValueError):
            if parent_model is None:
                raise ValueError(f"Workflow child model is unavailable: {requested}")
            warning = (
                "workflow_model_substituted: "
                f"requested={requested}, resolved={parent_model}"
            )
            with self._lock:
                if warning not in self._warnings:
                    self._warnings.append(warning)
            return parent_model

    def _create_worktree(self, call: AgentCallSpec) -> Path:
        target = (
            self._context.workspace_root
            / self._config_dirname
            / "sessions"
            / self._context.parent_session_id
            / "workflows"
            / "runs"
            / self._workflow_run_id
            / "worktrees"
            / f"wa_{call.start_ordinal:06d}"
        )
        target.parent.mkdir(parents=True, exist_ok=True)
        result = subprocess.run(
            ["git", "worktree", "add", "--detach", str(target), "HEAD"],
            cwd=self._context.workspace_root,
            text=True,
            capture_output=True,
            check=False,
        )
        if result.returncode != 0:
            raise RuntimeError(
                "unable to create Workflow worktree: "
                + (result.stderr.strip() or result.stdout.strip())
            )
        return target

    def _cleanup_worktree(self, target: Path) -> None:
        status = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=target,
            text=True,
            capture_output=True,
            check=False,
        )
        if status.returncode != 0 or status.stdout.strip():
            return
        subprocess.run(
            ["git", "worktree", "remove", str(target)],
            cwd=self._context.workspace_root,
            text=True,
            capture_output=True,
            check=False,
        )


def _extract_value(turn: TurnResult, schema: Any) -> Any:
    text: str | None = None
    for message in reversed(turn.messages):
        if message.role == "assistant" and isinstance(message.content, str):
            text = message.content.strip()
            if text:
                break
    if schema is None:
        return text
    results = [
        result
        for result in turn.tool_results
        if result.name == _STRUCTURED_OUTPUT_TOOL
        and result.error is None
        and isinstance(result.output, dict)
    ]
    if not results:
        raise ValueError(
            "structured Workflow Agent did not call the StructuredOutput tool"
        )
    return dict(results[-1].output)


def _turn_usage(turn: TurnResult) -> dict[str, int] | None:
    usage = turn.usage
    if usage is None:
        return None
    return {
        "prompt_tokens": usage.prompt_tokens,
        "completion_tokens": usage.completion_tokens,
        "total_tokens": usage.total_tokens,
    }
