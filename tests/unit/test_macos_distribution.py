"""Regression checks for Mac release admission that need no signing identity."""

import importlib.util
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location(
    "distribution", ROOT / "packaging/desktop/macos/distribution.py"
)
assert spec and spec.loader
distribution = importlib.util.module_from_spec(spec)
spec.loader.exec_module(distribution)


def test_missing_signing_credentials_stop_before_creating_artifacts(tmp_path):
    target = tmp_path / "signed"
    with pytest.raises(ValueError, match="Developer ID"):
        distribution.sign_candidate(tmp_path / "candidate", target, "", "")
    assert not target.exists()


def test_rejected_notary_submission_cannot_be_stapled(tmp_path, monkeypatch):
    monkeypatch.setattr(
        distribution, "output", lambda *args: '{"id":"test","status":"Invalid"}'
    )
    monkeypatch.setattr(
        distribution, "run", lambda *args: pytest.fail(f"unexpected staple: {args}")
    )
    with pytest.raises(ValueError, match="Apple rejected"):
        distribution.notarize(tmp_path / "app.zip", tmp_path / "Crewden.app", "test")


def test_higher_native_minimum_rejects_candidate_even_when_node_would_run(monkeypatch):
    monkeypatch.setattr(
        distribution,
        "output",
        lambda *args: "platform MACOS\n   minos 15.0\n    sdk 15.4",
    )
    with pytest.raises(ValueError, match="requires macOS 15.0"):
        distribution.check_target(Path("required-addon.node"), "13.5")
    distribution.check_target(Path("required-addon.node"), "15.0")


def test_signed_channel_rejects_unsigned_dmg_before_mount(tmp_path, monkeypatch):
    dmg = tmp_path / distribution.DMG
    dmg.write_bytes(b"unsigned candidate")
    distribution.write_json(
        tmp_path / distribution.MANIFEST, {"installer": distribution.metadata(dmg)}
    )

    def reject(*args):
        assert args[0] == "codesign" and args[-1] == dmg
        raise subprocess.CalledProcessError(1, args)

    monkeypatch.setattr(distribution, "run", reject)
    with pytest.raises(subprocess.CalledProcessError):
        distribution.verify(tmp_path, "developer-id-notarized", "AAAAAAAAAA")
    assert "macos_distribution" not in distribution.read_json(
        tmp_path / distribution.MANIFEST
    )
