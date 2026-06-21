"""bugfix-417-M7 (decision 12): foreground stopper wiring + injection redirect.

These pin the接线 contract the milestone changes:
  - wire_background_tasks exposes a ForegroundExecutionRegistry alongside the
    BackgroundTaskRegistry;
  - build_kernel injects ForegroundExecutionRegistry.stop_for_session (NOT the old
    BackgroundTaskRegistry.stop_foreground_for_session, which is deleted) into the
    core RunsRegistry as the foreground stopper port.

The core RunsRegistry interrupt/cancel logic is unchanged — it only sees the injected
``(session_id) -> bool`` port; what backs that port is the only thing M7 moves.
"""

from __future__ import annotations

from pathlib import Path

from agent.core.background_tasks.foreground_registry import ForegroundExecutionRegistry
from agent.platform.background_tasks.wiring import wire_background_tasks


def test_wiring_exposes_foreground_registry(tmp_path: Path) -> None:
    wiring = wire_background_tasks(workspace_root=tmp_path)
    assert isinstance(wiring.foreground_registry, ForegroundExecutionRegistry)


def test_background_registry_has_no_foreground_patches(tmp_path: Path) -> None:
    """The foreground-specific patches are gone from BackgroundTaskRegistry — the
    structural cleanup that removes the dual-channel bug's habitat."""
    wiring = wire_background_tasks(workspace_root=tmp_path)
    registry = wiring.registry
    assert not hasattr(registry, "stop_foreground_for_session")
    assert not hasattr(registry, "_foreground_task_ids")


def test_kernel_injects_foreground_registry_stopper(tmp_path: Path) -> None:
    """build_kernel must wire the RunsRegistry foreground stopper to the new
    ForegroundExecutionRegistry.stop_for_session, not the background registry."""
    from agent.sdk import LLMConfig, LLMModel, LLMProvider, build_kernel

    llm = LLMConfig(
        provider="openai_compat",
        model="codex_oauth:gpt-5.5",
        base_url="http://127.0.0.1:4000",
        default_model="codex_oauth:gpt-5.5",
        providers=(
            LLMProvider(
                name="openai_compat",
                base_url="http://127.0.0.1:4000",
                models=(LLMModel(name="codex_oauth:gpt-5.5"),),
            ),
        ),
    )
    kernel = build_kernel(
        llm=llm,
        workspace_config_dirname=".nanocode",
        repo_root=tmp_path,
    )
    try:
        runs_registry = kernel._c.runs_registry  # type: ignore[attr-defined]
        injected = runs_registry._foreground_stopper  # type: ignore[attr-defined]
        # The injected port is the foreground registry's bound method.
        assert getattr(injected, "__name__", "") == "stop_for_session"
        assert isinstance(
            getattr(injected, "__self__", None), ForegroundExecutionRegistry
        )
    finally:
        kernel.close()
