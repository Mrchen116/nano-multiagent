from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_personal_assistant_main_entry_exists() -> None:
    assert (REPO_ROOT / "src" / "personal_assistant" / "main.py").is_file()
