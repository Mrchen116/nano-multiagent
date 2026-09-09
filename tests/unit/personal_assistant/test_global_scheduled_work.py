"""Protect global automatic execution ownership and busy admission semantics."""

import asyncio
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

from personal_assistant.config.local_store import AgentWorkspaceConfig, HeartbeatConfig
from personal_assistant.gateway.agent_catalog import LiveAgentCatalog
from personal_assistant.gateway.runtime_delivery.context import RunDeliveryContextStore
from personal_assistant.scheduler.cron_runner import CronRunner
from personal_assistant.scheduler.cron_scheduler import CronJob
from personal_assistant.scheduler.heartbeat_runner import PollingHeartbeatRunner
from personal_assistant.scheduler.heartbeat_scheduler import (
    HeartbeatRunRecord,
    HeartbeatScheduler,
    HeartbeatSchedulerStateStore,
    HeartbeatTickSummary,
)


def agent_catalog(tmp_path):
    path = tmp_path / ".nanoassistant" / "HEARTBEAT.md"
    path.parent.mkdir(exist_ok=True)
    path.write_text("- Check progress\n")
    agent = AgentWorkspaceConfig(
        agent_id="global",
        workspace_root=tmp_path,
        work_mode="global",
        heartbeat_every="1s",
        features={"heartbeat": True},
    )
    return agent, LiveAgentCatalog((agent,))


class Binder:
    async def resolve_global(self, snapshot):
        return SimpleNamespace(
            kernel_session_id="main", workspace_root=snapshot.config.workspace_root
        )

    def find_canonical_direct(self, **kwargs):
        raise AssertionError("Global work cannot route through the last direct chat")


@pytest.mark.asyncio
async def test_global_heartbeat_uses_idle_main_and_busy_ticks_do_not_queue(tmp_path):
    agent, catalog = agent_catalog(tmp_path)
    admitted = []

    class Client:
        busy = True

        def try_submit_idle(self, **kwargs):
            admitted.append(kwargs)
            return None if self.busy else {"run_id": "heartbeat"}

        async def ensure_agent_runtime(self, **kwargs):
            assert kwargs["metadata"]["pa_work_scope"] == "global_main"

    client = Client()
    scheduler = HeartbeatScheduler(
        agents=(agent,),
        agent_catalog=catalog,
        kernel_client=client,
        session_binder=Binder(),
        state_store=HeartbeatSchedulerStateStore(tmp_path / "state.json"),
    )
    now = datetime(2026, 9, 9, tzinfo=UTC)
    busy = await scheduler.tick(now=now)
    assert not busy.triggered_runs
    assert busy.skipped_agents == ("global",)
    client.busy = False
    assert not (await scheduler.tick(now=now)).triggered_runs
    active = await scheduler.tick(now=now + timedelta(seconds=1))
    assert active.triggered_runs[0].session_id == "main"
    assert active.triggered_runs[0].work_scope == "global_main"
    assert admitted[-1]["origin"] == "heartbeat"
    assert admitted[-1]["revalidate_output"] is True


@pytest.mark.asyncio
async def test_global_heartbeat_records_work_without_chat_delivery_or_transcript_trim(
    tmp_path,
):
    agent, catalog = agent_catalog(tmp_path)
    finished = asyncio.Event()

    class Scheduler:
        async def tick(self):
            return HeartbeatTickSummary(
                (
                    HeartbeatRunRecord(
                        agent_id="global",
                        due_at=datetime.now(UTC),
                        run_id="hb",
                        session_id="main",
                        work_scope="global_main",
                    ),
                ),
                (),
            )

    class Kernel:
        async def stream(self, session_id, **kwargs):
            for event in (
                {"event": "assistant_message", "content": "Internal progress"},
                {"event": "tool_start", "name": "bash"},
                {"event": "run_status", "status": "completed"},
            ):
                if event["event"] == "run_status":
                    finished.set()
                yield {"run_id": "hb", **event}

        async def discard_run_messages(self, run):
            raise AssertionError("Global work must retain its main context")

    chats = []
    runner = PollingHeartbeatRunner(
        scheduler=Scheduler(),
        config=HeartbeatConfig(tick_interval_seconds=60),
        kernel=Kernel(),
        run_context_store=RunDeliveryContextStore(),
        owner_user_id="owner",
        kernel_event_observer=chats.append,
        agent_catalog=catalog,
    )
    await runner.start()
    # Stream consumers stop at terminal; a following tick is unnecessary.
    await asyncio.wait_for(finished.wait(), timeout=2)
    await runner.close()
    assert chats == []


@pytest.mark.asyncio
async def test_cron_registers_isolated_execution_and_awareness_uses_global_main(
    tmp_path,
):
    _, catalog = agent_catalog(tmp_path)
    registered = {}
    submitted = []
    awareness = []

    class Recorder:
        def register(self, **kwargs):
            registered.update(kwargs)

        def record(self, **kwargs):
            pass

    class Client:
        async def create_session(self, **kwargs):
            assert kwargs["metadata"]["pa_work_scope"] == "cron"
            return {"session_id": "cron-session"}

        def submit_message(self, **kwargs):
            assert registered["scope"] == "cron"
            assert registered["session_id"] == kwargs["session_id"]
            submitted.append(kwargs)
            return {"run_id": "cron-run"}

        def append_message(self, **kwargs):
            awareness.append(kwargs)

    runner = CronRunner(
        agent_id="global",
        workspace_root=tmp_path,
        kernel_client=Client(),
        session_binder=Binder(),
        agent_catalog=catalog,
        work_recorder=Recorder(),
        canonical_session_id_provider=lambda: "wrong-old-chat",
    )
    job = CronJob(
        id="job",
        name="check",
        schedule={"kind": "every", "everyMs": 1000},
        instruction="Check",
    )
    assert await runner.submit(job=job, request_id="request", trigger="manual") == (
        "cron-run",
        "cron-session",
    )
    assert submitted[0]["origin"] == "cron"
    assert registered["trigger"] == "manual"
    await runner.append_awareness(result_text="Already delivered result")
    assert awareness[0]["session_id"] == "main"


@pytest.mark.asyncio
async def test_global_cron_delivers_only_terminal_body_even_after_fallback(tmp_path):
    from dataclasses import replace

    from personal_assistant.gateway.model_fallback import ModelStickyStore
    from personal_assistant.scheduler.cron_execution_service import (
        CronRunTerminalConsumer,
    )

    agent, catalog = agent_catalog(tmp_path)
    catalog.publish(
        replace(
            agent, default_model="openai:primary", model_fallbacks=("openai:backup",)
        )
    )
    delivered = []

    class Kernel:
        async def stream(self, session_id, **kwargs):
            if not kwargs.get("after_sequence"):
                yield {
                    "event": "run_status",
                    "run_id": "failed",
                    "status": "failed",
                    "error": {"kind": "quota", "message": "quota exhausted"},
                }
                return
            for item in (
                {"event": "assistant_message", "content": "Investigating"},
                {
                    "event": "tool_start",
                    "name": "bash",
                    "arguments": {"command": "private command"},
                },
                {
                    "event": "assistant_message",
                    "content": "Delivered final",
                    "reasoning_content": "private reasoning",
                },
                {"event": "turn_end"},
                {"event": "run_status", "status": "completed"},
            ):
                yield {"run_id": "replay", **item}

        async def reconfigure_session(self, **kwargs):
            assert "pa.global_routing" not in {
                piece.name for piece in kwargs["runtime"].prompt.body
            }

        def replay_last_user(self, **kwargs):
            return SimpleNamespace(run_id="replay", start_sequence=2)

    consumer = CronRunTerminalConsumer(
        kernel=Kernel(),
        owner_user_id="owner",
        run_context_store=RunDeliveryContextStore(),
        observer=delivered.append,
        agent_catalog=catalog,
        sticky_store=ModelStickyStore(),
    )
    outcome = await consumer.consume(
        run_id="failed", kernel_session_id="cron-session", agent_id="global"
    )
    assert outcome.status == "completed"
    bodies = [event for event in delivered if event["event"] == "assistant_message"]
    assert bodies[-1]["content"] == "Delivered final"
    assert all("reasoning_content" not in event for event in bodies)
    assert not any(
        event.get("content") == "Investigating" or event["event"] == "tool_start"
        for event in delivered
    )


@pytest.mark.asyncio
async def test_global_fallback_retains_main_prompt_and_publication_guard(tmp_path):
    from dataclasses import replace

    from agent.sdk import RunOrigin
    from personal_assistant.gateway.model_fallback import (
        ModelStickyStore,
        failover_unattended_run,
    )
    from personal_assistant.gateway.runtime_delivery.stream import StreamRunOutcome

    agent, catalog = agent_catalog(tmp_path)
    snapshot = catalog.publish(
        replace(agent, default_model="openai:first", model_fallbacks=("openai:second",))
    )
    captured = []

    class Kernel:
        async def reconfigure_session(self, **kwargs):
            captured.append(kwargs["runtime"])

        def replay_last_user(self, **kwargs):
            assert kwargs["revalidate_output"] is True
            return SimpleNamespace(run_id="replay", start_sequence=1)

    async def consume(**kwargs):
        return StreamRunOutcome(
            status="completed", final_text="done", delivery=None, error=None
        )

    result = await failover_unattended_run(
        kernel=Kernel(),
        session_id="main",
        workspace_root=tmp_path,
        agent_snapshot=snapshot,
        sticky_store=ModelStickyStore(),
        product_default=None,
        reasoning_catalog=None,
        time_context=None,
        current_model="openai:first",
        outcome=StreamRunOutcome(
            status="failed",
            final_text="",
            delivery=None,
            error="quota",
            error_kind="quota",
        ),
        origin=RunOrigin.HEARTBEAT,
        consume_replay=consume,
        scenario={"agent_id": "global", "pa_work_scope": "global_main"},
        revalidate_output=True,
    )
    assert result.status == "completed"
    assert "pa.global_routing" in {piece.name for piece in captured[0].prompt.body}


@pytest.mark.asyncio
async def test_runtime_adapter_rejects_busy_configuration_without_false_applied_event(
    tmp_path,
):
    from personal_assistant.gateway.kernel_client import InProcessKernelClient

    _, catalog = agent_catalog(tmp_path)
    records = []

    class Kernel:
        def identify_runtime(self, **kwargs):
            return SimpleNamespace(
                fingerprint_schema="v1", runtime_fingerprint="changed"
            )

        async def get_session_runtime(self, **kwargs):
            return None

        async def reconfigure_session(self, **kwargs):
            assert kwargs["only_if_idle"] is True
            assert "pa.global_routing" in {
                piece.name for piece in kwargs["runtime"].prompt.body
            }
            return None

    class Recorder:
        def register(self, **kwargs):
            pass

        def record(self, **kwargs):
            records.append(kwargs)

    client = InProcessKernelClient(
        Kernel(),
        agent_catalog=catalog,
        product_default_model="openai:primary",
        work_recorder=Recorder(),
    )
    assert not await client.ensure_agent_runtime(
        session_id="main",
        agent_snapshot=catalog.require("global"),
        workspace_root=str(tmp_path),
        metadata={"agent_id": "global", "pa_work_scope": "global_main"},
        only_if_idle=True,
    )
    assert records == []
