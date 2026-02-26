from nano_multiagent.server.app import create_app


def test_app_wires_session_service() -> None:
    app = create_app()

    session = app.state.session_service.create_session()

    assert session.session_id.startswith('sess_')
    assert session.status == 'active'
