"""Architecture guards for Gateway inbound state ownership."""

from __future__ import annotations

from pathlib import Path


_ROOT = Path(__file__).resolve().parents[2]


def _source(relative: str) -> str:
    return (_ROOT / relative).read_text(encoding="utf-8")


def test_composition_and_schedulers_do_not_reach_pipeline_state() -> None:
    sources = {
        "main": _source("src/personal_assistant/main.py"),
        "heartbeat": _source(
            "src/personal_assistant/scheduler/heartbeat_scheduler.py"
        ),
        "cron": _source("src/personal_assistant/scheduler/cron_runner.py"),
    }
    forbidden = (
        "pipeline._agents",
        "pipeline._session_store",
        "pipeline._run_queue",
        'getattr(self._run_queue, "_active_sessions"',
    )

    violations = [
        f"{name}: {snippet}"
        for name, source in sources.items()
        for snippet in forbidden
        if snippet in source
    ]

    assert violations == []


def test_config_and_shadow_adapters_are_not_defined_in_composition_root() -> None:
    main_source = _source("src/personal_assistant/main.py")

    assert "class _IMConfigSyncClient" not in main_source
    assert "class _IMShadowConversationSyncClient" not in main_source
    assert "_IMConfigSyncClient =" not in main_source
    assert "_IMShadowConversationSyncClient =" not in main_source


def test_runtime_consumers_do_not_import_binding_repository() -> None:
    consumers = (
        "src/personal_assistant/gateway/internal_dispatch.py",
        "src/personal_assistant/gateway/runtime_delivery/background.py",
        "src/personal_assistant/scheduler/heartbeat_scheduler.py",
        "src/personal_assistant/scheduler/cron_runner.py",
    )

    violations = [
        relative
        for relative in consumers
        if "gateway.session_keys import" in _source(relative)
    ]

    assert violations == []
