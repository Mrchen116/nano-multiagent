"""The public /stop cancels a real foreground shell and leaves the chat usable."""

from __future__ import annotations

import json
import os
import shlex
from pathlib import Path

import pytest

from ._im_client import IMClient
from ._im_polling import poll_until
from ._recording import StubLLMStack, _load_records, stub_im_user, stub_llm_stack


@pytest.mark.parametrize(
    "stub_llm_stack",
    [
        {
            "script": "anthropic_sse_events_recording.py",
            "env": {"NANO_FIXTURE_SCENARIO": "stop"},
        }
    ],
    indirect=True,
)
def test_stop_aborts_active_run(
    stub_im_user: IMClient, stub_llm_stack: StubLLMStack
) -> None:
    client = stub_im_user
    client.update_agent_config("e2e", tool_allowlist=["bash"])
    conversation = client.create_direct_conversation("e2e")
    started = Path(stub_llm_stack.wt_dir) / "shell-started"
    finished = Path(stub_llm_stack.wt_dir) / "shell-finished"
    args = {
        "description": "Run a cancellable isolated foreground command",
        "command": f"echo $$ > {shlex.quote(str(started))}; sleep 60; touch {shlex.quote(str(finished))}",
        "timeoutMs": 120000,
    }
    ws = client.connect_ws()
    try:
        client.send_message(conversation, "EVENTS-COMMAND " + json.dumps(args))
        poll_until(
            lambda: started.exists(),
            bool,
            timeout=30,
            interval=0.1,
            desc="actual foreground shell started",
        )
        pid = int(started.read_text())
        client.send_message(conversation, "/stop")
        ws.wait_for_event(
            "message.completed",
            lambda event: (
                event.conversation_id == conversation
                and "已停止当前操作" in event.data.get("content", "")
            ),
            timeout=30,
        )

        def gone() -> bool:
            try:
                os.kill(pid, 0)
            except ProcessLookupError:
                return True
            return False

        poll_until(
            gone, bool, timeout=10, interval=0.1, desc="cancelled shell process exited"
        )
        assert not finished.exists()
        client.send_message(conversation, "EVENTS-AFTER-STOP")
        client.wait_for_agent_reply_with(conversation, "STOP-RECOVERED", timeout=30)
        records = _load_records(Path(stub_llm_stack.record_path))
        assert any(
            "event-bash" in json.dumps(request)
            and "EVENTS-AFTER-STOP" in json.dumps(request)
            for request in records
        )
    finally:
        ws.close()
