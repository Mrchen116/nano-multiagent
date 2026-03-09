"""Guard that core-oriented packages do not depend on platform facades."""

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = PROJECT_ROOT / "src" / "nano_multiagent"


CORE_ORIENTED_DIRS = [
    SRC_ROOT / "agent",
    SRC_ROOT / "core",
    SRC_ROOT / "session",
    SRC_ROOT / "skills",
    SRC_ROOT / "runs",
    SRC_ROOT / "observability",
]

FORBIDDEN_SNIPPETS = [
    "nano_multiagent.platform.http_api",
    "nano_multiagent.platform.sdk",
    "fastapi",
]



def test_core_oriented_packages_do_not_import_platform_http_or_sdk() -> None:
    checked = 0
    for directory in CORE_ORIENTED_DIRS:
        for path in directory.rglob("*.py"):
            checked += 1
            source = path.read_text(encoding="utf-8")
            for snippet in FORBIDDEN_SNIPPETS:
                assert snippet not in source, f"{path} imports forbidden platform surface: {snippet}"
    assert checked > 0
