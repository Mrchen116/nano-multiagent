"""Prevent the removed standalone Kernel process seam from returning to active code."""

from __future__ import annotations

from pathlib import Path

import yaml


_ROOT = Path(__file__).resolve().parents[2]


def _read(relative_path: str) -> str:
    return (_ROOT / relative_path).read_text(encoding="utf-8")


def test_gateway_runtime_and_config_expose_only_in_process_kernel() -> None:
    forbidden_by_file = {
        "src/personal_assistant/main.py": (
            "GatewayProcessManager",
            "process_manager",
            "health_url",
            "_wait_for_gateway_ready",
            "def _spawn_process(",
        ),
        "src/personal_assistant/config/local_store.py": (
            "class KernelConfig",
            "kernel: KernelConfig",
            "DEFAULT_LOCAL_KERNEL_TOKEN",
            "def _parse_kernel",
            "def _derive_kernel_base_url",
        ),
    }

    for relative_path, forbidden in forbidden_by_file.items():
        content = _read(relative_path)
        for snippet in forbidden:
            assert snippet not in content, f"{relative_path} contains {snippet!r}"


def test_active_gateway_entrypoints_do_not_describe_kernel_process_artifacts() -> None:
    active_paths = (
        "AGENTS.md",
        "scripts/e2e-up.sh",
        "scripts/e2e-down.sh",
        "scripts/acceptance/m170_runtime.py",
        "scripts/fixtures/README.md",
        "scripts/fixtures/anthropic_sse_error.py",
        "tests/e2e/conftest.py",
        "tests/unit/test_e2e_conftest_finalizer.py",
        "tests/unit/test_runtime_helpers.py",
    )
    forbidden = (
        ".api.pid",
        "personal_assistant.kernel_app",
        "agent.platform.http_api.app:app",
    )

    for relative_path in active_paths:
        content = _read(relative_path)
        assert "kernel api" not in content.lower(), relative_path
        for snippet in forbidden:
            assert snippet not in content, f"{relative_path} contains {snippet!r}"


def test_tracked_active_sample_configs_do_not_contain_kernel_block() -> None:
    config_paths = (
        "node-config.yaml",
        "ACCEPTANCE/M171-node-config.yaml",
        "ACCEPTANCE/M224-runtime-node-config.yaml",
    )

    for relative_path in config_paths:
        payload = yaml.safe_load(_read(relative_path))
        assert isinstance(payload, dict)
        assert "kernel" not in payload, relative_path


def test_active_test_fixtures_do_not_construct_removed_kernel_config() -> None:
    legacy_name = "Kernel" + "Config"
    guard_path = Path(__file__).resolve()

    for path in (_ROOT / "tests").rglob("*.py"):
        if path.resolve() == guard_path:
            continue
        content = path.read_text(encoding="utf-8")
        assert legacy_name not in content, path.relative_to(_ROOT)


def test_gateway_operator_docs_describe_pid_confirmation_not_health_readiness() -> None:
    for relative_path in ("README.md", "docs/operator-runbook.md"):
        content = _read(relative_path)
        assert "health_url=" not in content, relative_path
        assert "Gateway started (pid=<pid>)" in content, relative_path
        assert "Log:" in content, relative_path
        assert "IM service:" in content, relative_path
        assert "不代表 runtime/channel ready" in content, relative_path
