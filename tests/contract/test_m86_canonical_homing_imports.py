"""Import guards for M86 canonical ownership after physical implementation moves."""

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = PROJECT_ROOT / "src" / "nano_multiagent"

DIRECTORY_GUARDS = {
    "apps/coding_cli": ("nano_multiagent.cli.",),
    "platform/llm/providers": (
        "nano_multiagent.llm.providers",
        "nano_multiagent.llm.translator",
    ),
    "platform/persistence/session": (
        "nano_multiagent.session.serializers",
        "nano_multiagent.session.service",
    ),
    "platform/hooks": (
        "nano_multiagent.hooks.session_events",
        "nano_multiagent.hooks.session_usage",
    ),
    "platform/tools": (
        "nano_multiagent.tools.base",
        "nano_multiagent.tools.constants",
        "nano_multiagent.tools.registry",
    ),
}

FILE_GUARDS = {
    "agent/runtime.py": ("nano_multiagent.hooks.session_events",),
    "runs/registry.py": ("nano_multiagent.hooks.session_events",),
    "platform/bootstrap.py": ("nano_multiagent.tools.registry",),
    "platform/http_api/app.py": (
        "nano_multiagent.hooks.session_events",
        "nano_multiagent.session.service",
        "nano_multiagent.tools.registry",
    ),
    "platform/http_api/deps.py": (
        "nano_multiagent.session.service",
        "nano_multiagent.tools.registry",
    ),
    "platform/http_api/routes/session.py": (
        "nano_multiagent.hooks.session_usage",
        "nano_multiagent.session.service",
        "nano_multiagent.tools.registry",
    ),
}


def test_m86_directory_canonical_homes_do_not_import_legacy_modules() -> None:
    for relative_dir, forbidden_snippets in DIRECTORY_GUARDS.items():
        for path in sorted((SRC_ROOT / relative_dir).rglob("*.py")):
            source = path.read_text(encoding="utf-8")
            relative_path = path.relative_to(SRC_ROOT)
            for snippet in forbidden_snippets:
                assert snippet not in source, f"{relative_path} still imports legacy path: {snippet}"



def test_m86_active_wiring_layers_do_not_depend_on_legacy_homes() -> None:
    for relative_path, forbidden_snippets in FILE_GUARDS.items():
        source = (SRC_ROOT / relative_path).read_text(encoding="utf-8")
        for snippet in forbidden_snippets:
            assert snippet not in source, f"{relative_path} still imports legacy path: {snippet}"
