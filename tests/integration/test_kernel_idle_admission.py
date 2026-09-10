"""Protect nonqueue Session admission and restart-safe input receipt behavior."""

import asyncio
import threading
from dataclasses import replace

import pytest

from agent.sdk import PromptSlots, PromptText, SessionRuntimeConfig
from tests.contract.test_kernel_sdk_behavior_contract import (
    _lc_llm,
    _wait_for_terminal_run,
)
from tests.integration.test_kernel_committed_observation import _Client, _kernel


@pytest.mark.asyncio
async def test_idle_submission_busy_dedup_and_durable_restart_receipt(tmp_path):
    client = _Client(block=True)
    kernel = _kernel(tmp_path, client)
    events = []
    subscription = kernel.observe_events(events.append)
    try:
        session = await kernel.create_session()
        args = dict(
            session_id=session.session_id,
            parts=[{"type": "text", "text": "wake"}],
            submission_id="inbox:1",
        )
        first = kernel.try_submit_idle(**args)
        assert first is not None
        assert kernel.try_submit_idle(**args).run_id == first.run_id
        assert kernel.try_submit_idle(**{**args, "submission_id": "inbox:2"}) is None
        assert await asyncio.to_thread(client.entered.wait, 2)
        proof = next(
            event for event in events if event["event"] == "turn_input_committed"
        )
        receipt = kernel.get_submission_receipt(
            session_id=session.session_id, submission_id="inbox:1"
        )
        assert receipt["input_committed"] is True
        assert receipt["turn_id"] == proof["turn_id"]
        assert proof["submission_id"] == "inbox:1"
        assert proof["event_id"] and proof["created_at"]
    finally:
        subscription.close()
        kernel.close()
    reopened = _kernel(tmp_path, _Client())
    try:
        receipt = reopened.get_submission_receipt(
            session_id=session.session_id, submission_id="inbox:1"
        )
        assert receipt["input_committed"] and receipt["run_id"] == first.run_id
    finally:
        reopened.close()


@pytest.mark.asyncio
async def test_terminal_uncommitted_submission_can_be_readmitted_with_same_identity(
    tmp_path,
):
    handled = False

    def setup(hooks):
        async def first_input(event, ctx):
            nonlocal handled
            if not handled:
                handled = True
                return {"action": "handled"}
            return None

        hooks.on("input", first_input, priority=0)

    kernel = _kernel(tmp_path, _Client(), hooks=[setup])
    released = threading.Event()
    subscription = kernel.observe_events(
        lambda event: released.set() if event["event"] == "session_idle" else None
    )
    try:
        session = await kernel.create_session()
        args = dict(
            session_id=session.session_id,
            submission_id="wake:retry",
            parts=[{"type": "text", "text": "wake"}],
        )
        first = kernel.try_submit_idle(**args)
        await _wait_for_terminal_run(kernel, first.run_id)
        assert await asyncio.to_thread(released.wait, 2)
        receipt = kernel.get_submission_receipt(
            session_id=session.session_id, submission_id="wake:retry"
        )
        assert receipt["input_committed"] is False
        second = kernel.try_submit_idle(**args)
        assert second is not None and second.run_id != first.run_id
        await _wait_for_terminal_run(kernel, second.run_id)
        receipt = kernel.get_submission_receipt(
            session_id=session.session_id, submission_id="wake:retry"
        )
        assert receipt["input_committed"] and receipt["run_id"] == second.run_id
    finally:
        subscription.close()
        kernel.close()


@pytest.mark.asyncio
async def test_changed_runtime_idle_reconfigure_rejects_busy_without_queueing(tmp_path):
    kernel = _kernel(tmp_path, _Client(block=True))
    released = threading.Event()
    entered = threading.Event()

    def observe(event):
        if event["event"] == "turn_input_committed":
            entered.set()
        elif event["event"] == "session_idle":
            released.set()

    subscription = kernel.observe_events(observe)
    runtime = SessionRuntimeConfig(
        model=_lc_llm().model,
        prompt=PromptSlots(),
        skills=None,
        enabled_tools=[],
        features=None,
    )
    try:
        session = await kernel.create_session(runtime=runtime)
        run = kernel.submit(
            session_id=session.session_id, parts=[{"type": "text", "text": "working"}]
        )
        assert await asyncio.to_thread(entered.wait, 2)
        args = dict(
            session_id=session.session_id, workspace_root=tmp_path, only_if_idle=True
        )
        same = await asyncio.wait_for(
            kernel.reconfigure_session(runtime=runtime, **args), 0.5
        )
        assert same is not None and same.changed is False
        changed = replace(
            runtime, prompt=PromptSlots(tail=(PromptText("new", "next runtime"),))
        )
        rejected = await asyncio.wait_for(
            kernel.reconfigure_session(runtime=changed, **args), 0.5
        )
        assert rejected is None
        kernel.cancel(run.run_id)
        assert await asyncio.to_thread(released.wait, 2)
        saved = await kernel.get_session_runtime(
            session_id=session.session_id, workspace_root=tmp_path
        )
        assert saved.runtime == runtime
        applied = await kernel.reconfigure_session(runtime=changed, **args)
        assert applied.changed and applied.state.runtime == changed
    finally:
        subscription.close()
        kernel.close()
