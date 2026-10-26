"""True IM exhaustion keeps existing interactive/Global/child/timer routes."""

from pathlib import Path

import pytest
import yaml

from ._auto_review_retry import _login, _records, _stack, _trace
from ._im_polling import poll_until

pytestmark = pytest.mark.timeout(1800)


@pytest.mark.e2e
@pytest.mark.parametrize(
    "profile,fallback",
    [
        ("interactive", "deny"),
        ("global", "allow"),
        ("child", "allow"),
        ("schedule", "deny"),
        ("schedule", "allow"),
        ("heartbeat", "deny"),
        ("heartbeat", "allow"),
    ],
)
def test_real_im_exhaustion_preserves_source_and_configured_route(
    tmp_path: Path, profile: str, fallback: str
) -> None:
    with _stack(tmp_path, profile=profile, fallback=fallback) as (stack, records):
        client = _login(stack)
        ws = client.connect_ws()
        try:
            for policy, agent in (("nano", "e2e"), ("codex", "e2e-peer")):
                timed = profile in {"schedule", "heartbeat"}
                suffix = f"{profile}-{fallback}" if timed else profile
                case = f"{policy}-route-{suffix}"
                conversation = client.create_direct_conversation(agent)
                config_before = client.get_agent_config(agent)
                client.send_message(
                    conversation,
                    f"RETRY_CASE={case} TARGET={conversation} 仅执行一次受控测试，不要重发被阻断工具。",
                )
                heartbeat = None
                if profile == "heartbeat":
                    client.wait_for_agent_reply_with(
                        conversation, f"READY:{case}", timeout=60
                    )
                    heartbeat = (
                        Path(stack.wt_dir)
                        / ".gateway-workspace"
                        / agent
                        / ".nanoassistant/HEARTBEAT.md"
                    )
                    heartbeat.write_text(
                        f"HEARTBEAT_EXEC RETRY_CASE={case} TARGET={conversation} Run one test effect; never repeat it.\n"
                    )
                    client.update_agent_config(
                        agent,
                        features={"heartbeat": True},
                        heartbeat_json='{"every":"5s"}',
                    )
                    config_before = client.get_agent_config(agent)
                if profile == "interactive":
                    frame = ws.wait_for_event(
                        "permission.request",
                        lambda frame: (
                            (frame.data.get("permission_request") or {}).get("call_id")
                            == f"retry-{case}"
                        ),
                        timeout=420,
                    )
                    request = frame.data["permission_request"]
                    assert frame.conversation_id == conversation
                    client.resolve_permission(
                        conversation,
                        request["request_id"],
                        frame.data["message_id"],
                        "deny",
                    )
                poll_until(
                    lambda: _records(records, case),
                    lambda rows: (
                        len(
                            [
                                r
                                for r in rows
                                if r["kind"] == "review" and r["pending_tool"] == "bash"
                            ]
                        )
                        == 3
                    ),
                    timeout=420,
                    interval=0.1,
                    desc="three real HTTP failures for the pending bash",
                )
                client.wait_for_agent_reply_with(
                    conversation, f"ACK:{case}", timeout=420
                )
                if heartbeat is not None:
                    heartbeat.unlink()
                trace = _trace(stack, case)
                recovery = trace["recovery"]
                expected = (
                    "interactive_pending"
                    if profile == "interactive"
                    else "unattended"
                    if timed
                    else "return_to_agent"
                )
                assert trace["decision"] == "no_verdict"
                assert trace["consecutive"] == trace["total"] == 0
                assert recovery["finalRoute"] == expected
                assert recovery["retriesUsed"] == 2
                assert recovery["terminalReason"] == "transient"
                if timed:
                    assert recovery["fallbackOutcome"] == fallback
                else:
                    assert "fallbackOutcome" not in recovery
                effect = (
                    Path(stack.wt_dir)
                    / ".gateway-workspace"
                    / agent
                    / f"retry-{case}.txt"
                )
                if timed and fallback == "allow":
                    assert effect.read_text().splitlines() == [f"effect:{case}"]
                    assert trace["source"] == "classifier_unavailable"
                else:
                    assert not effect.exists()
                rows = _records(records, case)
                if profile == "child":
                    assert len({r["session"] for r in rows if r["kind"] == "main"}) == 2
                if profile == "schedule":
                    # A native schedule_create call and later SCHEDULE_EXEC request,
                    # not a synthetic session.submit with a forged system source.
                    assert any(
                        "schedule_create" in str(r["request"])
                        for r in rows
                        if r["kind"] == "main"
                    )
                    assert any(
                        "SCHEDULE_EXEC" in str(r["request"])
                        for r in rows
                        if r["kind"] == "main"
                    )
                if profile == "heartbeat":
                    assert any(
                        "HEARTBEAT_EXEC" in str(r["request"])
                        for r in rows
                        if r["kind"] == "main"
                    )
                    assert trace["source"] == "classifier_unavailable"
                if profile != "interactive":
                    timeline = client.list_timeline(conversation, limit=50)
                    assert not any(
                        item.get("type") == "permission_request"
                        or item.get("permission_request")
                        or (item.get("message") or {}).get("permission_requests")
                        for item in timeline
                    ), timeline
                config_after = client.get_agent_config(agent)
                for key in (
                    "approval_mode",
                    "tool_allowlist",
                    "features",
                    "default_model",
                    "reasoning_effort",
                    "profile_version",
                ):
                    assert config_after[key] == config_before[key]
                auto = yaml.safe_load(
                    (
                        Path(stack.wt_dir)
                        / ".gateway-workspace"
                        / agent
                        / ".nanoassistant/config.yaml"
                    ).read_text()
                )["auto_mode"]
                assert auto == {
                    "enabled": True,
                    "dangerously_skip_permissions": False,
                    "unattended_fallback": fallback,
                }
        finally:
            ws.close()
            client.close()
