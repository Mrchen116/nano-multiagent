"""Gateway-owned resolution of historical conversation distill prompts."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

from personal_assistant.channels.web_relay_adapter import WebRelayAdapter
from personal_assistant.gateway.session_binder import GatewaySessionBinder
from personal_assistant.gateway.session_keys import (
    build_conversation_session_key,
    build_external_session_key,
)
from personal_assistant.config.skill_selection import (
    EXPLICIT_ALLOWLIST,
    effective_skills_selection_mode,
)


_DISTILL_SKILL = "conversation-skill-distiller"


def build_distill_prompt_handler(
    *,
    kernel: Any,
    session_binder: GatewaySessionBinder,
    channel_name: str = WebRelayAdapter.name,
):
    """Build the Gateway handler for one IM distill-prompt control request.

    The Gateway already owns both the durable conversation binding and the local
    workspace.  This handler resolves the binding into the existing ordinary-chat
    prompt without exposing that filesystem work to IM.
    """

    async def handle(payload: Mapping[str, object]) -> Mapping[str, object]:
        execution_agent_id = _text(payload.get("execution_agent_id"))
        target_scope = _text(payload.get("target_scope"))
        source_payloads = payload.get("sources")
        if not execution_agent_id or target_scope not in {"agent", "global"}:
            return _error("invalid_request", "distill request is invalid")
        if not isinstance(source_payloads, list) or not source_payloads:
            return _error("invalid_request", "at least one source is required")

        try:
            execution_agent = session_binder.current_agent(execution_agent_id)
        except ValueError:
            return _error("execution_unavailable", "execution agent is unavailable")
        readiness_error = _readiness_error(
            kernel=kernel, execution_agent=execution_agent
        )
        if readiness_error is not None:
            return readiness_error

        source_paths: list[Path] = []
        for item in source_payloads:
            if not isinstance(item, Mapping):
                return _error("invalid_request", "distill source is invalid")
            conversation_id = _text(item.get("conversation_id"))
            source_agent_id = _text(item.get("source_agent_id"))
            if not conversation_id or not source_agent_id:
                return _error("invalid_request", "distill source is invalid")
            source = session_binder.capture_binding_provenance(
                build_conversation_session_key(
                    channel_name=channel_name,
                    conversation_id=conversation_id,
                    agent_id=source_agent_id,
                ),
                expected_agent_id=source_agent_id,
            )
            if source is None:
                external_source = _text(item.get("external_source"))
                external_chat_id = _text(item.get("external_chat_id"))
                if external_source and external_chat_id:
                    source = session_binder.capture_binding_provenance(
                        build_external_session_key(
                            external_source=external_source,
                            external_chat_id=external_chat_id,
                            agent_id=source_agent_id,
                        ),
                        expected_agent_id=source_agent_id,
                    )
            if source is None:
                return _error(
                    "source_unavailable", "source session binding is unavailable"
                )
            session_path = (
                source.agent.config.workspace_root
                / ".nanoassistant"
                / "sessions"
                / f"{source.binding.kernel_session_id}.jsonl"
            )
            if not session_path.is_file():
                return _error(
                    "source_unavailable", "source session file is unavailable"
                )
            source_paths.append(session_path.resolve())

        return {
            "prompt": _build_prompt(
                source_paths=source_paths,
                execution_agent_id=execution_agent_id,
                target_scope=target_scope,
            )
        }

    return handle


def _readiness_error(
    *, kernel: Any, execution_agent: Any
) -> Mapping[str, object] | None:
    """Return a current local capability error before any source is resolved."""
    configured_skills = set(execution_agent.config.skills)
    selection_mode = effective_skills_selection_mode(
        execution_agent.config.skills_selection_mode,
        execution_agent.config.skills,
    )
    if selection_mode == EXPLICIT_ALLOWLIST and _DISTILL_SKILL not in configured_skills:
        return _error(
            "distiller_unavailable", "execution agent lacks the distiller skill"
        )
    discovered_skills = {
        str(getattr(skill, "name", ""))
        for skill in kernel.list_skills(execution_agent.config.workspace_root)
    }
    if _DISTILL_SKILL not in discovered_skills:
        return _error(
            "distiller_unavailable", "execution agent lacks the distiller skill"
        )
    tools = set(execution_agent.config.tool_allowlist)
    if "skill_view" not in tools:
        return _error("skill_view_unavailable", "execution agent lacks skill_view")
    return None


def _build_prompt(
    *, source_paths: list[Path], execution_agent_id: str, target_scope: str
) -> str:
    """Return the pre-existing normal-chat distiller prompt verbatim in shape."""
    scope_label = "global" if target_scope == "global" else "agent"
    return "\n".join(
        [
            f"/skill:{_DISTILL_SKILL}",
            "source_jsonl_paths:",
            *(f"  {path}" for path in source_paths),
            f"execution_agent_id: {execution_agent_id}",
            f"target_scope: {target_scope}",
            "",
            f"请基于上述会话 transcript，总结我反复使用且值得复用的工作方式，直接生成并写入一个 {scope_label} 级 skill。重点关注：",
            "- 触发这个 skill 的场景",
            "- 应遵循的步骤/检查点",
            "- 失败或边界情况",
            "如果这些会话不足以形成稳定模式，请说明原因，不要创建 skill。",
        ]
    )


def _error(error_code: str, message: str) -> Mapping[str, object]:
    """Return the small, action-oriented control error shape."""
    return {"error_code": error_code, "message": message}


def _text(value: object) -> str:
    """Normalize one protocol text field without accepting non-text coercions."""
    return value.strip() if isinstance(value, str) else ""
