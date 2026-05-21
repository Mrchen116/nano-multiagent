"""Import guard for M89 core wiring after agent/runs/observability closure."""

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = PROJECT_ROOT / "src" / "agent"

FORBIDDEN_IMPORTS = {
    "core/agent/loop.py": (
        "agent.agent",
        "agent.tools.registry",
    ),
    "core/agent/runtime.py": (
        "agent.agent",
        "agent.skills.workspace",
        "agent.tools.registry",
        "agent.platform",
    ),
    "core/agent/prompting.py": (
        "agent.agent",
        "agent.tools.builtins",
    ),
    "core/runs/registry.py": (
        "agent.runs",
        "agent.observability",
        "agent.platform",
    ),
    "core/observability/logger.py": ("agent.observability",),
    "core/observability/tracing.py": ("agent.observability",),
    "core/llm/factory.py": (
        "agent.llm.protocols",
        "agent.llm.providers",
        "agent.llm.translator",
    ),
    "products/base.py": ("agent.tools.registry",),
    "platform/http_api/app.py": (
        "agent.agent",
        "agent.runs",
        "agent.observability",
    ),
    "platform/http_api/deps.py": (
        "agent.agent",
        "agent.runs",
    ),
    "platform/http_api/routes/session.py": (
        "agent.agent",
        "agent.runs",
    ),
    "platform/http_api/routes/run.py": ("agent.runs",),
    "platform/tools/registry.py": ("agent.observability",),
    "platform/hooks/builtins/usage_metrics.py": ("agent.hooks.session_usage",),
    "platform/hooks/builtins/auto_mode_gate.py": ("agent.tools.safety",),
}


def test_m85_active_layers_do_not_import_legacy_wiring_paths() -> None:
    for relative_path, forbidden_snippets in FORBIDDEN_IMPORTS.items():
        source = (SRC_ROOT / relative_path).read_text(encoding="utf-8")
        for snippet in forbidden_snippets:
            assert snippet not in source, f"{relative_path} still imports legacy path: {snippet}"
