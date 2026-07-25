"""Guard that platform packages do not depend on the sdk composition surface.

`test_core_no_platform_imports.py` already guards `core` against `platform`/`sdk`.
This is the symmetric guard for the other direction of the dependency rule
(``platform → core``, never ``platform → sdk``): platform-owned tools (e.g. the
`agent` tool's built-in subagent type catalog, feat-474) must consume core-owned
value objects like `PromptSlotSeed` directly, not the sdk's `PromptSlots` — sdk is
the outermost layer that assembles both core and platform, so platform importing
it would be a layering inversion.

Only import statements are checked (not docstrings or comments) to avoid false
positives when a module's documentation mentions `agent.sdk` by name without
actually importing it.
"""

import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = PROJECT_ROOT / "src" / "agent"
PLATFORM_ROOT = SRC_ROOT / "platform"

_IMPORT_LINE_RE = re.compile(r"^\s*(?:from|import)\s+", re.MULTILINE)

FORBIDDEN_PREFIXES = ["agent.sdk"]


def test_platform_packages_do_not_import_sdk_surface() -> None:
    checked = 0
    for path in PLATFORM_ROOT.rglob("*.py"):
        checked += 1
        source = path.read_text(encoding="utf-8")
        import_lines = "\n".join(
            line for line in source.splitlines() if _IMPORT_LINE_RE.match(line)
        )
        for prefix in FORBIDDEN_PREFIXES:
            assert prefix not in import_lines, (
                f"{path} imports forbidden higher-level surface: {prefix}"
            )
    assert checked > 0
