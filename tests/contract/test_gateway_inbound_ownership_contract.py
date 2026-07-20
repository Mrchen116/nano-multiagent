"""Architecture guards for Gateway inbound state ownership."""

from __future__ import annotations

import ast
from pathlib import Path


_ROOT = Path(__file__).resolve().parents[2]


def _source(relative: str) -> str:
    return (_ROOT / relative).read_text(encoding="utf-8")


def _method_node(
    relative: str, *, class_name: str, method_name: str
) -> ast.FunctionDef:
    tree = ast.parse(_source(relative))
    owner = next(
        node
        for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == class_name
    )
    return next(
        node
        for node in owner.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name == method_name
    )


def _called_names(node: ast.AST) -> set[str]:
    return {
        call.func.id
        for call in ast.walk(node)
        if isinstance(call, ast.Call) and isinstance(call.func, ast.Name)
    }


def _imported_names(relative: str, *, module: str) -> set[str]:
    return {
        alias.name
        for node in ast.walk(ast.parse(_source(relative)))
        if isinstance(node, ast.ImportFrom) and node.module == module
        for alias in node.names
    }


def test_composition_and_schedulers_do_not_reach_pipeline_state() -> None:
    sources = {
        "composition": _source("src/personal_assistant/gateway/composition.py"),
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
    composition_source = _source("src/personal_assistant/gateway/composition.py")

    assert "class _IMConfigSyncClient" not in composition_source
    assert "class _IMShadowConversationSyncClient" not in composition_source
    assert "_IMConfigSyncClient =" not in composition_source
    assert "_IMShadowConversationSyncClient =" not in composition_source


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
    runtime_source = _source("src/personal_assistant/gateway/runtime.py")

    assert "run_coordinator: SessionRunCoordinator" in runtime_source
    assert "self._run_coordinator" in runtime_source
    assert "SessionRunQueue" not in runtime_source
    assert "_run_queue" not in runtime_source
    assert "_background_subscriptions" not in runtime_source


def test_composition_builds_coordinator_before_public_heartbeat_wiring() -> None:
    composition_source = _source("src/personal_assistant/gateway/composition.py")
    build_source = composition_source[composition_source.index("def compose_gateway") :]

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
        not in build_source[build_source.rindex("return runtime.GatewayRuntime(") :]
    )


def test_config_sync_callback_is_constructor_owned_and_tests_use_real_owners() -> None:
    config_sync = _source("src/personal_assistant/gateway/agent_config_sync.py")
    composition_source = _source("src/personal_assistant/gateway/composition.py")

    assert "im_config_sync_client.on_agent_created =" not in composition_source
    assert "self.on_agent_created" not in config_sync
    for relative in (
        "tests/unit/personal_assistant/test_gateway_im_config_sync.py",
        "tests/unit/personal_assistant/test_gateway_reconcile_callback.py",
        "tests/unit/personal_assistant/test_gateway_reconcile_on_connect.py",
        "tests/unit/personal_assistant/test_cron_config_sync.py",
    ):
        assert "def _ownership(" not in _source(relative)


def test_composition_root_does_not_implement_cron_execution_lifecycle() -> None:
    composition_source = _source("src/personal_assistant/gateway/composition.py")
    build_runtime = composition_source[
        composition_source.index("def compose_gateway") :
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
    source = _source("src/personal_assistant/gateway/runtime.py")
    shutdown = source[source.index("async def _run_until_shutdown") :]

    assert shutdown.index('"IM outbound drain"') < shutdown.index(
        '"IM connection close"'
    )


def test_foreground_and_unattended_session_capabilities_share_one_owner() -> None:
    binder_resolve = _method_node(
        "src/personal_assistant/gateway/session_binder.py",
        class_name="GatewaySessionBinder",
        method_name="resolve",
    )
    unattended_create = _method_node(
        "src/personal_assistant/gateway/kernel_client.py",
        class_name="InProcessKernelClient",
        method_name="create_session",
    )

    assert "project_agent_session_capabilities" in _called_names(binder_resolve)
    assert "project_agent_session_capabilities" in _called_names(unattended_create)
    assert not {
        "prompt_for",
        "resolve_enabled_tools",
    }.intersection(_called_names(binder_resolve))
    assert not {
        "prompt_for",
        "resolve_enabled_tools",
    }.intersection(_called_names(unattended_create))


def test_im_http_consumers_depend_on_neutral_public_transport_owner() -> None:
    transport_module = "personal_assistant.gateway.im_http_transport"
    expected_transport_imports = {
        "src/personal_assistant/gateway/agent_config_sync.py": {
            "build_im_http_headers",
            "normalize_im_http_base_url",
        },
        "src/personal_assistant/gateway/shadow_sync.py": {
            "build_im_http_headers",
            "normalize_im_http_base_url",
        },
        "src/personal_assistant/gateway/composition.py": {
            "normalize_im_http_base_url",
        },
        "src/personal_assistant/gateway/image_attachments.py": {
            "build_im_http_headers",
        },
    }

    for relative, expected_public in expected_transport_imports.items():
        assert expected_public.issubset(
            _imported_names(relative, module=transport_module)
        )
        assert not {
            "_im_http_base_url",
            "_im_http_headers",
        }.intersection(
            _imported_names(
                relative,
                module="personal_assistant.gateway.agent_config_sync",
            )
        )


def test_composition_only_constructs_runtime_config_owner() -> None:
    composition_source = _source("src/personal_assistant/gateway/composition.py")

    assert "RuntimeConfigOwner(config)" in composition_source
    assert "provision_feishu_doc_skill_for_gateway" not in composition_source
    assert "register_configured_agents" not in composition_source
