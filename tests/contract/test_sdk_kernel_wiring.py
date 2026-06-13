"""R3 contract: build_kernel(基座) + create_session(per-agent) new-signature wiring.

refactor-406 决策 1/2/4/5/6: the SDK building blocks (LLMConfig / Tool Protocol /
PromptSlots / DTOs) are wired into the kernel. This test drives the **new**
signature end-to-end — an agent-package-external application that only imports
``agent.sdk``:

- ``build_kernel(llm=LLMConfig, tools=[native objects], hooks=[setup], …)`` with
  zero registry pre-init (决策 5 footgun removal),
- ``create_session(enabled_tools=…, features=…, prompt=PromptSlots)`` → ``SessionInfo``,
- ``submit`` → ``RunInfo``, ``get_run`` → ``RunInfo``,
- ``get_llm_config`` / ``reconfigure_llm`` → ``LLMConfig`` DTO,
- ``list_models`` / ``list_tools`` / ``list_features`` / ``list_skills`` consistent
  with the assembled kernel,
- a closure-backed side-effect tool (no host-capability bridge) executes and reaches
  the application's own subsystem (决策 9 shape: side effect direct to app, no回桥).

This is the design.md M1 「外部产品最小证明」exit-criterion in test form.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any, Mapping

import pytest

from agent.sdk import (
    HookAPI,
    Kernel,
    LLMConfig,
    PromptSlots,
    PromptText,
    RunOrigin,
    SessionInfo,
    Tool,
    ToolContext,
    build_kernel,
)
from agent.sdk.dto import FeatureInfo, ModelInfo, RunInfo, ToolInfo
from agent.core.llm.interfaces import LLMMessage, LLMToolCall


# ---------------------------------------------------------------------------
# Helpers — fake LLM, native tools, hooks (an external application's own code)
# ---------------------------------------------------------------------------


def _fake_llm_client(*, content: str = "ok") -> Any:
    class _FakeClient:
        def generate(self, request: Any):  # noqa: ANN001, ANN201
            return _stub(content)

    return _FakeClient()


async def _stub(content: str):
    yield LLMMessage(
        role="assistant", content=content, finish_reason="stop", tool_calls=(), usage=None
    )


def _tool_calling_llm_client(tool_name: str) -> Any:
    """A client that issues one tool call on the first turn, then stops."""

    state = {"called": False}

    class _Client:
        def generate(self, request: Any):  # noqa: ANN001, ANN201
            if not state["called"]:
                state["called"] = True
                return _tool_call_stream(tool_name)
            return _stub("done")

    return _Client()


async def _tool_call_stream(tool_name: str):
    # The loop treats a message with empty content + finish_reason as terminal
    # metadata; tool_calls must ride a non-terminal assistant message (finish_reason
    # None), then the loop dispatches them and re-queries the model.
    yield LLMMessage(
        role="assistant",
        content="calling",
        finish_reason=None,
        tool_calls=(
            LLMToolCall(call_id="call-1", name=tool_name, arguments={"note": "hi"}),
        ),
        usage=None,
    )


async def _allow_all(tool, tool_input, ctx):  # noqa: ANN001
    from agent.platform.permissions.broker import PermissionDecision  # noqa: PLC0415

    return PermissionDecision(behavior="allow")


class _EchoTool:
    """Native tool: satisfies the SDK ``Tool`` Protocol, no kernel base class."""

    name = "echo"
    description = "Echo a note back."
    input_schema: dict = {"type": "object", "properties": {"note": {"type": "string"}}}

    def run(self, args: Mapping[str, Any], ctx: ToolContext) -> Mapping[str, Any]:
        return {"echoed": args.get("note", "")}


def _make_recording_tool(sink: list[str]) -> _RecordingTool:
    """A closure-backed side-effect tool that writes to the app's own subsystem.

    Mirrors决策 9: the tool closes over the application's handle (``sink``) and the
    side effect goes straight there — no kernel host-capability bridge.
    """
    return _RecordingTool(sink)


class _RecordPresenter:
    """A presenter that travels with the closure tool (决策 12).

    Proves a product tool brings its own IM render card: the kernel resolves this
    presenter off the tool object (no global registry), and the label/summary/detail
    surface on the tool_start / tool_end events.
    """

    def format_start(self, args: Mapping[str, Any]):
        from agent.sdk import ToolPresentationEvent  # noqa: PLC0415

        return ToolPresentationEvent(
            visible=True, label="Record", summary=f"note={args.get('note', '')}"
        )

    def format_end(self, args: Mapping[str, Any], result: Any, duration_ms: int):
        from agent.sdk import ToolPresentationEvent  # noqa: PLC0415

        return ToolPresentationEvent(
            visible=True,
            label="Record",
            summary="recorded",
            detail={"note": str(args.get("note", ""))},
        )


class _RecordingTool:
    name = "record"
    description = "Record a note into the application subsystem."
    input_schema: dict = {"type": "object", "properties": {"note": {"type": "string"}}}
    presenter = _RecordPresenter()  # 决策 12: presentation travels with the tool object

    def __init__(self, sink: list[str]) -> None:
        self._sink = sink

    def run(self, args: Mapping[str, Any], ctx: ToolContext) -> Mapping[str, Any]:
        self._sink.append(str(args.get("note", "")))
        return {"recorded": True}


def _llm_config() -> LLMConfig:
    return LLMConfig(
        provider="openai_compat",
        model="codex_oauth:gpt-5.5",
        base_url="http://127.0.0.1:4000",
        default_model="codex_oauth:gpt-5.5",
    )


def _build(tmp_path: Path, **kwargs: Any) -> Kernel:
    defaults: dict[str, Any] = dict(
        llm=_llm_config(),
        tools=[_EchoTool()],
        hooks=[],
        workspace_config_dirname=".nanotest",
        repo_root=tmp_path,
        _llm_client_override=_fake_llm_client(),
    )
    defaults.update(kwargs)
    return build_kernel(**defaults)


async def _wait_terminal(kernel: Kernel, run_id: str, *, timeout: float = 3.0) -> Any:
    deadline = asyncio.get_event_loop().time() + timeout
    while asyncio.get_event_loop().time() < deadline:
        record = kernel.get_run(run_id)
        if record and record.status in {"completed", "failed", "cancelled"}:
            return record
        await asyncio.sleep(0.02)
    raise AssertionError(f"run {run_id} did not terminate in {timeout}s")


# ---------------------------------------------------------------------------
# 决策 5: zero pre-init build from LLMConfig
# ---------------------------------------------------------------------------


def test_build_kernel_from_llm_config_no_pre_init(tmp_path: Path) -> None:
    """build_kernel(llm=LLMConfig) assembles with no consumer-side registry init."""
    kernel = _build(tmp_path)
    assert isinstance(kernel, Kernel)
    cfg = kernel.get_llm_config()
    assert isinstance(cfg, LLMConfig)
    assert cfg.provider == "openai_compat"
    assert cfg.model == "codex_oauth:gpt-5.5"


# ---------------------------------------------------------------------------
# 决策 1/6: create_session per-agent → SessionInfo; submit → RunInfo
# ---------------------------------------------------------------------------


async def test_create_session_returns_session_info(tmp_path: Path) -> None:
    kernel = _build(tmp_path)
    try:
        session = await kernel.create_session(
            workspace_root=tmp_path,
            enabled_tools=["echo"],
            features={"memory_curation": True, "skill_creation": True},
            prompt=PromptSlots(head=(PromptText(name="app.identity", text="# App"),)),
        )
        assert isinstance(session, SessionInfo)
        assert session.session_id
    finally:
        await kernel.aclose()


async def test_submit_and_get_run_return_run_info(tmp_path: Path) -> None:
    kernel = _build(tmp_path)
    try:
        session = await kernel.create_session(
            workspace_root=tmp_path, enabled_tools=["echo"]
        )
        run = kernel.submit(
            session_id=session.session_id,
            parts=[{"type": "text", "text": "hello"}],
            origin=RunOrigin.USER,
        )
        assert isinstance(run, RunInfo)
        assert run.session_id == session.session_id
        record = await _wait_terminal(kernel, run.run_id)
        assert isinstance(kernel.get_run(run.run_id), RunInfo)
        assert record.status == "completed"
    finally:
        await kernel.aclose()


# ---------------------------------------------------------------------------
# 决策 2/9: native tool + closure side-effect tool execute (no host bridge)
# ---------------------------------------------------------------------------


async def test_closure_side_effect_tool_runs(tmp_path: Path) -> None:
    sink: list[str] = []
    kernel = _build(
        tmp_path,
        tools=[_EchoTool(), _make_recording_tool(sink)],
        can_use_tool=_allow_all,
        _llm_client_override=_tool_calling_llm_client("record"),
    )
    try:
        session = await kernel.create_session(
            workspace_root=tmp_path, enabled_tools=["echo", "record"]
        )
        run = kernel.submit(
            session_id=session.session_id,
            parts=[{"type": "text", "text": "record hi"}],
            origin=RunOrigin.USER,
        )
        await _wait_terminal(kernel, run.run_id)
        assert sink == ["hi"], f"closure tool side effect not observed: {sink!r}"
    finally:
        await kernel.aclose()


async def test_closure_tool_presenter_surfaces_in_stream(tmp_path: Path) -> None:
    """A product tool's own presenter (决策 12) reaches tool_start/tool_end events.

    This drives the **real** resolution path: realtime_stream reads the presenter
    off the assembled tool object via ctx.tool_registry (no global registry). Guards
    that presentation is resolved through the kernel-scoped hook chain, not just the
    presenter function in isolation (orchestrator nail-down #1).
    """
    sink: list[str] = []
    kernel = _build(
        tmp_path,
        tools=[_EchoTool(), _make_recording_tool(sink)],
        can_use_tool=_allow_all,
        _llm_client_override=_tool_calling_llm_client("record"),
    )
    presentations: dict[str, dict[str, Any]] = {}
    try:
        session = await kernel.create_session(
            workspace_root=tmp_path, enabled_tools=["echo", "record"]
        )
        run = kernel.submit(
            session_id=session.session_id,
            parts=[{"type": "text", "text": "record hi"}],
            origin=RunOrigin.USER,
        )

        async def _collect() -> None:
            async for ev in kernel.stream(session.session_id):
                name = ev.get("event")
                if name in ("tool_start", "tool_end") and ev.get("name") == "record":
                    presentations[name] = ev.get("presentation") or {}
                if name == "run_status" and ev.get("status") in {
                    "completed",
                    "failed",
                    "cancelled",
                }:
                    return

        await asyncio.wait_for(_collect(), timeout=3.0)

        assert "tool_start" in presentations, "no tool_start presentation captured"
        start = presentations["tool_start"]
        assert start["label"] == "Record"
        assert start["summary"] == "note=hi"
        end = presentations["tool_end"]
        assert end["label"] == "Record"
        assert end["summary"] == "recorded"
        assert end["detail"] == {"note": "hi"}
    finally:
        await kernel.aclose()


# ---------------------------------------------------------------------------
# 决策 4: list_* consistent with assembled kernel
# ---------------------------------------------------------------------------


def test_list_tools_reflects_catalog(tmp_path: Path) -> None:
    sink: list[str] = []
    kernel = _build(tmp_path, tools=[_EchoTool(), _make_recording_tool(sink)])
    names = {t.name for t in kernel.list_tools()}
    assert {"echo", "record"} <= names
    assert all(isinstance(t, ToolInfo) for t in kernel.list_tools())


def test_list_models_includes_default(tmp_path: Path) -> None:
    cfg = LLMConfig(
        provider="anthropic",
        model="kimiCoding:K2.6",
        base_url="http://127.0.0.1:4000",
        default_model="kimiCoding:K2.6",
        providers=(),
    )
    kernel = _build(tmp_path, llm=cfg)
    models = kernel.list_models()
    assert all(isinstance(m, ModelInfo) for m in models)
    assert any(m.is_default for m in models)


def test_list_features_only_kernel_general(tmp_path: Path) -> None:
    kernel = _build(tmp_path)
    feats = kernel.list_features()
    keys = {f.key for f in feats}
    assert keys == {"memory_curation", "skill_creation"}
    assert all(isinstance(f, FeatureInfo) for f in feats)


def test_list_skills_per_workspace(tmp_path: Path) -> None:
    kernel = _build(tmp_path)
    # Empty workspace → empty (or whatever resolves), but the call must be typed.
    skills = kernel.list_skills(workspace_root=tmp_path)
    from agent.sdk.dto import SkillInfo  # noqa: PLC0415

    assert all(isinstance(s, SkillInfo) for s in skills)


# ---------------------------------------------------------------------------
# 决策 8: per-session PromptSlots reach the assembled system prompt
# ---------------------------------------------------------------------------


async def test_prompt_slots_reach_preview(tmp_path: Path) -> None:
    """assemble_prompt_preview with PromptSlots renders the product text."""
    kernel = _build(tmp_path)
    slots = PromptSlots(
        head=(PromptText(name="app.identity", text="# UNIQUE-IDENTITY-MARKER"),)
    )
    result = kernel.assemble_prompt_preview(
        prompt=slots,
        features={"memory_curation": True},
        enabled_tools=["echo"],
        workspace_root=tmp_path,
        scenario="direct",
    )
    assert "UNIQUE-IDENTITY-MARKER" in result["prompt"]
