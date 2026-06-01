"""Import guard for M89 canonical homes after core physical closure."""

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = PROJECT_ROOT / "src" / "agent"

DIRECTORY_GUARDS = {
    "apps/coding_cli": (
        "agent.cli",
        "agent.sdk",
    ),
    "platform/llm/providers": ("agent.llm",),
    "platform/persistence/session": ("agent.session",),
    "platform/hooks": (
        "agent.hooks",
        "agent.tools",
    ),
    "platform/tools": ("agent.tools",),
    "core/agent": (
        "agent.agent",
        "agent.runs",
        "agent.observability",
        "agent.platform",
    ),
    "core/observability": ("agent.observability",),
    "core/runs": (
        "agent.runs",
        "agent.observability",
        "agent.platform",
    ),
    "core/skills": ("agent.skills",),
}

FILE_GUARDS = {
    "core/agent/loop.py": (
        "agent.agent",
        "agent.tools",
    ),
    "core/agent/runtime.py": (
        "agent.agent",
        "agent.skills",
        "agent.tools",
        "agent.platform",
    ),
    "core/agent/prompting.py": (
        "agent.agent",
        "agent.tools",
    ),
    "core/hooks/context.py": (
        "agent.hooks",
        "agent.observability",
    ),
    "core/llm/factory.py": ("agent.llm",),
    "core/runs/registry.py": (
        "agent.runs",
        "agent.observability",
        "agent.platform",
    ),
    "products/base.py": ("agent.tools",),
}

REMOVED_ROOTS = (
    "agent",
    "cli",
    "hooks",
    "llm",
    "observability",
    "runs",
    # "sdk" removed from this list in refactor-387-M1: agent/sdk/ is now the
    # public surface for products (build_kernel → Kernel).  The old "agent.sdk"
    # legacy root referenced here was a prior shallow alias; the new agent/sdk/
    # package is architecturally correct and intentional.
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
                assert snippet not in source, (
                    f"{relative_path} still references legacy path: {snippet}"
                )


def test_m86_active_wiring_layers_do_not_reference_removed_roots() -> None:
    for relative_path, forbidden_snippets in FILE_GUARDS.items():
        source = (SRC_ROOT / relative_path).read_text(encoding="utf-8")
        for snippet in forbidden_snippets:
            assert snippet not in source, (
                f"{relative_path} still references legacy path: {snippet}"
            )


def test_m86_removed_legacy_roots_are_physically_absent() -> None:
    for root_name in REMOVED_ROOTS:
        assert not (SRC_ROOT / root_name).exists(), (
            f"legacy root should be deleted in M88: {root_name}"
        )
