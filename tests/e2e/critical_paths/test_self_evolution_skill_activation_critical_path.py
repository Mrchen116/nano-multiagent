"""Critical path for terminal-late self-evolution Skill activation and replay."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from ._im_client import IMClient, restart_gateway
from ._im_polling import poll_until
from .test_agent_config_context_continuity_critical_path import (
    StubLLMStack,
    stub_llm_stack,
)
from .test_self_evolution_visibility_critical_path import (
    _FIXTURE_SCRIPT,
    _fixture_control,
    _fixture_state,
    _system_notices,
    _wait_for_fixture_event,
    _write_self_evolution_config,
)

_REPO_ROOT = Path(__file__).resolve().parents[3]
_FAULT_RUNNER = _REPO_ROOT / "scripts/fixtures/self_evolution_gateway_replay_fault.py"
_SKILL_NAME = "deterministic-review-workflow"
_FOREGROUND_SKILL = "FOREGROUND-SKILL-COMPLETE"
_RAW_SKILL_REPLY = "Saved: deterministic-review-workflow."
_SKILL_USED = "NEW-SESSION-SKILL-USED"


def _fault_records(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _wait_for_fault(path: Path, kind: str) -> list[dict[str, Any]]:
    return poll_until(
        lambda: _fault_records(path),
        lambda records: any(record.get("kind") == kind for record in records),
        timeout=30.0,
        interval=0.1,
        desc=f"controlled subscriber fault {kind!r}",
    )


@pytest.mark.e2e
@pytest.mark.parametrize(
    "stub_llm_stack",
    (
        {
            "script": _FIXTURE_SCRIPT,
            "provider": "openai_compat",
        },
    ),
    indirect=True,
)
def test_terminal_late_skill_create_replays_and_activates_in_a_new_session(
    stub_llm_stack: StubLLMStack,
) -> None:
    """A real review tool call survives one stream fault and updates the product."""

    runtime_root = Path(stub_llm_stack.wt_dir)
    fault_state = runtime_root / "self-evolution-replay.jsonl"
    fault_arm = runtime_root / "self-evolution-replay.arm"
    client = IMClient(stub_llm_stack.im_url)
    client.register_or_login("nano", "nano1234", display_name="Test User")

    replacement_started_after = restart_gateway(
        stub_llm_stack.wt_dir,
        stub_llm_stack.im_port,
        gateway_entrypoint=str(_FAULT_RUNNER),
        env_overrides={
            "NANO_E2E_REPLAY_FAULT_STATE": str(fault_state),
            "NANO_E2E_REPLAY_FAULT_ARM": str(fault_arm),
        },
    )
    client.wait_for_node_reconnect(
        node_id=stub_llm_stack.node_id,
        replacement_started_after=replacement_started_after,
    )

    agent_id = client.first_agent_id()
    updated = client.update_agent_config(
        agent_id,
        tool_allowlist=["memory", "skill_manage", "skill_view"],
        skills=[],
        skills_selection_mode="explicit_allowlist",
    )
    assert updated["skills_selection_mode"] == "explicit_allowlist"
    assert updated["skills"] == []
    _write_self_evolution_config(
        stub_llm_stack,
        agent_id,
        skill_interval=1,
        memory_interval=100,
    )
    _fixture_control(stub_llm_stack, scenario="skill_create", reset=True)
    conversation_id = client.create_direct_conversation(agent_id)

    ws = client.connect_ws()
    try:
        client.send_message(conversation_id, "Run the controlled Skill journey.")
        foreground = ws.wait_for_event(
            "message.completed",
            lambda frame: (
                frame.conversation_id == conversation_id
                and _FOREGROUND_SKILL in str(frame.data.get("content") or "")
            ),
        )
        assert foreground.data.get("delivery_status") == "completed"
        _wait_for_fixture_event(stub_llm_stack, "skill_review_waiting")
        _wait_for_fault(fault_state, "stream_opened")

        fault_arm.write_text("armed\n", encoding="utf-8")
        _fixture_control(
            stub_llm_stack,
            scenario="skill_create",
            release_review=True,
        )
        _wait_for_fixture_event(stub_llm_stack, "skill_review_completed")
        replay_records = _wait_for_fault(fault_state, "replayed")

        reconciled = poll_until(
            lambda: client.get_agent_config(agent_id),
            lambda config: (
                config.get("skills_selection_mode") == "explicit_allowlist"
                and _SKILL_NAME in config.get("skills", [])
            ),
            timeout=30.0,
            interval=0.2,
            desc="explicit allowlist containing the review-created Skill",
        )
        messages = poll_until(
            lambda: client.list_messages(conversation_id),
            lambda value: len(_system_notices(value, "skills")) == 1,
            timeout=30.0,
            interval=0.2,
            desc="one structured skills review notice",
        )
    finally:
        ws.close()

    assert reconciled["skills_selection_mode"] == "explicit_allowlist"
    assert _SKILL_NAME in reconciled["skills"]
    skill_path = (
        runtime_root
        / ".gateway-workspace"
        / agent_id
        / ".nanoassistant"
        / "skills"
        / _SKILL_NAME
        / "SKILL.md"
    )
    assert skill_path.is_file()
    assert _SKILL_NAME in skill_path.read_text(encoding="utf-8")
    assert len(_system_notices(messages, "skills")) == 1
    visible_text = "\n".join(str(message.get("content") or "") for message in messages)
    assert _RAW_SKILL_REPLY not in visible_text
    assert "Traceback" not in visible_text

    disconnects = [
        record for record in replay_records if record.get("kind") == "disconnected"
    ]
    replays = [record for record in replay_records if record.get("kind") == "replayed"]
    assert len(disconnects) == len(replays) == 1
    assert disconnects[0]["sequence"] == replays[0]["sequence"]

    _write_self_evolution_config(
        stub_llm_stack,
        agent_id,
        skill_interval=100,
        memory_interval=100,
        enabled=False,
    )
    _fixture_control(stub_llm_stack, scenario="verify_skill", reset=True)
    next_conversation_id = client.create_direct_conversation(agent_id)
    ws_next = client.connect_ws()
    try:
        client.send_message(next_conversation_id, "Use the newly activated Skill.")
        completed = ws_next.wait_for_event(
            "message.completed",
            lambda frame: (
                frame.conversation_id == next_conversation_id
                and _SKILL_USED in str(frame.data.get("content") or "")
            ),
        )
        assert completed.data.get("delivery_status") == "completed"
        _wait_for_fixture_event(stub_llm_stack, "skill_use_completed")
        replies = client.agent_messages(next_conversation_id, agent_id)
    finally:
        ws_next.close()
        client.close()

    [reply] = replies
    assert _SKILL_USED in str(reply.get("content") or "")
    skill_calls = [
        call for call in reply.get("tool_calls", []) if call.get("name") == "skill_view"
    ]
    assert len(skill_calls) == 1
    assert skill_calls[0]["status"] == "completed"

    state = _fixture_state(stub_llm_stack)
    assert any(
        request.get("routing_basis") == "structural_tool_result"
        for request in state.get("requests", [])
        if isinstance(request, dict)
    )
