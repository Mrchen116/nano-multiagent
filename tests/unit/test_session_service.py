from agent.platform.persistence.session.service import SessionService


def test_create_session_generates_prefixed_id() -> None:
    service = SessionService()

    from pathlib import Path
    session = service.create_session(workspace_root=Path.cwd())

    assert session.session_id.startswith('sess_')
    assert session.status == 'active'
