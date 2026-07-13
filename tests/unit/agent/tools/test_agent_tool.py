"""Behavior tests for the Agent tool's conversation-scoped control port."""

from __future__ import annotations

import time
from concurrent.futures import TimeoutError as FutureTimeoutError
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from agent.core.background_tasks.models import BackgroundTaskStatus
from agent.core.background_tasks.registry import BackgroundTaskRegistry
from agent.core.errors import ToolError
from agent.core.skills import SkillMetadata
from agent.core.tools.base import ToolContext
from agent.platform.tools.builtins.agent import AgentTool
from agent.platform.tools.safety import ToolSafety, ToolSafetyConfig


class _Turn:
    messages = (SimpleNamespace(role="assistant", content="subagent result"),)
    usage = None
    tool_calls = ()


class _Handle:
    def __init__(self, *, timeout_once: bool = False) -> None:
        self._timeout_once = timeout_once
        self.messages: list[str] = []
        self.stopped = False

    def stop(self) -> None:
        self.stopped = True

    def send_message(self, prompt: str) -> bool:
        if self.stopped:
            return False
        self.messages.append(prompt)
        return True

    def result(self, timeout: float | None = None) -> _Turn:
        if timeout is not None and self._timeout_once:
            self._timeout_once = False
            raise FutureTimeoutError
        return _Turn()


class _Runner:
    def __init__(self, *, foreground_timeout: bool = False) -> None:
        self.foreground_timeout = foreground_timeout
        self.start_calls: list[dict[str, Any]] = []
        self.foreground_calls: list[dict[str, Any]] = []
        self.background_handle = _Handle()

    def start(self, **kwargs: Any) -> _Handle:
        self.start_calls.append(dict(kwargs))
        return self.background_handle

    def start_foreground(self, **kwargs: Any) -> _Handle:
        self.foreground_calls.append(dict(kwargs))
        return _Handle(timeout_once=self.foreground_timeout)


class _Control:
    def __init__(self, workspace_root: Path, *, skills: tuple[str, ...] = ()) -> None:
        self.workspace_root = workspace_root
        self.model = "parent-model"
        self.skills = skills
        self.created: list[dict[str, Any]] = []
        self.found: dict[str, Any] | None = None

    def resolve_run_model(self) -> str:
        return self.model

    def resolve_available_skills(
        self,
        workspace_root: Path,
        *,
        include_names: tuple[str, ...] | None = None,
    ) -> tuple[SkillMetadata, ...]:
        del workspace_root
        names = self.skills if include_names is None else include_names
        known = set(self.skills)
        return tuple(
            SkillMetadata(
                name=name,
                description=f"{name} description",
                location=self.workspace_root,
                base_dir=self.workspace_root,
            )
            for name in names
            if name in known
        )

    def create_subagent(self, **kwargs: Any) -> SimpleNamespace:
        self.created.append(dict(kwargs))
        return SimpleNamespace(session_id="subagent-session")

    def output_path(
        self,
        session_id: str,
        *,
        workspace_root: Path,
        parent_session_id: str,
    ) -> Path:
        return workspace_root / f"{parent_session_id}-{session_id}.jsonl"

    def find_subagent(self, agent_id: str) -> dict[str, Any] | None:
        del agent_id
        return self.found


def _make_tool(
    tmp_path: Path,
    *,
    skills: tuple[str, ...] = (),
    foreground_timeout: bool = False,
) -> tuple[AgentTool, ToolContext, _Control, _Runner, BackgroundTaskRegistry]:
    control = _Control(tmp_path, skills=skills)
    runner = _Runner(foreground_timeout=foreground_timeout)
    registry = BackgroundTaskRegistry()
    wiring = SimpleNamespace(registry=registry, subagent_runner=runner)
    safety = ToolSafety(repo_root=tmp_path, config=ToolSafetyConfig())
    context = ToolContext(
        repo_root=tmp_path,
        cwd=tmp_path,
        safety=safety,
        session_id="parent-session",
        subagent_control=control,
    )
    return AgentTool(wiring=wiring), context, control, runner, registry


def _new_agent_args(**overrides: Any) -> dict[str, Any]:
    args: dict[str, Any] = {
        "description": "inspect subsystem",
        "prompt": "Inspect the subsystem and report findings.",
        "subagent_type": "explore",
        "load_skills": [],
        "run_in_background": True,
    }
    args.update(overrides)
    return args


def test_background_launch_uses_conversation_control(tmp_path: Path) -> None:
    tool, context, control, runner, registry = _make_tool(tmp_path)

    result = tool.run(_new_agent_args(), context)

    assert result["status"] == "async_launched"
    record = registry.get(result["agent_id"])
    assert record is not None
    assert record.agent_session_id == "subagent-session"
    assert control.created[0]["parent_session_id"] == "parent-session"
    assert runner.start_calls[0]["llm_session_id"] == "parent-session"
    assert runner.start_calls[0]["model"] == "parent-model"


def test_foreground_completion_stays_out_of_background_registry(
    tmp_path: Path,
) -> None:
    tool, context, _control, runner, registry = _make_tool(tmp_path)

    result = tool.run(
        _new_agent_args(run_in_background=False, timeout_seconds=0.1), context
    )

    assert result == {
        "status": "completed",
        "content": "subagent result",
        "agent_id": result["agent_id"],
    }
    assert registry.get(result["agent_id"]) is None
    assert runner.foreground_calls[0]["llm_session_id"] == "parent-session"
    assert runner.foreground_calls[0]["model"] == "parent-model"


def test_foreground_timeout_hands_off_and_watcher_completes(tmp_path: Path) -> None:
    tool, context, _control, _runner, registry = _make_tool(
        tmp_path, foreground_timeout=True
    )

    result = tool.run(
        _new_agent_args(run_in_background=False, timeout_seconds=0.01), context
    )
    assert result["status"] == "async_launched"

    for _ in range(50):
        record = registry.get(result["agent_id"])
        if record is not None and record.status == BackgroundTaskStatus.COMPLETED:
            break
        time.sleep(0.01)
    record = registry.get(result["agent_id"])
    assert record is not None
    assert record.status == BackgroundTaskStatus.COMPLETED
    assert record.result_text == "subagent result"


def test_running_continuation_requires_live_delivery(tmp_path: Path) -> None:
    tool, context, _control, runner, registry = _make_tool(tmp_path)
    launched = tool.run(_new_agent_args(), context)

    result = tool.run(
        {
            "agent_id": launched["agent_id"],
            "description": "inspect subsystem",
            "prompt": "Also inspect shutdown behavior.",
            "load_skills": [],
        },
        context,
    )

    assert result["status"] == "message_queued"
    assert runner.background_handle.messages == ["Also inspect shutdown behavior."]
    runner.background_handle.stop()
    with pytest.raises(ToolError, match="did not confirm live delivery"):
        tool.run(
            {
                "agent_id": launched["agent_id"],
                "description": "inspect subsystem",
                "prompt": "This must not be falsely acknowledged.",
                "load_skills": [],
            },
            context,
        )


def test_terminal_continuation_resumes_same_conversation(tmp_path: Path) -> None:
    tool, context, _control, runner, registry = _make_tool(tmp_path)
    launched = tool.run(_new_agent_args(), context)
    registry.complete(launched["agent_id"], result_text="done")

    result = tool.run(
        {
            "agent_id": launched["agent_id"],
            "description": "inspect subsystem",
            "prompt": "Continue with tests.",
            "load_skills": [],
        },
        context,
    )

    assert result["status"] == "async_launched"
    assert runner.start_calls[-1]["agent_session_id"] == "subagent-session"
    assert runner.start_calls[-1]["model"] == "parent-model"


def test_cold_continuation_rehydrates_through_control(tmp_path: Path) -> None:
    tool, context, control, runner, _registry = _make_tool(tmp_path)
    control.found = {
        "session_id": "cold-subagent",
        "metadata": {
            "description": "cold task",
            "agent_type": "explore",
        },
        "output_path": tmp_path / "cold.jsonl",
    }

    result = tool.run(
        {
            "agent_id": "a-cold",
            "description": "cold task",
            "prompt": "Resume from disk.",
            "load_skills": [],
        },
        context,
    )

    assert result["status"] == "async_launched"
    assert runner.start_calls[-1]["agent_session_id"] == "cold-subagent"


def test_unknown_cold_agent_fails_explicitly(tmp_path: Path) -> None:
    tool, context, _control, _runner, _registry = _make_tool(tmp_path)

    with pytest.raises(ToolError) as exc_info:
        tool.run(
            {
                "agent_id": "a-missing",
                "description": "missing task",
                "prompt": "Resume.",
                "load_skills": [],
            },
            context,
        )

    assert exc_info.value.details["code"] == "agent_not_found"


@pytest.mark.parametrize(
    ("overrides", "match"),
    [
        ({"description": ""}, "description"),
        ({"prompt": ""}, "prompt"),
        ({"category": "coding"}, "mutually exclusive"),
    ],
)
def test_new_agent_validation(
    tmp_path: Path, overrides: dict[str, Any], match: str
) -> None:
    tool, context, _control, _runner, _registry = _make_tool(tmp_path)

    with pytest.raises(ToolError, match=match):
        tool.run(_new_agent_args(**overrides), context)


def test_skill_validation_uses_conversation_control(tmp_path: Path) -> None:
    tool, context, _control, _runner, _registry = _make_tool(
        tmp_path, skills=("known-skill",)
    )

    result = tool.run(_new_agent_args(load_skills=["known-skill"]), context)
    assert result["status"] == "async_launched"

    with pytest.raises(ToolError) as exc_info:
        tool.run(_new_agent_args(load_skills=["missing-skill"]), context)
    assert exc_info.value.details["missing_skills"] == ["missing-skill"]


def test_missing_control_fails_without_reaching_wiring(tmp_path: Path) -> None:
    safety = ToolSafety(repo_root=tmp_path, config=ToolSafetyConfig())
    context = ToolContext(repo_root=tmp_path, cwd=tmp_path, safety=safety)

    with pytest.raises(ToolError, match="subagent control is not configured"):
        AgentTool().run(_new_agent_args(), context)


@pytest.mark.parametrize(
    ("output", "snippet"),
    [
        (
            {
                "status": "async_launched",
                "agent_id": "a1",
                "description": "task",
                "output_file": "/tmp/out",
            },
            "Background agent launched",
        ),
        (
            {
                "status": "message_queued",
                "agent_id": "a1",
                "description": "task",
                "output_file": "/tmp/out",
            },
            "Message queued for agent",
        ),
        (
            {"status": "completed", "agent_id": "a1", "content": "done"},
            "done",
        ),
    ],
)
def test_result_serialization(output: dict[str, Any], snippet: str) -> None:
    assert snippet in AgentTool().serialize_result(output)
