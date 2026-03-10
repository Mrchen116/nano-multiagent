"""Import guard for M85 canonical wiring and legacy path containment."""

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = PROJECT_ROOT / "src" / "nano_multiagent"

FORBIDDEN_IMPORTS = {
    "agent/runtime.py": ("nano_multiagent.skills.workspace",),
    "platform/tools/builtins/task.py": ("nano_multiagent.skills.workspace",),
    "platform/http_api/app.py": ("nano_multiagent.session.service",),
    "platform/http_api/deps.py": ("nano_multiagent.session.service",),
    "platform/http_api/routes/session.py": ("nano_multiagent.session.service",),
    "runs/registry.py": ("nano_multiagent.server.sse",),
    "core/llm/factory.py": ("nano_multiagent.llm.protocols",),
    "platform/llm/providers/__init__.py": ("nano_multiagent.llm.protocols",),
    "products/local_coding/prompts.py": ("nano_multiagent.agent.prompting",),
}


def test_m85_active_layers_do_not_import_legacy_wiring_paths() -> None:
    for relative_path, forbidden_snippets in FORBIDDEN_IMPORTS.items():
        source = (SRC_ROOT / relative_path).read_text(encoding="utf-8")
        for snippet in forbidden_snippets:
            assert snippet not in source, f"{relative_path} still imports legacy path: {snippet}"
