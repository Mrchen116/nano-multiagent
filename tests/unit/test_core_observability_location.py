"""Verify core/observability is the canonical home for tracing and logs."""

from importlib.util import find_spec

from nano_multiagent.core.observability import (
    bind_correlation,
    capture_logs,
    current_correlation,
    current_trace_id,
    log_debug,
    log_error,
    log_info,
    log_warn,
)
from nano_multiagent.core.observability.logger import capture_logs as CoreCaptureLogs
from nano_multiagent.core.observability.logger import log_debug as CoreLogDebug
from nano_multiagent.core.observability.logger import log_error as CoreLogError
from nano_multiagent.core.observability.logger import log_info as CoreLogInfo
from nano_multiagent.core.observability.logger import log_warn as CoreLogWarn
from nano_multiagent.core.observability.tracing import bind_correlation as CoreBindCorrelation
from nano_multiagent.core.observability.tracing import current_correlation as CoreCurrentCorrelation
from nano_multiagent.core.observability.tracing import current_trace_id as CoreCurrentTraceId


def test_core_observability_is_canonical_home() -> None:
    assert bind_correlation is CoreBindCorrelation
    assert capture_logs is CoreCaptureLogs
    assert current_correlation is CoreCurrentCorrelation
    assert current_trace_id is CoreCurrentTraceId
    assert log_debug is CoreLogDebug
    assert log_error is CoreLogError
    assert log_info is CoreLogInfo
    assert log_warn is CoreLogWarn

    assert bind_correlation.__module__ == "nano_multiagent.core.observability.tracing"
    assert capture_logs.__module__ == "nano_multiagent.core.observability.logger"
    assert current_correlation.__module__ == "nano_multiagent.core.observability.tracing"
    assert current_trace_id.__module__ == "nano_multiagent.core.observability.tracing"
    assert log_debug.__module__ == "nano_multiagent.core.observability.logger"
    assert log_error.__module__ == "nano_multiagent.core.observability.logger"
    assert log_info.__module__ == "nano_multiagent.core.observability.logger"
    assert log_warn.__module__ == "nano_multiagent.core.observability.logger"


def test_legacy_observability_root_is_removed() -> None:
    assert find_spec("nano_multiagent.observability") is None
