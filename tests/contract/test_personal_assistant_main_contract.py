from pathlib import Path

from personal_assistant import main as personal_assistant_main


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_personal_assistant_main_entry_exists() -> None:
    assert (REPO_ROOT / "src" / "personal_assistant" / "main.py").is_file()


def test_personal_assistant_main_exports_runtime_lifecycle_controls() -> None:
    assert hasattr(personal_assistant_main, "GatewayRuntime")
    assert hasattr(personal_assistant_main.GatewayRuntime, "wait_until_ready")
    assert hasattr(personal_assistant_main.GatewayRuntime, "request_shutdown")
