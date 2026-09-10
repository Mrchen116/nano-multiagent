"""Protect global Gateway stop and restart lifecycle through the real kernel."""

import pytest

from tests.integration.test_global_gateway_runtime import (
    _Model,
    _close,
    _message,
    _receive,
    _runtime,
    _wait,
)


@pytest.mark.asyncio
async def test_stop_retains_inbox_and_new_rejects_without_rebinding(tmp_path):
    model = _Model(pause=True)
    rt = await _runtime(tmp_path, model)
    try:
        await _receive(rt, _message("m1", "Initial requirement"))
        await _wait(model.read_done.is_set)
        await _receive(rt, _message("m2", "Another request", "group-b"))
        main = rt.store.get_global_session("worker")["session_id"]
        await _receive(
            rt,
            _message("stop", "/stop", "group-b"),
            command="stop",
            operation_id="stop-op",
        )
        await _receive(
            rt, _message("new", "/new", "group-c"), command="new", operation_id="new-op"
        )
        assert rt.store.get_global_session("worker")["session_id"] == main
        assert rt.store.get_signal_state("worker")["stop_through_seq"] == 2
        assert len(rt.inbox.blocking_entries("worker", "group-b")) == 1
        assert [row[1] for row in rt.controls] == ["group-b", "group-c"]
        rt.store.update_signal_state("worker", latest_signal_seq=3)
        await _receive(
            rt,
            _message("stop", "/stop", "group-b"),
            command="stop",
            operation_id="stop-op",
        )
        assert rt.store.get_signal_state("worker")["stop_through_seq"] == 2
    finally:
        model.resume.set()
        await _close(rt)


@pytest.mark.asyncio
async def test_restart_restores_one_main_and_does_not_reawaken_committed_signal(
    tmp_path,
):
    first = await _runtime(tmp_path, _Model())
    try:
        await _receive(first, _message("m1", "Read this once"))
        await _wait(
            lambda: (
                first.manager.sent
                and not first.coordinator._monitors
                and not first.coordinator._drains
            )
        )
        main_id = first.store.get_global_session("worker")["session_id"]
    finally:
        await _close(first)
    model = _Model()
    restored = await _runtime(tmp_path, model)
    try:
        restored.coordinator.start()
        await _wait(lambda: not restored.coordinator._drains)
        assert not model.requests
        assert restored.store.get_global_session("worker")["session_id"] == main_id
        await _receive(restored, _message("m2", "A new input after restart"))
        await _wait(
            lambda: (
                model.requests
                and not restored.coordinator._monitors
                and not restored.coordinator._drains
            )
        )
        assert len(model.requests) == 1
        assert restored.store.get_signal_state("worker")["signaled_through_seq"] == 2
        assert len(restored.inbox.blocking_entries("worker", "group-a")) == 1
        # Choosing not to read leaves pending content without a repeated wake.
        restored.coordinator.notify("worker")
        await _wait(lambda: not restored.coordinator._drains)
        assert len(model.requests) == 1
    finally:
        await _close(restored)
