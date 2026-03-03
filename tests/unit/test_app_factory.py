from fastapi import FastAPI

from nano_multiagent.hooks.session_events import get_session_event_publisher
from nano_multiagent.server.app import create_app


def test_create_app_returns_fastapi_instance() -> None:
    app = create_app()
    assert isinstance(app, FastAPI)


def test_create_app_binds_session_event_publisher_with_session_consistency() -> None:
    app = create_app()
    publisher = get_session_event_publisher(
        registry=app.state.hook_registry,
        session_id="sess_app_factory",
    )
    assert publisher is not None

    publisher(
        "custom_event",
        {
            "session_id": "spoofed_session",
            "note": "payload",
        },
    )

    own_events = list(
        app.state.event_stream_hub.stream(
            session_id="sess_app_factory",
            max_events=5,
            timeout_seconds=0.0,
        )
    )
    assert own_events
    latest = own_events[-1]
    assert latest.event == "custom_event"
    assert latest.session_id == "sess_app_factory"
    assert latest.data["session_id"] == "sess_app_factory"
