from nano_multiagent.session.service import SessionService


def test_create_session_generates_prefixed_id() -> None:
    service = SessionService()

    session = service.create_session()

    assert session.session_id.startswith('sess_')
    assert session.status == 'active'
