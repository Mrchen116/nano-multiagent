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
from agent.core.session.types import PromptSlotSeed
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


class _ParentSession:
    """Stands in for `directory.get(control.ref)` — the parent's persisted config."""

    def __init__(
        self,
        *,
        tool_allowlist: tuple[str, ...] | None,
        skills: tuple[str, ...] | None,
    ) -> None:
        self.tool_allowlist = tool_allowlist
        self.skills = skills


class _Directory:
    def __init__(self, session: _ParentSession | None) -> None:
        self._session = session

    def get(self, ref: Any) -> _ParentSession | None:
        del ref
        return self._session


class _Control:
    """Fakes the `_SessionSubagentControl` surface `AgentTool` depends on.

    feat-474: `AgentTool` now reads the parent's `tool_allowlist`/`skills` via
    `control.directory.get(control.ref)` and, when the parent has no persisted
    allowlist, falls back to `control.list_parent_enabled_tool_names()` — this
    fake mirrors both paths so tests can exercise either.
    """

    def __init__(
        self,
        workspace_root: Path,
        *,
        parent_tool_allowlist: tuple[str, ...] | None = (
            "read",
            "write",
            "edit",
            "bash",
            "agent",
            "skill_manage",
        ),
        parent_skills: tuple[str, ...] | None = (),
        active_enabled_tools: tuple[str, ...] = (),
    ) -> None:
        self.workspace_root = workspace_root
        self.ref = object()
        self.directory = _Directory(
            _ParentSession(tool_allowlist=parent_tool_allowlist, skills=parent_skills)
        )
        self._active_enabled_tools = active_enabled_tools
        self.model = "parent-model"
        self.created: list[dict[str, Any]] = []
        self.found: dict[str, Any] | None = None

    def resolve_run_model(self) -> str:
        return self.model

    def list_parent_enabled_tool_names(self) -> tuple[str, ...]:
        return self._active_enabled_tools

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
    foreground_timeout: bool = False,
    parent_tool_allowlist: tuple[str, ...] | None = (
        "read",
        "write",
        "edit",
        "bash",
        "agent",
        "skill_manage",
    ),
    parent_skills: tuple[str, ...] | None = (),
    active_enabled_tools: tuple[str, ...] = (),
) -> tuple[AgentTool, ToolContext, _Control, _Runner, BackgroundTaskRegistry]:
    control = _Control(
        tmp_path,
        parent_tool_allowlist=parent_tool_allowlist,
        parent_skills=parent_skills,
        active_enabled_tools=active_enabled_tools,
    )
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

    result = tool.run(_new_agent_args(run_in_background=False), context)

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

    result = tool.run(_new_agent_args(run_in_background=False), context)
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
            "description": "inspect subsystem",
            "agent_id": launched["agent_id"],
            "prompt": "Also inspect shutdown behavior.",
        },
        context,
    )

    assert result["status"] == "message_queued"
    assert runner.background_handle.messages == ["Also inspect shutdown behavior."]
    runner.background_handle.stop()
    with pytest.raises(ToolError, match="did not confirm live delivery"):
        tool.run(
            {
                "description": "inspect subsystem",
                "agent_id": launched["agent_id"],
                "prompt": "This must not be falsely acknowledged.",
            },
            context,
        )


def test_terminal_continuation_resumes_same_conversation(tmp_path: Path) -> None:
    tool, context, _control, runner, registry = _make_tool(tmp_path)
    launched = tool.run(_new_agent_args(), context)
    registry.complete(launched["agent_id"], result_text="done")

    result = tool.run(
        {
            "description": "inspect subsystem",
            "agent_id": launched["agent_id"],
            "prompt": "Continue with tests.",
        },
        context,
    )

    assert result["status"] == "async_launched"
    assert runner.start_calls[-1]["agent_session_id"] == "subagent-session"
    assert runner.start_calls[-1]["model"] == "parent-model"
    # bugfix-474-fix1: the resumed result carries the record's real
    # agent_type so the presenter can show it instead of guessing.
    assert result["agent_type"] == "general-purpose"


def test_running_continuation_message_queued_carries_real_agent_type(
    tmp_path: Path,
) -> None:
    # bugfix-474-fix1: a still-running continuation's message_queued output
    # must also surface the record's real agent_type — the presenter has no
    # other way to distinguish an Explore/Plan follow-up from general-purpose.
    tool, context, _control, _runner, _registry = _make_tool(tmp_path)
    launched = tool.run(_new_agent_args(subagent_type="Explore"), context)

    result = tool.run(
        {
            "description": "inspect subsystem",
            "agent_id": launched["agent_id"],
            "prompt": "Keep exploring.",
        },
        context,
    )

    assert result["status"] == "message_queued"
    assert result["agent_type"] == "Explore"


def test_cold_continuation_rehydrates_through_control(tmp_path: Path) -> None:
    tool, context, control, runner, _registry = _make_tool(tmp_path)
    control.found = {
        "session_id": "cold-subagent",
        "metadata": {
            "description": "cold task",
            "agent_type": "Explore",
        },
        "output_path": tmp_path / "cold.jsonl",
    }

    result = tool.run(
        {
            "agent_id": "a-cold",
            "description": "cold task",
            "prompt": "Resume from disk.",
        },
        context,
    )

    assert result["status"] == "async_launched"
    assert runner.start_calls[-1]["agent_session_id"] == "cold-subagent"
    # bugfix-474-fix1: rehydrated-from-JSONL type also flows into the result
    # so the presenter shows the real type, not a general-purpose guess.
    assert result["agent_type"] == "Explore"


def test_unknown_cold_agent_fails_explicitly(tmp_path: Path) -> None:
    tool, context, _control, _runner, _registry = _make_tool(tmp_path)

    with pytest.raises(ToolError) as exc_info:
        tool.run(
            {
                "agent_id": "a-missing",
                "description": "missing task",
                "prompt": "Resume.",
            },
            context,
        )

    assert exc_info.value.details["code"] == "agent_not_found"


@pytest.mark.parametrize(
    ("overrides", "match"),
    [
        ({"description": ""}, "description"),
        ({"prompt": ""}, "prompt"),
    ],
)
def test_new_agent_validation(
    tmp_path: Path, overrides: dict[str, Any], match: str
) -> None:
    tool, context, _control, _runner, _registry = _make_tool(tmp_path)

    with pytest.raises(ToolError, match=match):
        tool.run(_new_agent_args(**overrides), context)


def test_missing_control_fails_without_reaching_wiring(tmp_path: Path) -> None:
    safety = ToolSafety(repo_root=tmp_path, config=ToolSafetyConfig())
    context = ToolContext(repo_root=tmp_path, cwd=tmp_path, safety=safety)

    with pytest.raises(ToolError, match="subagent control is not configured"):
        AgentTool().run(_new_agent_args(), context)


# ---------------------------------------------------------------------------
# feat-474: built-in agent type resolution, tool deny sets, skills/prompt_seed
# ---------------------------------------------------------------------------


def test_default_omitted_type_resolves_general_purpose_with_full_parent_tools(
    tmp_path: Path,
) -> None:
    tool, context, control, _runner, _registry = _make_tool(
        tmp_path,
        parent_tool_allowlist=(
            "read",
            "write",
            "edit",
            "bash",
            "agent",
            "skill_manage",
        ),
    )

    result = tool.run(_new_agent_args(), context)

    assert result["status"] == "async_launched"
    created = control.created[0]
    assert created["tool_allowlist"] == [
        "read",
        "write",
        "edit",
        "bash",
        "agent",
        "skill_manage",
    ]
    assert created["metadata"]["agent_type"] == "general-purpose"


@pytest.mark.parametrize("type_name", ["Explore", "Plan"])
def test_read_only_types_drop_write_edit_agent_skill_manage(
    tmp_path: Path, type_name: str
) -> None:
    tool, context, control, _runner, _registry = _make_tool(
        tmp_path,
        parent_tool_allowlist=(
            "read",
            "write",
            "edit",
            "bash",
            "agent",
            "skill_manage",
            "web_fetch",
        ),
    )

    result = tool.run(_new_agent_args(subagent_type=type_name), context)

    assert result["status"] == "async_launched"
    created = control.created[0]
    assert created["tool_allowlist"] == ["read", "bash", "web_fetch"]
    assert created["metadata"]["agent_type"] == type_name


def test_parent_none_allowlist_falls_back_to_active_enabled_tools(
    tmp_path: Path,
) -> None:
    """spec: parent `tool_allowlist=None` (product default) still yields an
    explicit child allowlist, resolved via the control's narrow window rather
    than staying `None` (which would let the child inherit the full registry —
    potentially wider than the parent)."""
    tool, context, control, _runner, _registry = _make_tool(
        tmp_path,
        parent_tool_allowlist=None,
        active_enabled_tools=("read", "bash", "agent"),
    )

    result = tool.run(_new_agent_args(), context)

    assert result["status"] == "async_launched"
    assert control.created[0]["tool_allowlist"] == ["read", "bash", "agent"]


@pytest.mark.parametrize("bad_name", ["oracle", "explore", "PLAN", "general_purpose"])
def test_unknown_or_wrong_case_type_fails_with_available_agents(
    tmp_path: Path, bad_name: str
) -> None:
    tool, context, control, _runner, _registry = _make_tool(tmp_path)

    with pytest.raises(ToolError) as exc_info:
        tool.run(_new_agent_args(subagent_type=bad_name), context)

    assert "Available agents: general-purpose, Explore, Plan" in str(exc_info.value)
    assert control.created == []


@pytest.mark.parametrize("skills", [None, (), ("known-skill", "another-skill")])
def test_child_skills_mirror_parent_without_folding(
    tmp_path: Path, skills: tuple[str, ...] | None
) -> None:
    tool, context, control, _runner, _registry = _make_tool(
        tmp_path, parent_skills=skills
    )

    result = tool.run(_new_agent_args(), context)

    assert result["status"] == "async_launched"
    assert control.created[0]["skills"] == skills


def test_type_specific_prompt_seed_is_passed_to_create_subagent(
    tmp_path: Path,
) -> None:
    tool, context, control, _runner, _registry = _make_tool(tmp_path)

    tool.run(_new_agent_args(subagent_type="Explore"), context)

    seed = control.created[0]["prompt_seed"]
    assert isinstance(seed, PromptSlotSeed)
    body_text = " ".join(item.text for item in seed.body)
    assert "READ-ONLY" in body_text


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
