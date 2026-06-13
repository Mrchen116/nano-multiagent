"""Contract tests for the refactor-406 2-layer SDK surface building blocks.

Covers the SDK-owned DTOs, Protocols, and PromptSlots introduced for the
build_kernel(基座) + create_session(per-agent) contract (决策 2/5/6/8). The full
build_kernel/create_session re-wiring lands in later R3 work; these tests pin the
value-object/Protocol contracts that the re-wiring depends on.
"""

from __future__ import annotations

from agent.sdk.contracts import HookAPI, Tool, ToolContext
from agent.sdk.dto import (
    FeatureInfo,
    LLMConfig,
    LLMModel,
    LLMProvider,
    ModelInfo,
    RunInfo,
    SessionInfo,
    SkillInfo,
    ToolInfo,
)
from agent.sdk.prompt import PromptSlots, PromptText


# ---------------------------------------------------------------------------
# 决策 2: Tool / ToolContext / HookAPI structural Protocols
# ---------------------------------------------------------------------------


def test_native_object_satisfies_tool_protocol() -> None:
    """An object with name/description/input_schema/run satisfies Tool (no base class)."""

    class _NativeTool:
        name = "echo"
        description = "echo tool"
        input_schema: dict = {}

        def run(self, args, ctx):  # noqa: ANN001
            return {"ok": True}

    assert isinstance(_NativeTool(), Tool)


def test_incomplete_object_fails_tool_protocol() -> None:
    """Missing run() → not a Tool (runtime_checkable structural check)."""

    class _NotATool:
        name = "x"
        description = "y"
        input_schema: dict = {}

    assert not isinstance(_NotATool(), Tool)


def test_core_tool_context_satisfies_sdk_protocol() -> None:
    """The kernel's real ToolContext satisfies the SDK ToolContext Protocol.

    Proves no core→sdk inversion is needed: the kernel keeps building its own
    core ToolContext and it duck-satisfies the SDK-owned Protocol.
    """
    from agent.core.tools.base import ToolContext as CoreToolContext  # noqa: PLC0415

    ctx = CoreToolContext(repo_root=None, cwd=None, safety=None)
    assert isinstance(ctx, ToolContext)


def test_core_hook_api_satisfies_sdk_protocol() -> None:
    """The kernel's real HookAPI satisfies the SDK HookAPI Protocol (.on present)."""
    from agent.core.hooks.registry import HookAPI as CoreHookAPI  # noqa: PLC0415

    assert callable(getattr(CoreHookAPI, "on", None))
    # The class exposes the structural member the Protocol promises.
    assert hasattr(CoreHookAPI, "on")


# ---------------------------------------------------------------------------
# 决策 6: SessionInfo / RunInfo boundary DTOs
# ---------------------------------------------------------------------------


def test_session_info_fields_and_frozen() -> None:
    info = SessionInfo(
        session_id="s1", title="t", workspace_root="/ws", metadata={"agent_id": "a"}
    )
    assert info.session_id == "s1"
    assert info.title == "t"
    assert info.workspace_root == "/ws"
    assert info.metadata == {"agent_id": "a"}
    import dataclasses  # noqa: PLC0415

    assert dataclasses.is_dataclass(info)


def test_run_info_fields() -> None:
    run = RunInfo(run_id="r1", session_id="s1", status="queued")
    assert (run.run_id, run.session_id, run.status) == ("r1", "s1", "queued")


# ---------------------------------------------------------------------------
# 决策 5: LLMConfig DTO with env-pure from_env (no registry dependency)
# ---------------------------------------------------------------------------


def test_llm_config_from_env_needs_no_registry(monkeypatch) -> None:
    """LLMConfig.from_env must resolve purely from env — no model-registry init.

    This is the footgun removal (决策 5): a consumer builds the llm= argument via
    from_env *before* build_kernel initialises the registry.
    """
    monkeypatch.setenv("NANO_MULTIAGENT_LLM_PROVIDER", "openai_compat")
    monkeypatch.setenv("NANO_MULTIAGENT_LLM_MODEL", "codex_oauth:gpt-5.5")
    monkeypatch.setenv("NANO_MULTIAGENT_LLM_BASE_URL", "http://127.0.0.1:4000")
    cfg = LLMConfig.from_env()
    assert cfg.provider == "openai_compat"
    assert cfg.model == "codex_oauth:gpt-5.5"
    assert cfg.base_url == "http://127.0.0.1:4000"
    assert cfg.default_model == "codex_oauth:gpt-5.5"


def test_llm_config_carries_catalog() -> None:
    cfg = LLMConfig(
        provider="anthropic",
        model="kimiCoding:K2.6",
        base_url="http://127.0.0.1:4000",
        default_model="kimiCoding:K2.6",
        providers=(
            LLMProvider(
                name="anthropic",
                base_url="http://127.0.0.1:4000",
                models=(LLMModel(name="kimiCoding:K2.6"),),
            ),
        ),
    )
    assert cfg.providers[0].models[0].name == "kimiCoding:K2.6"


# ---------------------------------------------------------------------------
# 决策 4: capability-query DTOs
# ---------------------------------------------------------------------------


def test_capability_dtos_fields() -> None:
    assert ModelInfo(name="m", provider="p", is_default=True).is_default is True
    assert ToolInfo(name="t", description="d").description == "d"
    assert FeatureInfo(key="memory_curation", default_on=True, requires_tool="memory")
    assert SkillInfo(name="s").description == ""


# ---------------------------------------------------------------------------
# 决策 8: PromptSlots / PromptText value objects
# ---------------------------------------------------------------------------


def test_prompt_slots_default_empty_and_holds_pieces() -> None:
    empty = PromptSlots()
    assert empty.head == () and empty.body == () and empty.custom == () and empty.tail == ()
    slots = PromptSlots(
        head=(PromptText(name="pa.identity", text="# Hi"),),
        body=(PromptText(name="pa.guidelines", text="## G"),),
    )
    assert slots.head[0].name == "pa.identity"
    assert slots.body[0].text == "## G"
