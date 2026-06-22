"""Real-LLM e2e regression guard for bugfix-418 (#117).

Foreground ``agent`` tool subagents used to crash at startup with
``... is bound to a different event loop`` because the path ran a *shared*
AgentRuntime via bare ``asyncio.run`` on a transient loop in a private
ThreadPoolExecutor. The fix submits the bare ``runtime.run(...)`` coroutine onto
the kernel's dedicated event loop (``RunsRegistry``'s loop) via
``RuntimeRunner.submit_foreground``.

This e2e wires a REAL ``RunsRegistry`` (real dedicated loop), a REAL
``AgentRuntime`` talking to the local LLM proxy, and the REAL background-task
wiring — i.e. the exact production path — then:

1. dispatches a foreground subagent and asserts it returns a completed result
   (not a cross-loop error);
2. dispatches a *failing* subagent and asserts the failure is contained to the
   tool result AND the dedicated loop / a subsequent run survive (isolation —
   the incident's "single subagent failure takes the whole node offline").

Gated behind ``NANO_MULTIAGENT_RUN_LIVE_PROXY_E2E=1`` + proxy health, same as
the other live-proxy e2e tests.
"""

from __future__ import annotations

import os
from pathlib import Path

import httpx
import pytest

from agent.core.agent.runtime import AgentRuntime
from agent.core.llm.factory import LLMFactoryConfig
from agent.core.runs.registry import RunsRegistry
from agent.core.session.jsonl_store import JsonlSessionStore
from agent.core.tools.base import (
    set_tool_safety_config_factory,
    set_tool_safety_factory,
)
from agent.platform.background_tasks.wiring import wire_background_tasks
from agent.platform.llm.factory import create_llm_client
from agent.platform.persistence.session.service import SessionService
from agent.platform.tools.base import ToolContext
from agent.platform.tools.builtins.agent import AgentTool
from agent.platform.tools.safety import ToolSafety, ToolSafetyConfig

set_tool_safety_factory(ToolSafety)
set_tool_safety_config_factory(ToolSafetyConfig)


def _llm_proxy_available() -> bool:
    try:
        response = httpx.get("http://127.0.0.1:4000/health", timeout=1.5)
    except httpx.HTTPError:
        return False
    return response.status_code == 200


def _require_live_proxy() -> None:
    if os.getenv("NANO_MULTIAGENT_RUN_LIVE_PROXY_E2E") != "1":
        pytest.skip(
            "set NANO_MULTIAGENT_RUN_LIVE_PROXY_E2E=1 to run live proxy e2e tests"
        )
    if not _llm_proxy_available():
        pytest.skip("LLM_PROXY is unavailable on http://127.0.0.1:4000")


def _make_ctx(tmp_path: Path) -> ToolContext:
    return ToolContext.create(repo_root=tmp_path).with_session(session_id="sess_parent")


@pytest.mark.e2e
def test_foreground_subagent_completes_via_dedicated_loop(tmp_path: Path) -> None:
    """A foreground subagent runs on the dedicated loop and returns a result."""
    _require_live_proxy()

    service = SessionService(store=JsonlSessionStore(data_dir=tmp_path / "sessions"))
    llm_client = create_llm_client(config=LLMFactoryConfig.from_env())
    runtime = AgentRuntime(
        session_manager=service.manager, llm_client=llm_client, model=""
    )
    runs = RunsRegistry(runtime=runtime, session_manager=service.manager)
    try:
        wiring = wire_background_tasks(
            workspace_root=tmp_path, runtime=runtime, runs_registry=runs
        )
        tool = AgentTool(runtime=runtime, wiring=wiring)
        ctx = _make_ctx(tmp_path)

        result = tool.run(
            {
                "description": "say pong",
                "prompt": "Reply with exactly one word: pong",
                "subagent_type": "explore",
                "load_skills": [],
                "run_in_background": False,
                "timeout_seconds": 90,
            },
            ctx,
        )

        assert result["status"] == "completed", result
        assert "different event loop" not in str(result.get("content", "")), result
        assert "pong" in str(result.get("content", "")).lower(), result
    finally:
        runs.shutdown()


@pytest.mark.e2e
def test_failing_foreground_subagent_does_not_kill_dedicated_loop(
    tmp_path: Path,
) -> None:
    """A subagent failure is contained; the dedicated loop keeps serving runs.

    Mirrors the incident's escalation: a single failing subagent must NOT take
    the resident node offline. We force a failure by pointing the runtime at a
    non-existent model, observe the tool returns status=failed, then run a second
    subagent on a healthy runtime sharing the SAME dedicated loop and assert it
    still completes.
    """
    _require_live_proxy()

    service = SessionService(store=JsonlSessionStore(data_dir=tmp_path / "sessions"))
    llm_client = create_llm_client(config=LLMFactoryConfig.from_env())

    good_runtime = AgentRuntime(
        session_manager=service.manager, llm_client=llm_client, model=""
    )
    # The dedicated loop belongs to the healthy runtime; the FAILING subagent
    # coroutine is still submitted onto this same loop. Isolation requires that
    # its failure stay inside the returned future and not kill this loop.
    runs = RunsRegistry(runtime=good_runtime, session_manager=service.manager)
    try:
        ctx = _make_ctx(tmp_path)

        # A runtime whose subagent turn deterministically raises. It shares the
        # healthy runtime's session manager so _create_subagent_session works,
        # but its run() blows up — mimicking the incident's failing subagent.
        class _FailingRuntime(AgentRuntime):
            async def run(self, *args, **kwargs):  # type: ignore[override]
                raise RuntimeError("subagent turn exploded (injected)")

        failing_runtime = _FailingRuntime(
            session_manager=service.manager, llm_client=llm_client, model=""
        )
        bad_wiring = wire_background_tasks(
            workspace_root=tmp_path, runtime=failing_runtime, runs_registry=runs
        )
        bad_tool = AgentTool(runtime=failing_runtime, wiring=bad_wiring)

        failed = bad_tool.run(
            {
                "description": "doomed",
                "prompt": "this will fail",
                "subagent_type": "explore",
                "load_skills": [],
                "run_in_background": False,
                "timeout_seconds": 90,
            },
            ctx,
        )
        assert failed["status"] == "failed", failed
        assert "exploded" in str(failed.get("error", "")), failed

        # The SAME dedicated loop must still be alive and serve a healthy run.
        good_wiring = wire_background_tasks(
            workspace_root=tmp_path, runtime=good_runtime, runs_registry=runs
        )
        good_tool = AgentTool(runtime=good_runtime, wiring=good_wiring)

        ok = good_tool.run(
            {
                "description": "still alive",
                "prompt": "Reply with exactly one word: pong",
                "subagent_type": "explore",
                "load_skills": [],
                "run_in_background": False,
                "timeout_seconds": 90,
            },
            ctx,
        )

        assert ok["status"] == "completed", ok
        assert "pong" in str(ok.get("content", "")).lower(), ok
        # The dedicated loop survived the failure.
        assert runs.get_event_loop() is not None
        assert runs.get_event_loop().is_running()
    finally:
        runs.shutdown()
