#!/usr/bin/env python3
"""Quick test to verify client behavior with duplicate text_delta events."""

import io
from coding_cli.events.repl_events import consume_async_run_events, EventDedupeWindow, ReplRenderPhaseMachine

def test_duplicate_text_delta():
    out = io.StringIO()
    dedupe = EventDedupeWindow()
    phase = ReplRenderPhaseMachine()

    # Simulate 5 identical text_delta events with different sequence numbers
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

    # Now test with preview_writer (like emit_external_text)
    out2 = io.StringIO()
    dedupe2 = EventDedupeWindow()
    phase2 = ReplRenderPhaseMachine()
    preview_lines = []

    def preview_writer(text):
        preview_lines.append(text)
        out2.write(text)
        out2.flush()

    assistant_text2, consumed2, streamed2 = consume_async_run_events(
        out=out2,
        events=events,
        run_id="run_123",
        assistant_text="",
        dedupe_window=dedupe2,
        render_phase_machine=phase2,
        emit_preview=True,
        preview_writer=preview_writer,
    )

    print(f"\nWith preview_writer:")
    print(f"consumed={consumed2}, streamed={streamed2}")
    print(f"preview_lines count={len(preview_lines)}")
    print(f"out2.getvalue()={out2.getvalue()!r}")

if __name__ == "__main__":
    test_duplicate_text_delta()
