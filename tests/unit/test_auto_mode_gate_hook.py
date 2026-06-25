"""Tests for auto_mode_gate hook logic: gate flow, M6 bash via check_permissions."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from agent.platform.config.auto_mode import AutoModeConfig
from agent.platform.hooks.builtins.auto_mode_gate import (
    setup as gate_setup,
)
from agent.platform.permissions.broker import PermissionBroker


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


# ---------------------------------------------------------------------------
# Gate hook logic (mocked HookContext)
# ---------------------------------------------------------------------------


class TestGateHookLogic:
    """Integration tests for the gate hook on_tool_call coroutine."""

    def _get_handler(self, config: AutoModeConfig | None = None):
        """Extract the on_tool_call handler from gate_setup."""
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
        handler, config = self._get_handler(
            AutoModeConfig(dangerously_skip_permissions=True)
        )
        ctx = self._make_ctx_with_config(
            AutoModeConfig(dangerously_skip_permissions=True)
        )
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
        result = await handler(
            {"name": "bash", "args": {"command": ":(){:|:&};:"}}, ctx
        )
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
        result = await handler(
            {"name": "write", "args": {"file_path": "/tmp/f", "content": "data"}}, ctx
        )
        assert result is None or result.get("block") is not True

    @pytest.mark.asyncio
    async def test_classifier_deny_blocks(self):
        model_result = MagicMock()
        model_result.content = "<block>yes</block><reason>dangerous action</reason>"
        handler, config = self._get_handler()
        ctx = self._make_ctx_with_config(config, call_model_result=model_result)
        result = await handler(
            {"name": "write", "args": {"file_path": "/tmp/f", "content": "data"}}, ctx
        )
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

        result = await handler(
            {"name": "write", "args": {"file_path": "/tmp/f", "content": "data"}}, ctx
        )
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

        result = await handler(
            {"name": "write", "args": {"file_path": "/tmp/f", "content": "x"}}, ctx
        )
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

        ctx = self._make_ctx_with_config(
            deny_limit_config, call_model_result=model_result, run_origin="user"
        )
        ctx.request_permission = mock_requester
        ctx.metadata = dict(ctx.metadata)
        ctx.metadata["run_id"] = "run-1"
        ctx.metadata["permission_broker"] = broker

        result = await handler(
            {"name": "write", "args": {"file_path": "/tmp/f", "content": "x"}}, ctx
        )
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

    def _make_ctx_with_bash_tool(
        self, config=None, *, call_model_result=None, tool_registry=None
    ):
        """Make HookContext with BashTool in tool_registry so check_permissions is dispatched."""
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
            ctx.call_model = AsyncMock(
                return_value=MagicMock(content="<block>no</block>")
            )
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

        result = await handler(
            {"name": "bash", "args": {"command": "python3 script.py"}}, ctx
        )
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
# feat-434-M1: _handle_ask 返回 approval 信号（allow 链起点）
# ---------------------------------------------------------------------------


class TestHandleAskApprovalSignal:
    """gate 的 ask 流在用户决策后须返回 approval 信号，供下游标「已授权/已拒绝」。

    现状 allow_* 分支返回裸 {block:False}，与自动放行无从区分；deny 分支只带 reason。
    feat-434 让用户卡决策的放行/拒绝都带 approval，自动放行路径不返回 approval（保持 None）。
    """

    def _make_park_ctx(self, response):
        ctx = MagicMock()
        ctx.session_id = "sess-ask"

        async def _requester(req):
            return response

        ctx.request_permission = _requester
        return ctx

    def _resp(self, decision, reason=""):
        r = MagicMock()
        r.decision = decision
        r.reason = reason
        return r

    @pytest.mark.asyncio
    async def test_allow_once_returns_user_allow(self):
        from agent.platform.hooks.builtins.auto_mode_gate import _handle_ask

        ctx = self._make_park_ctx(self._resp("allow_once"))
        result = await _handle_ask(
            ctx,
            "bash",
            {"command": "ls"},
            "risky",
            "run-1",
            "sess-ask",
            AutoModeConfig(),
            None,
        )
        assert result.get("block") is False
        assert result.get("approval") == "user_allow"

    @pytest.mark.asyncio
    async def test_allow_session_returns_user_allow(self):
        from agent.platform.hooks.builtins.auto_mode_gate import _handle_ask

        ctx = self._make_park_ctx(self._resp("allow_session"))
        result = await _handle_ask(
            ctx,
            "bash",
            {"command": "ls"},
            "risky",
            "run-1",
            "sess-ask",
            AutoModeConfig(),
            None,
        )
        assert result.get("block") is False
        assert result.get("approval") == "user_allow"

    @pytest.mark.asyncio
    async def test_allow_always_returns_user_allow(self):
        from agent.platform.hooks.builtins.auto_mode_gate import _handle_ask

        ctx = self._make_park_ctx(self._resp("allow_always"))
        result = await _handle_ask(
            ctx,
            "bash",
            {"command": "ls"},
            "risky",
            "run-1",
            "sess-ask",
            AutoModeConfig(),
            None,
        )
        assert result.get("block") is False
        assert result.get("approval") == "user_allow"

    @pytest.mark.asyncio
    async def test_deny_returns_user_deny(self):
        from agent.platform.hooks.builtins.auto_mode_gate import _handle_ask

        ctx = self._make_park_ctx(self._resp("deny", reason="no"))
        result = await _handle_ask(
            ctx,
            "bash",
            {"command": "ls"},
            "risky",
            "run-1",
            "sess-ask",
            AutoModeConfig(),
            None,
        )
        assert result.get("block") is True
        assert result.get("approval") == "user_deny"
