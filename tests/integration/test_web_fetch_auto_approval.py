"""Real WebFetch permissions and execution through SDK main/child sessions."""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest
import yaml

from agent.core.llm.interfaces import LLMMessage, LLMToolCall
from agent.sdk import build_kernel
from tests.contract.test_kernel_sdk_behavior_contract import (
    _lc_llm,
    _wait_for_terminal_run,
)


class _Client:
    def __init__(self, url, delegated, verdict):
        self.url = url
        self.delegated = delegated
        self.verdict = verdict
        self.approvals = []
        self.actions = set()
        self.fetch_results = []

    async def generate(self, request):
        if not request.tools:
            self.approvals.append(request)
            if self.verdict == "unavailable":
                raise RuntimeError("approval provider unavailable")
            content = {
                "allow": "<block>no</block>",
                "deny": "<block>yes</block><reason>Do not fetch.</reason>",
                "malformed": "no decision",
            }[self.verdict]
            yield LLMMessage(role="assistant", content=content)
            yield LLMMessage(role="assistant", content="", finish_reason="stop")
            return
        self.fetch_results.extend(
            str(m.content)
            for m in request.messages
            if m.role == "tool" and m.tool_call_id == "fetch"
        )
        last_user = next(
            str(m.content) for m in reversed(request.messages) if m.role == "user"
        )
        child = "FETCH_CHILD" in last_user
        action = "delegate" if self.delegated and not child else "fetch"
        if action in self.actions:
            yield LLMMessage(role="assistant", content="done", finish_reason="stop")
            return
        self.actions.add(action)
        call = LLMToolCall(
            call_id=action,
            name="agent" if action == "delegate" else "web_fetch",
            arguments=(
                {"description": "Read webpage", "prompt": "FETCH_CHILD: read webpage"}
                if action == "delegate"
                else {"url": self.url}
            ),
        )
        yield LLMMessage(role="assistant", content="", tool_calls=(call,))
        yield LLMMessage(role="assistant", content="", finish_reason="tool_calls")


@pytest.mark.asyncio
@pytest.mark.parametrize("delegated", [False, True], ids=["main", "child"])
@pytest.mark.parametrize(
    ("config", "url", "verdict", "approval_calls", "fetched"),
    [
        ({}, "https://example.org/", "allow", 1, True),
        ({}, "https://example.org/", "deny", 2, False),
        ({}, "https://example.org/", "unavailable", 1, False),
        ({}, "https://example.org/", "malformed", 1, False),
        (
            {"web_fetch": {"ask_hosts": ["example.org"]}},
            "https://example.org/",
            "allow",
            0,
            False,
        ),
        (
            {"web_fetch": {"deny_hosts": ["example.org"]}},
            "https://example.org/",
            "allow",
            0,
            False,
        ),
        (
            {"web_fetch": {"allow_hosts": ["example.org"]}},
            "https://example.org/",
            "deny",
            0,
            True,
        ),
        ({}, "https://docs.python.org/3/", "deny", 0, True),
        ({"enabled": False}, "https://example.org/", "allow", 0, False),
        ({}, "http://localhost/", "allow", 0, False),
    ],
    ids=[
        "allow",
        "deny",
        "unavailable",
        "malformed",
        "ask-rule",
        "deny-rule",
        "allow-rule",
        "preapproved",
        "auto-disabled",
        "invalid-url",
    ],
)
async def test_web_fetch_approval_controls_actual_execution(
    tmp_path, monkeypatch, delegated, config, url, verdict, approval_calls, fetched
):
    config_dir = tmp_path / ".nanocode"
    config_dir.mkdir()
    (config_dir / "config.yaml").write_text(yaml.safe_dump({"auto_mode": config}))
    fetch = Mock(
        return_value=SimpleNamespace(
            status_code=200,
            text="FETCH_BODY_MARKER",
            headers={"content-type": "text/plain"},
            url=url,
        )
    )
    monkeypatch.setattr("agent.platform.tools.builtins.web_fetch._do_fetch", fetch)
    client = _Client(url, delegated, verdict)
    kernel = build_kernel(
        llm=_lc_llm(),
        repo_root=tmp_path,
        workspace_config_dirname=".nanocode",
        _llm_client_override=client,
    )
    try:
        session = await kernel.create_session(
            enabled_tools=["agent", "web_fetch"],
            metadata={"auto_mode_interaction": "return_to_agent"},
        )
        record = kernel.submit(
            session_id=session.session_id,
            parts=[{"type": "text", "text": f"Please read the public page {url}."}],
        )
        terminal = await _wait_for_terminal_run(kernel, record.run_id)
        assert terminal.status == "completed", terminal
        assert len(client.approvals) == approval_calls
        assert fetch.call_count == int(fetched)
        assert client.fetch_results
        assert any("FETCH_BODY_MARKER" in r for r in client.fetch_results) is fetched
        if fetched:
            fetch.assert_called_once_with(url)
        if approval_calls:
            transcript = str(client.approvals[0].messages)
            assert url in transcript
            assert "Please read the public page" in transcript
    finally:
        kernel.close()
