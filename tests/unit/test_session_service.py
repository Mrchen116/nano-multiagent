from pathlib import Path

from agent.core.session.jsonl_store import JsonlSessionStore
from agent.platform.persistence.session.service import SessionService


def test_create_session_generates_prefixed_id() -> None:
    service = SessionService()

    session = service.create_session(workspace_root=Path.cwd())

    assert session.session_id.startswith('sess_')
    assert session.status == 'active'


# ---------------------------------------------------------------------------
# M6 regression: default_session_metadata wired into create_session
# ---------------------------------------------------------------------------


def _service_with_default(tmp_path: Path, default_metadata: dict) -> SessionService:
    store = JsonlSessionStore(data_dir=tmp_path / ".nano")
    return SessionService(store=store, default_session_metadata=default_metadata)


def test_create_session_inherits_default_metadata_when_caller_passes_none(tmp_path: Path) -> None:
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


def test_create_session_caller_metadata_overrides_default_top_level_key(tmp_path: Path) -> None:
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


def test_create_session_no_default_no_caller_metadata_yields_no_self_evolution(tmp_path: Path) -> None:
    """Without a default and without caller metadata, no self_evolution key leaks in."""
    service = SessionService(store=JsonlSessionStore(data_dir=tmp_path / ".nano"))

    session = service.create_session(workspace_root=tmp_path)

    assert "self_evolution" not in session.metadata
