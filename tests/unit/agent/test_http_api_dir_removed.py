"""Verify agent/platform/http_api/ directory is removed (refactor-387-M4-R3).

http_api was the FastAPI HTTP layer that existed solely to serialize/deserialize
the in-process Kernel calls over the network.  After the SDK migration (M1-M3)
nothing imports it from src/; it must be deleted in M4.
"""

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
HTTP_API_DIR = PROJECT_ROOT / "src" / "agent" / "platform" / "http_api"


def test_http_api_directory_deleted() -> None:
    """agent/platform/http_api/ must be fully deleted in M4."""
    assert not HTTP_API_DIR.exists(), (
        "agent/platform/http_api/ is a dead HTTP layer that must be deleted in M4; "
        f"it still exists at {HTTP_API_DIR}"
    )
