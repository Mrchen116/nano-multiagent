"""Diagnostic approval export stays prompt-free and accepts pre-recovery rows."""

import importlib.util
import json
from pathlib import Path

import pytest

_PATH = Path(__file__).resolve().parents[2] / "scripts/fixtures/export_review_trace.py"
_SPEC = importlib.util.spec_from_file_location("review_trace_export", _PATH)
assert _SPEC and _SPEC.loader
_MODULE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_MODULE)


def test_old_and_recovery_rows_export_without_prompt_material(tmp_path: Path) -> None:
    directory = tmp_path / "state/nano_approval/sessions"
    directory.mkdir(parents=True)
    trace = {"reviewId": "r", "callId": "new", "attempts": [], "complete": True}
    document = {
        "version": 1,
        "record": [
            {
                "callId": "old",
                "decision": "allow",
                "reason": "private old reason",
                "entries": ["private input"],
            },
            {
                "callId": "new",
                "recovery": trace,
                "reason": "private new reason",
                "delegatedEvidence": "private rows",
            },
        ],
    }
    (directory / "s.json").write_text(json.dumps(document))
    rows = _MODULE.export(tmp_path)
    assert rows[0] == {
        "sessionId": "s",
        "locator": "state/nano_approval/sessions/s.json",
        "callId": "old",
        "decision": "allow",
    }
    assert rows[1]["recovery"] == trace
    assert "private" not in json.dumps(rows)
    assert _MODULE.export(tmp_path, session="missing") == []
    assert _MODULE.export(tmp_path, call_id="new") == [rows[1]]


def test_export_rejects_record_symlink_outside_explicit_root(tmp_path: Path) -> None:
    directory = tmp_path / "runtime/nano_approval/sessions"
    directory.mkdir(parents=True)
    outside = tmp_path / "outside.json"
    outside.write_text('{"version":1,"record":[]}')
    (directory / "s.json").symlink_to(outside)
    with pytest.raises(ValueError, match="escaped"):
        _MODULE.export(tmp_path / "runtime")
