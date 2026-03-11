from agent.core.observability.logger import capture_logs, log_info
from agent.core.observability.tracing import bind_correlation


REQUIRED = {"session_id", "turn_id", "tool_call_id", "trace_id"}


def test_log_fields_default_to_none_without_bound_context() -> None:
    with capture_logs() as records:
        log_info("unit_event")

    assert len(records) == 1
    fields = records[0]["fields"]
    assert REQUIRED.issubset(fields.keys())
    assert fields["session_id"] is None
    assert fields["turn_id"] is None
    assert fields["tool_call_id"] is None
    assert fields["trace_id"] is None


def test_log_fields_include_bound_correlation_values() -> None:
    with capture_logs() as records:
        with bind_correlation(
            session_id="sess_obs_unit",
            turn_id="turn_obs_unit",
            tool_call_id="call_obs_unit",
            trace_id="trace_obs_unit",
        ):
            log_info("unit_event_bound")

    assert len(records) == 1
    fields = records[0]["fields"]
    assert fields["session_id"] == "sess_obs_unit"
    assert fields["turn_id"] == "turn_obs_unit"
    assert fields["tool_call_id"] == "call_obs_unit"
    assert fields["trace_id"] == "trace_obs_unit"
