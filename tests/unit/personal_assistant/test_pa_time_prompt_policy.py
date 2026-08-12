"""PA runtime and preview share one stable timezone/footer policy."""

from __future__ import annotations

from pathlib import Path
from zoneinfo import ZoneInfo

from personal_assistant.config.local_store import AgentWorkspaceConfig
from personal_assistant.gateway.agent_catalog import LiveAgentCatalog
from personal_assistant.gateway.composition import _make_prompt_preview_provider
from personal_assistant.gateway.human_message_context import PaTimeContext
from personal_assistant.gateway.session_composition import (
    project_agent_runtime,
    project_agent_session_capabilities,
)


def _snapshot(tmp_path: Path):
    return LiveAgentCatalog(
        (
            AgentWorkspaceConfig(
                agent_id="agent-a",
                workspace_root=tmp_path,
                features={"include_session_created_datetime": True},
            ),
        )
    ).require("agent-a")


def _time_context() -> PaTimeContext:
    return PaTimeContext(zone=ZoneInfo("Asia/Shanghai"), prompt_label="Asia/Shanghai")


def test_all_pa_runtime_projections_force_footer_false_and_add_timezone(
    tmp_path: Path,
) -> None:
    snapshot = _snapshot(tmp_path)
    foreground = project_agent_runtime(
        snapshot,
        scenario={"run_origin": "user"},
        resolved_model="test-model",
        time_context=_time_context(),
    ).runtime
    unattended = project_agent_runtime(
        snapshot,
        scenario={"run_origin": "heartbeat"},
        resolved_model="test-model",
        time_context=_time_context(),
    ).runtime
    legacy = project_agent_session_capabilities(
        snapshot,
        scenario={"run_origin": "cron"},
        time_context=_time_context(),
    )

    assert foreground.features["include_session_created_datetime"] is False
    assert unattended.features["include_session_created_datetime"] is False
    assert legacy.features is not None
    assert legacy.features["include_session_created_datetime"] is False
    assert foreground.features == unattended.features
    assert any(
        piece.name == "pa.timezone" and piece.text == "Time zone: Asia/Shanghai"
        for piece in foreground.prompt.head
    )


def test_prompt_preview_forces_same_internal_policy_without_ui_toggle() -> None:
    captured: dict[str, object] = {}

    class _Kernel:
        def assemble_prompt_preview(self, **kwargs):  # noqa: ANN003, ANN202
            captured.update(kwargs)
            return {"prompt": "ok", "section_count": 1}

    provider = _make_prompt_preview_provider(_Kernel(), time_context=_time_context())
    provider("agent-a", "/tmp/ws", {}, None, [], "direct", [])

    assert captured["features"] == {"include_session_created_datetime": False}
    prompt = captured["prompt"]
    assert any(
        piece.name == "pa.timezone" and piece.text == "Time zone: Asia/Shanghai"
        for piece in prompt.head
    )
