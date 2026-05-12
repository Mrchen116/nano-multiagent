#!/usr/bin/env python3
import io
from coding_cli.events.repl_events import consume_async_run_events
from coding_cli.events.event_pipeline import EventDedupeWindow, ReplRenderPhaseMachine, consume_event_for_run, normalize_session_event

def test_detail():
    print("=== Testing consume_event_for_run directly ===")
    dedupe_window = EventDedupeWindow()
    run_id = "run_123"
    for i in range(5):
        event = {
            "sequence_num": i + 1,
            "event_id": f"evt-{i+1}",
            "event": "text_delta",
            "data": {
                "run_id": "run_123",
                "delta": "让我先看看当前目录的结构",
            }
        }
        normalized = normalize_session_event(event)
        print(f"Event {i+1} (event_id={normalized.event_id}):")
        result = consume_event_for_run(
            normalized_event=normalized,
            run_id=run_id,
            dedupe_window=dedupe_window
        )
        print(f"  consume_event_for_run returned: {result}")
        print(f"  _event_ids in dedupe_window: {list(dedupe_window._event_ids.keys())}")
        print(f"  _fallback_by_run: {dict(dedupe_window._fallback_by_run)}")

    print("\n=== Testing consume_async_run_events ===")
    out = io.StringIO()
    dedupe = EventDedupeWindow()
    phase = ReplRenderPhaseMachine()

    events = []
    for i in range(5):
        events.append({
            "sequence_num": i + 1,
            "event_id": f"evt-{i+1}",
            "event": "text_delta",
            "data": {
                "run_id": "run_123",
                "delta": "让我先看看当前目录的结构",
            }
        })

    assistant_text, consumed, streamed = consume_async_run_events(
        out=out,
        events=events,
        run_id="run_123",
        assistant_text="",
        dedupe_window=dedupe,
        render_phase_machine=phase,
        emit_preview=True,
    )

    print(f"consumed={consumed}, streamed={streamed}")
    print(f"assistant_text={assistant_text!r}")
    print(f"out.getvalue()={out.getvalue()!r}")
    print(f"len(out.getvalue())={len(out.getvalue())}")

if __name__ == "__main__":
    test_detail()
