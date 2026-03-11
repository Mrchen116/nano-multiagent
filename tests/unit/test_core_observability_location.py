"""Verify core/observability is the canonical home for tracing and logs."""

from importlib.util import find_spec

from agent.core.observability import (
    bind_correlation,
    capture_logs,
    current_correlation,
    current_trace_id,
    log_debug,
    log_error,
    log_info,
    log_warn,
)
from agent.core.observability.logger import capture_logs as CoreCaptureLogs
from agent.core.observability.logger import log_debug as CoreLogDebug
from agent.core.observability.logger import log_error as CoreLogError
from agent.core.observability.logger import log_info as CoreLogInfo
from agent.core.observability.logger import log_warn as CoreLogWarn
from agent.core.observability.tracing import bind_correlation as CoreBindCorrelation
from agent.core.observability.tracing import current_correlation as CoreCurrentCorrelation
from agent.core.observability.tracing import current_trace_id as CoreCurrentTraceId


def test_core_observability_is_canonical_home() -> None:
    assert bind_correlation is CoreBindCorrelation
    assert capture_logs is CoreCaptureLogs
    assert current_correlation is CoreCurrentCorrelation
    assert current_trace_id is CoreCurrentTraceId
    assert log_debug is CoreLogDebug
    assert log_error is CoreLogError
    assert log_info is CoreLogInfo
    assert log_warn is CoreLogWarn

    assert bind_correlation.__module__ == "agent.core.observability.tracing"
    assert capture_logs.__module__ == "agent.core.observability.logger"
    assert current_correlation.__module__ == "agent.core.observability.tracing"
    assert current_trace_id.__module__ == "agent.core.observability.tracing"
    assert log_debug.__module__ == "agent.core.observability.logger"
    assert log_error.__module__ == "agent.core.observability.logger"
    assert log_info.__module__ == "agent.core.observability.logger"
    assert log_warn.__module__ == "agent.core.observability.logger"


def test_legacy_observability_root_is_removed() -> None:
    assert find_spec("agent.observability") is None
