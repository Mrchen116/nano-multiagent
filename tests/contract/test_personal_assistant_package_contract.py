from pathlib import Path

import tomllib


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_personal_assistant_package_root_exists() -> None:
    package_root = REPO_ROOT / "src" / "personal_assistant"

    assert package_root.is_dir()
    assert (package_root / "__init__.py").is_file()
    assert (package_root / "config" / "local_store.py").is_file()


def test_setuptools_package_discovery_includes_personal_assistant() -> None:
    pyproject = tomllib.loads(
        (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    )
    include = pyproject["tool"]["setuptools"]["packages"]["find"]["include"]

    assert "personal_assistant*" in include
