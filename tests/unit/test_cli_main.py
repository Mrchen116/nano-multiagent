import io
import json
import time

from coding_cli import commands as cli_commands
from coding_cli.input import repl_commands, repl_input
from coding_cli.main import run_cli


def test_cli_commands_surface_matches_app_commands_module() -> None:
    import coding_cli.commands as app_commands

    assert cli_commands.build_parser is app_commands.build_parser
    assert cli_commands.run_cli is app_commands.run_cli
    assert run_cli is app_commands.run_cli


def test_cli_internal_modules_live_under_apps_coding_cli_subpackages() -> None:
    from coding_cli.events import repl_events as layered_events
    from coding_cli.input import repl_commands as layered_repl_commands
    from coding_cli.input import repl_input as layered_repl_input
    from coding_cli.render import context_budget as layered_context_budget
    from coding_cli.render import error_presenter as layered_error_presenter
    from coding_cli.render import repl_render as layered_repl_render
    from coding_cli.render import turn_usage as layered_turn_usage
    from coding_cli.runtime import repl_runtime as layered_repl_runtime

    assert layered_events.consume_async_run_events.__module__ == "coding_cli.events.repl_events"
    assert layered_repl_input.emit_external_text.__module__ == "coding_cli.input.repl_input"
    assert layered_repl_commands.REPL_COMMANDS
    assert layered_repl_render.print_repl_turn_summary.__module__ == "coding_cli.render.repl_render"
    assert layered_repl_runtime.ReplRunQueue.__module__ == "coding_cli.runtime.repl_runtime"
    assert layered_context_budget.print_context_budget_snapshot.__module__ == "coding_cli.render.context_budget"
    assert layered_error_presenter.error_layer_for_exception.__module__ == "coding_cli.render.error_presenter"
    assert layered_turn_usage.extract_turn_usage_metrics.__module__ == "coding_cli.render.turn_usage"


def test_cli_event_pipeline_layer_exposes_normalize_dedupe_and_view_model() -> None:
    from coding_cli.events import event_pipeline

    assert hasattr(event_pipeline, "NormalizedSessionEvent")
    assert hasattr(event_pipeline, "EventDedupeWindow")
    assert hasattr(event_pipeline, "normalize_session_event")
    assert hasattr(event_pipeline, "consume_event_for_run")
    assert hasattr(event_pipeline, "build_repl_view_model")


def test_consume_async_run_events_fallback_dedupe_window_evicts_old_semantic_keys() -> None:
    from coding_cli.events.event_pipeline import EventDedupeWindow
    from coding_cli.events.repl_events import consume_async_run_events

    out = io.StringIO()
    dedupe_window = EventDedupeWindow(max_event_ids=8, max_runs=1, max_fallback_keys_per_run=2)
    seen_event_ids: set[str] = set()
    seen_event_fingerprints: set[str] = set()
    assistant_text = ""
    consumed_counts: list[int] = []

    event_batches = [
        [{"event": "tool_start", "data": {"run_id": "run_window", "name": "bash", "call_id": "call_a"}}],
        [{"event": "tool_start", "data": {"run_id": "run_window", "name": "bash", "call_id": "call_b"}}],
        [{"event": "tool_start", "data": {"run_id": "run_window", "name": "bash", "call_id": "call_c"}}],
        [{"event": "tool_start", "data": {"run_id": "run_window", "name": "bash", "call_id": "call_a"}}],
    ]
    for events in event_batches:
        assistant_text, consumed = consume_async_run_events(
            out=out,
            events=events,
            run_id="run_window",
            seen_event_ids=seen_event_ids,
            seen_event_fingerprints=seen_event_fingerprints,
            dedupe_window=dedupe_window,
            assistant_text=assistant_text,
            emit_preview=False,
        )
        consumed_counts.append(consumed)
    assert consumed_counts == [1, 1, 1, 1]


def test_cli_render_phase_machine_transitions_and_guards() -> None:
    from coding_cli.events.event_pipeline import ReplRenderPhase
    from coding_cli.events.event_pipeline import ReplRenderPhaseMachine

    machine = ReplRenderPhaseMachine()
    assert machine.phase is ReplRenderPhase.STREAMING
    assert machine.can_emit_preview() is True

    machine.begin_finalizing()
    assert machine.phase is ReplRenderPhase.FINALIZING
    assert machine.can_emit_preview() is False

    machine.mark_finalized()
    assert machine.phase is ReplRenderPhase.FINALIZED
    assert machine.can_emit_preview() is False


def test_consume_async_run_events_stops_preview_after_finalizing() -> None:
    from coding_cli.events.event_pipeline import EventDedupeWindow
    from coding_cli.events.event_pipeline import ReplRenderPhase
    from coding_cli.events.event_pipeline import ReplRenderPhaseMachine
    from coding_cli.events.repl_events import consume_async_run_events

    out = io.StringIO()
    preview_lines: list[str] = []
    machine = ReplRenderPhaseMachine()
    assistant_text, consumed = consume_async_run_events(
        out=out,
        events=[
            {
                "event": "tool_start",
                "event_id": "evt-1",
                "data": {"run_id": "run_phase", "name": "bash", "arguments": "ping", "call_id": "call_1"},
            },
            {
                "event": "run_status",
                "event_id": "evt-2",
                "data": {"run_id": "run_phase", "status": "completed"},
            },
        ],
        run_id="run_phase",
        dedupe_window=EventDedupeWindow(),
        assistant_text="",
        emit_preview=True,
        preview_writer=preview_lines.append,
        render_phase_machine=machine,
    )

    assert assistant_text == ""
    assert consumed == 2
    assert machine.phase is ReplRenderPhase.FINALIZING
    assert preview_lines == ["Tool: bash start args=ping [call_id=call_1]"]

    assistant_text, consumed = consume_async_run_events(
        out=out,
        events=[
            {
                "event": "tool_exec_started",
                "event_id": "evt-3",
                "data": {"run_id": "run_phase", "name": "bash", "status": "started", "elapsed_ms": 0, "call_id": "call_1"},
            }
        ],
        run_id="run_phase",
        dedupe_window=EventDedupeWindow(),
        assistant_text=assistant_text,
        emit_preview=True,
        preview_writer=preview_lines.append,
        render_phase_machine=machine,
    )

    assert consumed == 1
    assert preview_lines == ["Tool: bash start args=ping [call_id=call_1]"]


def test_cli_render_phase_machine_filters_previewed_tool_lines_from_final_summary() -> None:
    from coding_cli.events.event_pipeline import ReplRenderPhaseMachine

    machine = ReplRenderPhaseMachine()
    preview_identity = "run_target|bash|call_1|start"
    assert machine.should_emit_tool_preview(preview_identity) is True
    machine.record_tool_preview(preview_identity=preview_identity, preview_line_identity="bash start args=ping")
    assert machine.should_emit_tool_preview(preview_identity) is False

    machine.begin_finalizing()
    filtered = machine.filter_summary_tool_updates(
        ["bash start args=ping", "bash exit code=0 status=completed duration=10ms"],
        line_identity_resolver=lambda line: line.strip(),
    )
    assert filtered == ["bash exit code=0 status=completed duration=10ms"]


def test_build_repl_view_model_isolates_orphan_exec_exit_from_active_call_timeline() -> None:
    from coding_cli.events.event_pipeline import build_repl_view_model
    from coding_cli.events.repl_events import _event_preview_line

    model = build_repl_view_model(
        events=[
            ("tool_start", {"run_id": "run_orphan", "name": "bash", "call_id": "call_active", "arguments": {"command": "echo ok"}}),
            ("tool_exec_started", {"run_id": "run_orphan", "name": "bash", "call_id": "call_active", "status": "started", "elapsed_ms": 0}),
            ("tool_exec_exit", {"run_id": "run_orphan", "name": "bash", "call_id": "call_orphan", "status": "failed", "duration_ms": 44, "exit_code": 99}),
            ("tool_exec_exit", {"run_id": "run_orphan", "name": "bash", "call_id": "call_active", "status": "completed", "duration_ms": 21, "exit_code": 0}),
        ],
        preview_line_resolver=lambda event_name, data: _event_preview_line(event_name=event_name, data=data),
    )

    assert "orphan_events=1" in model.status_updates
    assert any(line.startswith("orphan ") and "exit code=99" in line for line in model.tool_updates)
    assert any("Tool: bash exit code=0 status=completed duration=21ms" in line for line in model.tool_updates)


def test_consume_async_run_events_high_frequency_batch_records_perf_baseline() -> None:
    from coding_cli.events.event_pipeline import EventDedupeWindow
    from coding_cli.events.event_pipeline import ReplPerfTracker
    from coding_cli.events.repl_events import consume_async_run_events

    out = io.StringIO()
    preview_lines: list[str] = []
    events: list[dict[str, object]] = [
        {"event_id": "evt_hf_start", "event": "tool_start", "data": {"run_id": "run_hf", "name": "bash", "call_id": "call_hf", "arguments": {"command": "echo hi"}}},
        {"event_id": "evt_hf_started", "event": "tool_exec_started", "data": {"run_id": "run_hf", "name": "bash", "call_id": "call_hf", "status": "started", "elapsed_ms": 0}},
    ]
    events.extend(
        {
            "event_id": f"evt_hf_chunk_{idx}",
            "event": "tool_exec_chunk",
            "data": {"run_id": "run_hf", "name": "bash", "call_id": "call_hf", "stream": "stdout", "chunk": f"line-{idx}", "seq": idx},
        }
        for idx in range(1, 81)
    )
    events.append(
        {
            "event_id": "evt_hf_exit",
            "event": "tool_exec_exit",
            "data": {"run_id": "run_hf", "name": "bash", "call_id": "call_hf", "status": "completed", "duration_ms": 200, "exit_code": 0},
        }
    )

    tracker = ReplPerfTracker()
    _, consumed = consume_async_run_events(
        out=out,
        events=events,
        run_id="run_hf",
        dedupe_window=EventDedupeWindow(),
        assistant_text="",
        emit_preview=True,
        preview_writer=preview_lines.append,
        perf_tracker=tracker,
    )

    snapshot = tracker.snapshot()
    assert consumed == len(events)
    assert snapshot["sample_ready"] is True
    assert snapshot["throughput_ok"] is True
    assert snapshot["redraw_ratio_ok"] is True
    assert snapshot["polled_events"] == len(events)
    assert snapshot["consumed_events"] == len(events)
    assert snapshot["preview_emitted"] == 3


def test_consume_async_run_events_long_session_batches_keep_perf_guardrails_stable() -> None:
    from coding_cli.events.event_pipeline import EventDedupeWindow
    from coding_cli.events.event_pipeline import ReplPerfTracker
    from coding_cli.events.repl_events import consume_async_run_events

    out = io.StringIO()
    tracker = ReplPerfTracker()
    dedupe_window = EventDedupeWindow(max_event_ids=512, max_runs=8, max_fallback_keys_per_run=512)
    assistant_text = ""

    for batch_idx in range(1, 6):
        events: list[dict[str, object]] = [
            {"event_id": f"evt_other_run_{batch_idx}", "event": "tool_start", "data": {"run_id": "run_other", "name": "bash", "call_id": f"other_{batch_idx}", "arguments": {"command": "echo other"}}},
            {"event_id": f"evt_long_start_{batch_idx}", "event": "tool_start", "data": {"run_id": "run_long", "name": "bash", "call_id": f"call_{batch_idx}", "arguments": {"command": "echo long"}}},
            {"event_id": f"evt_long_start_{batch_idx}", "event": "tool_start", "data": {"run_id": "run_long", "name": "bash", "call_id": f"call_{batch_idx}", "arguments": {"command": "echo long"}}},
        ]
        events.extend(
            {
                "event_id": f"evt_long_chunk_{batch_idx}_{chunk_idx}",
                "event": "tool_exec_chunk",
                "data": {
                    "run_id": "run_long",
                    "name": "bash",
                    "call_id": f"call_{batch_idx}",
                    "stream": "stdout",
                    "chunk": f"chunk-{batch_idx}-{chunk_idx}",
                    "seq": chunk_idx,
                },
            }
            for chunk_idx in range(1, 11)
        )
        events.append(
            {
                "event_id": f"evt_long_exit_{batch_idx}",
                "event": "tool_exec_exit",
                "data": {"run_id": "run_long", "name": "bash", "call_id": f"call_{batch_idx}", "status": "completed", "duration_ms": 80 + batch_idx, "exit_code": 0},
            }
        )
        assistant_text, _ = consume_async_run_events(
            out=out,
            events=events,
            run_id="run_long",
            dedupe_window=dedupe_window,
            assistant_text=assistant_text,
            emit_preview=False,
            perf_tracker=tracker,
        )

    snapshot = tracker.snapshot()
    assert snapshot["batches"] == 5
    assert snapshot["run_filtered"] == 5
    assert snapshot["dedupe_dropped"] >= 5
    assert snapshot["sample_ready"] is True
    assert snapshot["stable"] is True


def test_consume_async_run_events_perf_snapshot_marks_unstable_with_guardrail_reason() -> None:
    from coding_cli.events.event_pipeline import EventDedupeWindow
    from coding_cli.events.event_pipeline import ReplPerfTracker
    from coding_cli.events.repl_events import consume_async_run_events

    out = io.StringIO()
    tracker = ReplPerfTracker(min_sample_events=10, min_throughput_ratio=0.8)
    dedupe_window = EventDedupeWindow()

    events = [{"event_id": f"evt_other_{idx}", "event": "tool_start", "data": {"run_id": "run_other", "name": "bash", "call_id": f"other_{idx}", "arguments": {"command": "echo other"}}} for idx in range(1, 16)]
    events.extend(
        [
            {"event_id": "evt_target_start", "event": "tool_start", "data": {"run_id": "run_target", "name": "bash", "call_id": "call_target", "arguments": {"command": "echo target"}}},
            {"event_id": "evt_target_exit", "event": "tool_exec_exit", "data": {"run_id": "run_target", "name": "bash", "call_id": "call_target", "status": "completed", "duration_ms": 12, "exit_code": 0}},
        ]
    )

    _, consumed = consume_async_run_events(
        out=out,
        events=events,
        run_id="run_target",
        dedupe_window=dedupe_window,
        assistant_text="",
        emit_preview=False,
        perf_tracker=tracker,
    )

    snapshot = tracker.snapshot()
    assert consumed == 2
    assert snapshot["sample_ready"] is False
    assert snapshot["throughput_ok"] is False
    assert snapshot["stable"] is False
    assert snapshot["guardrail_reason"] == "throughput, sample_size"


def test_send_message_with_async_events_exposes_perf_metrics_snapshot() -> None:
    from coding_cli.events.repl_events import send_message_with_async_events

    payload = send_message_with_async_events(
        out=io.StringIO(),
        client=_AsyncToolExecStreamingStubClient(),
        session_id="sess_cli",
        text="ping",
    )

    view = payload.get("_repl_view")
    assert isinstance(view, dict)
    perf_metrics = view.get("perf_metrics")
    assert isinstance(perf_metrics, dict)
    assert perf_metrics["batches"] >= 1
    assert perf_metrics["polled_events"] >= 1
    assert perf_metrics["consumed_events"] >= 1
    assert "sample_ready" in perf_metrics
    assert "throughput_ok" in perf_metrics
    assert "redraw_ratio_ok" in perf_metrics
    assert "stable" in perf_metrics


class _StubClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, object] | None]] = []

    def __enter__(self) -> "_StubClient":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        del exc_type, exc, tb

    def health(self) -> dict[str, object]:
        self.calls.append(("health", None))
        return {"healthy": True}

    def create_session(self, *, title: str | None = None) -> dict[str, str]:
        self.calls.append(("create_session", {"title": title or ""}))
        return {"session_id": "sess_cli"}

    def send_message(self, *, session_id: str, text: str) -> dict[str, object]:
        self.calls.append(("send_message", {"session_id": session_id, "text": text}))
        return {"session_id": session_id, "message": {"content": f"echo:{text}"}}

    def list_session_tools(self, *, session_id: str) -> dict[str, object]:
        self.calls.append(("list_session_tools", {"session_id": session_id}))
        return {
            "session_id": session_id,
            "tools": [{"name": "read", "description": "Read", "input_schema": {}}],
        }

    def compact_session(self, *, session_id: str) -> dict[str, object]:
        self.calls.append(("compact_session", {"session_id": session_id}))
        return {"session_id": session_id, "compacted": False, "result": None}

    def get_context_budget(self, *, session_id: str) -> dict[str, object]:
        self.calls.append(("get_context_budget", {"session_id": session_id}))
        return {
            "session_id": session_id,
            "used_tokens": 64,
            "max_tokens": 200,
            "remaining_tokens": 136,
            "usage_ratio": 0.32,
        }

    def get_llm_config(self) -> dict[str, object]:
        self.calls.append(("get_llm_config", None))
        return {
            "provider": "openai_compat",
            "model": "codexOAuth:gpt-5.2-codex",
            "base_url": "http://127.0.0.1:4000",
            "api_key_configured": False,
            "timeout_seconds": 30.0,
        }

    def set_llm_config(
        self,
        *,
        provider: str | None = None,
        model: str | None = None,
        base_url: str | None = None,
        api_key: str | None = None,
        timeout_seconds: float | None = None,
        clear_api_key: bool = False,
    ) -> dict[str, object]:
        self.calls.append(
            (
                "set_llm_config",
                {
                    "provider": provider,
                    "model": model,
                    "base_url": base_url,
                    "api_key": api_key,
                    "timeout_seconds": timeout_seconds,
                    "clear_api_key": clear_api_key,
                },
            )
        )
        resolved_api_key = None if clear_api_key else api_key
        return {
            "provider": provider or "openai_compat",
            "model": model or "codexOAuth:gpt-5.2-codex",
            "base_url": base_url or "http://127.0.0.1:4000",
            "api_key_configured": bool(resolved_api_key),
            "timeout_seconds": timeout_seconds or 30.0,
        }


class _UsageStubClient(_StubClient):
    def send_message(self, *, session_id: str, text: str) -> dict[str, object]:
        self.calls.append(("send_message", {"session_id": session_id, "text": text}))
        return {
            "session_id": session_id,
            "turn_id": "turn_usage",
            "message": {"message_id": "msg_usage", "role": "assistant", "content": f"echo:{text}"},
            "completed": True,
            "stop_reason": "stop",
            "usage": {
                "prompt_tokens": 120,
                "completion_tokens": 35,
                "total_tokens": 155,
            },
        }


class _StopReasonOnlyStubClient(_StubClient):
    def send_message(self, *, session_id: str, text: str) -> dict[str, object]:
        self.calls.append(("send_message", {"session_id": session_id, "text": text}))
        return {
            "session_id": session_id,
            "message": {"role": "assistant", "content": f"echo:{text}"},
            "stop_reason": "stop",
        }


class _CompactedStubClient(_StubClient):
    def compact_session(self, *, session_id: str) -> dict[str, object]:
        self.calls.append(("compact_session", {"session_id": session_id}))
        return {
            "session_id": session_id,
            "compacted": True,
            "result": {
                "summary": "context compacted",
                "kept_event_ids": ["evt_keep_1", "evt_keep_2"],
                "dropped_event_ids": ["evt_drop_1"],
            },
        }


class _ThresholdBudgetStubClient(_StubClient):
    def __init__(self, *, used_tokens: int, max_tokens: int) -> None:
        super().__init__()
        self._used_tokens = used_tokens
        self._max_tokens = max_tokens

    def get_context_budget(self, *, session_id: str) -> dict[str, object]:
        self.calls.append(("get_context_budget", {"session_id": session_id}))
        usage_ratio = float(self._used_tokens) / float(self._max_tokens)
        return {
            "session_id": session_id,
            "used_tokens": self._used_tokens,
            "max_tokens": self._max_tokens,
            "remaining_tokens": max(self._max_tokens - self._used_tokens, 0),
            "usage_ratio": usage_ratio,
        }


class _FailingBudgetStubClient(_StubClient):
    def get_context_budget(self, *, session_id: str) -> dict[str, object]:
        self.calls.append(("get_context_budget", {"session_id": session_id}))
        raise RuntimeError("request failed (503): {'error': 'budget unavailable'}")


class _FailingToolsStubClient(_StubClient):
    def list_session_tools(self, *, session_id: str) -> dict[str, object]:
        self.calls.append(("list_session_tools", {"session_id": session_id}))
        raise RuntimeError("request failed (500): {'error': 'tools unavailable'}")


class _ConnectionRefusedOnSendStubClient(_StubClient):
    def send_message(self, *, session_id: str, text: str) -> dict[str, object]:
        self.calls.append(("send_message", {"session_id": session_id, "text": text}))
        raise ConnectionRefusedError(61, "Connection refused")


class _TimeoutOnSendStubClient(_StubClient):
    def send_message(self, *, session_id: str, text: str) -> dict[str, object]:
        self.calls.append(("send_message", {"session_id": session_id, "text": text}))
        raise TimeoutError("timed out")


class _ConnectionRefusedOnHealthStubClient(_StubClient):
    def health(self) -> dict[str, object]:
        self.calls.append(("health", None))
        raise ConnectionRefusedError(61, "Connection refused")


class _AsyncEventingStubClient(_StubClient):
    def __init__(self) -> None:
        super().__init__()
        self._stream_calls = 0

    def send_message_async(self, *, session_id: str, text: str) -> dict[str, object]:
        self.calls.append(("send_message_async", {"session_id": session_id, "text": text}))
        return {"run_id": "run_target", "session_id": session_id, "status": "queued"}

    def stream_session_events(
        self,
        *,
        session_id: str,
        max_events: int = 20,
        timeout_seconds: float = 0.25,
    ) -> list[dict[str, object]]:
        del max_events, timeout_seconds
        self.calls.append(("stream_session_events", {"session_id": session_id}))
        self._stream_calls += 1
        if self._stream_calls == 1:
            return [
                {
                    "event_id": "evt_dup",
                    "event": "run_status",
                    "data": {"run_id": "run_target", "status": "queued"},
                },
                {
                    "event_id": "evt_dup",
                    "event": "run_status",
                    "data": {"run_id": "run_target", "status": "queued"},
                },
                {
                    "event_id": "evt_other",
                    "event": "text_delta",
                    "data": {"run_id": "run_other", "delta": "ignore-me"},
                },
                {
                    "event_id": "evt_tool_start",
                    "event": "tool_start",
                    "data": {
                        "run_id": "run_target",
                        "name": "echo",
                        "call_id": "call_1",
                        "arguments": {"text": "ping"},
                    },
                },
                {
                    "event_id": "evt_tool_end",
                    "event": "tool_end",
                    "data": {
                        "run_id": "run_target",
                        "name": "echo",
                        "call_id": "call_1",
                        "output": {"text": "echo:ping"},
                        "error": None,
                    },
                },
                {
                    "event_id": "evt_text",
                    "event": "text_delta",
                    "data": {"run_id": "run_target", "delta": "final:echo:ping"},
                },
            ]
        return []

    def get_run(self, *, run_id: str) -> dict[str, object]:
        self.calls.append(("get_run", {"run_id": run_id}))
        if self._stream_calls >= 1:
            return {
                "run_id": run_id,
                "session_id": "sess_cli",
                "status": "completed",
                "created_at": "2026-03-02T00:00:00+00:00",
                "updated_at": "2026-03-02T00:00:00+00:00",
                "turn_id": "turn_async",
                "stop_reason": "stop",
                "error": None,
            }
        return {
            "run_id": run_id,
            "session_id": "sess_cli",
            "status": "running",
            "created_at": "2026-03-02T00:00:00+00:00",
            "updated_at": "2026-03-02T00:00:00+00:00",
            "turn_id": None,
            "stop_reason": None,
            "error": None,
        }


class _AsyncMultilineToolOutputStubClient(_StubClient):
    def send_message_async(self, *, session_id: str, text: str) -> dict[str, object]:
        self.calls.append(("send_message_async", {"session_id": session_id, "text": text}))
        return {"run_id": "run_multiline", "session_id": session_id, "status": "queued"}

    def stream_session_events(
        self,
        *,
        session_id: str,
        max_events: int = 20,
        timeout_seconds: float = 0.25,
    ) -> list[dict[str, object]]:
        del max_events, timeout_seconds
        self.calls.append(("stream_session_events", {"session_id": session_id}))
        return [
            {
                "event_id": "evt_ml_tool_start",
                "event": "tool_start",
                "data": {
                    "run_id": "run_multiline",
                    "name": "echo",
                    "call_id": "call_ml",
                    "arguments": {"text": "ping"},
                },
            },
            {
                "event_id": "evt_ml_tool_end",
                "event": "tool_end",
                "data": {
                    "run_id": "run_multiline",
                    "name": "echo",
                    "call_id": "call_ml",
                    "output": {"text": "line1\nline2"},
                    "error": None,
                },
            },
            {
                "event_id": "evt_ml_text",
                "event": "text_delta",
                "data": {"run_id": "run_multiline", "delta": "final:echo:ping"},
            },
        ]

    def get_run(self, *, run_id: str) -> dict[str, object]:
        self.calls.append(("get_run", {"run_id": run_id}))
        return {
            "run_id": run_id,
            "session_id": "sess_cli",
            "status": "completed",
            "created_at": "2026-03-04T00:00:00+00:00",
            "updated_at": "2026-03-04T00:00:00+00:00",
            "turn_id": "turn_ml",
            "stop_reason": "stop",
            "error": None,
        }


class _AsyncUsageEventingStubClient(_AsyncEventingStubClient):
    def get_run(self, *, run_id: str) -> dict[str, object]:
        payload = super().get_run(run_id=run_id)
        if payload["status"] == "completed":
            payload["usage"] = {
                "prompt_tokens": 320,
                "completion_tokens": 41,
                "total_tokens": 361,
            }
        return payload


class _AsyncLongToolOutputStubClient(_StubClient):
    def send_message_async(self, *, session_id: str, text: str) -> dict[str, object]:
        self.calls.append(("send_message_async", {"session_id": session_id, "text": text}))
        return {"run_id": "run_long_output", "session_id": session_id, "status": "queued"}

    def stream_session_events(
        self,
        *,
        session_id: str,
        max_events: int = 20,
        timeout_seconds: float = 0.25,
    ) -> list[dict[str, object]]:
        del max_events, timeout_seconds
        self.calls.append(("stream_session_events", {"session_id": session_id}))
        long_output = "HEAD-" + ("x" * 200) + "-TAIL"
        return [
            {
                "event_id": "evt_long_tool_start",
                "event": "tool_start",
                "data": {
                    "run_id": "run_long_output",
                    "name": "echo",
                    "call_id": "call_long",
                    "arguments": {"text": "ping"},
                },
            },
            {
                "event_id": "evt_long_tool_end",
                "event": "tool_end",
                "data": {
                    "run_id": "run_long_output",
                    "name": "echo",
                    "call_id": "call_long",
                    "output": {"text": long_output},
                    "error": None,
                },
            },
            {
                "event_id": "evt_long_text",
                "event": "text_delta",
                "data": {"run_id": "run_long_output", "delta": "final:echo:ping"},
            },
        ]

    def get_run(self, *, run_id: str) -> dict[str, object]:
        self.calls.append(("get_run", {"run_id": run_id}))
        return {
            "run_id": run_id,
            "session_id": "sess_cli",
            "status": "completed",
            "created_at": "2026-03-04T00:00:00+00:00",
            "updated_at": "2026-03-04T00:00:00+00:00",
            "turn_id": "turn_long_output",
            "stop_reason": "stop",
            "error": None,
        }


class _AsyncSameToolTwiceStubClient(_StubClient):
    def send_message_async(self, *, session_id: str, text: str) -> dict[str, object]:
        self.calls.append(("send_message_async", {"session_id": session_id, "text": text}))
        return {"run_id": "run_twice", "session_id": session_id, "status": "queued"}

    def stream_session_events(
        self,
        *,
        session_id: str,
        max_events: int = 20,
        timeout_seconds: float = 0.25,
    ) -> list[dict[str, object]]:
        del max_events, timeout_seconds
        self.calls.append(("stream_session_events", {"session_id": session_id}))
        return [
            {
                "event_id": "evt_twice_start_1",
                "event": "tool_start",
                "data": {
                    "run_id": "run_twice",
                    "name": "echo",
                    "call_id": "call_1",
                    "arguments": {"text": "first"},
                },
            },
            {
                "event_id": "evt_twice_end_1",
                "event": "tool_end",
                "data": {
                    "run_id": "run_twice",
                    "name": "echo",
                    "call_id": "call_1",
                    "output": {"text": "echo:first"},
                    "error": None,
                },
            },
            {
                "event_id": "evt_twice_start_2",
                "event": "tool_start",
                "data": {
                    "run_id": "run_twice",
                    "name": "echo",
                    "call_id": "call_2",
                    "arguments": {"text": "second"},
                },
            },
            {
                "event_id": "evt_twice_end_2",
                "event": "tool_end",
                "data": {
                    "run_id": "run_twice",
                    "name": "echo",
                    "call_id": "call_2",
                    "output": {"text": "echo:second"},
                    "error": None,
                },
            },
            {
                "event_id": "evt_twice_text",
                "event": "text_delta",
                "data": {"run_id": "run_twice", "delta": "final:echo:second"},
            },
        ]

    def get_run(self, *, run_id: str) -> dict[str, object]:
        self.calls.append(("get_run", {"run_id": run_id}))
        return {
            "run_id": run_id,
            "session_id": "sess_cli",
            "status": "completed",
            "created_at": "2026-03-04T00:00:00+00:00",
            "updated_at": "2026-03-04T00:00:00+00:00",
            "turn_id": "turn_twice",
            "stop_reason": "stop",
            "error": None,
        }


class _AsyncSameToolSameOutputStubClient(_StubClient):
    def send_message_async(self, *, session_id: str, text: str) -> dict[str, object]:
        self.calls.append(("send_message_async", {"session_id": session_id, "text": text}))
        return {"run_id": "run_same_output", "session_id": session_id, "status": "queued"}

    def stream_session_events(
        self,
        *,
        session_id: str,
        max_events: int = 20,
        timeout_seconds: float = 0.25,
    ) -> list[dict[str, object]]:
        del max_events, timeout_seconds
        self.calls.append(("stream_session_events", {"session_id": session_id}))
        return [
            {
                "event_id": "evt_same_output_start_1",
                "event": "tool_start",
                "data": {
                    "run_id": "run_same_output",
                    "name": "echo",
                    "call_id": "call_same_1",
                    "arguments": {"text": "same"},
                },
            },
            {
                "event_id": "evt_same_output_end_1",
                "event": "tool_end",
                "data": {
                    "run_id": "run_same_output",
                    "name": "echo",
                    "call_id": "call_same_1",
                    "output": {"text": "echo:same"},
                    "error": None,
                },
            },
            {
                "event_id": "evt_same_output_start_2",
                "event": "tool_start",
                "data": {
                    "run_id": "run_same_output",
                    "name": "echo",
                    "call_id": "call_same_2",
                    "arguments": {"text": "same"},
                },
            },
            {
                "event_id": "evt_same_output_end_2",
                "event": "tool_end",
                "data": {
                    "run_id": "run_same_output",
                    "name": "echo",
                    "call_id": "call_same_2",
                    "output": {"text": "echo:same"},
                    "error": None,
                },
            },
            {
                "event_id": "evt_same_output_text",
                "event": "text_delta",
                "data": {"run_id": "run_same_output", "delta": "final:echo:same"},
            },
        ]

    def get_run(self, *, run_id: str) -> dict[str, object]:
        self.calls.append(("get_run", {"run_id": run_id}))
        return {
            "run_id": run_id,
            "session_id": "sess_cli",
            "status": "completed",
            "created_at": "2026-03-04T00:00:00+00:00",
            "updated_at": "2026-03-04T00:00:00+00:00",
            "turn_id": "turn_same_output",
            "stop_reason": "stop",
            "error": None,
        }


class _AsyncToolExecStreamingStubClient(_StubClient):
    def __init__(self) -> None:
        super().__init__()
        self._stream_calls = 0

    def send_message_async(self, *, session_id: str, text: str) -> dict[str, object]:
        self.calls.append(("send_message_async", {"session_id": session_id, "text": text}))
        return {"run_id": "run_tool_exec", "session_id": session_id, "status": "queued"}

    def stream_session_events(
        self,
        *,
        session_id: str,
        max_events: int = 20,
        timeout_seconds: float = 0.25,
    ) -> list[dict[str, object]]:
        del max_events, timeout_seconds
        self.calls.append(("stream_session_events", {"session_id": session_id}))
        self._stream_calls += 1
        if self._stream_calls == 1:
            return [
                {
                    "event_id": "evt_tool_start",
                    "event": "tool_start",
                    "data": {
                        "run_id": "run_tool_exec",
                        "name": "bash",
                        "call_id": "call_bash_1",
                        "arguments": {"command": "printf out-line; printf err-line >&2", "timeout": 1},
                    },
                },
                {
                    "event_id": "evt_tool_exec_started",
                    "event": "tool_exec_started",
                    "data": {
                        "run_id": "run_tool_exec",
                        "name": "bash",
                        "call_id": "call_bash_1",
                        "status": "started",
                        "elapsed_ms": 0,
                    },
                },
                {
                    "event_id": "evt_tool_exec_running",
                    "event": "tool_exec_running",
                    "data": {
                        "run_id": "run_tool_exec",
                        "name": "bash",
                        "call_id": "call_bash_1",
                        "status": "running",
                        "elapsed_ms": 120,
                    },
                },
                {
                    "event_id": "evt_tool_exec_chunk_stdout",
                    "event": "tool_exec_chunk",
                    "data": {
                        "run_id": "run_tool_exec",
                        "name": "bash",
                        "call_id": "call_bash_1",
                        "stream": "stdout",
                        "chunk": "out-line",
                        "seq": 1,
                    },
                },
                {
                    "event_id": "evt_tool_exec_chunk_stderr",
                    "event": "tool_exec_chunk",
                    "data": {
                        "run_id": "run_tool_exec",
                        "name": "bash",
                        "call_id": "call_bash_1",
                        "stream": "stderr",
                        "chunk": "err-line",
                        "seq": 2,
                    },
                },
                {
                    "event_id": "evt_tool_exec_exit",
                    "event": "tool_exec_exit",
                    "data": {
                        "run_id": "run_tool_exec",
                        "name": "bash",
                        "call_id": "call_bash_1",
                        "status": "completed",
                        "duration_ms": 210,
                        "exit_code": 0,
                    },
                },
                {
                    "event_id": "evt_tool_exec_text",
                    "event": "text_delta",
                    "data": {"run_id": "run_tool_exec", "delta": "done"},
                },
            ]
        return []

    def get_run(self, *, run_id: str) -> dict[str, object]:
        self.calls.append(("get_run", {"run_id": run_id}))
        return {
            "run_id": run_id,
            "session_id": "sess_cli",
            "status": "completed",
            "created_at": "2026-03-04T00:00:00+00:00",
            "updated_at": "2026-03-04T00:00:00+00:00",
            "turn_id": "turn_tool_exec",
            "stop_reason": "stop",
            "error": None,
        }


class _AsyncOrphanExecExitStubClient(_StubClient):
    def __init__(self) -> None:
        super().__init__()
        self._stream_calls = 0

    def send_message_async(self, *, session_id: str, text: str) -> dict[str, object]:
        self.calls.append(("send_message_async", {"session_id": session_id, "text": text}))
        return {"run_id": "run_orphan", "session_id": session_id, "status": "queued"}

    def stream_session_events(
        self,
        *,
        session_id: str,
        max_events: int = 20,
        timeout_seconds: float = 0.25,
    ) -> list[dict[str, object]]:
        del max_events, timeout_seconds
        self.calls.append(("stream_session_events", {"session_id": session_id}))
        self._stream_calls += 1
        if self._stream_calls == 1:
            return [
                {
                    "event_id": "evt_orphan_start",
                    "event": "tool_start",
                    "data": {
                        "run_id": "run_orphan",
                        "name": "bash",
                        "call_id": "call_active",
                        "arguments": {"command": "echo active"},
                    },
                },
                {
                    "event_id": "evt_orphan_started",
                    "event": "tool_exec_started",
                    "data": {
                        "run_id": "run_orphan",
                        "name": "bash",
                        "call_id": "call_active",
                        "status": "started",
                        "elapsed_ms": 0,
                    },
                },
                {
                    "event_id": "evt_orphan_exit",
                    "event": "tool_exec_exit",
                    "data": {
                        "run_id": "run_orphan",
                        "name": "bash",
                        "call_id": "call_orphan",
                        "status": "failed",
                        "duration_ms": 31,
                        "exit_code": 137,
                    },
                },
                {
                    "event_id": "evt_active_exit",
                    "event": "tool_exec_exit",
                    "data": {
                        "run_id": "run_orphan",
                        "name": "bash",
                        "call_id": "call_active",
                        "status": "completed",
                        "duration_ms": 19,
                        "exit_code": 0,
                    },
                },
                {
                    "event_id": "evt_orphan_text",
                    "event": "text_delta",
                    "data": {"run_id": "run_orphan", "delta": "final:orphan-isolated"},
                },
            ]
        return []

    def get_run(self, *, run_id: str) -> dict[str, object]:
        self.calls.append(("get_run", {"run_id": run_id}))
        status = "completed" if self._stream_calls >= 2 else "running"
        return {
            "run_id": run_id,
            "session_id": "sess_cli",
            "status": status,
            "created_at": "2026-03-04T00:00:00+00:00",
            "updated_at": "2026-03-04T00:00:00+00:00",
            "turn_id": "turn_orphan" if status == "completed" else None,
            "stop_reason": "stop" if status == "completed" else None,
            "error": None,
        }


class _AsyncNoEventIdReplayStubClient(_StubClient):
    def __init__(self) -> None:
        super().__init__()
        self._stream_calls = 0

    def send_message_async(self, *, session_id: str, text: str) -> dict[str, object]:
        self.calls.append(("send_message_async", {"session_id": session_id, "text": text}))
        return {"run_id": "run_no_event_id", "session_id": session_id, "status": "queued"}

    def stream_session_events(
        self,
        *,
        session_id: str,
        max_events: int = 20,
        timeout_seconds: float = 0.25,
    ) -> list[dict[str, object]]:
        del max_events, timeout_seconds
        self.calls.append(("stream_session_events", {"session_id": session_id}))
        self._stream_calls += 1
        if self._stream_calls > 2:
            return []
        return [
            {
                "event": "tool_start",
                "data": {
                    "run_id": "run_no_event_id",
                    "name": "bash",
                    "call_id": "call_no_event_id",
                    "arguments": {"command": "echo hi"},
                },
            },
            {
                "event": "tool_exec_exit",
                "data": {
                    "run_id": "run_no_event_id",
                    "name": "bash",
                    "call_id": "call_no_event_id",
                    "status": "completed",
                    "duration_ms": 12,
                    "exit_code": 0,
                },
            },
            {
                "event": "text_delta",
                "data": {"run_id": "run_no_event_id", "delta": "final:no-event-id"},
            },
        ]

    def get_run(self, *, run_id: str) -> dict[str, object]:
        self.calls.append(("get_run", {"run_id": run_id}))
        status = "completed" if self._stream_calls >= 2 else "running"
        return {
            "run_id": run_id,
            "session_id": "sess_cli",
            "status": status,
            "created_at": "2026-03-04T00:00:00+00:00",
            "updated_at": "2026-03-04T00:00:00+00:00",
            "turn_id": "turn_no_event_id" if status == "completed" else None,
            "stop_reason": "stop" if status == "completed" else None,
            "error": None,
        }


class _AsyncChangedEventIdReplayStubClient(_StubClient):
    def __init__(self) -> None:
        super().__init__()
        self._stream_calls = 0

    def send_message_async(self, *, session_id: str, text: str) -> dict[str, object]:
        self.calls.append(("send_message_async", {"session_id": session_id, "text": text}))
        return {"run_id": "run_changed_event_id", "session_id": session_id, "status": "queued"}

    def stream_session_events(
        self,
        *,
        session_id: str,
        max_events: int = 20,
        timeout_seconds: float = 0.25,
    ) -> list[dict[str, object]]:
        del max_events, timeout_seconds
        self.calls.append(("stream_session_events", {"session_id": session_id}))
        self._stream_calls += 1
        if self._stream_calls == 1:
            return [
                {
                    "event_id": "evt_tool_start_1",
                    "event": "tool_start",
                    "data": {
                        "run_id": "run_changed_event_id",
                        "name": "bash",
                        "call_id": "call_changed_event_id",
                        "arguments": {"command": "echo hi"},
                    },
                },
                {
                    "event_id": "evt_tool_exec_exit_1",
                    "event": "tool_exec_exit",
                    "data": {
                        "run_id": "run_changed_event_id",
                        "name": "bash",
                        "call_id": "call_changed_event_id",
                        "status": "completed",
                        "duration_ms": 18,
                        "exit_code": 0,
                    },
                },
                {
                    "event_id": "evt_text_1",
                    "event": "text_delta",
                    "data": {"run_id": "run_changed_event_id", "delta": "final:changed-event-id"},
                },
            ]
        if self._stream_calls == 2:
            return [
                {
                    "event_id": "evt_tool_start_2",
                    "event": "tool_start",
                    "data": {
                        "run_id": "run_changed_event_id",
                        "name": "bash",
                        "call_id": "call_changed_event_id",
                        "arguments": {"command": "echo hi"},
                    },
                }
            ]
        return []

    def get_run(self, *, run_id: str) -> dict[str, object]:
        self.calls.append(("get_run", {"run_id": run_id}))
        status = "completed" if self._stream_calls >= 2 else "running"
        return {
            "run_id": run_id,
            "session_id": "sess_cli",
            "status": status,
            "created_at": "2026-03-04T00:00:00+00:00",
            "updated_at": "2026-03-04T00:00:00+00:00",
            "turn_id": "turn_changed_event_id" if status == "completed" else None,
            "stop_reason": "stop" if status == "completed" else None,
            "error": None,
        }


class _AsyncChangedEventIdWithTimestampReplayStubClient(_StubClient):
    def __init__(self) -> None:
        super().__init__()
        self._stream_calls = 0

    def send_message_async(self, *, session_id: str, text: str) -> dict[str, object]:
        self.calls.append(("send_message_async", {"session_id": session_id, "text": text}))
        return {"run_id": "run_changed_event_id_ts", "session_id": session_id, "status": "queued"}

    def stream_session_events(
        self,
        *,
        session_id: str,
        max_events: int = 20,
        timeout_seconds: float = 0.25,
    ) -> list[dict[str, object]]:
        del max_events, timeout_seconds
        self.calls.append(("stream_session_events", {"session_id": session_id}))
        self._stream_calls += 1
        if self._stream_calls == 1:
            return [
                {
                    "event_id": "evt_ts_start_1",
                    "event": "tool_start",
                    "data": {
                        "run_id": "run_changed_event_id_ts",
                        "name": "bash",
                        "call_id": "call_changed_event_id_ts",
                        "arguments": {"command": "echo hi"},
                        "ts": "2026-03-04T00:00:00.100Z",
                    },
                },
                {
                    "event_id": "evt_ts_started_1",
                    "event": "tool_exec_started",
                    "data": {
                        "run_id": "run_changed_event_id_ts",
                        "name": "bash",
                        "call_id": "call_changed_event_id_ts",
                        "status": "started",
                        "elapsed_ms": 0,
                    },
                },
            ]
        if self._stream_calls == 2:
            return [
                {
                    "event_id": "evt_ts_start_2",
                    "event": "tool_start",
                    "data": {
                        "run_id": "run_changed_event_id_ts",
                        "name": "bash",
                        "call_id": "call_changed_event_id_ts",
                        "arguments": {"command": "echo hi"},
                        "ts": "2026-03-04T00:00:00.300Z",
                    },
                },
                {
                    "event_id": "evt_ts_exit_1",
                    "event": "tool_exec_exit",
                    "data": {
                        "run_id": "run_changed_event_id_ts",
                        "name": "bash",
                        "call_id": "call_changed_event_id_ts",
                        "status": "completed",
                        "duration_ms": 19,
                        "exit_code": 0,
                    },
                },
                {
                    "event_id": "evt_ts_text_1",
                    "event": "text_delta",
                    "data": {"run_id": "run_changed_event_id_ts", "delta": "final:changed-event-id-ts"},
                },
            ]
        return []

    def get_run(self, *, run_id: str) -> dict[str, object]:
        self.calls.append(("get_run", {"run_id": run_id}))
        status = "completed" if self._stream_calls >= 2 else "running"
        return {
            "run_id": run_id,
            "session_id": "sess_cli",
            "status": status,
            "created_at": "2026-03-04T00:00:00+00:00",
            "updated_at": "2026-03-04T00:00:00+00:00",
            "turn_id": "turn_changed_event_id_ts" if status == "completed" else None,
            "stop_reason": "stop" if status == "completed" else None,
            "error": None,
        }


class _AsyncFailedRunStubClient(_StubClient):
    def send_message_async(self, *, session_id: str, text: str) -> dict[str, object]:
        self.calls.append(("send_message_async", {"session_id": session_id, "text": text}))
        return {"run_id": "run_failed", "session_id": session_id, "status": "queued"}

    def stream_session_events(
        self,
        *,
        session_id: str,
        max_events: int = 20,
        timeout_seconds: float = 0.25,
    ) -> list[dict[str, object]]:
        del max_events, timeout_seconds
        self.calls.append(("stream_session_events", {"session_id": session_id}))
        return [
            {
                "event_id": "evt_fail_queued",
                "event": "run_status",
                "data": {"run_id": "run_failed", "status": "queued"},
            }
        ]

    def get_run(self, *, run_id: str) -> dict[str, object]:
        self.calls.append(("get_run", {"run_id": run_id}))
        return {
            "run_id": run_id,
            "session_id": "sess_cli",
            "status": "failed",
            "created_at": "2026-03-02T00:00:00+00:00",
            "updated_at": "2026-03-02T00:00:00+00:00",
            "turn_id": None,
            "stop_reason": "timeout",
            "error": {
                "code": "run_timeout",
                "message": "timed out waiting for upstream; root_cause=connect ETIMEDOUT",
            },
        }


class _CompletedStatusFirstStubClient(_StubClient):
    def send_message_async(self, *, session_id: str, text: str) -> dict[str, object]:
        self.calls.append(("send_message_async", {"session_id": session_id, "text": text}))
        return {"run_id": "run_completed_first", "session_id": session_id, "status": "queued"}

    def stream_session_events(
        self,
        *,
        session_id: str,
        max_events: int = 20,
        timeout_seconds: float = 0.25,
    ) -> list[dict[str, object]]:
        del max_events, timeout_seconds
        self.calls.append(("stream_session_events", {"session_id": session_id}))
        return [
            {
                "event_id": "evt_completed",
                "event": "run_status",
                "data": {"run_id": "run_completed_first", "status": "completed"},
            },
            {
                "event_id": "evt_tool_start",
                "event": "tool_start",
                "data": {
                    "run_id": "run_completed_first",
                    "name": "echo",
                    "call_id": "call_1",
                    "arguments": {"text": "ping"},
                },
            },
            {
                "event_id": "evt_tool_end",
                "event": "tool_end",
                "data": {
                    "run_id": "run_completed_first",
                    "name": "echo",
                    "call_id": "call_1",
                    "output": {"text": "echo:ping"},
                    "error": None,
                },
            },
            {
                "event_id": "evt_text",
                "event": "text_delta",
                "data": {"run_id": "run_completed_first", "delta": "final:echo:ping"},
            },
        ]

    def get_run(self, *, run_id: str) -> dict[str, object]:
        self.calls.append(("get_run", {"run_id": run_id}))
        return {
            "run_id": run_id,
            "session_id": "sess_cli",
            "status": "completed",
            "created_at": "2026-03-02T00:00:00+00:00",
            "updated_at": "2026-03-02T00:00:00+00:00",
            "turn_id": "turn_async",
            "stop_reason": "stop",
            "error": None,
        }


class _CompletedThenTailEventsStubClient(_StubClient):
    def __init__(self) -> None:
        super().__init__()
        self._stream_calls = 0

    def send_message_async(self, *, session_id: str, text: str) -> dict[str, object]:
        self.calls.append(("send_message_async", {"session_id": session_id, "text": text}))
        return {"run_id": "run_tail", "session_id": session_id, "status": "queued"}

    def stream_session_events(
        self,
        *,
        session_id: str,
        max_events: int = 20,
        timeout_seconds: float = 0.25,
    ) -> list[dict[str, object]]:
        del max_events, timeout_seconds
        self.calls.append(("stream_session_events", {"session_id": session_id}))
        self._stream_calls += 1
        if self._stream_calls == 1:
            return [
                {
                    "event_id": "evt_tail_completed",
                    "event": "run_status",
                    "data": {"run_id": "run_tail", "status": "completed"},
                }
            ]
        if self._stream_calls == 2:
            return [
                {
                    "event_id": "evt_tail_tool_start",
                    "event": "tool_start",
                    "data": {
                        "run_id": "run_tail",
                        "name": "echo",
                        "call_id": "call_tail",
                        "arguments": {"text": "tail"},
                    },
                },
                {
                    "event_id": "evt_tail_tool_end",
                    "event": "tool_end",
                    "data": {
                        "run_id": "run_tail",
                        "name": "echo",
                        "call_id": "call_tail",
                        "output": {"text": "echo:tail"},
                        "error": None,
                    },
                },
                {
                    "event_id": "evt_tail_text",
                    "event": "text_delta",
                    "data": {"run_id": "run_tail", "delta": "final:echo:tail"},
                },
            ]
        return []

    def get_run(self, *, run_id: str) -> dict[str, object]:
        self.calls.append(("get_run", {"run_id": run_id}))
        return {
            "run_id": run_id,
            "session_id": "sess_cli",
            "status": "completed",
            "created_at": "2026-03-02T00:00:00+00:00",
            "updated_at": "2026-03-02T00:00:00+00:00",
            "turn_id": "turn_tail",
            "stop_reason": "stop",
            "error": None,
        }


class _AsyncRetryingStatusStubClient(_StubClient):
    def __init__(self) -> None:
        super().__init__()
        self._poll_count = 0

    def send_message_async(self, *, session_id: str, text: str) -> dict[str, object]:
        self.calls.append(("send_message_async", {"session_id": session_id, "text": text}))
        return {"run_id": "run_retrying", "session_id": session_id, "status": "queued"}

    def stream_session_events(
        self,
        *,
        session_id: str,
        max_events: int = 20,
        timeout_seconds: float = 0.25,
    ) -> list[dict[str, object]]:
        del max_events, timeout_seconds
        self.calls.append(("stream_session_events", {"session_id": session_id}))
        self._poll_count += 1
        if self._poll_count == 1:
            return [
                {
                    "event_id": "evt_retry_1",
                    "event": "run_status",
                    "data": {
                        "run_id": "run_retrying",
                        "status": "running",
                        "attempt": 1,
                        "next_delay": 0.5,
                        "cooldown": 0.0,
                        "last_error": {"code": "model_error", "message": "upstream flaky #1"},
                    },
                }
            ]
        if self._poll_count == 2:
            return [
                {
                    "event_id": "evt_retry_2",
                    "event": "run_status",
                    "data": {
                        "run_id": "run_retrying",
                        "status": "running",
                        "attempt": 5,
                        "next_delay": 1.0,
                        "cooldown": 30.0,
                        "last_error": {"code": "model_error", "message": "upstream flaky #5"},
                    },
                }
            ]
        return []

    def get_run(self, *, run_id: str) -> dict[str, object]:
        self.calls.append(("get_run", {"run_id": run_id}))
        if self._poll_count >= 2:
            return {
                "run_id": run_id,
                "session_id": "sess_cli",
                "status": "completed",
                "created_at": "2026-03-03T00:00:00+00:00",
                "updated_at": "2026-03-03T00:00:00+00:00",
                "turn_id": "turn_retry",
                "stop_reason": "completed",
                "error": None,
            }
        return {
            "run_id": run_id,
            "session_id": "sess_cli",
            "status": "running",
            "created_at": "2026-03-03T00:00:00+00:00",
            "updated_at": "2026-03-03T00:00:00+00:00",
            "turn_id": None,
            "stop_reason": None,
            "error": None,
        }


class _AsyncQueueingStubClient(_StubClient):
    def __init__(self) -> None:
        super().__init__()
        self._run_count = 0
        self._poll_by_run: dict[str, int] = {}

    def send_message_async(self, *, session_id: str, text: str) -> dict[str, object]:
        self._run_count += 1
        run_id = f"run_queue_{self._run_count}"
        self.calls.append(("send_message_async", {"session_id": session_id, "text": text}))
        return {"run_id": run_id, "session_id": session_id, "status": "queued"}

    def stream_session_events(
        self,
        *,
        session_id: str,
        max_events: int = 20,
        timeout_seconds: float = 0.25,
    ) -> list[dict[str, object]]:
        del max_events, timeout_seconds
        self.calls.append(("stream_session_events", {"session_id": session_id}))
        return []

    def get_run(self, *, run_id: str) -> dict[str, object]:
        self.calls.append(("get_run", {"run_id": run_id}))
        poll_count = self._poll_by_run.get(run_id, 0) + 1
        self._poll_by_run[run_id] = poll_count

        # Hold first run in-progress briefly so REPL can accept and queue next input.
        if run_id == "run_queue_1" and poll_count < 4:
            time.sleep(0.03)
            return {
                "run_id": run_id,
                "session_id": "sess_cli",
                "status": "running",
                "created_at": "2026-03-04T00:00:00+00:00",
                "updated_at": "2026-03-04T00:00:00+00:00",
                "turn_id": None,
                "stop_reason": None,
                "error": None,
            }
        return {
            "run_id": run_id,
            "session_id": "sess_cli",
            "status": "completed",
            "created_at": "2026-03-04T00:00:00+00:00",
            "updated_at": "2026-03-04T00:00:00+00:00",
            "turn_id": f"turn_{run_id}",
            "stop_reason": "stop",
            "error": None,
        }


def _iter_keys(keys: list[str]):
    iterator = iter(keys)

    def _reader() -> str | None:
        try:
            return next(iterator)
        except StopIteration:
            return None

    return _reader


class _ScriptedReplInputReader:
    def __init__(self, scripted_lines: list[list[str]]) -> None:
        self._line_iterator = iter(scripted_lines)
        self.render = io.StringIO()

    def read_line(self, prompt: str, history: tuple[str, ...] | list[str]) -> str:
        keys = next(self._line_iterator)
        key_iterator = iter(keys)

        def _read_key() -> str | None:
            try:
                return next(key_iterator)
            except StopIteration:
                return None

        return repl_input.read_interactive_line(
            prompt=prompt,
            history=tuple(history),
            key_reader=_read_key,
            out=self.render,
            command_suggestions=repl_commands.REPL_COMMANDS,
        )


class _TTYStringIO(io.StringIO):
    def isatty(self) -> bool:  # pragma: no cover - simple test seam
        return True


def test_repl_input_engine_supports_inline_insert_at_cursor() -> None:
    typed = repl_input.read_interactive_line(
        prompt="nano> ",
        history=(),
        key_reader=_iter_keys(["h", "e", "l", "l", "o", "\x1b[D", "\x1b[D", "X", "\n"]),
        out=io.StringIO(),
    )

    assert typed == "helXlo"


def test_repl_input_engine_supports_left_right_with_backspace_editing() -> None:
    typed = repl_input.read_interactive_line(
        prompt="nano> ",
        history=(),
        key_reader=_iter_keys(["a", "b", "c", "\x1b[D", "\x7f", "\x1b[C", "!", "\n"]),
        out=io.StringIO(),
    )

    assert typed == "ac!"


def test_repl_input_engine_arrow_up_recalls_and_allows_editing() -> None:
    typed = repl_input.read_interactive_line(
        prompt="nano> ",
        history=("first", "second"),
        key_reader=_iter_keys(["\x1b[A", "\x1b[D", "\x1b[D", "X", "\n"]),
        out=io.StringIO(),
    )

    assert typed == "secoXnd"


def test_repl_input_engine_history_navigation_moves_up_and_down() -> None:
    typed = repl_input.read_interactive_line(
        prompt="nano> ",
        history=("first", "second"),
        key_reader=_iter_keys(["\x1b[A", "\x1b[A", "\x1b[B", "\n"]),
        out=io.StringIO(),
    )

    assert typed == "second"


def test_repl_input_engine_slash_menu_down_enter_fills_selected_command() -> None:
    typed = repl_input.read_interactive_line(
        prompt="nano> ",
        history=("from-history",),
        key_reader=_iter_keys(["/", "\x1b[B", "\n", "\n"]),
        out=io.StringIO(),
        command_suggestions=repl_commands.REPL_COMMANDS,
    )

    assert typed == "/new"


def test_repl_input_engine_slash_menu_up_wraps_without_history_recall() -> None:
    typed = repl_input.read_interactive_line(
        prompt="nano> ",
        history=("from-history",),
        key_reader=_iter_keys(["/", "\x1b[A", "\n", "\n"]),
        out=io.StringIO(),
        command_suggestions=repl_commands.REPL_COMMANDS,
    )

    assert typed == "/exit"


def test_repl_input_engine_slash_menu_does_not_render_multiline_panel() -> None:
    output = io.StringIO()
    typed = repl_input.read_interactive_line(
        prompt="nano> ",
        history=("from-history",),
        key_reader=_iter_keys(["/", "\x1b[B", "\n", "\n"]),
        out=output,
        command_suggestions=repl_commands.REPL_COMMANDS,
    )

    assert typed == "/new"
    assert "Commands ↓ " not in output.getvalue()


def test_repl_input_external_output_replays_prompt_without_layout_break() -> None:
    output = io.StringIO()

    repl_input.render_interactive_line(
        out=output,
        prompt="nano> ",
        chars=list("ping"),
        cursor=4,
    )
    repl_input.emit_external_text(out=output, text="[tool echo] output=ok")

    text = output.getvalue()
    assert "[tool echo] output=ok" in text
    assert "\r[tool echo] output=ok\r\n" in text
    assert text.count("nano> ping") >= 2


def test_repl_input_external_multiline_output_uses_terminal_safe_line_endings() -> None:
    output = io.StringIO()

    repl_input.render_interactive_line(
        out=output,
        prompt="nano> ",
        chars=list("ping"),
        cursor=4,
    )
    repl_input.emit_external_text(out=output, text="line-1\nline-2")

    text = output.getvalue()
    assert "line-1\r\nline-2\r\n" in text
    assert text.count("nano> ping") >= 2


def test_repl_input_engine_supports_cjk_cursor_movement_for_visible_characters() -> None:
    typed = repl_input.read_interactive_line(
        prompt="nano> ",
        history=(),
        key_reader=_iter_keys(["你", "好", "世", "界", "\x1b[D", "\x1b[D", "A", "\n"]),
        out=io.StringIO(),
    )

    assert typed == "你好A世界"


def test_repl_input_render_uses_display_width_for_mixed_text_cursor_position() -> None:
    output = io.StringIO()

    repl_input.render_interactive_line(
        out=output,
        prompt="nano> ",
        chars=list("你a好"),
        cursor=1,
    )

    text = output.getvalue()
    assert "\x1b[2D" not in text
    assert "\x1b[3D" in text


def test_repl_input_render_uses_display_width_for_cjk_inline_hint_cursor_position() -> None:
    output = io.StringIO()

    repl_input.render_interactive_line(
        out=output,
        prompt="nano> ",
        chars=list("你/"),
        cursor=1,
        command_items=repl_commands.REPL_COMMANDS,
        selected_command_index=0,
    )

    text = output.getvalue()
    expected_tail_columns = 1 + len("  (/help)")
    assert f"\x1b[{expected_tail_columns}D" in text


def test_repl_input_engine_supports_crlf_line_break_for_terminal_mode() -> None:
    output = io.StringIO()
    typed = repl_input.read_interactive_line(
        prompt="nano> ",
        history=(),
        key_reader=_iter_keys(["h", "i", "\n"]),
        out=output,
        line_break="\r\n",
    )

    assert typed == "hi"
    assert output.getvalue().endswith("\r\n")


def test_repl_input_state_machine_reports_needs_redraw_for_noop_and_mutating_keys() -> None:
    from coding_cli.input import repl_input as layered_repl_input

    state = layered_repl_input._initial_input_state(history=(), command_items=repl_commands.REPL_COMMANDS)

    noop = layered_repl_input._apply_input_key(state=state, key="\x1b[D")
    assert noop.needs_redraw is False
    assert noop.state.cursor == 0
    assert noop.state.chars == ()

    inserted = layered_repl_input._apply_input_key(state=noop.state, key="a")
    assert inserted.needs_redraw is True
    assert inserted.state.cursor == 1
    assert inserted.state.chars == ("a",)
    assert inserted.final_line is None


def test_repl_input_engine_skips_redundant_redraw_for_noop_keys(monkeypatch) -> None:
    from coding_cli.input import repl_input as layered_repl_input

    output = io.StringIO()
    render_calls: list[tuple[str, str, int]] = []
    original_render = layered_repl_input.render_interactive_line

    def _counting_render(*, out, prompt, chars, cursor, command_items=(), selected_command_index=None):
        render_calls.append(("render", "".join(chars), cursor))
        return original_render(
            out=out,
            prompt=prompt,
            chars=chars,
            cursor=cursor,
            command_items=command_items,
            selected_command_index=selected_command_index,
        )

    monkeypatch.setattr(layered_repl_input, "render_interactive_line", _counting_render)

    typed = repl_input.read_interactive_line(
        prompt="nano> ",
        history=(),
        key_reader=_iter_keys(["\x1b[D", "\x1b[D", "a", "\n"]),
        out=output,
        command_suggestions=repl_commands.REPL_COMMANDS,
    )

    assert typed == "a"
    # Initial render + one mutating render.
    assert len(render_calls) == 2


def test_repl_input_state_machine_skips_redraw_when_history_up_hits_top_boundary() -> None:
    from coding_cli.input import repl_input as layered_repl_input

    state = layered_repl_input._initial_input_state(history=("first",), command_items=repl_commands.REPL_COMMANDS)

    first_up = layered_repl_input._apply_input_key(state=state, key="\x1b[A")
    assert first_up.needs_redraw is True
    assert first_up.state.chars == ("f", "i", "r", "s", "t")

    second_up = layered_repl_input._apply_input_key(state=first_up.state, key="\x1b[A")
    assert second_up.needs_redraw is False
    assert second_up.state == first_up.state


def test_run_cli_repl_up_recalls_previous_command_line() -> None:
    stub = _StubClient()
    output = io.StringIO()
    scripted_reader = _ScriptedReplInputReader(
        scripted_lines=[
            ["/", "n", "e", "w", "\n"],
            ["/", "h", "e", "l", "p", "\n"],
            ["\x1b[A", "\n"],
            ["/", "e", "x", "i", "t", "\n"],
        ]
    )

    exit_code = run_cli(
        ["--base-url", "http://127.0.0.1:8000", "--token", "test-token"],
        stdout=output,
        client_factory=lambda _: stub,
        repl_input_reader_factory=lambda: scripted_reader,
    )

    assert exit_code == 0
    assert output.getvalue().count("Commands: /help /new /use <session_id>") == 2


def test_cli_help_mentions_repl_editing_budget_and_error_layers() -> None:
    help_text = cli_commands.build_parser().format_help()

    assert "REPL quick commands" in help_text
    assert "/compact /history [n] /exit" in help_text
    assert "Inline editing" in help_text
    assert "History recall" in help_text
    assert "HTTP-only boundary" in help_text
    assert "single final JSON object on stdout" in help_text
    assert "LLM usage: shown per turn" in help_text
    assert "Error layers: input / network / runtime" in help_text


def test_run_cli_health_outputs_json_payload() -> None:
    stub = _StubClient()
    output = io.StringIO()

    exit_code = run_cli(
        ["--base-url", "http://127.0.0.1:8000", "--token", "test-token", "health"],
        stdout=output,
        client_factory=lambda _: stub,
    )

    assert exit_code == 0
    assert json.loads(output.getvalue()) == {"healthy": True}
    assert stub.calls == [("health", None)]


def test_run_cli_send_message_uses_session_id_from_env(monkeypatch) -> None:
    monkeypatch.setenv("NANO_MULTIAGENT_SESSION_ID", "sess_env")
    stub = _StubClient()
    output = io.StringIO()

    exit_code = run_cli(
        [
            "--base-url",
            "http://127.0.0.1:8000",
            "--token",
            "test-token",
            "send-message",
            "--text",
            "ping",
        ],
        stdout=output,
        client_factory=lambda _: stub,
    )

    assert exit_code == 0
    raw = output.getvalue().strip()
    assert "\n" not in raw
    payload = json.loads(raw)
    assert payload["session_id"] == "sess_env"
    assert payload["message"]["content"] == "echo:ping"


def test_run_cli_repl_supports_required_commands() -> None:
    stub = _StubClient()
    output = io.StringIO()
    inputs = iter(["/help", "/new", "hello repl", "/session", "/tools", "/compact", "/exit"])

    exit_code = run_cli(
        ["--base-url", "http://127.0.0.1:8000", "--token", "test-token"],
        stdout=output,
        client_factory=lambda _: stub,
        input_fn=lambda _: next(inputs),
    )

    assert exit_code == 0
    lines = output.getvalue()
    assert "/help /new /use <session_id> /session /tools /compact" in lines
    assert "/history [n]" in lines
    assert "/exit" in lines
    assert "Started new session sess_cli." in lines
    assert "Active session: sess_cli." in lines
    assert '{"session_id":' not in lines
    assert "hello repl" in lines
    assert "Tools for session sess_cli (1):" in lines
    assert "- read: Read" in lines
    assert "Compaction for session sess_cli: no changes." in lines
    assert "Context budget: 64/200 (32.0%)" in lines
    assert [call[0] for call in stub.calls] == [
        "create_session",
        "send_message",
        "get_context_budget",
        "list_session_tools",
        "compact_session",
        "get_context_budget",
    ]


def test_run_cli_repl_use_switches_active_session() -> None:
    stub = _StubClient()
    output = io.StringIO()
    inputs = iter(["/use sess_manual", "ping", "/exit"])

    exit_code = run_cli(
        ["--base-url", "http://127.0.0.1:8000", "--token", "test-token"],
        stdout=output,
        client_factory=lambda _: stub,
        input_fn=lambda _: next(inputs),
    )

    assert exit_code == 0
    assert "Switched to session sess_manual." in output.getvalue()
    assert ("send_message", {"session_id": "sess_manual", "text": "ping"}) in stub.calls


def test_run_cli_repl_session_transitions_render_active_copy_without_json() -> None:
    stub = _StubClient()
    output = io.StringIO()
    inputs = iter(["hello auto", "/new", "/use sess_manual", "/exit"])

    exit_code = run_cli(
        ["--base-url", "http://127.0.0.1:8000", "--token", "test-token"],
        stdout=output,
        client_factory=lambda _: stub,
        input_fn=lambda _: next(inputs),
    )

    assert exit_code == 0
    text = output.getvalue()
    assert text.count("Started new session sess_cli.") == 2
    assert text.count("Active session: sess_cli.") >= 2
    assert "Switched to session sess_manual." in text
    assert "Active session: sess_manual." in text
    assert '{"session_id":' not in text
    assert '"session_id":' not in text


def test_run_cli_repl_history_shows_recent_messages() -> None:
    stub = _StubClient()
    output = io.StringIO()
    inputs = iter(["/new", "first", "second", "/history 2", "/exit"])

    exit_code = run_cli(
        ["--base-url", "http://127.0.0.1:8000", "--token", "test-token"],
        stdout=output,
        client_factory=lambda _: stub,
        input_fn=lambda _: next(inputs),
    )

    assert exit_code == 0
    text = output.getvalue()
    assert "History for session sess_cli (last 2/4):" in text
    assert "user: second" in text
    assert "assistant: echo:second" in text
    assert "assistant: echo:first" not in text


def test_run_cli_repl_command_errors_include_actionable_suggestions() -> None:
    stub = _StubClient()
    output = io.StringIO()
    inputs = iter(["/tools", "/use", "/unknown", "/exit"])

    exit_code = run_cli(
        ["--base-url", "http://127.0.0.1:8000", "--token", "test-token"],
        stdout=output,
        client_factory=lambda _: stub,
        input_fn=lambda _: next(inputs),
    )

    assert exit_code == 0
    text = output.getvalue()
    assert "Error: no active session." in text
    assert "Layer: input" in text
    assert "Suggestion: run /new or /use <session_id>." in text
    assert "Error: missing session_id for /use." in text
    assert "Suggestion: try /use <session_id>." in text
    assert "Error: unknown command '/unknown'." in text
    assert "Suggestion: run /help to see available commands." in text


def test_run_cli_repl_absolute_path_input_is_not_treated_as_command() -> None:
    stub = _StubClient()
    output = io.StringIO()
    path_line = "/Users/czj/Repos/nano-multiagent/Snipaste_2026-03-03_12-54-14.png这个呢"
    inputs = iter(["/new", path_line, "/exit"])

    exit_code = run_cli(
        ["--base-url", "http://127.0.0.1:8000", "--token", "test-token"],
        stdout=output,
        client_factory=lambda _: stub,
        input_fn=lambda _: next(inputs),
    )

    assert exit_code == 0
    text = output.getvalue()
    assert f"echo:{path_line}" in text
    assert "unknown command" not in text
    assert ("send_message", {"session_id": "sess_cli", "text": path_line}) in stub.calls


def test_run_cli_repl_ignores_blank_input_and_exits_on_eof() -> None:
    stub = _StubClient()
    output = io.StringIO()
    calls = iter(["   "])

    def _input(_: str) -> str:
        try:
            return next(calls)
        except StopIteration as exc:
            raise EOFError() from exc

    exit_code = run_cli(
        ["--base-url", "http://127.0.0.1:8000", "--token", "test-token"],
        stdout=output,
        client_factory=lambda _: stub,
        input_fn=_input,
    )

    assert exit_code == 0
    assert output.getvalue().strip() == "bye"
    assert stub.calls == []


def test_run_cli_repl_rejects_invalid_command_arguments() -> None:
    stub = _StubClient()
    output = io.StringIO()
    inputs = iter(["/new extra", "/session now", "/use a b", "/history 0", "/exit"])

    exit_code = run_cli(
        ["--base-url", "http://127.0.0.1:8000", "--token", "test-token"],
        stdout=output,
        client_factory=lambda _: stub,
        input_fn=lambda _: next(inputs),
    )

    assert exit_code == 0
    text = output.getvalue()
    assert "Error: command /new does not accept arguments." in text
    assert "Layer: input" in text
    assert "Suggestion: try /new." in text
    assert "Usage: /new" in text
    assert "Error: command /session does not accept arguments." in text
    assert "Suggestion: try /session." in text
    assert "Usage: /session" in text
    assert "Error: /use expects exactly one session_id." in text
    assert "Suggestion: try /use <session_id>." in text
    assert "Usage: /use <session_id>" in text
    assert "Error: invalid n for /history." in text
    assert "Suggestion: try /history 10." in text
    assert "Usage: /history [n]" in text
    assert ("create_session", {"title": ""}) not in stub.calls


def test_run_cli_repl_compact_summary_displays_key_fields() -> None:
    stub = _CompactedStubClient()
    output = io.StringIO()
    inputs = iter(["/new", "/compact", "/exit"])

    exit_code = run_cli(
        ["--base-url", "http://127.0.0.1:8000", "--token", "test-token"],
        stdout=output,
        client_factory=lambda _: stub,
        input_fn=lambda _: next(inputs),
    )

    assert exit_code == 0
    text = output.getvalue()
    assert "Compaction for session sess_cli: compacted." in text
    assert "Summary: context compacted" in text
    assert "Kept events: 2" in text
    assert "Dropped events: 1" in text
    assert "Context budget (after /compact): 64/200 (32.0%)" in text


def test_run_cli_repl_compact_prints_post_compact_budget_state_line() -> None:
    stub = _CompactedStubClient()
    output = io.StringIO()
    inputs = iter(["/new", "/compact", "/exit"])

    exit_code = run_cli(
        ["--base-url", "http://127.0.0.1:8000", "--token", "test-token"],
        stdout=output,
        client_factory=lambda _: stub,
        input_fn=lambda _: next(inputs),
    )

    assert exit_code == 0
    text = output.getvalue()
    assert "Compaction for session sess_cli: compacted." in text
    assert "Context budget (after /compact): 64/200 (32.0%)" in text


def test_run_cli_repl_edit_history_budget_compact_chain_regression() -> None:
    stub = _CompactedStubClient()
    output = io.StringIO()
    scripted_reader = _ScriptedReplInputReader(
        scripted_lines=[
            ["/", "n", "e", "w", "\n"],
            ["h", "e", "l", "l", "o", "\x1b[D", "\x1b[D", "X", "\n"],
            ["\x1b[A", "\x1b[C", "!", "\n"],
            ["/", "c", "o", "m", "p", "a", "c", "t", "\n"],
            ["/", "h", "i", "s", "t", "o", "r", "y", " ", "4", "\n"],
            ["/", "e", "x", "i", "t", "\n"],
        ]
    )

    exit_code = run_cli(
        ["--base-url", "http://127.0.0.1:8000", "--token", "test-token"],
        stdout=output,
        client_factory=lambda _: stub,
        repl_input_reader_factory=lambda: scripted_reader,
    )

    assert exit_code == 0
    text = output.getvalue()
    assert "echo:helXlo" in text
    assert "echo:helXlo!" in text
    assert "History for session sess_cli" in text
    assert "user: helXlo!" in text
    assert "Compaction for session sess_cli: compacted." in text
    assert "Context budget (after /compact): 64/200 (32.0%)" in text


def test_run_cli_repl_context_budget_shows_threshold_hint() -> None:
    stub = _ThresholdBudgetStubClient(used_tokens=174, max_tokens=200)
    output = io.StringIO()
    inputs = iter(["/new", "hello", "/exit"])

    exit_code = run_cli(
        ["--base-url", "http://127.0.0.1:8000", "--token", "test-token"],
        stdout=output,
        client_factory=lambda _: stub,
        input_fn=lambda _: next(inputs),
    )

    assert exit_code == 0
    text = output.getvalue()
    assert "echo:hello" in text
    assert "Context budget: 174/200 (87.0%)" in text
    assert "Budget hint: usage >= 85%, consider /compact soon." in text


def test_run_cli_repl_context_budget_fetch_failure_is_fail_open() -> None:
    stub = _FailingBudgetStubClient()
    output = io.StringIO()
    inputs = iter(["/new", "hello", "/exit"])

    exit_code = run_cli(
        ["--base-url", "http://127.0.0.1:8000", "--token", "test-token"],
        stdout=output,
        client_factory=lambda _: stub,
        input_fn=lambda _: next(inputs),
    )

    assert exit_code == 0
    text = output.getvalue()
    assert "echo:hello" in text
    assert "Context budget: unavailable" in text


def test_run_cli_repl_prints_turn_llm_usage_when_available() -> None:
    stub = _UsageStubClient()
    output = io.StringIO()
    inputs = iter(["/new", "hello", "/exit"])

    exit_code = run_cli(
        ["--base-url", "http://127.0.0.1:8000", "--token", "test-token"],
        stdout=output,
        client_factory=lambda _: stub,
        input_fn=lambda _: next(inputs),
    )

    assert exit_code == 0
    text = output.getvalue()
    assert "echo:hello" in text
    assert "State: completed | stop=stop | session=sess_cli" in text
    assert "Usage: prompt=120, completion=35, total=155" in text
    assert "[status]" not in text
    assert "[usage]" not in text


def test_run_cli_repl_infers_completed_state_when_sync_payload_has_stop_reason() -> None:
    stub = _StopReasonOnlyStubClient()
    output = io.StringIO()
    inputs = iter(["/new", "hello", "/exit"])

    exit_code = run_cli(
        ["--base-url", "http://127.0.0.1:8000", "--token", "test-token"],
        stdout=output,
        client_factory=lambda _: stub,
        input_fn=lambda _: next(inputs),
    )

    assert exit_code == 0
    text = output.getvalue()
    assert "State: completed | stop=stop | session=sess_cli" in text


def test_run_cli_repl_request_failures_include_suggestions() -> None:
    stub = _FailingToolsStubClient()
    output = io.StringIO()
    inputs = iter(["/new", "/tools", "/exit"])

    exit_code = run_cli(
        ["--base-url", "http://127.0.0.1:8000", "--token", "test-token"],
        stdout=output,
        client_factory=lambda _: stub,
        input_fn=lambda _: next(inputs),
    )

    assert exit_code == 0
    text = output.getvalue()
    assert "Error: failed to run /tools." in text
    assert "Layer: network" in text
    assert "Suggestion: check server status/token and retry /tools." in text


def test_run_cli_repl_connection_refused_shows_base_url_suggestion() -> None:
    stub = _ConnectionRefusedOnSendStubClient()
    output = io.StringIO()
    inputs = iter(["hi", "/exit"])

    exit_code = run_cli(
        ["--base-url", "http://127.0.0.1:8000", "--token", "test-token"],
        stdout=output,
        client_factory=lambda _: stub,
        input_fn=lambda _: next(inputs),
    )

    assert exit_code == 0
    text = output.getvalue()
    assert "Assistant: (empty)" in text
    assert "send failed: [Errno 61] Connection refused" in text
    assert "layer=network" in text
    assert "suggestion=check --base-url and ensure API server is running." in text


def test_run_cli_repl_timeout_shows_timeout_tuning_suggestion() -> None:
    stub = _TimeoutOnSendStubClient()
    output = io.StringIO()
    inputs = iter(["hi", "/exit"])
    manager = _ManagedServerSpy()

    exit_code = run_cli(
        ["--mode", "managed", "--base-url", "http://127.0.0.1:8000", "--token", "test-token"],
        stdout=output,
        client_factory=lambda _: stub,
        input_fn=lambda _: next(inputs),
        managed_server_factory=lambda config: manager.bind(config),
    )

    assert exit_code == 0
    text = output.getvalue().lower()
    assert "assistant: (empty)" in text
    assert "send failed: timed out" in text
    assert "layer=network" in text
    assert "agent_api_timeout_seconds" in text


def test_run_cli_repl_uses_async_events_with_run_filter_and_dedup() -> None:
    stub = _AsyncEventingStubClient()
    output = io.StringIO()
    inputs = iter(["/new", "ping", "/exit"])

    exit_code = run_cli(
        ["--base-url", "http://127.0.0.1:8000", "--token", "test-token"],
        stdout=output,
        client_factory=lambda _: stub,
        input_fn=lambda _: next(inputs),
    )

    assert exit_code == 0
    text = output.getvalue()
    assert "status=queued" not in text
    assert "Tool: echo start args=ping" in text
    assert "Tool echo start args=ping" not in text
    assert "Tool: echo output=echo:ping" in text
    assert "Assistant:" in text
    assert "final:echo:ping" in text
    assert "ignore-me" not in text
    assert ("send_message_async", {"session_id": "sess_cli", "text": "ping"}) in stub.calls


def test_send_message_with_async_events_sanitizes_multiline_tool_preview() -> None:
    stub = _AsyncMultilineToolOutputStubClient()
    output = io.StringIO()
    inputs = iter(["/new", "ping", "/exit"])

    exit_code = run_cli(
        ["--base-url", "http://127.0.0.1:8000", "--token", "test-token"],
        stdout=output,
        client_factory=lambda _: stub,
        input_fn=lambda _: next(inputs),
    )

    assert exit_code == 0
    text = output.getvalue()
    assert "Tool: echo output=line1\\nline2" in text
    assert "Tool: echo output=line1\nline2" not in text


def test_send_message_with_async_events_truncates_long_tool_output_with_head_and_tail() -> None:
    stub = _AsyncLongToolOutputStubClient()
    output = io.StringIO()
    inputs = iter(["/new", "ping", "/exit"])

    exit_code = run_cli(
        ["--base-url", "http://127.0.0.1:8000", "--token", "test-token"],
        stdout=output,
        client_factory=lambda _: stub,
        input_fn=lambda _: next(inputs),
    )

    assert exit_code == 0
    text = output.getvalue()
    assert "Tool: echo output=HEAD-" in text
    assert "..." in text
    assert "-TAIL" in text
    assert "x" * 150 not in text


def test_run_cli_repl_groups_same_tool_name_events_by_call_id() -> None:
    stub = _AsyncSameToolTwiceStubClient()
    output = io.StringIO()
    inputs = iter(["/new", "ping", "/exit"])

    exit_code = run_cli(
        ["--base-url", "http://127.0.0.1:8000", "--token", "test-token"],
        stdout=output,
        client_factory=lambda _: stub,
        input_fn=lambda _: next(inputs),
    )

    assert exit_code == 0
    text = output.getvalue()
    assert text.count("Tool: echo start args=") == 2
    assert "Tool echo start args=" not in text
    assert "Tool: echo output=echo:first" in text
    assert "Tool: echo output=echo:second" in text


def test_run_cli_repl_keeps_same_tool_output_lines_for_distinct_call_id() -> None:
    stub = _AsyncSameToolSameOutputStubClient()
    output = io.StringIO()
    inputs = iter(["/new", "ping", "/exit"])

    exit_code = run_cli(
        ["--base-url", "http://127.0.0.1:8000", "--token", "test-token"],
        stdout=output,
        client_factory=lambda _: stub,
        input_fn=lambda _: next(inputs),
    )

    assert exit_code == 0
    text = output.getvalue()
    assert text.count("Tool: echo output=echo:same") == 2
    assert "final:echo:same" in text


def test_run_cli_repl_prints_compact_answer_first_summary_for_async_flow() -> None:
    stub = _AsyncEventingStubClient()
    output = io.StringIO()
    inputs = iter(["/new", "ping", "/exit"])

    exit_code = run_cli(
        ["--base-url", "http://127.0.0.1:8000", "--token", "test-token"],
        stdout=output,
        client_factory=lambda _: stub,
        input_fn=lambda _: next(inputs),
    )

    assert exit_code == 0
    text = output.getvalue()
    assert "Assistant:" in text
    assert "final:echo:ping" in text
    assert "State: completed | stop=stop | run=run_target | session=sess_cli" in text
    assert "Tool: echo start args=ping" in text
    assert "Tool echo start args=ping" not in text
    assert "Tool: echo output=echo:ping" in text
    assert "Usage: unavailable" in text
    assert '"run_id": "run_target"' not in text
    assert "[status]" not in text


def test_run_cli_repl_prints_async_turn_llm_usage_when_available() -> None:
    stub = _AsyncUsageEventingStubClient()
    output = io.StringIO()
    inputs = iter(["/new", "ping", "/exit"])

    exit_code = run_cli(
        ["--base-url", "http://127.0.0.1:8000", "--token", "test-token"],
        stdout=output,
        client_factory=lambda _: stub,
        input_fn=lambda _: next(inputs),
    )

    assert exit_code == 0
    text = output.getvalue()
    assert "Usage: prompt=320, completion=41, total=361" in text


def test_run_cli_repl_streams_started_running_chunk_and_exit_for_tool_execution() -> None:
    stub = _AsyncToolExecStreamingStubClient()
    output = io.StringIO()
    inputs = iter(["/new", "ping", "/exit"])

    exit_code = run_cli(
        ["--base-url", "http://127.0.0.1:8000", "--token", "test-token"],
        stdout=output,
        client_factory=lambda _: stub,
        input_fn=lambda _: next(inputs),
    )

    assert exit_code == 0
    text = output.getvalue()
    assert "Tool: bash start args=" in text
    assert "Tool: bash started status=started elapsed=0ms" in text
    assert "Tool: bash running status=running elapsed=120ms" not in text
    assert "Tool: bash chunk stdout#1: out-line" not in text
    assert "Tool: bash chunk stderr#2: err-line" not in text
    assert "Tool: bash chunk stdout#1: out-line" not in text
    assert "Tool: bash chunk stderr#2: err-line" not in text
    assert "Tool: bash progress chunks=2 (stdout=1, stderr=1)" in text
    assert text.count("Tool: bash exit code=0 status=completed duration=210ms") == 1
    assert text.index("Tool: bash started status=started elapsed=0ms") < text.index("State:")


def test_run_cli_repl_renders_orphan_tool_exit_as_isolated_timeline() -> None:
    stub = _AsyncOrphanExecExitStubClient()
    output = io.StringIO()
    inputs = iter(["/new", "ping", "/exit"])

    exit_code = run_cli(
        ["--base-url", "http://127.0.0.1:8000", "--token", "test-token"],
        stdout=output,
        client_factory=lambda _: stub,
        input_fn=lambda _: next(inputs),
    )

    assert exit_code == 0
    text = output.getvalue()
    assert "Tool: orphan bash exit code=137 status=failed duration=31ms" in text
    assert "Tool: bash exit code=0 status=completed duration=19ms" in text
    assert "Progress: orphan_events=1" in text
    assert "final:orphan-isolated" in text


def test_run_cli_repl_dedupes_replayed_tool_start_without_event_id() -> None:
    stub = _AsyncNoEventIdReplayStubClient()
    output = io.StringIO()
    inputs = iter(["/new", "ping", "/exit"])

    exit_code = run_cli(
        ["--base-url", "http://127.0.0.1:8000", "--token", "test-token"],
        stdout=output,
        client_factory=lambda _: stub,
        input_fn=lambda _: next(inputs),
    )

    assert exit_code == 0
    text = output.getvalue()
    assert text.count("bash start args=") == 1
    assert text.count("Tool: bash exit code=0 status=completed duration=12ms") == 1
    assert "final:no-event-id" in text


def test_run_cli_repl_dedupes_replayed_tool_start_with_changed_event_id() -> None:
    stub = _AsyncChangedEventIdReplayStubClient()
    output = io.StringIO()
    inputs = iter(["/new", "ping", "/exit"])

    exit_code = run_cli(
        ["--base-url", "http://127.0.0.1:8000", "--token", "test-token"],
        stdout=output,
        client_factory=lambda _: stub,
        input_fn=lambda _: next(inputs),
    )

    assert exit_code == 0
    text = output.getvalue()
    assert text.count("Tool: bash start args=") == 1
    assert "final:changed-event-id" in text


def test_run_cli_repl_dedupes_replayed_tool_start_with_changed_event_id_and_nonsemantic_metadata() -> None:
    stub = _AsyncChangedEventIdWithTimestampReplayStubClient()
    output = io.StringIO()
    inputs = iter(["/new", "ping", "/exit"])

    exit_code = run_cli(
        ["--base-url", "http://127.0.0.1:8000", "--token", "test-token"],
        stdout=output,
        client_factory=lambda _: stub,
        input_fn=lambda _: next(inputs),
    )

    assert exit_code == 0
    text = output.getvalue()
    assert text.count("Tool: bash start args=") == 1
    assert text.count("Tool: bash started status=started elapsed=0ms") == 1
    assert text.count("Tool: bash exit code=0 status=completed duration=19ms") == 1
    assert "final:changed-event-id-ts" in text


def test_run_cli_repl_failed_run_error_includes_run_id_for_diagnosis() -> None:
    stub = _AsyncFailedRunStubClient()
    output = io.StringIO()
    inputs = iter(["/new", "hi", "/exit"])

    exit_code = run_cli(
        ["--base-url", "http://127.0.0.1:8000", "--token", "test-token"],
        stdout=output,
        client_factory=lambda _: stub,
        input_fn=lambda _: next(inputs),
    )

    assert exit_code == 0
    text = output.getvalue()
    assert "Assistant: (empty)" in text
    assert "send failed: run_id=run_failed" in text
    assert "layer=runtime" in text
    assert "NANO_MULTIAGENT_API_TIMEOUT_SECONDS" in text


def test_run_cli_repl_prints_compact_error_summary_for_failed_run() -> None:
    stub = _AsyncFailedRunStubClient()
    output = io.StringIO()
    inputs = iter(["/new", "hi", "/exit"])

    exit_code = run_cli(
        ["--base-url", "http://127.0.0.1:8000", "--token", "test-token"],
        stdout=output,
        client_factory=lambda _: stub,
        input_fn=lambda _: next(inputs),
    )

    assert exit_code == 0
    text = output.getvalue()
    assert "Assistant: (empty)" in text
    assert "State: failed | layer=runtime" in text
    assert "Error: send failed: run_id=run_failed" in text
    assert "Usage: unavailable" in text
    assert "[status]" not in text


def test_run_cli_repl_prints_retry_progress_from_run_status_event() -> None:
    stub = _AsyncRetryingStatusStubClient()
    output = io.StringIO()
    inputs = iter(["/new", "ping", "/exit"])

    exit_code = run_cli(
        ["--base-url", "http://127.0.0.1:8000", "--token", "test-token"],
        stdout=output,
        client_factory=lambda _: stub,
        input_fn=lambda _: next(inputs),
    )

    assert exit_code == 0
    text = output.getvalue()
    assert "Progress: retrying (" in text
    assert "attempt 5" in text
    assert "attempt 1" not in text
    assert "next 1.0s" in text
    assert "cooldown 30.0s" in text
    assert "last error model_error:" in text
    assert "upstream flaky #5" in text


def test_run_cli_repl_delays_terminal_run_status_until_after_tool_tail_events() -> None:
    stub = _CompletedStatusFirstStubClient()
    output = io.StringIO()
    inputs = iter(["/new", "ping", "/exit"])

    exit_code = run_cli(
        ["--base-url", "http://127.0.0.1:8000", "--token", "test-token"],
        stdout=output,
        client_factory=lambda _: stub,
        input_fn=lambda _: next(inputs),
    )

    assert exit_code == 0
    text = output.getvalue()
    assert "State: completed | stop=stop | run=run_completed_first | session=sess_cli" in text
    assert "Tool: echo output=echo:ping" in text


def test_run_cli_repl_queues_user_input_while_previous_async_run_is_in_progress() -> None:
    stub = _AsyncQueueingStubClient()
    output = io.StringIO()
    inputs = iter(["/new", "first", "second", "/exit"])

    exit_code = run_cli(
        ["--base-url", "http://127.0.0.1:8000", "--token", "test-token"],
        stdout=output,
        client_factory=lambda _: stub,
        input_fn=lambda _: next(inputs),
    )

    assert exit_code == 0
    text = output.getvalue()
    assert "Queued message #1" in text
    send_async_calls = [call for call in stub.calls if call[0] == "send_message_async"]
    assert send_async_calls == [
        ("send_message_async", {"session_id": "sess_cli", "text": "first"}),
        ("send_message_async", {"session_id": "sess_cli", "text": "second"}),
    ]


def test_run_cli_repl_history_command_ignores_false_timeout_when_queue_already_drained(monkeypatch) -> None:
    from coding_cli import commands as app_commands

    class _FalseTimeoutAfterDrainQueue:
        def __init__(self, *, process_message, on_worker_error=None) -> None:  # noqa: ANN001
            del on_worker_error
            self._process_message = process_message
            self._pending: list[object] = []

        def enqueue(self, *, session_id: str, text: str) -> int:
            backlog_before = len(self._pending)
            self._pending.append(app_commands.QueuedReplMessage(session_id=session_id, text=text))
            return backlog_before

        def backlog_size(self) -> int:
            return len(self._pending)

        def wait_for_drain(self, *, timeout_seconds: float | None = None) -> bool:
            del timeout_seconds
            while self._pending:
                item = self._pending.pop(0)
                self._process_message(item)
            # Emulate deadline-race false negative: drained but returns False.
            return False

        def close(self, *, wait_for_drain: bool, drain_timeout_seconds: float | None = None) -> bool:
            del wait_for_drain, drain_timeout_seconds
            return True

    stub = _AsyncEventingStubClient()
    output = io.StringIO()
    inputs = iter(["/new", "ping", "/history", "/exit"])

    monkeypatch.setattr(app_commands, "ReplRunQueue", _FalseTimeoutAfterDrainQueue)
    exit_code = run_cli(
        ["--base-url", "http://127.0.0.1:8000", "--token", "test-token"],
        stdout=output,
        client_factory=lambda _: stub,
        input_fn=lambda _: next(inputs),
    )

    assert exit_code == 0
    text = output.getvalue()
    assert "History for session sess_cli" in text
    assert "assistant: final:echo:ping" in text
    assert "Timed out waiting for in-flight messages; skipping /history for now." not in text


def test_run_cli_repl_exit_reports_remaining_inflight_messages_after_timeout(monkeypatch) -> None:
    from coding_cli import commands as app_commands

    class _NeverDrainQueue:
        def __init__(self, *, process_message, on_worker_error=None) -> None:  # noqa: ANN001
            del process_message, on_worker_error
            self._pending = 0

        def enqueue(self, *, session_id: str, text: str) -> int:
            del session_id, text
            backlog_before = self._pending
            self._pending += 1
            return backlog_before

        def backlog_size(self) -> int:
            return self._pending

        def wait_for_drain(self, *, timeout_seconds: float | None = None) -> bool:
            del timeout_seconds
            return False

        def close(self, *, wait_for_drain: bool, drain_timeout_seconds: float | None = None) -> bool:
            del wait_for_drain, drain_timeout_seconds
            return True

    output = io.StringIO()
    inputs = iter(["/new", "first", "second", "/exit"])

    monkeypatch.setattr(app_commands, "ReplRunQueue", _NeverDrainQueue)
    exit_code = run_cli(
        ["--base-url", "http://127.0.0.1:8000", "--token", "test-token"],
        stdout=output,
        client_factory=lambda _: _AsyncEventingStubClient(),
        input_fn=lambda _: next(inputs),
    )

    assert exit_code == 0
    text = output.getvalue()
    assert "Waiting for 2 in-flight message(s) before exit." in text
    assert "Timed out waiting for in-flight messages before exit; 2 still in-flight message(s)." in text


def test_run_cli_repl_non_tty_async_output_avoids_emit_external_text_path(monkeypatch) -> None:
    stub = _AsyncToolExecStreamingStubClient()
    output = io.StringIO()
    inputs = iter(["/new", "ping", "/exit"])

    def _forbid_emit_external_text(*, out, text):  # noqa: ANN001
        del out, text
        raise AssertionError("non-tty path must not call emit_external_text")

    monkeypatch.setattr(repl_input, "emit_external_text", _forbid_emit_external_text)
    exit_code = run_cli(
        ["--base-url", "http://127.0.0.1:8000", "--token", "test-token"],
        stdout=output,
        client_factory=lambda _: stub,
        input_fn=lambda _: next(inputs),
    )

    assert exit_code == 0
    text = output.getvalue()
    assert "Tool: bash start args=" in text
    assert "State: completed" in text
    assert "\r" not in text
    assert "\x1b[" not in text


def test_run_cli_repl_tty_async_output_uses_emit_external_text_path(monkeypatch) -> None:
    stub = _AsyncToolExecStreamingStubClient()
    output = _TTYStringIO()
    inputs = iter(["/new", "ping", "/exit"])
    emitted: list[str] = []

    original_emit_external_text = repl_input.emit_external_text

    def _record_emit_external_text(*, out, text):  # noqa: ANN001
        emitted.append(text)
        return original_emit_external_text(out=out, text=text)

    monkeypatch.setattr(repl_input, "emit_external_text", _record_emit_external_text)
    exit_code = run_cli(
        ["--base-url", "http://127.0.0.1:8000", "--token", "test-token"],
        stdout=output,
        client_factory=lambda _: stub,
        input_fn=lambda _: next(inputs),
    )

    assert exit_code == 0
    assert emitted

class _ManagedServerSpy:
    def __init__(self, *, fail_on_start: Exception | None = None) -> None:
        self.fail_on_start = fail_on_start
        self.events: list[str] = []
        self.config_base_url: str | None = None
        self.config_token: str | None = None
        self.llm_provider: str | None = None
        self.llm_model: str | None = None
        self.llm_base_url: str | None = None
        self.llm_api_key: str | None = None
        self.llm_timeout_seconds: float | None = None

    def bind(self, config: object) -> "_ManagedServerSpy":
        self.config_base_url = getattr(config, "base_url", None)
        self.config_token = getattr(config, "token", None)
        self.llm_provider = getattr(config, "llm_provider", None)
        self.llm_model = getattr(config, "llm_model", None)
        self.llm_base_url = getattr(config, "llm_base_url", None)
        self.llm_api_key = getattr(config, "llm_api_key", None)
        self.llm_timeout_seconds = getattr(config, "llm_timeout_seconds", None)
        return self

    def start(self) -> None:
        self.events.append("start")
        if self.fail_on_start is not None:
            raise self.fail_on_start

    def stop(self) -> None:
        self.events.append("stop")


def test_run_cli_managed_mode_starts_and_stops_local_server() -> None:
    stub = _StubClient()
    output = io.StringIO()
    manager = _ManagedServerSpy()

    exit_code = run_cli(
        [
            "--mode",
            "managed",
            "--base-url",
            "http://127.0.0.1:8111",
            "--token",
            "test-token",
            "health",
        ],
        stdout=output,
        client_factory=lambda _: stub,
        managed_server_factory=lambda config: manager.bind(config),
    )

    assert exit_code == 0
    assert json.loads(output.getvalue()) == {"healthy": True}
    assert manager.config_base_url == "http://127.0.0.1:8111"
    assert manager.events == ["start", "stop"]


def test_run_cli_remote_mode_does_not_start_local_server() -> None:
    stub = _StubClient()
    output = io.StringIO()

    exit_code = run_cli(
        [
            "--mode",
            "remote",
            "--base-url",
            "http://127.0.0.1:8112",
            "--token",
            "test-token",
            "health",
        ],
        stdout=output,
        client_factory=lambda _: stub,
        managed_server_factory=lambda _: (_ for _ in ()).throw(AssertionError("should not start")),
    )

    assert exit_code == 0
    assert json.loads(output.getvalue()) == {"healthy": True}


def test_run_cli_managed_mode_start_failure_surfaces_actionable_suggestion() -> None:
    stub = _StubClient()
    output = io.StringIO()
    manager = _ManagedServerSpy(fail_on_start=RuntimeError("port 8000 already in use"))

    exit_code = run_cli(
        [
            "--mode",
            "managed",
            "--base-url",
            "http://127.0.0.1:8000",
            "--token",
            "test-token",
            "health",
        ],
        stdout=output,
        client_factory=lambda _: stub,
        managed_server_factory=lambda config: manager.bind(config),
    )

    assert exit_code == 1
    payload = json.loads(output.getvalue())
    assert "port 8000 already in use" in payload["error"]
    assert "remote" in payload["suggestion"].lower()


def test_run_cli_remote_mode_requires_base_url_with_actionable_error() -> None:
    output = io.StringIO()

    exit_code = run_cli(
        ["--mode", "remote", "--token", "test-token", "health"],
        stdout=output,
        client_factory=lambda _: (_ for _ in ()).throw(AssertionError("should not build client")),
    )

    assert exit_code == 1
    payload = json.loads(output.getvalue())
    assert "remote mode requires --base-url" in payload["error"]
    assert payload["layer"] == "input"
    assert "--base-url" in payload["suggestion"]


def test_run_cli_remote_mode_connection_failure_suggestion_mentions_remote_api() -> None:
    stub = _ConnectionRefusedOnHealthStubClient()
    output = io.StringIO()

    exit_code = run_cli(
        [
            "--mode",
            "remote",
            "--base-url",
            "http://127.0.0.1:8222",
            "--token",
            "test-token",
            "health",
        ],
        stdout=output,
        client_factory=lambda _: stub,
    )

    assert exit_code == 1
    payload = json.loads(output.getvalue())
    assert "connection refused" in payload["error"].lower()
    assert payload["layer"] == "network"
    assert "remote api" in payload["suggestion"].lower()


def test_run_cli_managed_mode_uses_higher_default_timeout_when_not_configured() -> None:
    observed: dict[str, float] = {}

    class _TimeoutCaptureClient(_StubClient):
        def __init__(self, timeout_seconds: float) -> None:
            super().__init__()
            observed["timeout_seconds"] = timeout_seconds

    output = io.StringIO()
    exit_code = run_cli(
        ["--mode", "managed", "--base-url", "http://127.0.0.1:8113", "--token", "test-token", "health"],
        stdout=output,
        client_factory=lambda config: _TimeoutCaptureClient(config.timeout_seconds),
        managed_server_factory=lambda _: _ManagedServerSpy(),
    )

    assert exit_code == 0
    assert observed["timeout_seconds"] == 120.0


def test_run_cli_respects_explicit_api_timeout_seconds() -> None:
    observed: dict[str, float] = {}

    class _TimeoutCaptureClient(_StubClient):
        def __init__(self, timeout_seconds: float) -> None:
            super().__init__()
            observed["timeout_seconds"] = timeout_seconds

    output = io.StringIO()
    exit_code = run_cli(
        [
            "--mode",
            "managed",
            "--base-url",
            "http://127.0.0.1:8114",
            "--token",
            "test-token",
            "--api-timeout-seconds",
            "45",
            "health",
        ],
        stdout=output,
        client_factory=lambda config: _TimeoutCaptureClient(config.timeout_seconds),
        managed_server_factory=lambda _: _ManagedServerSpy(),
    )

    assert exit_code == 0
    assert observed["timeout_seconds"] == 45.0


def test_run_cli_llm_config_get_outputs_payload() -> None:
    stub = _StubClient()
    output = io.StringIO()

    exit_code = run_cli(
        ["--mode", "remote", "--base-url", "http://127.0.0.1:8000", "--token", "test-token", "llm-config", "get"],
        stdout=output,
        client_factory=lambda _: stub,
    )

    assert exit_code == 0
    payload = json.loads(output.getvalue())
    assert payload["provider"] == "openai_compat"
    assert stub.calls == [("get_llm_config", None)]


def test_run_cli_llm_config_set_applies_requested_fields() -> None:
    stub = _StubClient()
    output = io.StringIO()

    exit_code = run_cli(
        [
            "--mode",
            "remote",
            "--base-url",
            "http://127.0.0.1:8000",
            "--token",
            "test-token",
            "llm-config",
            "set",
            "--provider",
            "anthropic",
            "--model",
            "claude-3-5-sonnet-20241022",
            "--base-url",
            "http://127.0.0.1:4100",
            "--api-key",
            "sk-cli",
            "--timeout-seconds",
            "55",
        ],
        stdout=output,
        client_factory=lambda _: stub,
    )

    assert exit_code == 0
    payload = json.loads(output.getvalue())
    assert payload["provider"] == "anthropic"
    assert stub.calls == [
        (
            "set_llm_config",
            {
                "provider": "anthropic",
                "model": "claude-3-5-sonnet-20241022",
                "base_url": "http://127.0.0.1:4100",
                "api_key": "sk-cli",
                "timeout_seconds": 55.0,
                "clear_api_key": False,
            },
        )
    ]


def test_run_cli_llm_config_set_requires_at_least_one_field() -> None:
    stub = _StubClient()
    output = io.StringIO()

    exit_code = run_cli(
        ["--mode", "remote", "--base-url", "http://127.0.0.1:8000", "--token", "test-token", "llm-config", "set"],
        stdout=output,
        client_factory=lambda _: stub,
    )

    assert exit_code == 1
    payload = json.loads(output.getvalue())
    assert "at least one" in payload["error"].lower()
    assert payload["layer"] == "input"
    assert "llm-config set" in payload["suggestion"]


def test_run_cli_llm_config_set_rejects_conflicting_api_key_flags() -> None:
    stub = _StubClient()
    output = io.StringIO()

    exit_code = run_cli(
        [
            "--mode",
            "remote",
            "--base-url",
            "http://127.0.0.1:8000",
            "--token",
            "test-token",
            "llm-config",
            "set",
            "--api-key",
            "sk-cli",
            "--clear-api-key",
        ],
        stdout=output,
        client_factory=lambda _: stub,
    )

    assert exit_code == 1
    payload = json.loads(output.getvalue())
    assert "cannot be used together" in payload["error"].lower()
    assert "choose either" in payload["suggestion"].lower()


def test_run_cli_managed_mode_forwards_llm_startup_options_to_managed_server() -> None:
    stub = _StubClient()
    output = io.StringIO()
    manager = _ManagedServerSpy()

    exit_code = run_cli(
        [
            "--mode",
            "managed",
            "--base-url",
            "http://127.0.0.1:8115",
            "--token",
            "test-token",
            "--llm-provider",
            "anthropic",
            "--llm-model",
            "claude-3-5-sonnet-20241022",
            "--llm-base-url",
            "http://127.0.0.1:4100",
            "--llm-api-key",
            "sk-managed",
            "--llm-timeout-seconds",
            "75",
            "health",
        ],
        stdout=output,
        client_factory=lambda _: stub,
        managed_server_factory=lambda config: manager.bind(config),
    )

    assert exit_code == 0
    assert manager.config_base_url == "http://127.0.0.1:8115"
    assert manager.config_token == "test-token"
    assert manager.llm_provider == "anthropic"
    assert manager.llm_model == "claude-3-5-sonnet-20241022"
    assert manager.llm_base_url == "http://127.0.0.1:4100"
    assert manager.llm_api_key == "sk-managed"
    assert manager.llm_timeout_seconds == 75.0
