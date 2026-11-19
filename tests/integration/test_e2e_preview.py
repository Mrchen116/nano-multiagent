"""Exercise preview ownership and recovery without provisioning network resources."""

from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import subprocess
import tempfile
import tomllib

import httpx
import pytest

from scripts import e2e_preview_remote as preview


@pytest.fixture
def pool(tmp_path: Path) -> Path:
    for name in ("routes", "leases", "instances"):
        (tmp_path / name).mkdir()
    (tmp_path / "hosts").write_text("a.example.org\nb.example.org\n")
    return tmp_path


def test_two_concurrent_claims_never_share_a_domain(pool: Path) -> None:
    with ThreadPoolExecutor(max_workers=2) as executor:
        hosts = list(
            executor.map(
                lambda name: preview._claim_host(pool, pool / name), ("a", "b")
            )
        )
    assert set(hosts) == {"a.example.org", "b.example.org"}
    with pytest.raises(RuntimeError, match="full"):
        preview._claim_host(pool, pool / "c")


def test_update_failure_retry_and_return_only_own_lease(
    pool, monkeypatch, capsys
) -> None:
    a, b = (pool / "instances" / name for name in ("a", "b"))
    starts = []
    stops = []

    def build(root, instance, commit):
        if commit == "bad-build":
            raise RuntimeError("build failure")
        return Path(tempfile.mkdtemp(prefix="checkout-", dir=instance))

    def run(script, flag, runtime, *args, cwd):
        assert flag == "--wt"
        if script.name == "e2e-down.sh":
            stops.append(runtime)
            assert not (pool / "routes" / f"{runtime.parent.name}.toml").exists()
        else:
            starts.append((runtime, args))
            if "--resume" not in args:
                (runtime / "record").write_text("user data")
                (runtime / ".e2e-preview-password").write_text("private-password")
                (runtime / ".e2e-preview-password").chmod(0o600)
                (runtime / ".e2e-ports.env").write_text(
                    "export IM_PORT=1234\nexport NODE_ID=own-node\n"
                )
            assert (runtime / "record").read_text() == "user data"

    def verified(url, password, node, **kwargs):
        assert password == "private-password" and node == "own-node"

    monkeypatch.setattr(preview, "_build", build)
    monkeypatch.setattr(preview, "_run", run)
    monkeypatch.setattr(preview, "_verify", verified)
    preview._operate(pool, "up", a, "good-a")
    preview._operate(pool, "up", b, "good-b")
    assert "private-password" not in capsys.readouterr().out
    b_state = (pool / "routes/b.toml").read_bytes()
    with pytest.raises(RuntimeError, match="already exists"):
        preview._operate(pool, "up", a, "other-a")
    with pytest.raises(RuntimeError, match="full"):
        preview._operate(pool, "up", pool / "instances/c", "good-c")
    assert not (pool / "instances/c").exists()
    with pytest.raises(RuntimeError, match="build failure"):
        preview._operate(pool, "update", a, "bad-build")
    assert (pool / "routes/a.toml").exists() and not stops

    def failed_probe(*_):
        raise RuntimeError("public login failed")

    monkeypatch.setattr(preview, "_verify", failed_probe)
    with pytest.raises(RuntimeError, match="public login failed"):
        preview._operate(pool, "update", a, "bad-probe")
    assert not (pool / "routes/a.toml").exists()
    assert preview._lease(pool, a).name == "a.example.org"
    monkeypatch.setattr(preview, "_verify", verified)
    preview._operate(pool, "update", a, "retry")
    assert starts[-1] == (
        a / "runtime",
        ("--preview-url", "https://a.example.org", "--resume"),
    )
    config = tomllib.loads((pool / "routes/a.toml").read_text())
    assert config["http"]["routers"]["a"]["rule"] == "Host(`a.example.org`)"
    assert "private-password" not in capsys.readouterr().out
    preview._operate(pool, "password", a, None)
    assert capsys.readouterr().out.strip() == "private-password"
    preview._operate(pool, "down", a, None)
    assert not a.exists() and preview._lease(pool, a) is None
    assert all(wt == a / "runtime" for wt in stops)
    assert (pool / "routes/b.toml").read_bytes() == b_state
    monkeypatch.setattr(preview, "_verify", failed_probe)
    with pytest.raises(RuntimeError, match="public login failed"):
        preview._operate(pool, "up", a, "fresh")
    assert not a.exists() and preview._lease(pool, a) is None
    assert preview._lease(pool, b).name == "b.example.org"


def test_public_probe_uses_browser_origin_and_checks_owner(monkeypatch) -> None:
    session_headers = []

    def handle(request):
        session_headers.append(request.headers)
        if request.url.path.endswith("login"):
            assert json.loads(request.content) == {
                "username": "nano",
                "password": "private-password",
            }
            return httpx.Response(
                200, json={"access_token": "test-token", "user": {"owner_id": "a"}}
            )
        if request.url.path.endswith("logout"):
            return httpx.Response(200, json={"ok": True})
        assert request.headers["Authorization"] == "Bearer test-token"
        return httpx.Response(
            200, json=[{"node_id": "expected", "status": "online", "owner_id": "b"}]
        )

    client = httpx.Client
    monkeypatch.setattr(
        httpx,
        "Client",
        lambda **kw: client(transport=httpx.MockTransport(handle), **kw),
    )
    with pytest.raises(RuntimeError, match="Expected online node"):
        preview._verify("https://a.example.org", "private-password", "expected", wait=0)
    assert all(
        headers["X-IM-Session"] == "browser"
        and headers["Origin"] == "https://a.example.org"
        for headers in session_headers
    )


def test_builds_requested_commit_with_locked_dependencies(tmp_path, monkeypatch):
    repo = tmp_path / "seed"
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    (repo / "scripts").mkdir()
    (repo / "scripts/e2e_ui.py").write_text("print('UI built')\n")
    subprocess.run(["git", "add", "."], cwd=repo, check=True)
    subprocess.run(
        [
            "git",
            "-c",
            "user.name=Tester",
            "-c",
            "user.email=tester@example.org",
            "commit",
            "-qm",
            "fixture",
        ],
        cwd=repo,
        check=True,
    )
    commit = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=repo, text=True
    ).strip()
    subprocess.run(
        ["git", "clone", "--bare", "-q", repo, tmp_path / "source.git"], check=True
    )
    instance = tmp_path / "instance"
    instance.mkdir()
    calls = []
    run = preview._run

    def build_tools(*args, cwd):
        if args[0] in {"pnpm", "npm"}:
            calls.append(args)
        else:
            run(*args, cwd=cwd)

    monkeypatch.setattr(preview, "_run", build_tools)
    source = preview._build(tmp_path, instance, commit)
    assert (
        subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=source, text=True
        ).strip()
        == commit
    )
    assert calls == [
        ("pnpm", "install", "--frozen-lockfile"),
        ("npm", "--prefix", "src/IM/frontend", "ci"),
        ("pnpm", "build"),
    ]


def test_air_cli_sends_head_and_uses_mini_environment(tmp_path, monkeypatch):
    """Exercise the complete Air command with a local SSH transport and real bare Git."""
    import os
    import shlex
    import sys

    mini = tmp_path / "mini"
    root = mini / ".local/share/nano-preview"
    root.mkdir(parents=True)
    subprocess.run(["git", "init", "--bare", "-q", root / "source.git"], check=True)
    (root / "env").write_text(
        "export PATH="
        + shlex.quote(str(Path(sys.executable).parent) + ":" + os.environ["PATH"])
        + "\n"
    )
    (root / "routes").mkdir()
    (root / "hosts").write_text("")
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    ssh = bin_dir / "ssh"
    ssh.write_text(
        "#!/bin/sh\nfor last do :; done\n"
        'export HOME="$FAKE_MINI"\ncd "$HOME" || exit 1\nexec sh -c "$last"\n'
    )
    ssh.chmod(0o755)
    monkeypatch.setenv("PATH", str(bin_dir) + ":" + os.environ["PATH"])
    monkeypatch.setenv("GIT_SSH_COMMAND", str(ssh))
    monkeypatch.setenv("GIT_SSH_VARIANT", "ssh")
    monkeypatch.setenv("FAKE_MINI", str(mini))
    monkeypatch.setenv("NANO_PREVIEW_HOST", "preview-test")
    air = tmp_path / "air"
    air.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=air, check=True)
    subprocess.run(
        [
            "git",
            "-c",
            "user.name=Tester",
            "-c",
            "user.email=tester@example.org",
            "commit",
            "--allow-empty",
            "-qm",
            "air",
        ],
        cwd=air,
        check=True,
    )
    sha = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=air, text=True
    ).strip()
    (air / "unsent").write_text("local only")
    cli = Path(preview.__file__).with_name("e2e-preview.py")
    up = subprocess.run(
        [sys.executable, cli, "up"], cwd=air, text=True, capture_output=True
    )
    assert (
        up.returncode != 0
        and "pool is full" in up.stderr
        and "Uncommitted edits" in up.stderr
    )
    ref = subprocess.check_output(
        ["git", "rev-parse", "refs/nano-preview/" + sha],
        cwd=root / "source.git",
        text=True,
    )
    assert ref.strip() == sha
    status = subprocess.check_output(
        [sys.executable, cli, "status"], cwd=air, text=True
    )
    assert json.loads(status)["status"] == "absent"


def test_down_preserves_unowned_checkout(pool):
    first, second = (pool / "instances" / name for name in ("first", "second"))
    first.mkdir()
    checkout = second / "checkout-foreign"
    checkout.mkdir(parents=True)
    marker = checkout / "file"
    marker.touch()
    (first / "active").symlink_to(checkout)
    with pytest.raises(RuntimeError, match="outside"):
        preview._operate(pool, "down", first, None)
    assert marker.is_file() and first.exists()
