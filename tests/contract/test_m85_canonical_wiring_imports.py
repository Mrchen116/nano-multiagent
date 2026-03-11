"""Import guard for M89 core wiring after agent/runs/observability closure."""

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = PROJECT_ROOT / "src" / "agent"

FORBIDDEN_IMPORTS = {
    "core/agent/loop.py": (
        "nano_multiagent.agent",
        "nano_multiagent.tools.registry",
    ),
    "core/agent/runtime.py": (
        "nano_multiagent.agent",
        "nano_multiagent.skills.workspace",
        "nano_multiagent.tools.registry",
        "nano_multiagent.platform",
    ),
    "core/agent/prompting.py": (
        "nano_multiagent.agent",
        "nano_multiagent.tools.builtins",
    ),
    "core/runs/registry.py": (
        "nano_multiagent.runs",
        "nano_multiagent.observability",
        "nano_multiagent.platform",
    ),
    "core/observability/logger.py": ("nano_multiagent.observability",),
    "core/observability/tracing.py": ("nano_multiagent.observability",),
    "core/llm/factory.py": (
        "nano_multiagent.llm.protocols",
        "nano_multiagent.llm.providers",
        "nano_multiagent.llm.translator",
    ),
    "products/base.py": ("nano_multiagent.tools.registry",),
    "platform/http_api/app.py": (
        "nano_multiagent.agent",
        "nano_multiagent.runs",
        "nano_multiagent.observability",
    ),
    "platform/http_api/deps.py": (
        "nano_multiagent.agent",
        "nano_multiagent.runs",
    ),
    "platform/http_api/routes/session.py": (
        "nano_multiagent.agent",
        "nano_multiagent.runs",
    ),
    "platform/http_api/routes/run.py": ("nano_multiagent.runs",),
    "platform/tools/registry.py": ("nano_multiagent.observability",),
    "platform/hooks/builtins/usage_metrics.py": ("nano_multiagent.hooks.session_usage",),
    "platform/hooks/builtins/bash_risk_gate.py": ("nano_multiagent.tools.safety",),
    "apps/coding_cli/__init__.py": ("nano_multiagent.cli",),
}


def test_m85_active_layers_do_not_import_legacy_wiring_paths() -> None:
    for relative_path, forbidden_snippets in FORBIDDEN_IMPORTS.items():
        source = (SRC_ROOT / relative_path).read_text(encoding="utf-8")
        for snippet in forbidden_snippets:
            assert snippet not in source, f"{relative_path} still imports legacy path: {snippet}"
