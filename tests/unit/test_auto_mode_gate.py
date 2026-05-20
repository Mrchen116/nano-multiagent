"""Tests for auto_mode_gate hook — pixel-perfect CC yoloClassifier replication.

Covers:
- System prompt three-layer assembly (base_prompt + permissions_template + user rules)
- Transcript construction: includes user text + assistant tool_use, excludes assistant text
- Two-stage XML classification: stage1 allow, stage1 block→stage2, parse failure→ask
- Safe-tool allowlist: built-in tools bypass classifier
- Tool input projection: bash/read/write/edit projections
- Gate hook: dangerously_skip → pass; safe_tool → pass; bash+allowed → pass;
  bash+denied → deny; bash+review+classifier_deny → deny; classifier_ask → ask
- deny-limit escalation: exceeding limit → ask
- Unattended origin short-circuit: heartbeat origin → unattended_fallback, no ask
- hook timeout_ms=None registration
"""

from __future__ import annotations

import asyncio
import re
from typing import Any, Mapping
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agent.platform.config.auto_mode import AutoModeConfig
from agent.platform.hooks.builtins.auto_mode_gate import (
    BASE_PROMPT,
    EXTERNAL_PERMISSIONS_TEMPLATE,
    SAFE_TOOL_ALLOWLIST,
    TOOL_PROJECTIONS,
    build_transcript_entries,
    build_yolo_system_prompt,
    is_safe_tool,
    parse_xml_block,
    parse_xml_reason,
    project_tool_input,
    setup as gate_setup,
    strip_thinking,
)
from agent.platform.permissions.broker import PermissionBroker


# ---------------------------------------------------------------------------
# System prompt three-layer assembly
# ---------------------------------------------------------------------------

class TestBuildYoloSystemPrompt:
    def test_base_prompt_embedded_in_output(self):
        cfg = AutoModeConfig()
        prompt = build_yolo_system_prompt(cfg)
        # The base prompt contains the core classification instruction
        assert "automated security classifier" in prompt
        assert "BLOCK" in prompt
        assert "ALLOW" in prompt

    def test_permissions_template_substituted(self):
        cfg = AutoModeConfig()
        prompt = build_yolo_system_prompt(cfg)
        # permissions_template placeholder should be replaced
        assert "<permissions_template>" not in prompt
        # Default rules from external permissions template should appear
        assert "Allow Rules" in prompt
        assert "Deny Rules" in prompt

    def test_user_allow_rules_replace_defaults(self):
        cfg = AutoModeConfig(allow=("my custom allow rule",))
        prompt = build_yolo_system_prompt(cfg)
        assert "my custom allow rule" in prompt
        # The tags themselves should be gone
        assert "<user_allow_rules_to_replace>" not in prompt

    def test_user_deny_rules_replace_defaults(self):
        cfg = AutoModeConfig(soft_deny=("never delete production db",))
        prompt = build_yolo_system_prompt(cfg)
        assert "never delete production db" in prompt

    def test_user_environment_replaces_defaults(self):
        cfg = AutoModeConfig(environment=("Rust project using cargo",))
        prompt = build_yolo_system_prompt(cfg)
        assert "Rust project using cargo" in prompt

    def test_empty_user_rules_keep_defaults(self):
        """Empty user rules should preserve the default text in the template."""
        cfg = AutoModeConfig()  # no user rules
        prompt = build_yolo_system_prompt(cfg)
        # Default allow rule from permissions_external template
        assert "Running read-only shell commands" in prompt or "read-only" in prompt.lower()

    def test_xml_output_format_replaces_tool_use_line(self):
        """The classify_result tool line must be replaced with XML format."""
        cfg = AutoModeConfig()
        prompt = build_yolo_system_prompt(cfg)
        assert "classify_result" not in prompt
        assert "<block>yes</block>" in prompt
        assert "<block>no</block>" in prompt
        assert "## Output Format" in prompt

    def test_classify_result_line_not_present(self):
        cfg = AutoModeConfig()
        prompt = build_yolo_system_prompt(cfg)
        assert "Use the classify_result tool" not in prompt


# ---------------------------------------------------------------------------
# Transcript construction
# ---------------------------------------------------------------------------

class TestBuildTranscriptEntries:
    def _make_user_msg(self, text: str) -> dict:
        return {"role": "user", "content": text}

    def _make_assistant_text_msg(self, text: str) -> dict:
        return {"role": "assistant", "content": text}

    def _make_assistant_tool_use(self, name: str, inp: dict) -> dict:
        return {
            "role": "assistant",
            "content": [{"type": "tool_use", "id": "t1", "name": name, "input": inp}],
        }

    def _make_assistant_mixed(self, text: str, tool_name: str, tool_inp: dict) -> dict:
        return {
            "role": "assistant",
            "content": [
                {"type": "text", "text": text},
                {"type": "tool_use", "id": "t2", "name": tool_name, "input": tool_inp},
            ],
        }

    def test_user_text_included(self):
        msgs = [self._make_user_msg("please list files")]
        entries = build_transcript_entries(msgs)
        assert len(entries) == 1
        assert entries[0]["role"] == "user"
        assert entries[0]["content"] == "please list files"

    def test_assistant_text_excluded(self):
        """Assistant text blocks must be excluded (prevents prompt injection)."""
        msgs = [self._make_assistant_text_msg("I will now run ls")]
        entries = build_transcript_entries(msgs)
        assert len(entries) == 0

    def test_assistant_tool_use_included(self):
        msgs = [self._make_assistant_tool_use("bash", {"command": "ls"})]
        entries = build_transcript_entries(msgs)
        assert len(entries) == 1
        assert entries[0]["role"] == "assistant"
        assert entries[0]["content"][0]["name"] == "bash"

    def test_assistant_mixed_content_only_tool_use(self):
        """Mixed assistant message: only tool_use should appear in transcript."""
        msgs = [self._make_assistant_mixed("thinking text", "bash", {"command": "ls -la"})]
        entries = build_transcript_entries(msgs)
        assert len(entries) == 1
        assert entries[0]["role"] == "assistant"
        # Only tool_use block
        for block in entries[0]["content"]:
            assert block["type"] == "tool_use"

    def test_list_content_user_message(self):
        """User messages with list content extract text blocks."""
        msgs = [
            {"role": "user", "content": [{"type": "text", "text": "hello world"}, {"type": "image", "source": {}}]}
        ]
        entries = build_transcript_entries(msgs)
        # Should get user entry with text
        user_entries = [e for e in entries if e["role"] == "user"]
        assert len(user_entries) == 1
        assert "hello world" in user_entries[0]["content"]

    def test_tool_results_excluded(self):
        """Tool result messages (role='tool') are not included."""
        msgs = [
            {"role": "tool", "content": "output", "tool_use_id": "t1"}
        ]
        entries = build_transcript_entries(msgs)
        assert len(entries) == 0

    def test_ordering_preserved(self):
        msgs = [
            self._make_user_msg("first"),
            self._make_assistant_tool_use("bash", {"command": "ls"}),
            self._make_user_msg("second"),
        ]
        entries = build_transcript_entries(msgs)
        assert entries[0]["role"] == "user"
        assert entries[1]["role"] == "assistant"
        assert entries[2]["role"] == "user"


# ---------------------------------------------------------------------------
# Two-stage XML classification helpers
# ---------------------------------------------------------------------------

class TestXmlParsing:
    def test_parse_block_no(self):
        assert parse_xml_block("<block>no</block>") is False

    def test_parse_block_yes(self):
        assert parse_xml_block("<block>yes</block>") is True

    def test_parse_block_yes_no_close_tag(self):
        # CC uses stop_sequences=['</block>'] so stage 1 may lack closing tag
        assert parse_xml_block("<block>no") is False
        assert parse_xml_block("<block>yes") is True

    def test_parse_block_case_insensitive(self):
        assert parse_xml_block("<block>YES</block>") is True
        assert parse_xml_block("<block>NO</block>") is False

    def test_parse_block_none_on_missing(self):
        assert parse_xml_block("No tags here") is None
        assert parse_xml_block("") is None

    def test_strip_thinking_removes_thinking_block(self):
        text = "<thinking>this should be removed</thinking><block>no</block>"
        stripped = strip_thinking(text)
        assert "thinking" not in stripped
        assert "<block>no</block>" in stripped

    def test_parse_block_skips_thinking_content(self):
        """Tags inside <thinking> must not be matched."""
        text = "<thinking><block>yes</block></thinking><block>no</block>"
        assert parse_xml_block(text) is False

    def test_parse_reason(self):
        text = "<block>yes</block><reason>deletes important files</reason>"
        assert parse_xml_reason(text) == "deletes important files"

    def test_parse_reason_none_on_missing(self):
        assert parse_xml_reason("<block>no</block>") is None

    def test_parse_reason_strips_thinking(self):
        text = "<thinking><reason>fake</reason></thinking><reason>real reason</reason>"
        assert parse_xml_reason(text) == "real reason"


# ---------------------------------------------------------------------------
# Safe-tool allowlist
# ---------------------------------------------------------------------------

class TestSafeToolAllowlist:
    def test_read_is_safe(self):
        assert is_safe_tool("read", AutoModeConfig()) is True

    def test_web_fetch_not_safe(self):
        # S1 (bugfix-355 M1): web_fetch removed from SAFE_TOOL_ALLOWLIST;
        # routing now via WebFetch.check_permissions (M3).
        assert is_safe_tool("web_fetch", AutoModeConfig()) is False

    def test_web_search_not_safe(self):
        # S2 (bugfix-355 M1): web_search removed from SAFE_TOOL_ALLOWLIST;
        # falls to classifier (passthrough behavior).
        assert is_safe_tool("web_search", AutoModeConfig()) is False

    def test_task_tools_safe(self):
        for tool in ("task_create", "task_get", "task_update", "task_list", "task_stop", "task_output"):
            assert is_safe_tool(tool, AutoModeConfig()) is True

    def test_agent_tool_safe(self):
        assert is_safe_tool("agent", AutoModeConfig()) is True

    def test_send_message_safe(self):
        assert is_safe_tool("send_message", AutoModeConfig()) is True

    def test_memory_safe(self):
        # bugfix-368: memory tool must fast-path allow in auto mode.
        # Without this entry, PA self-improvement loops on `tool blocked by hook`
        # because the classifier judges memory (a write/persistence tool) as deny.
        assert is_safe_tool("memory", AutoModeConfig()) is True

    def test_bash_not_safe(self):
        assert is_safe_tool("bash", AutoModeConfig()) is False

    def test_write_not_safe(self):
        assert is_safe_tool("write", AutoModeConfig()) is False

    def test_edit_not_safe(self):
        assert is_safe_tool("edit", AutoModeConfig()) is False

    def test_always_allow_tools_config_extension(self):
        cfg = AutoModeConfig(always_allow_tools=("my_custom_tool",))
        assert is_safe_tool("my_custom_tool", cfg) is True

    def test_safe_tool_allowlist_frozenset(self):
        assert isinstance(SAFE_TOOL_ALLOWLIST, frozenset)


# ---------------------------------------------------------------------------
# Tool input projection
# ---------------------------------------------------------------------------

class TestProjectToolInput:
    def test_bash_projects_command(self):
        result = project_tool_input("bash", {"command": "ls -la"})
        assert result == "ls -la"

    def test_read_projects_file_path(self):
        result = project_tool_input("read", {"file_path": "/home/user/main.py"})
        assert result == "/home/user/main.py"

    def test_write_projects_path_and_content_truncated(self):
        long_content = "x" * 500
        result = project_tool_input("write", {"file_path": "/tmp/f.py", "content": long_content})
        assert "/tmp/f.py" in result
        # Content truncated at 200 chars
        assert len(result) < len(long_content) + 50

    def test_edit_projects_path_and_new_string_truncated(self):
        long_content = "y" * 500
        result = project_tool_input("edit", {"file_path": "/tmp/f.py", "new_string": long_content})
        assert "/tmp/f.py" in result

    def test_unknown_tool_returns_empty(self):
        result = project_tool_input("unknown_tool", {"key": "value"})
        assert result == ""

    def test_bash_missing_command_returns_empty(self):
        result = project_tool_input("bash", {})
        assert result == ""


# ---------------------------------------------------------------------------
# Gate hook setup — registration uses timeout_ms=None
# ---------------------------------------------------------------------------

class TestGateSetup:
    def test_setup_registers_with_none_timeout(self):
        """auto_mode_gate must register with timeout_ms=None (self-managed)."""
        registrations = []

        class MockHooks:
            def on(self, event, handler, *, priority=100, timeout_ms=1500, **kwargs):
                registrations.append({
                    "event": event,
                    "priority": priority,
                    "timeout_ms": timeout_ms,
                })

        gate_setup(MockHooks())
        assert len(registrations) == 1
        assert registrations[0]["event"] == "tool_call"
        assert registrations[0]["timeout_ms"] is None


# ---------------------------------------------------------------------------
# Gate hook logic (mocked HookContext)
# ---------------------------------------------------------------------------

def _make_ctx(
    *,
    run_origin: str = "user",
    session_id: str = "sess-1",
    message_history=None,
    call_model_result=None,
    broker: PermissionBroker | None = None,
):
    """Build a mock HookContext for gate testing."""
    ctx = MagicMock()
    ctx.session_id = session_id
    ctx.metadata = {"run_origin": run_origin}
    ctx.repo_root = None
    if message_history is not None:
        ctx.message_history = tuple(message_history)
    else:
        ctx.message_history = ()

    if call_model_result is not None:
        async def _call_model(**kwargs):
            return call_model_result
        ctx.call_model = _call_model
    else:
        ctx.call_model = AsyncMock(return_value=MagicMock(content="<block>no</block>"))

    # broker via metadata
    if broker is not None:
        ctx.metadata = dict(ctx.metadata)
        ctx.metadata["permission_broker"] = broker

    return ctx


class TestGateHookLogic:
    """Integration tests for the gate hook on_tool_call coroutine."""

    def _get_handler(self, config: AutoModeConfig | None = None):
        """Extract the on_tool_call handler from gate_setup.

        Returns (handler, config) so callers can use the config for assertions
        and patch load_auto_mode_config appropriately during the async call.
        """
        if config is None:
            config = AutoModeConfig()
        handlers = []

        class MockHooks:
            def on(self, event, handler, **kwargs):
                handlers.append(handler)

        gate_setup(MockHooks())
        return handlers[0], config

    def _make_ctx_with_config(self, config: AutoModeConfig, **kwargs):
        """Make a mock ctx with config injected via metadata._auto_mode_config_loader."""
        ctx = _make_ctx(**kwargs)
        ctx.metadata = dict(ctx.metadata)
        ctx.metadata["_auto_mode_config_loader"] = lambda: config
        return ctx

    @pytest.mark.asyncio
    async def test_dangerously_skip_permissions_passes_all(self):
        handler, config = self._get_handler(AutoModeConfig(dangerously_skip_permissions=True))
        ctx = self._make_ctx_with_config(AutoModeConfig(dangerously_skip_permissions=True))
        result = await handler({"name": "bash", "args": {"command": "rm -rf /"}}, ctx)
        assert result is None or result.get("block") is not True

    @pytest.mark.asyncio
    async def test_safe_tool_passes_without_classifier(self):
        handler, config = self._get_handler()
        ctx = self._make_ctx_with_config(config)
        # read is in SAFE_TOOL_ALLOWLIST → should pass without calling model
        ctx.call_model = AsyncMock()  # should never be called
        result = await handler({"name": "read", "args": {"file_path": "/tmp/x"}}, ctx)
        assert result is None or result.get("block") is not True
        ctx.call_model.assert_not_called()

    def _make_bash_tool_registry(self):
        """Return a fake tool_registry with BashTool for M6 dispatch tests."""
        from agent.platform.tools.builtins.bash import BashTool
        bash_tool = BashTool()

        class FakeRegistry:
            def get(self, name):
                return bash_tool if name == "bash" else None

        return FakeRegistry()

    @pytest.mark.asyncio
    async def test_bash_allowed_prefix_passes(self):
        """bash commands matching allowed prefixes pass without classifier.

        After M6, requires tool_registry with BashTool so check_permissions is dispatched.
        """
        handler, config = self._get_handler()
        ctx = self._make_ctx_with_config(config)
        ctx.metadata = dict(ctx.metadata)
        ctx.metadata["tool_registry"] = self._make_bash_tool_registry()
        ctx.call_model = AsyncMock()  # should NOT be called
        result = await handler({"name": "bash", "args": {"command": "ls -la"}}, ctx)
        assert result is None or result.get("block") is not True
        ctx.call_model.assert_not_called()

    @pytest.mark.asyncio
    async def test_bash_blocked_fragment_denies(self):
        """Fork-bomb fragment is still hard-denied via ``bash_blocked_fragments``.

        ``rm -rf /`` was moved out of hard-deny in M6 to route through the
        classifier (CC Auto Mode parity — workspace destruction belongs in the
        ask flow, not a silent kill). Fork-bomb syntax has no base command so
        it remains in the fragment denylist as the canonical example.

        After M6, requires tool_registry with BashTool.
        """
        handler, config = self._get_handler()
        ctx = self._make_ctx_with_config(config)
        ctx.metadata = dict(ctx.metadata)
        ctx.metadata["tool_registry"] = self._make_bash_tool_registry()
        result = await handler({"name": "bash", "args": {"command": ":(){:|:&};:"}}, ctx)
        assert result is not None
        assert result.get("block") is True

    @pytest.mark.asyncio
    async def test_bash_blocked_command_denies(self):
        """``reboot`` is a base-command hard-deny (token match, not substring).

        After M6, requires tool_registry with BashTool.
        """
        handler, config = self._get_handler()
        ctx = self._make_ctx_with_config(config)
        ctx.metadata = dict(ctx.metadata)
        ctx.metadata["tool_registry"] = self._make_bash_tool_registry()
        result = await handler({"name": "bash", "args": {"command": "reboot"}}, ctx)
        assert result is not None
        assert result.get("block") is True

    @pytest.mark.asyncio
    async def test_classifier_allow_passes(self):
        model_result = MagicMock()
        model_result.content = "<block>no</block>"
        handler, config = self._get_handler()
        ctx = self._make_ctx_with_config(config, call_model_result=model_result)
        result = await handler({"name": "write", "args": {"file_path": "/tmp/f", "content": "data"}}, ctx)
        assert result is None or result.get("block") is not True

    @pytest.mark.asyncio
    async def test_classifier_deny_blocks(self):
        model_result = MagicMock()
        model_result.content = "<block>yes</block><reason>dangerous action</reason>"
        handler, config = self._get_handler()
        ctx = self._make_ctx_with_config(config, call_model_result=model_result)
        result = await handler({"name": "write", "args": {"file_path": "/tmp/f", "content": "data"}}, ctx)
        assert result is not None
        assert result.get("block") is True

    @pytest.mark.asyncio
    async def test_classifier_parse_failure_escalates_to_ask(self):
        """Stage 1 parse failure → ask (fail-closed-to-ask)."""
        model_result = MagicMock()
        model_result.content = "this is not xml"  # unparseable
        handler, config = self._get_handler()

        # Need permission_requester to handle ask
        deny_response = MagicMock()
        deny_response.decision = "deny"

        async def mock_requester(req):
            return deny_response

        ctx = self._make_ctx_with_config(config, call_model_result=model_result)
        ctx.request_permission = mock_requester
        ctx.metadata = dict(ctx.metadata)
        ctx.metadata["permission_requester"] = mock_requester

        result = await handler({"name": "write", "args": {"file_path": "/tmp/f", "content": "data"}}, ctx)
        # Result is block because user denied the ask
        assert result is not None
        assert result.get("block") is True

    @pytest.mark.asyncio
    async def test_unattended_origin_skips_ask(self):
        """heartbeat origin should use unattended_fallback instead of asking."""
        model_result = MagicMock()
        model_result.content = "unparseable"  # would cause ask
        handler, _ = self._get_handler(AutoModeConfig(unattended_fallback="deny"))
        ctx = self._make_ctx_with_config(
            AutoModeConfig(unattended_fallback="deny"),
            run_origin="heartbeat",
            call_model_result=model_result,
        )

        # request_permission should NOT be called
        ctx.request_permission = AsyncMock()

        result = await handler({"name": "write", "args": {"file_path": "/tmp/f", "content": "x"}}, ctx)
        assert result is not None
        assert result.get("block") is True
        ctx.request_permission.assert_not_called()

    @pytest.mark.asyncio
    async def test_deny_limit_escalates_to_ask(self):
        """Exceeding deny_limit for same tool → escalate to ask."""
        from agent.platform.config.auto_mode import AutoModeConfig
        deny_limit_config = AutoModeConfig(deny_limit=1)
        broker = PermissionBroker(config=deny_limit_config)
        # Pre-increment deny count past limit
        broker.increment_deny_count("run-1", "write")

        model_result = MagicMock()
        model_result.content = "<block>yes</block><reason>risky</reason>"
        handler, _ = self._get_handler(deny_limit_config)

        allow_response = MagicMock()
        allow_response.decision = "allow_once"

        async def mock_requester(req):
            return allow_response

        ctx = self._make_ctx_with_config(deny_limit_config, call_model_result=model_result, run_origin="user")
        ctx.request_permission = mock_requester
        ctx.metadata = dict(ctx.metadata)
        ctx.metadata["run_id"] = "run-1"
        ctx.metadata["permission_broker"] = broker

        result = await handler({"name": "write", "args": {"file_path": "/tmp/f", "content": "x"}}, ctx)
        # Deny limit exceeded → ask → user allowed → should pass
        assert result is None or result.get("block") is not True


# ---------------------------------------------------------------------------
# M6: Regression tests — step 6 deleted, bash via tool.check_permissions dispatch
# ---------------------------------------------------------------------------

class TestM6BashViaCheckPermissions:
    """M6: bash no longer has hardcoded step 6 in auto_mode_gate.

    After M6, bash walks through the generic tool.check_permissions dispatch
    (step 1 / step 5). The hook file must NOT contain 'if tool_name == "bash"'
    outside of allow_unlisted backward-compat returns (which are also deleted).
    """

    def _get_handler(self, config=None):
        if config is None:
            config = AutoModeConfig()
        handlers = []

        class MockHooks:
            def on(self, event, handler, **kwargs):
                handlers.append(handler)

        gate_setup(MockHooks())
        return handlers[0], config

    def _make_ctx_with_bash_tool(self, config=None, *, call_model_result=None, tool_registry=None):
        """Make HookContext with BashTool in tool_registry so check_permissions is dispatched."""
        from unittest.mock import MagicMock, AsyncMock
        if config is None:
            config = AutoModeConfig()
        ctx = MagicMock()
        ctx.session_id = "sess-m6"
        ctx.repo_root = None
        ctx.metadata = {
            "run_origin": "user",
            "_auto_mode_config_loader": lambda: config,
        }
        if tool_registry is not None:
            ctx.metadata["tool_registry"] = tool_registry

        if call_model_result is not None:
            async def _call_model(**kwargs):
                return call_model_result
            ctx.call_model = _call_model
        else:
            ctx.call_model = AsyncMock(return_value=MagicMock(content="<block>no</block>"))
        return ctx

    def _make_bash_registry(self):
        """Return a fake tool_registry with BashTool registered."""
        from agent.platform.tools.builtins.bash import BashTool
        bash_tool = BashTool()

        class FakeRegistry:
            def get(self, name):
                return bash_tool if name == "bash" else None

        return FakeRegistry()

    def test_step6_not_in_auto_mode_gate_source(self):
        """Regression: auto_mode_gate.py must NOT contain 'if tool_name == .bash.' hardcoded block.

        This is the canonical M6 architectural assertion.
        """
        import inspect
        from agent.platform.hooks.builtins import auto_mode_gate
        source = inspect.getsource(auto_mode_gate)
        # "Step 6: Bash" comment must be gone
        assert "Step 6: Bash" not in source, (
            "auto_mode_gate.py still has step 6 'Step 6: Bash' — M6 migration incomplete"
        )

    @pytest.mark.asyncio
    async def test_bash_allowed_prefix_via_check_permissions(self):
        """ls -la via BashTool.check_permissions → allow, no classifier round-trip."""
        handler, config = self._get_handler()
        registry = self._make_bash_registry()
        ctx = self._make_ctx_with_bash_tool(config, tool_registry=registry)
        ctx.call_model = AsyncMock()  # should NOT be called

        result = await handler({"name": "bash", "args": {"command": "ls -la"}}, ctx)
        assert result is None or result.get("block") is not True
        ctx.call_model.assert_not_called()

    @pytest.mark.asyncio
    async def test_bash_blocked_via_check_permissions_denies(self):
        """reboot via BashTool.check_permissions → deny, no classifier."""
        handler, config = self._get_handler()
        registry = self._make_bash_registry()
        ctx = self._make_ctx_with_bash_tool(config, tool_registry=registry)

        result = await handler({"name": "bash", "args": {"command": "reboot"}}, ctx)
        assert result is not None
        assert result.get("block") is True

    @pytest.mark.asyncio
    async def test_bash_review_goes_to_classifier(self):
        """python3 script.py (review) via BashTool.check_permissions → passthrough → classifier."""
        allow_result = MagicMock()
        allow_result.content = "<block>no</block>"
        handler, config = self._get_handler()
        registry = self._make_bash_registry()
        # Use AsyncMock so we can assert_called()
        call_model_mock = AsyncMock(return_value=allow_result)
        ctx = self._make_ctx_with_bash_tool(config, tool_registry=registry)
        ctx.call_model = call_model_mock

        result = await handler({"name": "bash", "args": {"command": "python3 script.py"}}, ctx)
        # Classifier allowed → pass
        assert result is None or result.get("block") is not True
        # call_model was called (classifier ran)
        call_model_mock.assert_called()

    def test_allow_unlisted_not_in_gate_source(self):
        """M6: allow_unlisted marker should not appear in auto_mode_gate.py after step 6 removal."""
        import inspect
        from agent.platform.hooks.builtins import auto_mode_gate
        source = inspect.getsource(auto_mode_gate)
        assert "allow_unlisted" not in source, (
            "auto_mode_gate.py still references allow_unlisted — M6 migration incomplete"
        )


# ---------------------------------------------------------------------------
# bugfix-369: 门禁分类器不得继承主 agent thinking
# ---------------------------------------------------------------------------

class TestClassifyActionThinkingDisabled:
    """_classify_action 的 call_model 调用必须显式关闭 thinking。

    根因：model_registry 将 thinking: adaptive 挂在模型元数据上，client.generate
    对所有调用无差别 merge，导致门禁 stage-1 64-token 被 reasoning 吃空。
    修复方向：门禁调用显式传 extra_body={"thinking": {"type": "disabled"}}。
    """

    def _make_ctx(self, stage1_content: str = "<block>no</block>") -> MagicMock:
        ctx = MagicMock()
        ctx.session_id = "test-session"
        ctx.call_model = AsyncMock(
            return_value=MagicMock(content=stage1_content)
        )
        return ctx

    @pytest.mark.asyncio
    async def test_stage1_call_model_passes_thinking_disabled_extra_body(self):
        """stage-1 call_model 必须携带 extra_body 显式关闭 thinking（bugfix-369 不变性）。"""
        from agent.platform.hooks.builtins.auto_mode_gate import _classify_action

        ctx = self._make_ctx(stage1_content="<block>no</block>")
        await _classify_action(ctx, "sys", "user")

        call_kwargs = ctx.call_model.call_args_list[0]
        extra_body = call_kwargs.kwargs.get("extra_body")
        assert extra_body is not None, (
            "stage-1 call_model 没有传 extra_body，thinking 未被显式关闭"
        )
        thinking = extra_body.get("thinking", {})
        assert thinking.get("type") == "disabled", (
            f"stage-1 extra_body.thinking.type 应为 'disabled'，实际为 {thinking!r}"
        )

    @pytest.mark.asyncio
    async def test_stage2_call_model_passes_thinking_disabled_extra_body(self):
        """stage-2 call_model 也必须携带 extra_body 关闭 thinking。"""
        from agent.platform.hooks.builtins.auto_mode_gate import _classify_action

        ctx = self._make_ctx()
        # stage-1 返回 yes → 触发 stage-2
        ctx.call_model = AsyncMock(
            return_value=MagicMock(content="<block>yes</block>")
        )
        await _classify_action(ctx, "sys", "user")

        assert ctx.call_model.call_count == 2, "stage-1 block 应触发 stage-2"
        for i, call in enumerate(ctx.call_model.call_args_list):
            extra_body = call.kwargs.get("extra_body")
            assert extra_body is not None, (
                f"stage-{i + 1} call_model 没有传 extra_body"
            )
            thinking = extra_body.get("thinking", {})
            assert thinking.get("type") == "disabled", (
                f"stage-{i + 1} extra_body.thinking.type 应为 'disabled'，实际 {thinking!r}"
            )

    @pytest.mark.asyncio
    async def test_stage1_empty_content_fails_closed_ask(self):
        """stage-1 content 为空（thinking 吃光 token 时的现象）→ fail-closed → ask。

        这是 bugfix-369 的 regression 测试：确保空 content 不会绕过门禁。
        """
        from agent.platform.hooks.builtins.auto_mode_gate import _classify_action

        ctx = self._make_ctx(stage1_content="")
        decision = await _classify_action(ctx, "sys", "user")
        assert decision.behavior == "ask", (
            "stage-1 content 为空应 fail-closed → ask，但实际返回了 allow/deny"
        )
