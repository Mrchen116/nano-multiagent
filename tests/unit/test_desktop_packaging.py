"""Unit tests for Crewden Desktop archive graph closure, commit normalization, and Inno Setup contract."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def _load_module(name: str, rel_path: str):
    path = ROOT / rel_path
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_normalize_commit_sha_resolves_short_sha_and_rejects_invalid_ref() -> None:
    bda = _load_module("build_desktop_archives", "scripts/build-desktop-archives.py")
    full_head = bda.normalize_commit_sha("HEAD", ROOT)
    assert len(full_head) == 40
    assert full_head == full_head.lower()

    short_head = full_head[:9]
    assert bda.normalize_commit_sha(short_head, ROOT) == full_head

    with pytest.raises(ValueError, match="Invalid --source-commit"):
        bda.normalize_commit_sha("not-a-valid-git-commit-ref-999999", ROOT)


def test_origin_and_release_base_security_rules() -> None:
    bda = _load_module("build_desktop_archives", "scripts/build-desktop-archives.py")

    assert bda.normalize_im_origin("https://im.crewden.work/") == (
        "https://im.crewden.work",
        "https",
    )
    assert bda.normalize_im_origin("http://10.24.8.15:8011") == (
        "http://10.24.8.15:8011",
        "private_http",
    )
    assert bda.normalize_im_origin("http://crewden-box.local:8011") == (
        "http://crewden-box.local:8011",
        "private_http",
    )
    assert bda.normalize_im_origin("http://127.0.0.1:18080") == (
        "http://127.0.0.1:18080",
        "loopback_http",
    )

    for bad_origin in (
        "http://im.crewden.work",
        "http://sub.crewden.work:8080",
        "http://10.evil.com",
        "http://192.168.evil.com",
        "http://100.64.0.1:8011",
        "https://im.crewden.work/subpath",
    ):
        with pytest.raises(ValueError):
            bda.normalize_im_origin(bad_origin)

    assert bda.normalize_release_base_url("http://10.24.8.15:9000/releases") == (
        "http://10.24.8.15:9000/releases/",
        "private_http",
    )
    with pytest.raises(ValueError):
        bda.normalize_release_base_url("http://im.crewden.work/releases")
    with pytest.raises(ValueError):
        bda.normalize_release_base_url("http://10.evil.com/releases")


def test_build_graph_closes_multi_version_hoists_and_dsh_web_zod_edge() -> None:
    bda = _load_module("build_desktop_archives", "scripts/build-desktop-archives.py")
    bwa = _load_module("build_windows_archives", "scripts/build-windows-archives.py")

    for graph_fn in (lambda: bda.build_graph(set()), bwa.build_graph):
        _app, runtime, groups = graph_fn()
        deps = json.loads(runtime["dependencies.json"].decode("utf-8"))

        visited_pkg_names = {label.rsplit("@", 1)[0] for label in groups.values()}
        missing_hoists = [
            pkg for pkg in visited_pkg_names if f"p/node_modules/{pkg}" not in deps
        ]
        assert missing_hoists == [], f"Missing fallback hoists: {missing_hoists}"
        assert "p/node_modules/zod" in deps

        dsh_web_prefixes = [
            prefix
            for prefix, label in groups.items()
            if label.startswith("@deepseek-ai/dsh-web@")
        ]
        assert dsh_web_prefixes, "Expected @deepseek-ai/dsh-web in runtime graph"
        for prefix in dsh_web_prefixes:
            assert deps.get(f"{prefix}/node_modules/zod") == deps["p/node_modules/zod"]


def test_inno_setup_manifest_defines_default_checked_desktop_shortcut_and_close_apps() -> (
    None
):
    iss_text = (ROOT / "packaging/desktop/windows/CrewdenDesktop.iss").read_text(
        encoding="utf-8"
    )
    assert "CloseApplications=yes" in iss_text
    assert "AppMutex=" not in iss_text
    assert "function PrepareToInstall" in iss_text
    assert "'--stop'" in iss_text
    assert 'Name: "desktopicon"; Description: "创建桌面快捷方式(&D)"' in iss_text
    # Must be checked by default (no `unchecked` flag on desktopicon task).
    task_lines = [
        line for line in iss_text.splitlines() if 'Name: "desktopicon"' in line
    ]
    assert len(task_lines) == 1
    assert "unchecked" not in task_lines[0].lower()
    assert 'Name: "{userdesktop}\\Crewden Desktop"' in iss_text
    assert "Tasks: desktopicon" in iss_text


def test_desktop_smoke_scripts_wait_for_seed_ready_flag_in_host_state() -> None:
    mac_wf = (ROOT / ".github/workflows/desktop-candidate.yml").read_text(
        encoding="utf-8"
    )
    win_smoke = (ROOT / "packaging/desktop/windows/smoke.ps1").read_text(
        encoding="utf-8"
    )
    assert 'data.get("ready") is True' in mac_wf
    assert 'if [ -f "$ISO_ROOT/desktop/host-state.json" ]; then break; fi' not in mac_wf
    assert "$candidate.ready -and $candidate.port" in win_smoke
