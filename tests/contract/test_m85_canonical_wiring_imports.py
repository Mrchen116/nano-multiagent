"""Import guard for M88 canonical wiring after zero-residue cleanup."""

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = PROJECT_ROOT / "src" / "nano_multiagent"

FORBIDDEN_IMPORTS = {
    "agent/loop.py": ("nano_multiagent.tools.registry",),
    "agent/runtime.py": (
        "nano_multiagent.skills.workspace",
        "nano_multiagent.tools.registry",
    ),
    "agent/prompting.py": ("nano_multiagent.tools.builtins",),
    "core/llm/factory.py": (
        "nano_multiagent.llm.protocols",
        "nano_multiagent.llm.providers",
        "nano_multiagent.llm.translator",
    ),
    "products/base.py": ("nano_multiagent.tools.registry",),
    "platform/hooks/builtins/usage_metrics.py": ("nano_multiagent.hooks.session_usage",),
    "platform/hooks/builtins/bash_risk_gate.py": ("nano_multiagent.tools.safety",),
    "apps/coding_cli/__init__.py": ("nano_multiagent.cli",),
}


def test_m85_active_layers_do_not_import_legacy_wiring_paths() -> None:
    for relative_path, forbidden_snippets in FORBIDDEN_IMPORTS.items():
        source = (SRC_ROOT / relative_path).read_text(encoding="utf-8")
        for snippet in forbidden_snippets:
            assert snippet not in source, f"{relative_path} still imports legacy path: {snippet}"
