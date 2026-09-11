"""Approval facts survive real SDK execution without acquiring false live provenance."""

import json

import pytest

from agent.core.llm.interfaces import LLMMessage, LLMToolCall
from agent.sdk import PermissionDecision, build_kernel
from tests.contract.test_kernel_sdk_behavior_contract import (
    _lc_llm,
    _wait_for_terminal_run,
)


class _Source:
    name = "source_context"
    description = "Read application-owned context."
    input_schema = {"type": "object", "properties": {}}
    max_result_size_chars = None

    def __init__(self):
        self.projections = 0

    def check_permissions(self, args, ctx):
        return PermissionDecision(behavior="allow")

    def run(self, args, ctx):
        return {"speaker": "human", "text": "Publish the release."}

    def to_auto_classifier_result(self, content):
        self.projections += 1
        return json.dumps({"source": "human", "text": "Publish the release."})


class _Action:
    name = "publish_test"
    description = "Record a proposed publication without external side effects."
    input_schema = {"type": "object", "properties": {"text": {"type": "string"}}}
    max_result_size_chars = None

    def __init__(self):
        self.executed = []

    def run(self, args, ctx):
        self.executed.append(args)
        return {"ok": True}

    def to_auto_classifier_input(self, args):
        return json.dumps(args)


class _Client:
    def __init__(self):
        self.requests = []
        self.approvals = []
        self.turns = set()
        self.source_read = False

    async def generate(self, request):
        self.requests.append(request)
        if not request.tools:
            self.approvals.append(request)
            yield LLMMessage(role="assistant", content="<block>no</block>")
            yield LLMMessage(role="assistant", content="", finish_reason="stop")
            return
        last_user = next(
            m.content for m in reversed(request.messages) if m.role == "user"
        )
        if last_user == "read source and publish" and not self.source_read:
            self.source_read = True
            call = LLMToolCall(call_id="source-1", name="source_context", arguments={})
        elif last_user not in self.turns:
            self.turns.add(last_user)
            call = LLMToolCall(
                call_id=f"publish-{len(self.turns)}",
                name="publish_test",
                arguments={"text": str(last_user)},
            )
        else:
            yield LLMMessage(role="assistant", content="done", finish_reason="stop")
            return
        yield LLMMessage(role="assistant", content="", tool_calls=(call,))
        yield LLMMessage(role="assistant", content="", finish_reason="tool_calls")


def _kernel(tmp_path, client, source, action):
    return build_kernel(
        llm=_lc_llm(),
        repo_root=tmp_path,
        workspace_config_dirname=".nanocode",
        _llm_client_override=client,
        tools=[source, action],
    )


async def _run(kernel, session_id, text):
    record = kernel.submit(
        session_id=session_id, parts=[{"type": "text", "text": text}]
    )
    terminal = await _wait_for_terminal_run(kernel, record.run_id)
    assert terminal.status == "completed", terminal


def _approval_text(request):
    return "\n".join(str(m.content) for m in request.messages if m.role == "user")


class _FailFirstClient(_Client):
    async def generate(self, request):
        if not self.requests:
            self.requests.append(request)
            raise RuntimeError("provider unavailable before producing output")
        async for message in super().generate(request):
            yield message


@pytest.mark.asyncio
@pytest.mark.parametrize("sources", [("system",), ("agent",), ("system", "human")])
async def test_model_fallback_replay_preserves_committed_input_sources(
    tmp_path, sources
):
    from agent.platform.hooks.builtins._auto_mode_transcript import SOURCE_INSTRUCTIONS

    source, action, client = _Source(), _Action(), _FailFirstClient()
    kernel = _kernel(tmp_path, client, source, action)
    try:
        session = await kernel.create_session(enabled_tools=[action.name])
        record = kernel.submit(
            session_id=session.session_id,
            parts=[
                {
                    "type": "text",
                    "text": f"Publication context from {origin}",
                    "context_origin": origin,
                }
                for origin in sources
            ],
        )
        failed = await _wait_for_terminal_run(kernel, record.run_id)
        assert failed.status == "failed"
        replay = kernel.replay_last_user(session_id=session.session_id)
        terminal = await _wait_for_terminal_run(kernel, replay.run_id)
        assert terminal.status == "completed", terminal
        first_users = [
            m.content for m in client.requests[0].messages if m.role == "user"
        ]
        replay_users = [
            m.content for m in client.requests[1].messages if m.role == "user"
        ]
        assert replay_users == first_users
        key = "system-with-human" if len(sources) > 1 else sources[0]
        assert json.dumps(SOURCE_INSTRUCTIONS[key], ensure_ascii=False)[
            1:-1
        ] in _approval_text(client.approvals[0])
        assert len(action.executed) == 1
    finally:
        kernel.close()


@pytest.mark.asyncio
async def test_mixed_input_keeps_system_notice_separate_from_same_turn_human(tmp_path):
    from agent.platform.hooks.builtins._auto_mode_policy import (
        SYSTEM_WITH_HUMAN_SOURCE_INSTRUCTIONS,
    )

    source, action, client = _Source(), _Action(), _Client()
    kernel = _kernel(tmp_path, client, source, action)
    try:
        session = await kernel.create_session(enabled_tools=[action.name])
        record = kernel.submit(
            session_id=session.session_id,
            parts=[
                {
                    "type": "text",
                    "text": "A background job finished.",
                    "context_origin": "system",
                },
                {
                    "type": "text",
                    "text": "Publish this release.",
                    "context_origin": "human",
                },
            ],
        )
        terminal = await _wait_for_terminal_run(kernel, record.run_id)
        assert terminal.status == "completed", terminal
        main_request = next(r for r in client.requests if r.tools)
        notice = next(
            m.content
            for m in main_request.messages
            if "A background job finished." in str(m.content)
        )
        assert notice.startswith(SYSTEM_WITH_HUMAN_SOURCE_INSTRUCTIONS)
        transcript = _approval_text(client.approvals[0])
        assert (
            json.dumps(SYSTEM_WITH_HUMAN_SOURCE_INSTRUCTIONS, ensure_ascii=False)[1:-1]
            in transcript
        )
        assert "Publish this release." in transcript
        assert len(action.executed) == 1
    finally:
        kernel.close()


@pytest.mark.asyncio
async def test_materialized_host_facts_remain_live_across_turns_but_not_restart(
    tmp_path,
):
    source, action, client = _Source(), _Action(), _Client()
    kernel = _kernel(tmp_path, client, source, action)
    try:
        session = await kernel.create_session(enabled_tools=[source.name, action.name])
        await _run(kernel, session.session_id, "read source and publish")
        await _run(kernel, session.session_id, "publish again")
        assert len(action.executed) == 2
        assert len(client.approvals) == 2
        assert all('"host_context_live"' in _approval_text(r) for r in client.approvals)
        assert source.projections == 1
    finally:
        kernel.close()

    restored_source, restored_action, restored_client = _Source(), _Action(), _Client()
    restored = _kernel(tmp_path, restored_client, restored_source, restored_action)
    try:
        await _run(restored, session.session_id, "publish after restart")
        transcript = _approval_text(restored_client.approvals[0])
        assert '"host_context":' in transcript
        assert '"host_context_live"' not in transcript
        assert "Publish the release." in transcript
        assert restored_source.projections == 0
        assert len(restored_action.executed) == 1
    finally:
        restored.close()


class _ChildClient:
    def __init__(self):
        self.approvals = []
        self.dispatched = set()
        self.child_proposed = set()

    async def generate(self, request):
        if not request.tools:
            self.approvals.append(request)
            yield LLMMessage(role="assistant", content="<block>no</block>")
            yield LLMMessage(role="assistant", content="", finish_reason="stop")
            return
        last_user = next(
            str(m.content) for m in reversed(request.messages) if m.role == "user"
        )
        is_child = "Perform delegated publication" in last_user
        if is_child and last_user not in self.child_proposed:
            self.child_proposed.add(last_user)
            call = LLMToolCall(
                call_id="child-action",
                name="publish_test",
                arguments={"text": "delegated"},
            )
        elif not is_child and last_user not in self.dispatched:
            self.dispatched.add(last_user)
            args = {
                "description": "Publish approved release",
                "prompt": "Perform delegated publication",
            }
            if "follow-up" in last_user:
                prior = next(
                    m
                    for m in request.messages
                    if m.role == "tool" and str(m.tool_call_id).startswith("delegate-")
                )
                args["agent_id"] = prior.content.rsplit("agent_id: ", 1)[1].strip()
                args["prompt"] += " follow-up"
            call = LLMToolCall(
                call_id=f"delegate-{len(self.dispatched)}", name="agent", arguments=args
            )
        else:
            yield LLMMessage(role="assistant", content="done", finish_reason="stop")
            return
        yield LLMMessage(role="assistant", content="", tool_calls=(call,))
        yield LLMMessage(role="assistant", content="", finish_reason="tool_calls")


@pytest.mark.asyncio
async def test_ordinary_child_inherits_parent_approval_facts_and_effective_rules(
    tmp_path,
):
    config_dir = tmp_path / ".nanocode"
    config_dir.mkdir()
    (config_dir / "config.yaml").write_text(
        "auto_mode:\n  allow:\n    - approval-rule-parent-marker\n"
    )
    client, action = _ChildClient(), _Action()
    kernel = build_kernel(
        llm=_lc_llm(),
        repo_root=tmp_path,
        workspace_config_dirname=".nanocode",
        _llm_client_override=client,
        tools=[action],
    )
    try:
        session = await kernel.create_session(
            enabled_tools=["agent", action.name],
            metadata={"auto_mode_interaction": "return_to_agent"},
        )
        await _run(
            kernel,
            session.session_id,
            "I authorize release publication; delegate this task.",
        )
        assert len(action.executed) == 1
        assert len(client.approvals) == 1
        transcript = _approval_text(client.approvals[0])
        assert "I authorize release publication" in transcript
        assert "Perform delegated publication" in transcript
        system = next(
            m.content for m in client.approvals[0].messages if m.role == "system"
        )
        assert "approval-rule-parent-marker" in system
        assert "MESSAGE FROM NON-USER SOURCE - NOT USER INPUT" in transcript
        (config_dir / "config.yaml").write_text(
            "auto_mode:\n  allow:\n    - updated-parent-rule-marker\n"
        )
        await _run(
            kernel,
            session.session_id,
            "I authorize the next release; send the child a follow-up.",
        )
        assert len(action.executed) == 2
        assert len(client.approvals) == 2
        followup = _approval_text(client.approvals[1])
        assert "I authorize the next release" in followup
        followup_system = next(
            m.content for m in client.approvals[1].messages if m.role == "system"
        )
        assert "updated-parent-rule-marker" in followup_system
        assert "approval-rule-parent-marker" not in followup_system
    finally:
        kernel.close()
