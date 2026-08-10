from pathlib import Path

import pytest

from agent.platform.workflows.saved import SavedWorkflowRegistry


SCRIPT = """
meta = {"name": "review", "description": "Review changes"}
async def main():
    return args
"""


def test_nearest_project_overrides_personal_and_save_is_discoverable(
    tmp_path: Path,
) -> None:
    project = tmp_path / "repo"
    nested = project / "packages" / "api"
    nested.mkdir(parents=True)
    (project / ".git").mkdir()
    personal = tmp_path / "home" / ".nanocode" / "workflows"
    personal.mkdir(parents=True)
    (personal / "review.py").write_text(
        SCRIPT.replace("project", "personal"), encoding="utf-8"
    )
    nearest = nested / ".nanocode" / "workflows"
    nearest.mkdir(parents=True)
    (nearest / "review.py").write_text(SCRIPT, encoding="utf-8")
    registry = SavedWorkflowRegistry(
        config_dirname=".nanocode",
        personal_root=personal,
    )

    resolved = registry.resolve("review", workspace_root=nested)
    saved = registry.save(
        source=SCRIPT,
        name="verify",
        scope="project",
        workspace_root=nested,
    )

    assert resolved is not None
    assert resolved.scope == "project"
    assert Path(resolved.path) == nearest / "review.py"
    assert Path(saved.path) == nearest / "verify.py"
    assert {item.name for item in registry.list(workspace_root=nested)} >= {
        "review",
        "verify",
    }


def test_project_save_rejects_symlinked_destination(tmp_path: Path) -> None:
    project = tmp_path / "repo"
    project.mkdir()
    (project / ".git").mkdir()
    actual = tmp_path / "actual"
    actual.mkdir()
    (project / ".nanocode").symlink_to(actual, target_is_directory=True)
    registry = SavedWorkflowRegistry(
        config_dirname=".nanocode",
        personal_root=tmp_path / "personal",
    )

    with pytest.raises(ValueError, match="symlink"):
        registry.save(
            source=SCRIPT,
            name="review",
            scope="project",
            workspace_root=project,
        )


def test_bundled_workflow_is_discovered_below_personal_and_project(
    tmp_path: Path,
) -> None:
    project = tmp_path / "repo"
    project.mkdir()
    (project / ".git").mkdir()
    bundled = tmp_path / "bundled"
    bundled.mkdir()
    (bundled / "deep-research.py").write_text(SCRIPT, encoding="utf-8")
    personal = tmp_path / "personal"
    personal.mkdir()
    (personal / "deep-research.py").write_text(
        SCRIPT.replace("Review changes", "Personal research"), encoding="utf-8"
    )
    registry = SavedWorkflowRegistry(
        config_dirname=".nanocode",
        personal_root=personal,
        bundled_root=bundled,
    )

    discovered = {item.name: item for item in registry.list(workspace_root=project)}

    assert discovered["deep-research"].scope == "personal"
    assert (
        registry.resolve("deep-research", workspace_root=project)
        == discovered["deep-research"]
    )
