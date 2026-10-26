"""Rejected IM configuration transactions must not revoke the current review."""

from pathlib import Path

import httpx
import pytest

from ._im_polling import poll_until
from ._auto_review_retry import _login, _records, _stack, _trace

pytestmark = pytest.mark.timeout(1800)


@pytest.mark.e2e
def test_real_im_rejected_configuration_transaction_preserves_current_review(
    tmp_path: Path,
) -> None:
    with _stack(tmp_path) as (stack, records):
        client = _login(stack)
        ws = client.connect_ws()
        try:
            for policy, agent in (("nano", "e2e"), ("codex", "e2e-peer")):
                for kind in ("config-request", "config-backoff"):
                    case = f"{policy}-{kind}"
                    conversation = client.create_direct_conversation(agent)
                    client.send_message(
                        conversation, f"RETRY_CASE={case} 仅追加一次隔离测试记录。"
                    )
                    poll_until(
                        lambda: _records(records, case),
                        lambda rows: any(row["kind"] == "review" for row in rows),
                        timeout=30,
                        interval=0.05,
                        desc="configuration request barrier",
                    )
                    # Actual HTTP PATCH traverses PA/Node ConfigurationOperations,
                    # including its rejection release; it is not a synthetic cancel.
                    with pytest.raises(httpx.HTTPStatusError) as rejected:
                        client.update_agent_config(agent, tool_allowlist=[])
                    assert rejected.value.response.status_code == 409
                    assert "capability_in_use" in rejected.value.response.text
                    assert "bash" in client.get_agent_config(agent)["tool_allowlist"]
                    ws.wait_for_event(
                        "message.completed",
                        lambda frame: (
                            f"ACK:{case}" in (frame.data.get("content") or "")
                        ),
                        timeout=420,
                    )
                    trace = _trace(stack, case)
                    assert trace["recovery"]["finalRoute"] == "allow"
                    assert trace["recovery"]["retriesUsed"] == (
                        1 if kind == "config-backoff" else 0
                    )
                    target = (
                        Path(stack.wt_dir)
                        / ".gateway-workspace"
                        / agent
                        / f"retry-{case}.txt"
                    )
                    assert target.read_text().splitlines() == [f"effect:{case}"]
        finally:
            ws.close()
            client.close()
