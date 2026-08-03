from pathlib import Path

import tomllib

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_setuptools_package_discovery_includes_personal_assistant() -> None:
    pyproject = tomllib.loads(
        (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    )
    include = pyproject["tool"]["setuptools"]["packages"]["find"]["include"]

    assert "personal_assistant*" in include
