import json

from nano_multiagent.server.sse import encode_sse_event


def test_encode_sse_event_includes_id_event_and_data_lines() -> None:
    payload = {
        "event": "run_status",
        "session_id": "sess_sse_unit",
        "run_id": "run_sse_unit",
        "status": "queued",
    }

    encoded = encode_sse_event(event_id="evt_sse_unit", event="run_status", data=payload)

    assert encoded.startswith("id: evt_sse_unit\n")
    assert "event: run_status\n" in encoded
    assert encoded.endswith("\n\n")

    data_line = next(line for line in encoded.splitlines() if line.startswith("data: "))
    assert json.loads(data_line.removeprefix("data: ")) == payload
