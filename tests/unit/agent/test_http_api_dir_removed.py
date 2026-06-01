"""Verify agent/platform/http_api/ source files are removed (refactor-387-M4-R3).

http_api was the FastAPI HTTP layer that existed solely to serialize/deserialize
the in-process Kernel calls over the network.  After the SDK migration (M1-M3)
nothing imports it from src/; it must be deleted in M4.

Note: we check for *.py source files rather than directory existence because
gitignored __pycache__ directories may physically linger after `git rm` even
though no tracked source remains.  No .py files → not importable → effectively
deleted from the module tree.
"""

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
HTTP_API_DIR = PROJECT_ROOT / "src" / "agent" / "platform" / "http_api"


def test_http_api_source_files_deleted() -> None:
    """agent/platform/http_api/ must contain no .py source files after M4.

    Checks .py files rather than directory existence so that gitignored
    __pycache__ residuals (left behind when the directory was last imported
    before deletion) do not cause false failures on machines that ran the
    test suite against the old code.
    """
    py_files = list(HTTP_API_DIR.rglob("*.py")) if HTTP_API_DIR.exists() else []
    assert py_files == [], (
        "agent/platform/http_api/ still contains .py source files — "
        "these must be deleted in M4:\n"
        + "\n".join(f"  {f}" for f in py_files)
    )
