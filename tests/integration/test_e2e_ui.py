"""Build/reuse decisions at the E2E UI preparation command boundary."""

from dataclasses import dataclass, field
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest


ROOT = Path(__file__).resolve().parents[2]
FRONTEND = "src/IM/frontend"
VIEWER = "packages/dsh-trajectory-viewer"
CONTRACTS = "packages/product-contracts"
TRAJECTORY = "packages/trajectory-ui"


@dataclass
class Repository:
    root: Path
    env: dict[str, str] = field(repr=False)


@pytest.fixture
def repository(tmp_path: Path) -> Repository:
    """Use real files and command execution with small local build substitutes."""
    repo = tmp_path / "repo"
    (repo / "scripts").mkdir(parents=True)
    shutil.copyfile(ROOT / "scripts/e2e_ui.py", repo / "scripts/e2e_ui.py")
    for target in (FRONTEND, VIEWER, CONTRACTS, TRAJECTORY):
        (repo / target / "src").mkdir(parents=True)
        (repo / target / "src/main.ts").write_text(target)
        (repo / target / "package.json").write_text("{}")
    (repo / "package.json").write_text("{}")
    (repo / "pnpm-lock.yaml").write_text("lockfileVersion: '9.0'")
    (repo / FRONTEND / "package-lock.json").write_text("{}")
    (repo / FRONTEND / "vite.config.ts").write_text("export default {}")
    (repo / FRONTEND / "index.html").write_text("<main></main>")
    (repo / VIEWER / "build.mjs").write_text("// build viewer")
    (repo / VIEWER / "index.html").write_text("<main></main>")
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    builder = bin_dir / "builder"
    builder.write_text(
        f"#!{sys.executable}\n"
        "import os, pathlib, sys\n"
        "if pathlib.Path(sys.argv[0]).name == 'node':\n"
        " print('v24.22.1'); sys.exit(0)\n"
        "target = pathlib.Path(sys.argv[2])\n"
        "repo = pathlib.Path(os.environ['FIXTURE_REPO'])\n"
        "with (repo / 'builds.log').open('a') as log:\n"
        " log.write(target.relative_to(repo).as_posix() + '\\n')\n"
        "output = target / ('lib' if target.name in ['product-contracts', 'trajectory-ui'] else 'dist')\n"
        "output.mkdir(exist_ok=True)\n"
        "(output / 'index.html').write_text('partial')\n"
        "if (target / 'fail-build').exists(): sys.exit(23)\n"
        "text = ''.join(p.read_text() for p in sorted((target / 'src').glob('*')))\n"
        "(output / 'index.html').write_text(text)\n"
        "(output / 'asset.js').write_text(text + os.environ.get('VITE_IM_API_BASE_URL', 'unset'))\n"
    )
    builder.chmod(0o755)
    for command in ("node", "npm", "pnpm"):
        (bin_dir / command).symlink_to(builder)
    env = {
        **os.environ,
        "PATH": f"{bin_dir}:{os.environ['PATH']}",
        "FIXTURE_REPO": str(repo),
        "VITE_IM_API_BASE_URL": "http://another-environment.invalid",
    }
    return Repository(repo, env)


def prepare(repository: Repository) -> subprocess.CompletedProcess[str]:
    """Run the same helper used by e2e-up, capturing its public outcome."""
    repo, env = repository.root, repository.env
    return subprocess.run(
        [sys.executable, str(repo / "scripts/e2e_ui.py")],
        cwd=repo,
        env=env,
        capture_output=True,
        text=True,
        timeout=15,
    )


def ui_builds(repo: Path) -> list[str]:
    """Read work performed by the two substitute frontend builders."""
    return [
        line
        for line in (repo / "builds.log").read_text().splitlines()
        if line in (FRONTEND, VIEWER)
    ]


def test_reuses_both_builds_after_backend_change_and_content_identical_touch(
    repository,
):
    repo = repository.root
    first = prepare(repository)
    assert first.returncode == 0, first.stderr
    assert ui_builds(repo) == [FRONTEND, VIEWER]
    assert "another-environment" not in (repo / FRONTEND / "dist/asset.js").read_text()
    (repo / "backend.ts").write_text("new backend behavior")
    (repo / FRONTEND / "src/main.ts").touch()
    again = prepare(repository)
    assert again.returncode == 0, again.stderr
    assert ui_builds(repo) == [FRONTEND, VIEWER]
    assert again.stdout.count("reuse") == 2


@pytest.mark.parametrize(
    ("path", "affected"),
    [
        (f"{FRONTEND}/src/new.ts", [FRONTEND]),
        (f"{FRONTEND}/vite.config.ts", [FRONTEND]),
        (f"{FRONTEND}/.env.production", [FRONTEND]),
        (f"{FRONTEND}/package-lock.json", [FRONTEND]),
        (f"{VIEWER}/src/new.ts", [VIEWER]),
        (f"{TRAJECTORY}/src/main.ts", [VIEWER]),
        (f"{CONTRACTS}/src/main.ts", [FRONTEND, VIEWER]),
        ("pnpm-lock.yaml", [FRONTEND, VIEWER]),
    ],
)
def test_rebuilds_affected_outputs_for_changed_or_new_inputs(
    repository, path, affected
):
    repo = repository.root
    assert prepare(repository).returncode == 0
    (repo / path).write_text("changed")
    result = prepare(repository)
    assert result.returncode == 0, result.stderr
    assert ui_builds(repo) == [FRONTEND, VIEWER, *affected]
    assert prepare(repository).returncode == 0
    assert ui_builds(repo) == [FRONTEND, VIEWER, *affected]


@pytest.mark.parametrize("target", [FRONTEND, VIEWER])
def test_rebuilds_after_source_deletion_and_missing_or_overwritten_assets(
    repository, target
):
    repo = repository.root
    assert prepare(repository).returncode == 0
    (repo / target / "src/main.ts").unlink()
    assert prepare(repository).returncode == 0
    (repo / target / "dist/asset.js").unlink()
    assert prepare(repository).returncode == 0
    (repo / target / "dist/index.html").write_text(
        "manually rebuilt for another environment"
    )
    assert prepare(repository).returncode == 0
    assert ui_builds(repo) == [FRONTEND, VIEWER, target, target, target]


def test_failed_build_cannot_be_reused_even_after_source_revert(repository):
    repo = repository.root
    assert prepare(repository).returncode == 0
    source = repo / FRONTEND / "src/main.ts"
    original = source.read_text()
    source.write_text("changed")
    failure = repo / FRONTEND / "fail-build"
    failure.touch()
    failed = prepare(repository)
    assert failed.returncode != 0
    source.write_text(original)
    failure.unlink()
    retried = prepare(repository)
    assert retried.returncode == 0, retried.stderr
    assert ui_builds(repo) == [FRONTEND, VIEWER, FRONTEND, FRONTEND]
    assert (repo / FRONTEND / "dist/index.html").read_text() == original


def test_build_environment_changes_invalidate_but_runtime_proxy_port_does_not(
    repository,
):
    repo, env = repository.root, repository.env
    assert prepare(repository).returncode == 0
    env["VITE_IM_PROXY_TARGET"] = "http://127.0.0.1:54321"
    assert prepare(repository).returncode == 0
    assert ui_builds(repo) == [FRONTEND, VIEWER]
    env["VITE_TEST_OPTION"] = "changed"
    assert prepare(repository).returncode == 0
    assert ui_builds(repo) == [FRONTEND, VIEWER, FRONTEND, VIEWER]
