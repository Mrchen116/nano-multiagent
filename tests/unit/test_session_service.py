from pathlib import Path

from agent.core.session.jsonl_store import JsonlSessionStore
from agent.platform.persistence.session.service import SessionService


def test_create_session_generates_prefixed_id() -> None:
    service = SessionService()

    session = service.create_session(workspace_root=Path.cwd())

    assert session.session_id.startswith("sess_")
    assert session.status == "active"


# ---------------------------------------------------------------------------
# M6 regression: default_session_metadata wired into create_session
# ---------------------------------------------------------------------------


def _service_with_default(tmp_path: Path, default_metadata: dict) -> SessionService:
    store = JsonlSessionStore(data_dir=tmp_path / ".nano")
    return SessionService(store=store, default_session_metadata=default_metadata)


def test_create_session_inherits_default_metadata_when_caller_passes_none(
    tmp_path: Path,
) -> None:
    """No caller-supplied metadata → session.metadata equals the bootstrap default.

    Regression for feat-349 M6: bootstrap_product wrote `default_session_metadata`
    into ResolvedProductConfig but SessionService never read it, so CLI-created
    sessions saw `self_evolution = {}` and the hook silently fell back to its
    interval=10 default — feat-349 self-evolution never triggered in real use.
    """
    default = {"self_evolution": {"enabled": True, "skill_nudge_interval": 3}}
    service = _service_with_default(tmp_path, default)

    session = service.create_session(workspace_root=tmp_path)

    assert session.metadata.get("self_evolution") == {
        "enabled": True,
        "skill_nudge_interval": 3,
    }


def test_create_session_caller_metadata_overrides_default_top_level_key(
    tmp_path: Path,
) -> None:
    """Caller-supplied keys win; unspecified keys keep the bootstrap default."""
    default = {
        "self_evolution": {"enabled": True, "skill_nudge_interval": 3},
        "feature_flag_x": "default",
    }
    service = _service_with_default(tmp_path, default)

    session = service.create_session(
        workspace_root=tmp_path,
        metadata={"feature_flag_x": "override"},
    )

    # Caller's top-level key wins; unspecified top-level key stays at default.
    assert session.metadata.get("feature_flag_x") == "override"
    assert session.metadata.get("self_evolution") == {
        "enabled": True,
        "skill_nudge_interval": 3,
    }


def test_create_session_no_default_no_caller_metadata_yields_no_self_evolution(
    tmp_path: Path,
) -> None:
    """Without a default and without caller metadata, no self_evolution key leaks in."""
    service = SessionService(store=JsonlSessionStore(data_dir=tmp_path / ".nano"))

    session = service.create_session(workspace_root=tmp_path)

    assert "self_evolution" not in session.metadata


# ---------------------------------------------------------------------------
# C1-R2: SessionService.prepare_transcript_for_run (RED tests)
# ---------------------------------------------------------------------------


import json


def _write_raw(path: Path, lines: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        for entry in lines:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def _read_raw(path: Path) -> list[dict]:
    result = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                result.append(json.loads(line))
    return result


class TestServicePrepareTranscript:
    """SessionService.prepare_transcript_for_run 委托 store，幂等。"""

    def test_service_prepare_orphaned_tool_call(self, tmp_path: Path) -> None:
        """service.prepare_transcript_for_run 补写未闭合 tool_call recovery entry。"""
        store = JsonlSessionStore(data_dir=tmp_path)
        service = SessionService(store=store)

        session = service.create_session(workspace_root=tmp_path)
        call_id = "call-svc-001"
        path = store.resolve_path(session.session_id)
        _write_raw(
            path,
            [
                {
                    "type": "turn",
                    "uuid": "msg-svc-asst-1",
                    "parent_uuid": None,
                    "session_id": session.session_id,
                    "role": "assistant",
                    "content": "",
                    "timestamp": "2026-01-01T00:00:00+00:00",
                    "tool_calls": [
                        {"call_id": call_id, "name": "bash", "arguments": {}}
                    ],
                }
            ],
        )

        service.prepare_transcript_for_run(session.session_id, reason="interrupted")

        raw = _read_raw(path)
        recovery = [e for e in raw if e.get("type") == "tool_call_recovery"]
        assert len(recovery) == 1
        assert recovery[0]["tool_call_id"] == call_id
        assert recovery[0]["idempotency_key"] == f"tool-call-recovery:{call_id}"

    def test_service_prepare_idempotent(self, tmp_path: Path) -> None:
        """两次 prepare 产生且仅产生一个 recovery entry。"""
        store = JsonlSessionStore(data_dir=tmp_path)
        service = SessionService(store=store)

        session = service.create_session(workspace_root=tmp_path)
        call_id = "call-svc-idem-002"
        path = store.resolve_path(session.session_id)
        _write_raw(
            path,
            [
                {
                    "type": "turn",
                    "uuid": "msg-svc-2",
                    "parent_uuid": None,
                    "session_id": session.session_id,
                    "role": "assistant",
                    "content": "",
                    "timestamp": "2026-01-01T00:00:00+00:00",
                    "tool_calls": [
                        {"call_id": call_id, "name": "read", "arguments": {}}
                    ],
                }
            ],
        )

        service.prepare_transcript_for_run(session.session_id, reason="cancelled")
        service.prepare_transcript_for_run(session.session_id, reason="cancelled")

        raw = _read_raw(path)
        recovery = [e for e in raw if e.get("type") == "tool_call_recovery"]
        assert len(recovery) == 1, "幂等: 两次 prepare 只产生一个 recovery entry"
