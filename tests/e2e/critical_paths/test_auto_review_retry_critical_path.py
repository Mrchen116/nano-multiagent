"""Real IM → PA/Node → native DSH → HTTP automatic review recovery.

This deterministic supplemental profile does not replace the live daily journey.
Long request observation uses the production budgets, never patched timers.
"""

from __future__ import annotations

import time
from pathlib import Path

import pytest

from ._auto_review_retry import _login, _records, _stack, _trace
from ._im_client import IMClient, IMUserWebSocket
from ._im_polling import poll_until
from .conftest import E2EStack

pytestmark = pytest.mark.timeout(1800)


def _journey(
    client: IMClient,
    stack: E2EStack,
    records: Path,
    policy: str,
    kind: str,
    ws: IMUserWebSocket | None = None,
) -> dict:
    case = f"{policy}-{kind}"
    agent = "e2e" if policy == "nano" else "e2e-peer"
    conversation = client.create_direct_conversation(agent)
    owns_socket = ws is None
    ws = ws or client.connect_ws()
    blocked = kind in {"auth", "persistent", "invalid", "long", "stage-exhaust"}
    started = time.monotonic()
    try:
        client.send_message(
            conversation,
            f"RETRY_CASE={case} 请仅在本workspace追加一次测试记录；审核失败时不要重新调用工具。",
        )
        if blocked:
            frame = ws.wait_for_event(
                "permission.request",
                lambda frame: (
                    (frame.data.get("permission_request") or {}).get("call_id")
                    == f"retry-{case}"
                ),
                timeout=420,
            )
            assert frame.conversation_id == conversation
            request = frame.data["permission_request"]
            client.resolve_permission(
                conversation, request["request_id"], frame.data["message_id"], "deny"
            )
            ws.wait_for_event(
                "permission.resolved",
                lambda frame: (
                    (frame.data.get("permission_request") or {}).get("request_id")
                    == request["request_id"]
                ),
                timeout=30,
            )
        ws.wait_for_event(
            "message.completed",
            lambda frame: (
                frame.conversation_id == conversation
                and f"ACK:{case}" in (frame.data.get("content") or "")
            ),
            timeout=420,
        )
    finally:
        if owns_socket:
            ws.close()
    seen = _records(records, case)
    review = [row for row in seen if row["kind"] == "review"]
    expected = (
        4
        if kind == "stage-exhaust"
        else 3
        if kind in {"persistent", "mixed", "stage2-service", "stage2-timeout"}
        else 1
        if kind in {"auth", "long"}
        else 2
    )
    assert len(review) == expected, seen
    target = Path(stack.wt_dir) / ".gateway-workspace" / agent / f"retry-{case}.txt"
    if blocked:
        assert not target.exists()
    else:
        assert target.read_text().splitlines() == [f"effect:{case}"]
    trace = _trace(stack, case)
    assert trace["rules"] == policy
    assert trace["recovery"]["retriesUsed"] == expected - (
        2 if kind.startswith("stage") else 1
    )
    assert trace["recovery"]["formatRetriesUsed"] == (
        1 if kind in {"format", "invalid", "mixed"} else 0
    )
    assert trace["recovery"]["finalRoute"] == (
        "interactive_pending" if blocked else "allow"
    )
    if kind in {"service", "rate", "persistent", "mixed"}:
        facts = trace["recovery"]["attempts"][0]["requests"][0]["http"]
        assert facts["status"] == (429 if kind == "rate" else 503)
        assert facts["retryAfterMs"] == 1000
        assert review[1]["time"] - review[0]["time"] >= 0.95
    if kind == "rate-date":
        facts = trace["recovery"]["attempts"][0]["requests"][0]["http"]
        assert facts["status"] == 429 and facts["retryAfterMs"] > 800
        assert (review[1]["time"] - review[0]["time"]) * 1000 >= facts[
            "retryAfterMs"
        ] - 50
    if kind == "timeout":
        budget = 30000 if policy == "nano" else 90000
        assert time.monotonic() - started >= budget / 1000
        assert [row["budgetMs"] for row in trace["recovery"]["attempts"]] == [
            budget,
            budget,
        ]
        assert trace["recovery"]["attempts"][0]["category"] == "review_timeout"
    if kind.startswith("stage"):
        attempts = trace["recovery"]["attempts"]
        assert [row["budgetMs"] for row in attempts] == (
            [30000, 30000, 30000, 60000]
            if kind == "stage-exhaust"
            else [30000, 60000, 60000]
        )
        if kind == "stage2-timeout":
            assert time.monotonic() - started >= 60
            assert attempts[1]["category"] == "review_timeout"
    if policy == "codex" and expected > 1:
        assert len({row["session"] for row in review}) == expected
    return trace


@pytest.mark.e2e
def test_real_im_http_retry_and_interactive_exhaustion(tmp_path: Path) -> None:
    with _stack(tmp_path) as (stack, records):
        client = _login(stack)
        ws = client.connect_ws()
        try:
            for policy in ("nano", "codex"):
                for kind in (
                    "service",
                    "rate",
                    "rate-date",
                    "transport",
                    "format",
                    "mixed",
                    "auth",
                    "persistent",
                    "invalid",
                    "long",
                ):
                    _journey(client, stack, records, policy, kind, ws)
        finally:
            ws.close()
            client.close()


@pytest.mark.e2e
def test_real_im_stop_request_and_backoff_without_successor(tmp_path: Path) -> None:
    with _stack(tmp_path) as (stack, records):
        client = _login(stack)
        try:
            for policy, agent in (("nano", "e2e"), ("codex", "e2e-peer")):
                for kind in ("cancel", "cancel-backoff"):
                    case = f"{policy}-{kind}"
                    conversation = client.create_direct_conversation(agent)
                    ws = client.connect_ws()
                    try:
                        client.send_message(
                            conversation, f"RETRY_CASE={case} 仅执行一次隔离测试。"
                        )
                        poll_until(
                            lambda: _records(records, case),
                            lambda rows: any(row["kind"] == "review" for row in rows),
                            timeout=30,
                            interval=0.05,
                            desc="real reviewer HTTP admission",
                        )
                        client.send_message(conversation, "/stop")
                        ws.wait_for_event(
                            "message.completed",
                            lambda frame: (
                                "已停止当前操作。" in (frame.data.get("content") or "")
                            ),
                            timeout=30,
                        )
                    finally:
                        ws.close()
                    poll_until(
                        lambda: _trace(stack, case),
                        lambda row: row["recovery"]["complete"],
                        timeout=10,
                        interval=0.1,
                        desc="cancel audit durability",
                    )
                    # Wait beyond backoff and request late-response windows only in the request case.
                    # Cancellation itself is asserted by the durable route and zero effect.
                    assert _trace(stack, case)["recovery"]["finalRoute"] == "cancel"
                    assert (
                        len(
                            [
                                row
                                for row in _records(records, case)
                                if row["kind"] == "review"
                            ]
                        )
                        == 1
                    )
                    assert not (
                        Path(stack.wt_dir)
                        / ".gateway-workspace"
                        / agent
                        / f"retry-{case}.txt"
                    ).exists()
        finally:
            client.close()


@pytest.mark.e2e
@pytest.mark.parametrize("policy", ["nano", "codex"])
def test_real_im_default_full_timeout_recovery(tmp_path: Path, policy: str) -> None:
    with _stack(tmp_path) as (stack, records):
        client = _login(stack)
        try:
            _journey(client, stack, records, policy, "timeout")
        finally:
            client.close()


@pytest.mark.e2e
def test_real_im_cc_stages_share_quota_and_full_second_stage_budget(
    tmp_path: Path,
) -> None:
    with _stack(tmp_path) as (stack, records):
        client = _login(stack)
        ws = client.connect_ws()
        try:
            for kind in ("stage2-service", "stage-exhaust", "stage2-timeout"):
                _journey(client, stack, records, "nano", kind, ws)
        finally:
            ws.close()
            client.close()
