from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pytest

from unittest.mock import MagicMock

from agent.core.errors import ToolError
from agent.core.types import Message, TurnResult
from agent.core.hooks.context import HookContext
from agent.platform.config.resolver import ConfigResolver
from agent.products.base import ProductProfile
from agent.platform.http_api.app import create_app


@dataclass(frozen=True, slots=True)
class _Session:
    session_id: str


class _FakeStore:
    def __init__(self, tmp_path: Path) -> None:
        self._tmp_path = tmp_path

    def resolve_path(self, session_id: str, *, parent_session_id: str | None = None) -> Path:
        return self._tmp_path / f"{session_id}.jsonl"

    def find_session_by_metadata(self, *, parent_session_id, match):
        return None


class _RuntimeStub:
    def __init__(self, *, config_resolver: ConfigResolver, tmp_path: Path | None = None) -> None:
        self.config_resolver = config_resolver
        self.created = 0
        self._session_manager = MagicMock()
        self._session_manager.store = _FakeStore(tmp_path or Path("/tmp"))

    async def create_session(
        self,
        *,
        workspace_root: Path,
        title: str | None = None,
        system_prompt: str | None = None,
        skills: tuple[str, ...] | None = None,
        tool_allowlist: tuple[str, ...] | None = None,
        metadata=None,
    ) -> _Session:
        del workspace_root, title, system_prompt, skills, tool_allowlist, metadata
        self.created += 1
        return _Session(session_id=f"sess_task_with_resolver_{self.created}")

    async def run(
        self,
        session_id: str,
        parts,
        *,
        stream: bool = True,
        llm_session_id: str | None = None,
        controller=None,
        parent_session_id: str | None = None,
    ) -> TurnResult:
        del stream, llm_session_id, controller, parent_session_id
        return TurnResult(
            session_id=session_id,
            turn_id="turn_task_with_resolver",
            messages=(Message(message_id="msg_task_with_resolver", role="assistant", content="ok"),),
            completed=True,
            stop_reason="completed",
        )

    async def continue_turn(
        self,
        session_id: str,
        *,
        stream: bool = True,
        llm_session_id: str | None = None,
    ) -> TurnResult:
        return await self.run(
            session_id,
            [{"type": "text", "text": "continue"}],
            stream=stream,
            llm_session_id=llm_session_id,
            parent_session_id=None,
        )


def _make_profile(global_home: Path) -> ProductProfile:
    return ProductProfile(
        product_id="resolver_agent",
        display_name="Resolver Agent",
        config_namespace="resolver-agent",
        global_config_home=global_home,
        workspace_config_dirname=".resolver-agent",
        session_db_filename="sessions.sqlite3",
    )


def _write_skill(root: Path, name: str) -> None:
    skill_dir = root / name
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text(
        f"---\nname: {name}\ndescription: {name} description\n---\n{name}\n",
        encoding="utf-8",
    )


async def test_agent_tool_accepts_resolver_workspace_skill(tmp_path: Path) -> None:
    profile = _make_profile(tmp_path / ".resolver-global")
    resolver = ConfigResolver(profile=profile, workspace_root=tmp_path)
    _write_skill(tmp_path / ".resolver-agent" / "skills", "resolver-skill")
    _write_skill(tmp_path / ".codex" / "skills", "legacy-only")

    app = create_app(runtime=_RuntimeStub(config_resolver=resolver, tmp_path=tmp_path), repo_root=tmp_path, product_profile=profile)

    result = await app.state.tool_registry.execute(
        "agent",
        {
            "run_in_background": False,
            "load_skills": ["resolver-skill"],
            "description": "delegate task",
            "prompt": "run task",
            "subagent_type": "oracle",
        },
        hook_context=HookContext(session_id="sess_main", repo_root=tmp_path),
    )

    assert result["status"] == "completed"
    assert result["content"] == "ok"


async def test_agent_tool_rejects_legacy_codex_skill_when_runtime_has_resolver(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CODEX_HOME", str(tmp_path / ".codex-home"))
    profile = _make_profile(tmp_path / ".resolver-global")
    resolver = ConfigResolver(profile=profile, workspace_root=tmp_path)
    _write_skill(tmp_path / ".resolver-agent" / "skills", "legacy-only")
    _write_skill(tmp_path / ".codex-home" / "skills", "legacy-home-only")

    app = create_app(runtime=_RuntimeStub(config_resolver=resolver, tmp_path=tmp_path), repo_root=tmp_path, product_profile=profile)

    with pytest.raises(ToolError, match="unknown skills requested"):
        await app.state.tool_registry.execute(
            "agent",
            {
                "run_in_background": False,
                "load_skills": ["legacy-only", "legacy-home-only"],
                "description": "delegate task",
                "prompt": "run task",
                "subagent_type": "oracle",
            },
            hook_context=HookContext(session_id="sess_main", repo_root=tmp_path),
        )
