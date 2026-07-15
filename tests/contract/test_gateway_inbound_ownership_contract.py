"""Architecture guards for Gateway inbound state ownership."""

from __future__ import annotations

from pathlib import Path


_ROOT = Path(__file__).resolve().parents[2]


def _source(relative: str) -> str:
    return (_ROOT / relative).read_text(encoding="utf-8")


def test_composition_and_schedulers_do_not_reach_pipeline_state() -> None:
    sources = {
        "main": _source("src/personal_assistant/main.py"),
        "heartbeat": _source("src/personal_assistant/scheduler/heartbeat_scheduler.py"),
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


def test_inbound_facade_does_not_own_session_run_resources() -> None:
    pipeline = _source("src/personal_assistant/gateway/inbound_pipeline.py")
    forbidden = (
        "SessionRunQueue",
        "_active_runs",
        "_user_interrupted_runs",
        "_session_drain_locks",
        "_image_resolver",
        "_background_subscriptions",
        "_await_terminal_run_async",
        "_handle_stop_command",
    )

    assert "SessionRunCoordinator" in pipeline
    assert [snippet for snippet in forbidden if snippet in pipeline] == []


def test_runtime_lifecycle_does_not_import_inbound_facade() -> None:
    lifecycle = _source("src/personal_assistant/gateway/runtime_delivery/lifecycle.py")

    assert "gateway.inbound_pipeline import" not in lifecycle


def test_gateway_runtime_owns_only_coordinator_session_lifecycle() -> None:
    main_source = _source("src/personal_assistant/main.py")
    runtime_source = main_source[
        main_source.index("class GatewayRuntime:") : main_source.index(
            "def _load_runtime_config"
        )
    ]

    assert "run_coordinator: SessionRunCoordinator" in runtime_source
    assert "self._run_coordinator" in runtime_source
    assert "SessionRunQueue" not in runtime_source
    assert "_run_queue" not in runtime_source
    assert "_background_subscriptions" not in runtime_source


def test_composition_builds_coordinator_before_public_heartbeat_wiring() -> None:
    main_source = _source("src/personal_assistant/main.py")
    build_source = main_source[
        main_source.index("def build_runtime") : main_source.index("def main(")
    ]

    coordinator = "run_coordinator = SessionRunCoordinator("
    heartbeat = "_heartbeat_scheduler = HeartbeatScheduler("
    assert coordinator in build_source
    assert heartbeat in build_source
    assert build_source.index(coordinator) < build_source.index(heartbeat)
    assert "is_session_busy=run_coordinator.is_session_busy" in build_source
    assert "heartbeat_runner._" not in build_source
    assert "run_queue=run_queue" not in build_source
    assert (
        "background_subscriptions=background_subscriptions"
        not in build_source[build_source.rindex("return GatewayRuntime(") :]
    )


def test_config_sync_callback_is_constructor_owned_and_tests_use_real_owners() -> None:
    config_sync = _source("src/personal_assistant/gateway/agent_config_sync.py")
    build_runtime = _source("src/personal_assistant/main.py")

    assert "im_config_sync_client.on_agent_created =" not in build_runtime
    assert "self.on_agent_created" not in config_sync
    for relative in (
        "tests/unit/personal_assistant/test_gateway_im_config_sync.py",
        "tests/unit/personal_assistant/test_gateway_reconcile_callback.py",
        "tests/unit/personal_assistant/test_gateway_reconcile_on_connect.py",
        "tests/unit/personal_assistant/test_cron_config_sync.py",
    ):
        assert "def _ownership(" not in _source(relative)


def test_composition_root_does_not_implement_cron_execution_lifecycle() -> None:
    build_runtime = _source("src/personal_assistant/main.py")
    build_runtime = build_runtime[
        build_runtime.index("def build_runtime") : build_runtime.index("def main(")
    ]

    assert "def _build_cron_execute_fn" not in build_runtime
    assert "CronRunsStore" not in build_runtime
    assert "._submit_cron_job" not in build_runtime
    assert "._append_awareness" not in build_runtime
    assert "._resolve_canonical_session_id" not in build_runtime


def test_config_sync_paths_share_one_mirror_decoder() -> None:
    source = _source("src/personal_assistant/gateway/agent_config_sync.py")

    assert source.count("self._decode_mirror_agent_config(") == 2


def test_gateway_drains_im_outbound_frames_before_transport_close() -> None:
    source = _source("src/personal_assistant/main.py")
    shutdown = source[source.index("async def _run_until_shutdown") :]

    assert shutdown.index('"IM outbound drain"') < shutdown.index(
        '"IM connection close"'
    )
