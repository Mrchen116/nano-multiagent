"""Regression coverage for Gateway-owned distill prompt construction."""

from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace

from personal_assistant.channels.web_relay_adapter import WebRelayAdapter
from personal_assistant.config.local_store import AgentWorkspaceConfig
from personal_assistant.gateway.agent_catalog import LiveAgentCatalog
from personal_assistant.gateway.distill_prompt import build_distill_prompt_handler
from personal_assistant.channels.base import InboundMessage, ReplyContext
from personal_assistant.gateway.session_binder import (
    GatewaySessionBinder,
    SessionBindingRequest,
)
from personal_assistant.gateway.session_keys import (
    build_conversation_session_key,
    build_external_session_key,
)


class _Kernel:
    """Expose just the local skill discovery used by the resolver."""

    def __init__(
        self, *, skills: tuple[str, ...] = ("conversation-skill-distiller",)
    ) -> None:
        self._skills = skills

    def list_skills(self, workspace_root: Path) -> list[SimpleNamespace]:
        del workspace_root
        return [SimpleNamespace(name=name) for name in self._skills]


class _BindingKernel:
    def __init__(self) -> None:
        self.next_session_id = "session-1"

    async def create_session(self, **_kwargs: object) -> SimpleNamespace:
        return SimpleNamespace(session_id=self.next_session_id)


def _bind_key(
    binder: GatewaySessionBinder,
    catalog: LiveAgentCatalog,
    *,
    session_key: str,
    conversation_id: str,
) -> None:
    message = InboundMessage(
        channel_name=WebRelayAdapter.name,
        text="source",
        external_user_id="user",
        external_chat_id=conversation_id,
        is_group=False,
        agent_id="source",
    )
    asyncio.run(
        binder.resolve(
            SessionBindingRequest(
                session_key=session_key,
                reply_context=ReplyContext(
                    channel_name=WebRelayAdapter.name,
                    target_chat_id=conversation_id,
                ),
                message=message,
            ),
            catalog.require("source"),
        )
    )


def _handler(
    tmp_path: Path,
    *,
    skills: tuple[str, ...] = ("conversation-skill-distiller",),
    configured_skills: tuple[str, ...] = (),
    skills_selection_mode: str | None = None,
    tool_allowlist: tuple[str, ...] = ("skill_view",),
    external_identity: tuple[str, str] | None = None,
):
    source_root = tmp_path / "source"
    execution_root = tmp_path / "execution"
    source = AgentWorkspaceConfig(agent_id="source", workspace_root=source_root)
    execution = AgentWorkspaceConfig(
        agent_id="execution",
        workspace_root=execution_root,
        skills=configured_skills,
        skills_selection_mode=skills_selection_mode,
        tool_allowlist=tool_allowlist,
    )
    catalog = LiveAgentCatalog((source, execution))
    binding_kernel = _BindingKernel()
    binder = GatewaySessionBinder(catalog=catalog, kernel=binding_kernel)
    session_key = (
        build_external_session_key(
            external_source=external_identity[0],
            external_chat_id=external_identity[1],
            agent_id="source",
        )
        if external_identity is not None
        else build_conversation_session_key(
            channel_name=WebRelayAdapter.name,
            conversation_id="source-conversation",
            agent_id="source",
        )
    )
    _bind_key(
        binder,
        catalog,
        session_key=session_key,
        conversation_id="source-conversation",
    )
    return (
        build_distill_prompt_handler(
            kernel=_Kernel(skills=skills),
            session_binder=binder,
            channel_name=WebRelayAdapter.name,
        ),
        source_root,
        (binder, binding_kernel, catalog),
    )


def test_gateway_resolves_its_local_binding_into_current_distill_prompt(
    tmp_path: Path,
) -> None:
    """The Gateway, not IM, supplies a complete ordinary-chat draft."""
    handler, source_root, _ = _handler(tmp_path)
    session_path = source_root / ".nanoassistant" / "sessions" / "session-1.jsonl"
    session_path.parent.mkdir(parents=True)
    session_path.write_text("{}\n", encoding="utf-8")

    result = asyncio.run(
        handler(
            {
                "sources": [
                    {
                        "conversation_id": "source-conversation",
                        "source_agent_id": "source",
                    }
                ],
                "execution_agent_id": "execution",
                "target_scope": "agent",
            }
        )
    )

    assert result == {"prompt": _prompt_with_path(session_path)}


def test_gateway_returns_no_partial_prompt_when_any_source_or_capability_is_unavailable(
    tmp_path: Path,
) -> None:
    """A missing source or unavailable execution capability stops before a draft."""
    handler, _, _ = _handler(tmp_path)

    missing_source = asyncio.run(
        handler(
            {
                "sources": [
                    {
                        "conversation_id": "source-conversation",
                        "source_agent_id": "source",
                    }
                ],
                "execution_agent_id": "execution",
                "target_scope": "agent",
            }
        )
    )

    assert missing_source == {
        "error_code": "source_unavailable",
        "message": "source session file is unavailable",
    }

    missing_skill_view, source_root, _ = _handler(tmp_path, tool_allowlist=())
    session_path = source_root / ".nanoassistant" / "sessions" / "session-1.jsonl"
    session_path.parent.mkdir(parents=True)
    session_path.write_text("{}\n", encoding="utf-8")

    missing_skill_view_result = asyncio.run(
        missing_skill_view(
            {
                "sources": [
                    {
                        "conversation_id": "source-conversation",
                        "source_agent_id": "source",
                    }
                ],
                "execution_agent_id": "execution",
                "target_scope": "agent",
            }
        )
    )

    assert missing_skill_view_result == {
        "error_code": "skill_view_unavailable",
        "message": "execution agent lacks skill_view",
    }


def test_gateway_rejects_explicit_empty_distiller_selection_before_source_resolution(
    tmp_path: Path,
) -> None:
    handler, source_root, _ = _handler(
        tmp_path,
        configured_skills=(),
        skills_selection_mode="explicit_allowlist",
    )
    session_path = source_root / ".nanoassistant" / "sessions" / "session-1.jsonl"
    session_path.parent.mkdir(parents=True)
    session_path.write_text("{}\n", encoding="utf-8")

    result = asyncio.run(
        handler(
            {
                "sources": [
                    {
                        "conversation_id": "source-conversation",
                        "source_agent_id": "source",
                    }
                ],
                "execution_agent_id": "execution",
                "target_scope": "agent",
            }
        )
    )

    assert result == {
        "error_code": "distiller_unavailable",
        "message": "execution agent lacks the distiller skill",
    }
    assert "prompt" not in result


def test_gateway_preserves_external_shadow_binding_fallback(tmp_path: Path) -> None:
    """Existing external shadows still resolve through their durable external key."""
    handler, source_root, binding = _handler(
        tmp_path,
        external_identity=("feishu", "chat-1"),
    )
    session_path = source_root / ".nanoassistant" / "sessions" / "session-1.jsonl"
    session_path.parent.mkdir(parents=True)
    session_path.write_text("{}\n", encoding="utf-8")

    fallback_result = asyncio.run(
        handler(
            {
                "sources": [
                    {
                        "conversation_id": "shadow-conversation",
                        "source_agent_id": "source",
                        "external_source": "feishu",
                        "external_chat_id": "chat-1",
                    }
                ],
                "execution_agent_id": "execution",
                "target_scope": "agent",
            }
        )
    )

    assert fallback_result["prompt"] == _prompt_with_path(session_path)

    normal_path = source_root / ".nanoassistant" / "sessions" / "normal-session.jsonl"
    normal_path.write_text("{}\n", encoding="utf-8")
    binder, binding_kernel, catalog = binding
    binding_kernel.next_session_id = "normal-session"
    _bind_key(
        binder,
        catalog,
        session_key=build_conversation_session_key(
            channel_name=WebRelayAdapter.name,
            conversation_id="shadow-conversation",
            agent_id="source",
        ),
        conversation_id="shadow-conversation",
    )

    normal_result = asyncio.run(
        handler(
            {
                "sources": [
                    {
                        "conversation_id": "shadow-conversation",
                        "source_agent_id": "source",
                        "external_source": "feishu",
                        "external_chat_id": "chat-1",
                    }
                ],
                "execution_agent_id": "execution",
                "target_scope": "agent",
            }
        )
    )

    assert normal_result["prompt"] == _prompt_with_path(normal_path)


def _prompt_with_path(session_path: Path) -> str:
    """Return the existing ordinary-chat prompt format for one local path."""
    return "\n".join(
        [
            "/skill:conversation-skill-distiller",
            "source_jsonl_paths:",
            f"  {session_path.resolve()}",
            "execution_agent_id: execution",
            "target_scope: agent",
            "",
            "请基于上述会话 transcript，总结我反复使用且值得复用的工作方式，直接生成并写入一个 agent 级 skill。重点关注：",
            "- 触发这个 skill 的场景",
            "- 应遵循的步骤/检查点",
            "- 失败或边界情况",
            "如果这些会话不足以形成稳定模式，请说明原因，不要创建 skill。",
        ]
    )
