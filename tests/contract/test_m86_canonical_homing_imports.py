"""Import guard for M89 canonical homes after core physical closure."""

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = PROJECT_ROOT / "src" / "agent"

DIRECTORY_GUARDS = {
    "apps/coding_cli": (
        "nano_multiagent.cli",
        "nano_multiagent.sdk",
    ),
    "platform/llm/providers": ("nano_multiagent.llm",),
    "platform/persistence/session": ("nano_multiagent.session",),
    "platform/hooks": (
        "nano_multiagent.hooks",
        "nano_multiagent.tools",
    ),
    "platform/tools": ("nano_multiagent.tools",),
    "core/agent": (
        "nano_multiagent.agent",
        "nano_multiagent.runs",
        "nano_multiagent.observability",
        "nano_multiagent.platform",
    ),
    "core/observability": ("nano_multiagent.observability",),
    "core/runs": (
        "nano_multiagent.runs",
        "nano_multiagent.observability",
        "nano_multiagent.platform",
    ),
    "core/skills": ("nano_multiagent.skills",),
}

FILE_GUARDS = {
    "core/agent/loop.py": (
        "nano_multiagent.agent",
        "nano_multiagent.tools",
    ),
    "core/agent/runtime.py": (
        "nano_multiagent.agent",
        "nano_multiagent.skills",
        "nano_multiagent.tools",
        "nano_multiagent.platform",
    ),
    "core/agent/prompting.py": (
        "nano_multiagent.agent",
        "nano_multiagent.tools",
    ),
    "core/hooks/context.py": (
        "nano_multiagent.hooks",
        "nano_multiagent.observability",
    ),
    "core/llm/factory.py": ("nano_multiagent.llm",),
    "core/runs/registry.py": (
        "nano_multiagent.runs",
        "nano_multiagent.observability",
        "nano_multiagent.platform",
    ),
    "products/base.py": ("nano_multiagent.tools",),
}

REMOVED_ROOTS = (
    "agent",
    "cli",
    "hooks",
    "llm",
    "observability",
    "runs",
    "sdk",
    "server",
    "session",
    "skills",
    "tools",
)


def test_m86_directory_canonical_homes_do_not_reference_legacy_modules() -> None:
    for relative_dir, forbidden_snippets in DIRECTORY_GUARDS.items():
        for path in sorted((SRC_ROOT / relative_dir).rglob("*.py")):
            source = path.read_text(encoding="utf-8")
            relative_path = path.relative_to(SRC_ROOT)
            for snippet in forbidden_snippets:
                assert snippet not in source, f"{relative_path} still references legacy path: {snippet}"



def test_m86_active_wiring_layers_do_not_reference_removed_roots() -> None:
    for relative_path, forbidden_snippets in FILE_GUARDS.items():
        source = (SRC_ROOT / relative_path).read_text(encoding="utf-8")
        for snippet in forbidden_snippets:
            assert snippet not in source, f"{relative_path} still references legacy path: {snippet}"



def test_m86_removed_legacy_roots_are_physically_absent() -> None:
    for root_name in REMOVED_ROOTS:
        assert not (SRC_ROOT / root_name).exists(), f"legacy root should be deleted in M88: {root_name}"
