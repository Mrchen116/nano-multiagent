from nano_multiagent.core import ids
from nano_multiagent.server.app import create_app


def test_session_service_uses_core_id_generator(monkeypatch) -> None:
    monkeypatch.setattr(ids, "make_session_id", lambda: "sess_from_core")
    app = create_app()

    created = app.state.session_service.create_session()

    assert created.session_id == "sess_from_core"
