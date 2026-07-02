from __future__ import annotations

from types import SimpleNamespace
import json
from pathlib import Path
from typing import Any

import pytest

from agent.sdk.kernel import Kernel
from agent.core.skills.registry import SkillRegistry
from agent.core.tools.base import ToolContext
from agent.platform.tools.builtins.skill_view import SkillViewTool


_SKILL = "---\nname: {name}\ndescription: test skill\n---\n\n# {name}\n\nBody."


class _Ctx:
    def __init__(
        self,
        *,
        workspace_root: Path,
        session_id: str = "session-1",
        tool_call_id: str = "call-1",
        metadata: dict[str, Any] | None = None,
    ) -> None:
        self.repo_root = workspace_root
        self.cwd = workspace_root
        self.session_id = session_id
        self.tool_call_id = tool_call_id
        self.session_metadata = {
            "workspace_root": str(workspace_root),
            "workspace_config_dirname": ".nanoassistant",
            **(metadata or {}),
        }
        self.registered: list[dict[str, str]] = []

    def register_invoked_skill(self, *, name: str, location: str, root_id: str) -> None:
        self.registered.append(
            {"name": name, "location": location, "root_id": root_id}
        )


def _write_skill(root: Path, name: str, body: str | None = None) -> Path:
    target = root / name / "SKILL.md"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(body or _SKILL.format(name=name), encoding="utf-8")
    return target


def test_skill_view_returns_skill_content_and_records_usage(tmp_path: Path) -> None:
    skill_root = tmp_path / ".nanoassistant" / "skills"
    skill_file = _write_skill(skill_root, "review-skill")
    tool = SkillViewTool(workspace_config_dirname=".nanoassistant")
    ctx = _Ctx(workspace_root=tmp_path)

    result = tool.run({"name": "review-skill"}, ctx)  # type: ignore[arg-type]

    assert result["success"] is True
    assert result["name"] == "review-skill"
    assert result["content"] == skill_file.read_text(encoding="utf-8")
    assert result["location"] == str(skill_file)
    usage = json.loads((skill_root / ".usage.json").read_text(encoding="utf-8"))
    assert usage["review-skill"]["use_count"] == 1
    assert usage["review-skill"]["source"] == "F1"
    assert usage["review-skill"]["session_refs"][0]["tool_call_id"] == "call-1"
    assert usage["review-skill"]["session_refs"][0]["location"] == str(skill_file)
    assert ctx.registered == [
        {
            "name": "review-skill",
            "location": str(skill_file),
            "root_id": str(skill_root.resolve()),
        }
    ]


def test_skill_view_failure_does_not_create_usage_file(tmp_path: Path) -> None:
    skill_root = tmp_path / ".nanoassistant" / "skills"
    skill_root.mkdir(parents=True)
    tool = SkillViewTool(workspace_config_dirname=".nanoassistant")
    ctx = _Ctx(workspace_root=tmp_path)

    result = tool.run({"name": "missing-skill"}, ctx)  # type: ignore[arg-type]

    assert result["success"] is False
    assert "not found" in result["error"]
    assert not (skill_root / ".usage.json").exists()
    assert ctx.registered == []


def test_skill_view_uses_existing_registry_precedence(tmp_path: Path) -> None:
    agent_root = tmp_path / "agent"
    shared_root = tmp_path / "shared"
    agent_skill = _write_skill(agent_root, "same-name", "agent copy")
    _write_skill(shared_root, "same-name", "shared copy")
    registry = SkillRegistry(search_roots=(agent_root, shared_root))
    tool = SkillViewTool(skill_root=agent_root, registry=registry)
    ctx = _Ctx(workspace_root=tmp_path)

    result = tool.run({"name": "same-name"}, ctx)  # type: ignore[arg-type]

    assert result["success"] is True
    assert result["content"] == "agent copy"
    assert result["location"] == str(agent_skill.resolve())


def test_skill_view_output_presenter_summarizes_auditable_details(
    tmp_path: Path,
) -> None:
    skill_root = tmp_path / "skills"
    skill_file = _write_skill(skill_root, "audit-skill")
    tool = SkillViewTool(
        skill_root=skill_root,
        registry=SkillRegistry(search_roots=(skill_root,)),
    )

    event = tool.presenter.format_end(
        {"name": "audit-skill"},
        type(
            "Result",
            (),
            {
                "output": {
                    "success": True,
                    "name": "audit-skill",
                    "location": str(skill_file),
                    "content": "abcdef",
                },
                "error": None,
            },
        )(),
        3,
    )

    assert event.summary == "查看 skill：audit-skill"
    assert event.detail is not None
    assert event.detail["name"] == "audit-skill"
    assert event.detail["location"] == str(skill_file)
    assert event.detail["content_preview"] == "abcdef"


def test_skill_view_tool_satisfies_tool_context_protocol() -> None:
    assert ToolContext.__name__ == "ToolContext"


@pytest.mark.asyncio
async def test_kernel_compact_reinjects_current_skill_content_from_usage_location(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    skill_root = workspace / ".nanoassistant" / "skills"
    skill_file = _write_skill(skill_root, "compact-skill", "old content")
    usage = {
        "compact-skill": {
            "source": "F1",
            "state": "active",
            "use_count": 1,
            "last_used_at": "2026-01-01T00:00:00Z",
            "session_refs": [
                {
                    "session_id": "sess-1",
                    "tool_call_id": "call-1",
                    "timestamp": "2026-01-01T00:00:00Z",
                    "location": str(skill_file),
                }
            ],
            "recent_call_keys": ["sess-1:call-1"],
            "uses_since_last_B": 1,
        }
    }
    (skill_root / ".usage.json").write_text(json.dumps(usage), encoding="utf-8")
    skill_file.write_text("current content", encoding="utf-8")

    appended: list[dict[str, Any]] = []

    class _Runtime:
        async def compact(self, session_id: str, *, workspace_root: Path | None = None):
            return SimpleNamespace(entry_id="compact-msg-1")

        def invalidate_session_cache(self, session_id: str) -> None:
            pass

    class _SessionService:
        def append_message(self, *args: Any, **kwargs: Any) -> SimpleNamespace:
            appended.append({"args": args, **kwargs})
            return SimpleNamespace(entry={"metadata": kwargs.get("metadata")})

    kernel = Kernel.__new__(Kernel)
    kernel._repo_root = workspace
    kernel._workspace_config_dirname = ".nanoassistant"
    kernel._skill_search_roots = ()
    kernel._c = SimpleNamespace(runtime=_Runtime(), session_service=_SessionService())

    await Kernel.compact(kernel, "sess-1", workspace_root=workspace)

    assert len(appended) == 1
    message = appended[0]
    assert message["role"] == "user"
    assert "<system-reminder>" in message["content"]
    assert "current content" in message["content"]
    assert "old content" not in message["content"]
    assert message["metadata"]["is_skill_reinjection"] is True
    refs = message["metadata"]["skill_reinjection_refs"]
    assert refs == [
        {
            "name": "compact-skill",
            "location": str(skill_file),
            "root_id": str(skill_root.resolve()),
        }
    ]
