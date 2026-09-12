"""Auto decisions follow the actual product entry and retain session denial state."""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from agent.core.errors import ModelError
from agent.platform.config.auto_mode import AutoModeConfig
from agent.platform.permissions.broker import PermissionBroker, PermissionDecision
from tests.unit.test_auto_mode_gate_dispatch import _get_handler, _make_ctx


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("origin", "kind", "blocked"),
    [
        ("human", None, True),
        ("background_task", None, True),
        ("heartbeat", None, False),
        ("cron", None, False),
        ("user", "subagent", True),
        ("background_task", "subagent", True),
    ],
)
async def test_global_interaction_preserves_automatic_entry_fallback(
    origin, kind, blocked
):
    config = AutoModeConfig(unattended_fallback="allow")
    tool = SimpleNamespace(to_auto_classifier_input=lambda args: "push branch")
    ctx = _make_ctx(config=config, tool_instance=tool, run_origin=origin)
    ctx.metadata.update(auto_mode_interaction="return_to_agent", kind=kind)
    ctx.call_model = AsyncMock(side_effect=RuntimeError("unavailable"))
    ctx.request_permission = AsyncMock()
    handler, _ = _get_handler()
    result = await handler({"name": "send_message", "args": {}}, ctx)
    assert bool(result and result.get("block")) is blocked
    assert result["decision_source"] == (
        "classifier_unavailable" if blocked else "unattended_fallback"
    )
    ctx.request_permission.assert_not_called()


@pytest.mark.asyncio
async def test_explicit_tool_deny_precedes_config_and_session_wide_grants():
    config = AutoModeConfig(always_allow_tools=("write",))
    broker = PermissionBroker(config=config)
    broker.add_session_allowlist("sess-1", "write")
    tool = SimpleNamespace(
        check_permissions=lambda args, ctx: PermissionDecision(
            behavior="deny", reason="explicit rule"
        )
    )
    ctx = _make_ctx(config=config, tool_instance=tool, broker=broker)
    handler, _ = _get_handler()
    result = await handler({"name": "write", "args": {}}, ctx)
    assert result["block"] is True and result["decision_source"] == "explicit_deny"
    ctx.call_model.assert_not_called()


@pytest.mark.asyncio
async def test_counts_cross_runs_and_tools_but_faults_do_not_count_or_latch():
    config = AutoModeConfig(deny_limit=3, total_deny_limit=4)
    broker = PermissionBroker(config=config)
    tool = SimpleNamespace(to_auto_classifier_input=lambda args: "remote change")
    ctx = _make_ctx(config=config, tool_instance=tool, broker=broker)
    ctx.metadata["auto_mode_interaction"] = "return_to_agent"
    ctx.request_permission = AsyncMock()
    handler, _ = _get_handler()
    for index in range(4):
        ctx.metadata["run_id"] = f"run-{index}"
        ctx.call_model = AsyncMock(
            return_value=SimpleNamespace(
                content="<block>yes</block><reason>needs consent</reason>"
            )
        )
        result = await handler(
            {"name": "write" if index % 2 else "bash", "args": {}}, ctx
        )
        assert result["block"] is True
    assert broker.get_auto_denial_counts("sess-1") == (0, 0)
    ctx.call_model = AsyncMock(return_value=SimpleNamespace(content="invalid XML"))
    await handler({"name": "write", "args": {}}, ctx)
    assert broker.get_auto_denial_counts("sess-1") == (0, 0)
    ctx.call_model = AsyncMock(
        return_value=SimpleNamespace(content="<block>no</block>")
    )
    assert await handler({"name": "write", "args": {}}, ctx) is None
    ctx.call_model.assert_awaited_once()
    ctx.request_permission.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("provider_code", "source"),
    [
        ("context_length_exceeded", "prompt_too_long"),
        ("invalid_api_key", "classifier_unavailable"),
    ],
)
async def test_structured_provider_fault_keeps_approval_reason_without_retry(
    provider_code, source
):
    broker = PermissionBroker(config=AutoModeConfig())
    tool = SimpleNamespace(to_auto_classifier_input=lambda args: "write project file")
    ctx = _make_ctx(config=AutoModeConfig(), tool_instance=tool, broker=broker)
    ctx.metadata["auto_mode_interaction"] = "return_to_agent"
    ctx.call_model = AsyncMock(
        side_effect=ModelError("too long", details={"provider_code": provider_code})
    )
    ctx.request_permission = AsyncMock()
    handler, _ = _get_handler()

    result = await handler({"name": "write", "args": {}}, ctx)

    assert result["block"] is True
    assert result["decision_source"] == source
    assert result["category"] == source
    assert broker.get_auto_denial_counts("sess-1") == (0, 0)
    ctx.call_model.assert_awaited_once()
    ctx.request_permission.assert_not_called()
