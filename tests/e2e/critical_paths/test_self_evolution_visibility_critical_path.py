"""Critical paths for private self-evolution output through the real IM relay."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import httpx
import pytest
import yaml

from ._im_client import IMClient
from ._im_polling import poll_until
from .test_agent_config_context_continuity_critical_path import (
    StubLLMStack,
    stub_llm_stack,
)

_FIXTURE_SCRIPT = "openai_self_evolution_recording.py"
_FOREGROUND_NO_SAVE = "FOREGROUND-NO-SAVE-COMPLETE"
_FOREGROUND_NO_SAVE_SEED = "FOREGROUND-NO-SAVE-SEED"
_RAW_NO_SAVE = "Nothing to save."


def _fixture_url(stack: StubLLMStack) -> str:
    return f"http://127.0.0.1:{stack.stub_port}"


def _fixture_control(stack: StubLLMStack, **payload: object) -> dict[str, Any]:
    response = httpx.post(
        f"{_fixture_url(stack)}/control",
        json=payload,
        timeout=5.0,
        trust_env=False,
    )
    response.raise_for_status()
    body = response.json()
    assert isinstance(body, dict)
    return body


def _fixture_state(stack: StubLLMStack) -> dict[str, Any]:
    response = httpx.get(
        f"{_fixture_url(stack)}/state",
        timeout=5.0,
        trust_env=False,
    )
    response.raise_for_status()
    body = response.json()
    assert isinstance(body, dict)
    return body


def _wait_for_fixture_event(
    stack: StubLLMStack,
    event_name: str,
    *,
    timeout: float = 30.0,
) -> dict[str, Any]:
    state = poll_until(
        lambda: _fixture_state(stack),
        lambda value: any(
            item.get("event") == event_name
            for item in value.get("events", [])
            if isinstance(item, dict)
        ),
        timeout=timeout,
        interval=0.1,
        desc=f"fixture event {event_name!r}",
    )
    return state


def _write_self_evolution_config(
    stack: StubLLMStack,
    agent_id: str,
    *,
    skill_interval: int,
    memory_interval: int,
    enabled: bool = True,
) -> Path:
    config_path = (
        Path(stack.wt_dir)
        / ".gateway-workspace"
        / agent_id
        / ".nanoassistant"
        / "config.yaml"
    )
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(
        yaml.safe_dump(
            {
                "self_evolution": {
                    "enabled": enabled,
                    "skill_creation": True,
                    "memory_curation": True,
                    "skill_nudge_interval": skill_interval,
                    "memory_nudge_interval": memory_interval,
                }
            },
            allow_unicode=True,
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    return config_path


def _system_notices(
    messages: list[dict[str, Any]], target: str
) -> list[dict[str, Any]]:
    return [
        message
        for message in messages
        if message.get("sender_type") == "system"
        and isinstance(message.get("system_notice"), dict)
        and target in message["system_notice"].get("updated_targets", [])
    ]


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
def test_no_save_review_stays_private_after_foreground_completion(
    stub_llm_stack: StubLLMStack,
) -> None:
    """A controlled no-save review executes without creating an Agent bubble."""

    client = IMClient(stub_llm_stack.im_url)
    client.register_or_login("nano", "nano1234", display_name="Test User")
    agent_id = client.first_agent_id()
    client.update_agent_config(
        agent_id,
        tool_allowlist=["memory", "skill_manage", "skill_view"],
        skills=[],
        skills_selection_mode="explicit_allowlist",
    )
    _write_self_evolution_config(
        stub_llm_stack,
        agent_id,
        skill_interval=100,
        memory_interval=1,
    )
    _fixture_control(stub_llm_stack, scenario="no_save", reset=True)
    conversation_id = client.create_direct_conversation(agent_id)

    ws = client.connect_ws()
    try:
        client.send_message(conversation_id, "Seed the controlled no-save journey.")
        ws.wait_for_event(
            "message.completed",
            lambda frame: (
                frame.conversation_id == conversation_id
                and _FOREGROUND_NO_SAVE_SEED in str(frame.data.get("content") or "")
            ),
        )
        client.send_message(conversation_id, "Run the controlled no-save journey.")
        completed = ws.wait_for_event(
            "message.completed",
            lambda frame: (
                frame.conversation_id == conversation_id
                and _FOREGROUND_NO_SAVE in str(frame.data.get("content") or "")
            ),
        )
        assert completed.data.get("delivery_status") == "completed"

        _wait_for_fixture_event(stub_llm_stack, "no_save_review_completed")
        messages = poll_until(
            lambda: client.list_messages(conversation_id),
            lambda value: len(_system_notices(value, "memory")) == 1,
            timeout=30.0,
            interval=0.2,
            desc="one structured memory review notice",
        )
    finally:
        ws.close()
        client.close()

    agent_messages = [
        message for message in messages if message.get("sender_type") == "agent"
    ]
    assert len(agent_messages) == 2
    assert any(
        _FOREGROUND_NO_SAVE in str(message.get("content") or "")
        for message in agent_messages
    )
    visible_text = "\n".join(str(message.get("content") or "") for message in messages)
    assert _RAW_NO_SAVE not in visible_text
    assert "Traceback" not in visible_text
    assert len(_system_notices(messages, "memory")) == 1

    state = _fixture_state(stub_llm_stack)
    requests = [item for item in state.get("requests", []) if isinstance(item, dict)]
    assert any(item.get("kind") == "foreground" for item in requests)
    assert any(item.get("kind") == "review" for item in requests)
    assert {item.get("routing_basis") for item in requests} <= {
        "scenario_request_index",
        "structural_no_tools",
    }
