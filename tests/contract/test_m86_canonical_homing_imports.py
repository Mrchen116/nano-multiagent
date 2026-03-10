"""Import guard for M88 canonical homes after legacy root deletion."""

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = PROJECT_ROOT / "src" / "nano_multiagent"

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
    "core/skills": ("nano_multiagent.skills",),
}

FILE_GUARDS = {
    "agent/loop.py": ("nano_multiagent.tools",),
    "agent/runtime.py": (
        "nano_multiagent.skills",
        "nano_multiagent.tools",
    ),
    "agent/prompting.py": ("nano_multiagent.tools",),
    "core/hooks/context.py": ("nano_multiagent.hooks",),
    "core/llm/factory.py": ("nano_multiagent.llm",),
    "products/base.py": ("nano_multiagent.tools",),
}

REMOVED_ROOTS = (
    "cli",
    "server",
    "session",
    "hooks",
    "skills",
    "llm",
    "tools",
    "sdk",
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
