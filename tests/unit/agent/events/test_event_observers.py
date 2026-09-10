"""Protect synchronous observation ordering, isolation and close semantics."""

import threading

from agent.core.events.hub import EventStreamHub


def test_observer_finishes_before_live_replay_and_close_waits_for_callback():
    hub = EventStreamHub()
    entered = threading.Event()
    release = threading.Event()
    closed = threading.Event()
    seen = []

    def record(event):
        seen.append(event)
        entered.set()
        assert release.wait(2)

    subscription = hub.observe(record)
    publisher = threading.Thread(
        target=lambda: hub.publish(event="tool_end", session_id="s", data={})
    )
    publisher.start()
    assert entered.wait(1)

    def close():
        subscription.close()
        closed.set()

    closer = threading.Thread(target=close)
    closer.start()
    try:
        assert not closed.wait(0.02)
        assert (
            list(
                hub.stream(
                    session_id="s", after_sequence=0, max_events=1, timeout_seconds=0
                )
            )
            == []
        )
    finally:
        release.set()
        publisher.join(2)
        closer.join(2)
    assert closed.is_set()
    replay = list(
        hub.stream(session_id="s", after_sequence=0, max_events=1, timeout_seconds=0)
    )
    assert replay[0].event_id == seen[0].event_id
    hub.publish(event="turn_end", session_id="s", data={})
    assert len(seen) == 1


def test_failing_observer_does_not_drop_other_observers_or_bounded_live_history():
    hub = EventStreamHub(history_limit=2)
    observed = []

    def failed(event):
        raise OSError("local recording unavailable")

    bad = hub.observe(failed)
    good = hub.observe(observed.append)
    try:
        for index in range(5):
            hub.publish(event="step", session_id="s", data={"index": index})
        assert [event.data["index"] for event in observed] == list(range(5))
        replay = list(
            hub.stream(
                session_id="s", after_sequence=0, max_events=5, timeout_seconds=0
            )
        )
        assert [event.data["index"] for event in replay] == [3, 4]
    finally:
        bad.close()
        good.close()
