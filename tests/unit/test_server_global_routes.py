from pathlib import Path

from nano_multiagent.llm.factory import LLMFactoryConfig
from nano_multiagent.server.routes.global_routes import build_capabilities_payload
from nano_multiagent.tools.base import ToolContext
from nano_multiagent.tools.registry import ToolRegistry


class _AlphaTool:
    name = "alpha"
    description = "alpha"
    input_schema = {"type": "object", "properties": {}, "required": []}

    def run(self, args, ctx):  # pragma: no cover - helper stub
        del args, ctx
        return {"ok": True}


class _ZetaTool:
    name = "zeta"
    description = "zeta"
    input_schema = {"type": "object", "properties": {}, "required": []}

    def run(self, args, ctx):  # pragma: no cover - helper stub
        del args, ctx
        return {"ok": True}


def test_build_capabilities_payload_reflects_active_llm_and_sorted_tools() -> None:
    registry = ToolRegistry(context=ToolContext.create(repo_root=Path.cwd()))
    registry.register(_ZetaTool())
    registry.register(_AlphaTool())

    payload = build_capabilities_payload(
        tool_registry=registry,
        llm_config=LLMFactoryConfig(
            provider="anthropic",
            model="claude-3-5-sonnet-20241022",
            base_url="http://127.0.0.1:4000",
        ),
    )

    assert payload["llm"]["active_provider"] == "anthropic"
    assert payload["llm"]["active_model"] == "claude-3-5-sonnet-20241022"
    assert [item["name"] for item in payload["tools"]] == ["alpha", "zeta"]

    providers = {item["provider"]: item for item in payload["llm"]["providers"]}
    assert "openai_compat" in providers
    assert "anthropic" in providers
    assert providers["openai_compat"]["default_model"] == "codexOAuth:gpt-5.2-codex"
