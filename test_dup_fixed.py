#!/usr/bin/env python3
import sys
import io

# Add src to path
sys.path.insert(0, '/Users/czj/Repos/nano-multiagent/src')

from coding_cli.events.repl_events import consume_async_run_events
from coding_cli.events.event_pipeline import EventDedupeWindow, ReplRenderPhaseMachine

def test_duplicate_text_delta():
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
    test_duplicate_text_delta()
