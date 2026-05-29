"""Verify coding_cli HTTP dead files are removed (refactor-387-M4-R2).

These files were part of the old managed-server/HTTP-client architecture
and have no callers after M2; they must not exist in the final state.
"""

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CODING_CLI_ROOT = PROJECT_ROOT / "src" / "coding_cli"


def test_coding_cli_client_py_deleted() -> None:
    """coding_cli/client.py (HTTP ServerClient) must be deleted in M4."""
    assert not (CODING_CLI_ROOT / "client.py").exists(), (
        "coding_cli/client.py is a dead HTTP file that must be deleted in M4"
    )


def test_coding_cli_kernel_app_py_deleted() -> None:
    """coding_cli/kernel_app.py (spawn kernel uvicorn) must be deleted in M4."""
    assert not (CODING_CLI_ROOT / "kernel_app.py").exists(), (
        "coding_cli/kernel_app.py is a dead file that must be deleted in M4"
    )


def test_coding_cli_managed_server_py_deleted() -> None:
    """coding_cli/managed_server.py (subprocess mgmt) must be deleted in M4."""
    assert not (CODING_CLI_ROOT / "managed_server.py").exists(), (
        "coding_cli/managed_server.py is a dead file that must be deleted in M4"
    )


def test_coding_cli_session_stream_py_deleted() -> None:
    """coding_cli/session_stream.py (bg thread SSE bridge) must be deleted in M4."""
    assert not (CODING_CLI_ROOT / "session_stream.py").exists(), (
        "coding_cli/session_stream.py is a dead file that must be deleted in M4"
    )
