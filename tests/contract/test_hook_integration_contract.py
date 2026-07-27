import asyncio
from pathlib import Path

import pytest

from agent.core.errors import ToolError
from agent.core.hooks.context import HookContext
from agent.core.hooks.registry import HookRegistry
from agent.core.hooks.runner import HookRunner
from agent.platform.tools.base import ToolContext
from agent.core.tools.registry import ToolRegistry
from agent.core.tools.base import (
    set_tool_safety_config_factory,
    set_tool_safety_factory,
)
from agent.platform.tools.safety import ToolSafety, ToolSafetyConfig


set_tool_safety_factory(ToolSafety)
set_tool_safety_config_factory(ToolSafetyConfig)


class EchoTool:
    name = "echo"
    description = "Echo text"
    input_schema = {
        "type": "object",
        "properties": {"text": {"type": "string"}},
        "required": ["text"],
        "additionalProperties": False,
    }

    def run(self, args, ctx):
        del ctx
        return {"text": args["text"]}


def test_tool_call_block_error_contract() -> None:
    registry = HookRegistry()

    async def block(event, ctx):
        del event, ctx
        return {"block": True, "reason": "policy"}

    registry.on("tool_call", block)

    tool_registry = ToolRegistry(
        context=ToolContext.create(repo_root=Path.cwd()),
        hook_runner=HookRunner(registry=registry),
    )
    tool_registry.register(EchoTool())

    with pytest.raises(ToolError) as exc_info:
        asyncio.run(
            tool_registry.execute(
                "echo",
                {"text": "ping"},
                hook_context=HookContext(
                    session_id="sess_contract", repo_root=Path.cwd()
                ),
            )
        )

    assert exc_info.value.details == {
        "blocked_by_hook": True,
        "reason": "policy",
        # bugfix-410-M2 (#97): dedicated badge classification alongside the free-text
        # reason; every hook block (auto block / user Deny) collapses to "denied".
        "reason_code": "denied",
        # feat-434-M1: user-decision verdict; None for an AUTO block (this gate
        # returns no approval), so the gate region stays hidden for非用户拒绝.
        "approval": None,
        "tool_name": "echo",
    }


def test_tool_result_rewrite_contract() -> None:
    registry = HookRegistry()

    async def rewrite(event, ctx):
        del event, ctx
        return {
            "content": {"text": "rewritten-by-hook"},
            "details": {"source": "hook"},
            "is_error": False,
        }

    registry.on("tool_result", rewrite)

    tool_registry = ToolRegistry(
        context=ToolContext.create(repo_root=Path.cwd()),
        hook_runner=HookRunner(registry=registry),
    )
    tool_registry.register(EchoTool())

    result = asyncio.run(
        tool_registry.execute(
            "echo",
            {"text": "ping"},
            hook_context=HookContext(session_id="sess_contract", repo_root=Path.cwd()),
        )
    )

    assert result == {"text": "rewritten-by-hook"}


def test_tool_result_rewrite_list_content_contract() -> None:
    registry = HookRegistry()

    async def rewrite(event, ctx):
        del event, ctx
        return {
            "content": [
                {"type": "text", "text": "part-a"},
                {"type": "image", "image_url": "data:image/png;base64,xxx"},
            ]
        }

    registry.on("tool_result", rewrite)

    tool_registry = ToolRegistry(
        context=ToolContext.create(repo_root=Path.cwd()),
        hook_runner=HookRunner(registry=registry),
    )
    tool_registry.register(EchoTool())

    result = asyncio.run(
        tool_registry.execute(
            "echo",
            {"text": "ping"},
            hook_context=HookContext(session_id="sess_contract", repo_root=Path.cwd()),
        )
    )

    assert result == {
        "content": [
            {"type": "text", "text": "part-a"},
            {"type": "image", "image_url": "data:image/png;base64,xxx"},
        ]
    }
