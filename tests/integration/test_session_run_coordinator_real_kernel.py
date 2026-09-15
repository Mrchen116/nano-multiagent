"""Real Kernel race coverage for Gateway run admission ownership."""

from __future__ import annotations

import asyncio
import threading
from pathlib import Path
from typing import Any

import pytest

from agent.core.llm.interfaces import LLMMessage, LLMToolCall
from agent.sdk import LLMConfig, PermissionDecision, build_kernel
from personal_assistant.config.local_store import (
    AgentWorkspaceConfig,
    LLMConfigPayload,
    LLMModelPayload,
    LLMProviderPayload,
)
from personal_assistant.config.model_reasoning import (
    ModelReasoningCapability,
    ModelReasoningCatalog,
)
from personal_assistant.gateway.agent_catalog import LiveAgentCatalog
from personal_assistant.gateway.channel_registry import ChannelRegistry
from personal_assistant.gateway.group_context_store import GroupContextStore
from personal_assistant.gateway.inbound_models import InboundRunRequest, RoutedInbound
from personal_assistant.gateway.outbound_router import OutboundRouter
from personal_assistant.gateway.session_binder import GatewaySessionBinder
from personal_assistant.gateway.session_keys import (
    SessionBindingStore,
    build_session_key,
)
from personal_assistant.gateway.session_run_coordinator import SessionRunCoordinator

from tests.unit.personal_assistant._pipeline_helpers import _FakeChannel
from tests.unit.personal_assistant._session_run_coordinator_helpers import inbound


async def _allow_all(_tool: str, _input: Any, _context: Any) -> PermissionDecision:
    return PermissionDecision(behavior="allow")


class _CountingClient:
    def __init__(self) -> None:
        self.requests: list[Any] = []

    async def generate(self, request: Any):
        self.requests.append(request)
        yield LLMMessage(
            role="assistant",
            content=f"reply-{len(self.requests)}",
            finish_reason="stop",
        )


class _SequentialWorkflowClient:
    """Hold each child until its foreground PA turn has become idle."""

    def __init__(self) -> None:
        self.requests: list[Any] = []
        self._launched_prompts: set[str] = set()
        self.child_started = (threading.Event(), threading.Event())
        self.child_release = (threading.Event(), threading.Event())
        self._child_count = 0

    def generate(self, request: Any):  # noqa: ANN201
        self.requests.append(request)
        tool_names = {tool.name for tool in request.tools}
        if "Workflow" not in tool_names:
            index = self._child_count
            self._child_count += 1
            return self._child_result(index)

        latest_user = _latest_user_text(request)
        if latest_user in {"first Workflow", "second Workflow"} and (
            latest_user not in self._launched_prompts
        ):
            self._launched_prompts.add(latest_user)
            return self._launch_workflow(len(self._launched_prompts))
        return self._finish_parent()

    async def _launch_workflow(self, ordinal: int):  # noqa: ANN202
        yield LLMMessage(
            role="assistant",
            content="launching",
            tool_calls=(
                LLMToolCall(
                    call_id=f"call-workflow-{ordinal}",
                    name="Workflow",
                    arguments={
                        "script": f"""\
meta = {{"name": "sequential-{ordinal}", "description": "Run one child"}}
async def main():
    return await agent("return child {ordinal}")
"""
                    },
                ),
            ),
        )

    async def _child_result(self, index: int):  # noqa: ANN202
        self.child_started[index].set()
        await asyncio.to_thread(self.child_release[index].wait)
        yield LLMMessage(
            role="assistant",
            content=f"child-{index + 1}",
            finish_reason="stop",
        )

    async def _finish_parent(self):  # noqa: ANN202
        yield LLMMessage(role="assistant", content="done", finish_reason="stop")


def _latest_user_text(request: Any) -> str:
    for message in reversed(request.messages):
        if message.role == "user" and isinstance(message.content, str):
            return message.content
    return ""


def _request(message, catalog: LiveAgentCatalog) -> InboundRunRequest:
    agent = catalog.require("agent-a")
    return InboundRunRequest(
        routed=RoutedInbound(message=message),
        agent=agent,
        session_key=build_session_key(message, agent_id=agent.agent_id),
        sender_label="Alice",
    )


async def _wait_for_background_terminals(
    kernel: Any, session_id: str, count: int
) -> None:
    async def _collect() -> None:
        completed: set[str] = set()
        async for event in kernel.stream(session_id):
            if (
                event.get("event") == "run_status"
                and event.get("origin") == "background_task"
                and event.get("status") in {"completed", "failed", "cancelled"}
            ):
                completed.add(str(event["run_id"]))
                if len(completed) >= count:
                    return

    await asyncio.wait_for(_collect(), timeout=3)


async def _wait_for_workflow_count(kernel: Any, session_id: str, count: int) -> None:
    deadline = asyncio.get_running_loop().time() + 3
    while asyncio.get_running_loop().time() < deadline:
        runs = kernel.list_workflow_runs(session_id=session_id)
        if len(runs) == count and all(run.status == "completed" for run in runs):
            return
        await asyncio.sleep(0.01)
    raise AssertionError(f"Workflow count did not reach {count}")


@pytest.mark.asyncio
async def test_pa_profile_runtime_reaches_two_workflow_children_and_continuations(
    tmp_path: Path,
) -> None:
    """A PA session owns model/effort across repeated unattended Workflow work."""

    deepseek = "deepseek:deepseek-v4-flash"
    luna = "codexOAuth:gpt-5.6-luna"
    selectable = ModelReasoningCapability(
        kind="selectable", default="high", levels=("low", "high", "xhigh", "max")
    )
    llm_payload = LLMConfigPayload(
        default_model=deepseek,
        providers=(
            LLMProviderPayload(
                name="openai_compat",
                base_url="http://127.0.0.1:1",
                models=(
                    LLMModelPayload(name=deepseek, reasoning=selectable),
                    LLMModelPayload(name=luna, reasoning=selectable),
                ),
            ),
        ),
    )
    reasoning_catalog = ModelReasoningCatalog(llm_payload)
    client = _SequentialWorkflowClient()
    workspace = tmp_path / "agent-a"
    workspace.mkdir()
    kernel = build_kernel(
        llm=LLMConfig.from_payload(llm_payload),
        can_use_tool=_allow_all,
        workspace_config_dirname=".nanoassistant",
        repo_root=tmp_path,
        workflow_subagent_model=luna,
        _llm_client_override=client,
    )
    catalog = LiveAgentCatalog(
        (
            AgentWorkspaceConfig(
                agent_id="agent-a",
                workspace_root=workspace,
                tool_allowlist=("Workflow",),
                default_model=luna,
                reasoning_effort="low",
            ),
        )
    )
    binder = GatewaySessionBinder(
        catalog=catalog,
        repository=SessionBindingStore(),
        kernel=kernel,
        reasoning_catalog=reasoning_catalog,
    )
    coordinator = SessionRunCoordinator(
        kernel=kernel,
        session_binder=binder,
        outbound_router=OutboundRouter(ChannelRegistry((_FakeChannel("web_relay"),))),
        group_context_store=GroupContextStore(tmp_path / "group.sqlite3"),
        product_default_model=deepseek,
        reasoning_catalog=reasoning_catalog,
    )
    session_id = ""
    try:
        for index, prompt in enumerate(("first Workflow", "second Workflow")):
            result = await coordinator.dispatch(
                _request(inbound(chat_id="chat-a", text=prompt), catalog)
            )
            session_id = result.kernel_session_id
            assert await asyncio.to_thread(client.child_started[index].wait, 3)
            client.child_release[index].set()
            await _wait_for_workflow_count(kernel, session_id, index + 1)
            await _wait_for_background_terminals(kernel, session_id, index + 1)

        child_requests = [
            request
            for request in client.requests
            if "Workflow" not in {tool.name for tool in request.tools}
        ]
        notification_requests = [
            request
            for request in client.requests
            if "<task-notification>" in _latest_user_text(request)
        ]

        assert len(child_requests) == 2
        assert len(notification_requests) == 2
        assert all(
            request.model == luna and request.reasoning_effort == "low"
            for request in (*child_requests, *notification_requests)
        )
        assert all(request.model != deepseek for request in client.requests)
    finally:
        for release in client.child_release:
            release.set()
        await kernel.aclose()


@pytest.mark.asyncio
async def test_terminal_observer_window_creates_one_fallback_run(
    tmp_path: Path,
) -> None:
    """Kernel-terminal/Gateway-active overlap must not create an orphan run."""

    workspace = tmp_path / "agent-a"
    workspace.mkdir()
    client = _CountingClient()
    kernel = build_kernel(
        llm=LLMConfig(
            provider="openai_compat",
            model="test-model",
            base_url="http://127.0.0.1:1",
        ),
        can_use_tool=_allow_all,
        workspace_config_dirname=".nanoassistant",
        repo_root=tmp_path,
        _llm_client_override=client,
    )
    terminal_seen = asyncio.Event()
    release_terminal = asyncio.Event()
    first_run_id: str | None = None

    async def _observer(event: dict[str, object]) -> None:
        nonlocal first_run_id
        if event.get("event") == "run_status" and not terminal_seen.is_set():
            first_run_id = str(event["run_id"])
            terminal_seen.set()
            await release_terminal.wait()

    catalog = LiveAgentCatalog(
        (AgentWorkspaceConfig(agent_id="agent-a", workspace_root=workspace),)
    )
    binder = GatewaySessionBinder(
        catalog=catalog,
        repository=SessionBindingStore(),
        kernel=kernel,
    )
    coordinator = SessionRunCoordinator(
        kernel=kernel,
        session_binder=binder,
        outbound_router=OutboundRouter(ChannelRegistry((_FakeChannel("web_relay"),))),
        group_context_store=GroupContextStore(tmp_path / "group.sqlite3"),
        kernel_event_observer=_observer,
    )
    try:
        first = asyncio.create_task(
            coordinator.dispatch(
                _request(inbound(chat_id="chat-a", text="first"), catalog)
            )
        )
        await asyncio.wait_for(terminal_seen.wait(), timeout=2)
        assert first_run_id is not None
        while kernel.get_run(first_run_id).status not in {
            "completed",
            "failed",
            "cancelled",
        }:
            await asyncio.sleep(0)
        second = asyncio.create_task(
            coordinator.dispatch(
                _request(inbound(chat_id="chat-a", text="second"), catalog)
            )
        )
        await asyncio.sleep(0)
        release_terminal.set()

        first_result, second_result = await asyncio.wait_for(
            asyncio.gather(first, second), timeout=3
        )

        assert first_result.run_id != second_result.run_id
        assert len(client.requests) == 2
        second_context = " ".join(
            str(message.content) for message in client.requests[-1].messages
        )
        assert second_context.count("second") == 1
    finally:
        release_terminal.set()
        await kernel.aclose()


@pytest.mark.asyncio
async def test_kernel_reconfigures_one_session_without_losing_transcript(
    tmp_path: Path,
) -> None:
    """A complete runtime replacement keeps the stable transcript address."""
    from agent.sdk import PromptSlots, PromptText, SessionRuntimeConfig

    workspace = tmp_path / "agent-a"
    workspace.mkdir()
    client = _CountingClient()
    kernel = build_kernel(
        llm=LLMConfig(
            provider="openai_compat",
            model="test-model",
            base_url="http://127.0.0.1:1",
        ),
        workspace_config_dirname=".nanoassistant",
        repo_root=tmp_path,
        _llm_client_override=client,
    )
    initial = SessionRuntimeConfig(
        model="model-a",
        prompt=PromptSlots(body=(PromptText(name="identity", text="old prompt"),)),
        skills=None,
        enabled_tools=[],
        features={},
        reasoning_effort="low",
        reasoning_effort_override="low",
    )
    replacement = SessionRuntimeConfig(
        model="model-b",
        prompt=PromptSlots(body=(PromptText(name="identity", text="new prompt"),)),
        skills=["research"],
        enabled_tools=["read"],
        features={"memory_curation": False},
        reasoning_effort="high",
        reasoning_effort_override="high",
        auto_mode_interaction="return_to_agent",
    )
    try:
        session = await kernel.create_session(
            workspace_root=workspace,
            runtime=initial,
        )
        created_runtime = await kernel.get_session_runtime(
            session_id=session.session_id,
            workspace_root=workspace,
        )
        first = kernel.submit(
            session_id=session.session_id,
            workspace_root=workspace,
            parts=[{"type": "text", "text": "remember this"}],
        )
        await _wait_for_terminal(kernel, first.run_id)

        changed = await kernel.reconfigure_session(
            session_id=session.session_id,
            workspace_root=workspace,
            runtime=replacement,
        )
        unchanged = await kernel.reconfigure_session(
            session_id=session.session_id,
            workspace_root=workspace,
            runtime=replacement,
        )
        current = await kernel.get_session_runtime(
            session_id=session.session_id,
            workspace_root=workspace,
        )
        second = kernel.submit(
            session_id=session.session_id,
            workspace_root=workspace,
            parts=[{"type": "text", "text": "what did I say?"}],
        )
        await _wait_for_terminal(kernel, second.run_id)

        assert created_runtime is not None
        assert created_runtime.runtime == initial
        assert changed.changed is True
        assert unchanged.changed is False
        assert unchanged.state == changed.state
        assert current is not None
        assert current.runtime == replacement
        assert changed.state == current
        assert client.requests[-1].model == "model-b"
        assert client.requests[0].reasoning_effort == "low"
        assert client.requests[-1].reasoning_effort == "high"
        assert any(
            message.content == "remember this"
            for message in client.requests[-1].messages
        )
    finally:
        await kernel.aclose()


@pytest.mark.asyncio
async def test_kernel_recovery_preserves_empty_feature_runtime_identity(
    tmp_path: Path,
) -> None:
    """A cold Kernel reconstructs the full runtime without collapsing {} into None."""
    from agent.sdk import PromptSlots, PromptText, SessionRuntimeConfig

    workspace = tmp_path / "agent-recovery"
    workspace.mkdir()
    runtime = SessionRuntimeConfig(
        model="model-a",
        prompt=PromptSlots(body=(PromptText(name="identity", text="persist me"),)),
        skills=None,
        enabled_tools=[],
        features={},
        reasoning_effort="high",
        reasoning_effort_override="high",
    )
    config = LLMConfig(
        provider="openai_compat",
        model="test-model",
        base_url="http://127.0.0.1:1",
    )
    first = build_kernel(
        llm=config,
        workspace_config_dirname=".nanoassistant",
        repo_root=tmp_path,
        _llm_client_override=_CountingClient(),
    )
    try:
        session = await first.create_session(workspace_root=workspace, runtime=runtime)
    finally:
        await first.aclose()

    recovered = build_kernel(
        llm=config,
        workspace_config_dirname=".nanoassistant",
        repo_root=tmp_path,
        _llm_client_override=_CountingClient(),
    )
    try:
        state = await recovered.get_session_runtime(
            session_id=session.session_id,
            workspace_root=workspace,
        )
        assert state is not None
        assert state.runtime == runtime
        assert state.identity == recovered.identify_runtime(runtime=runtime)
    finally:
        await recovered.aclose()


@pytest.mark.asyncio
async def test_kernel_fork_preserves_complete_runtime(tmp_path: Path) -> None:
    """A fork carries the source runtime, including explicit feature overrides."""
    from agent.sdk import PromptSlots, PromptText, SessionRuntimeConfig

    workspace = tmp_path / "agent-fork"
    workspace.mkdir()
    runtime = SessionRuntimeConfig(
        model="model-a",
        prompt=PromptSlots(body=(PromptText(name="identity", text="fork me"),)),
        skills=["research"],
        enabled_tools=["read"],
        features={"memory_curation": False},
        reasoning_effort="max",
        reasoning_effort_override="max",
    )
    kernel = build_kernel(
        llm=LLMConfig(
            provider="openai_compat",
            model="test-model",
            base_url="http://127.0.0.1:1",
        ),
        workspace_config_dirname=".nanoassistant",
        repo_root=tmp_path,
        _llm_client_override=_CountingClient(),
    )
    try:
        source = await kernel.create_session(workspace_root=workspace, runtime=runtime)
        fork = await kernel.fork_session(source.session_id, workspace_root=workspace)
        state = await kernel.get_session_runtime(
            session_id=fork.session_id,
            workspace_root=workspace,
        )

        assert state is not None
        assert state.runtime == runtime
    finally:
        await kernel.aclose()


async def _wait_for_terminal(kernel, run_id: str) -> None:
    while True:
        record = kernel.get_run(run_id)
        if record is not None and record.status in {"completed", "failed", "cancelled"}:
            return
        await asyncio.sleep(0)


@pytest.mark.asyncio
@pytest.mark.parametrize("skills", [[], None])
async def test_skill_catalog_freezes_until_compaction_and_manual_runtime_refresh(
    tmp_path: Path, skills: list[str] | None
) -> None:
    """SDK requests keep the catalog stable while files and allowlists evolve."""
    from dataclasses import replace
    from agent.sdk import PromptSlots, SessionRuntimeConfig

    client = _CountingClient()
    kernel = build_kernel(
        llm=LLMConfig(
            provider="openai_compat", model="test-model", base_url="http://127.0.0.1:1"
        ),
        workspace_config_dirname=".nanoassistant",
        repo_root=tmp_path,
        _llm_client_override=client,
    )
    runtime = SessionRuntimeConfig(
        model="test-model",
        prompt=PromptSlots(),
        skills=skills,
        enabled_tools=[],
        features={},
    )

    async def turn(session_id: str) -> str:
        run = kernel.submit(
            session_id=session_id,
            workspace_root=tmp_path,
            parts=[{"type": "text", "text": "Continue."}],
        )
        await _wait_for_terminal(kernel, run.run_id)
        assert kernel.get_run(run.run_id).status == "completed"
        return str(client.requests[-1].messages[0].content)

    try:
        session = await kernel.create_session(workspace_root=tmp_path, runtime=runtime)
        before = await turn(session.session_id)
        skill = tmp_path / ".nanoassistant/skills/new-review-skill/SKILL.md"
        skill.parent.mkdir(parents=True)
        skill.write_text(
            "---\nname: new-review-skill\ndescription: Newly learned workflow.\n---\nUse this workflow.\n"
        )
        if skills is not None:
            runtime = replace(runtime, skills=["new-review-skill"])
            await kernel.reconfigure_session(
                session_id=session.session_id,
                workspace_root=tmp_path,
                runtime=runtime,
                defer_skill_prompt_refresh=True,
            )
        assert await turn(session.session_id) == before
        fresh = await kernel.create_session(workspace_root=tmp_path, runtime=runtime)
        assert "new-review-skill" in await turn(fresh.session_id)
        await kernel.compact(session.session_id, workspace_root=tmp_path)
        assert "new-review-skill" in await turn(session.session_id)
        disabled = replace(runtime, skills=[])
        await kernel.reconfigure_session(
            session_id=session.session_id, workspace_root=tmp_path, runtime=disabled
        )
        assert "new-review-skill" not in await turn(session.session_id)
        await kernel.reconfigure_session(
            session_id=session.session_id,
            workspace_root=tmp_path,
            runtime=replace(runtime, skills=["new-review-skill"]),
        )
        assert "new-review-skill" in await turn(session.session_id)
        with pytest.raises(ValueError, match="only skill additions"):
            await kernel.reconfigure_session(
                session_id=session.session_id,
                workspace_root=tmp_path,
                runtime=replace(runtime, model="another-model"),
                defer_skill_prompt_refresh=True,
            )
    finally:
        await kernel.aclose()


@pytest.mark.asyncio
async def test_config_apply_admission_before_automatic_skill_patch_response(
    tmp_path: Path,
) -> None:
    """The first real config callback publication protects concurrent admission."""
    import json
    from dataclasses import replace

    import httpx

    from personal_assistant.channels.base import IMRelayIngress, InboundIngress
    from personal_assistant.config.local_store import (
        GatewayLifecycleConfig,
        HeartbeatConfig,
        LocalConfig,
        NodeConfig,
    )
    from personal_assistant.gateway.agent_config_sync import (
        IMAgentConfigSync,
        agent_operation_fingerprint,
    )
    from tests.unit.personal_assistant._config_operation_helpers import (
        _agent_payload,
        _llm,
    )

    workspace = tmp_path / "agent-a"
    workspace.mkdir()
    agent = AgentWorkspaceConfig(
        agent_id="agent-a",
        workspace_root=workspace,
        workspace_is_default=True,
        title="agent-a",
        skills=(),
        skills_selection_mode="explicit_allowlist",
        group_reply_policy="manual",
        default_model="test:model",
    )
    local_config = LocalConfig(
        node=NodeConfig(node_id="node-1"),
        agents=(agent,),
        channels=(),
        gateway=GatewayLifecycleConfig(),
        heartbeat=HeartbeatConfig(),
        im_service=None,
        llm=_llm(),
        source_path=tmp_path / "gateway.yaml",
    )
    client = _CountingClient()
    kernel = build_kernel(
        llm=LLMConfig.from_payload(local_config.llm),
        workspace_config_dirname=".nanoassistant",
        repo_root=tmp_path,
        _llm_client_override=client,
    )
    catalog = LiveAgentCatalog((agent,))
    store = SessionBindingStore()
    binder = GatewaySessionBinder(catalog=catalog, repository=store, kernel=kernel)
    coordinator = SessionRunCoordinator(
        kernel=kernel,
        session_binder=binder,
        node_id="node-1",
        outbound_router=OutboundRouter(ChannelRegistry((_FakeChannel("web_relay"),))),
        group_context_store=GroupContextStore(tmp_path / "group.sqlite3"),
    )
    published = threading.Event()
    release_response = threading.Event()
    initial_payload = {
        **_agent_payload(agent),
        "skills_selection_mode": "explicit_allowlist",
        "profile_version": 1,
    }

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET":
            return httpx.Response(200, json=initial_payload)
        assert request.method == "PATCH"
        body = json.loads(request.content)
        candidate = {**initial_payload, **body, "agent_id": agent.agent_id}
        result = sync.handle_agent_config_operation(
            "apply",
            {
                "operation_id": "automatic-skill-operation",
                "candidate_fingerprint": agent_operation_fingerprint(candidate),
                "expected_previous_fingerprint": agent_operation_fingerprint(
                    initial_payload
                ),
                "agent": candidate,
            },
        )
        assert result["status"] == "applied", result
        published.set()
        assert release_response.wait(5), "test did not release PATCH response"
        return httpx.Response(200, json={**candidate, "profile_version": 2})

    sync = IMAgentConfigSync(
        base_url="http://im.test",
        token=None,
        agent_catalog=catalog,
        session_binder=binder,
        local_config=local_config,
        client=httpx.Client(
            transport=httpx.MockTransport(handler), base_url="http://im.test"
        ),
    )

    async def dispatch(message_id: str) -> None:
        message = replace(
            inbound(chat_id="conversation-1", text=message_id),
            ingress=InboundIngress(
                im_relay=IMRelayIngress(
                    relay_task_id=message_id,
                    idempotency_key=message_id,
                    im_message_id=message_id,
                ),
            ),
        )
        await coordinator.dispatch(_request(message, catalog))

    sync_task = None
    try:
        await dispatch("before")
        before = client.requests[-1].messages[0].content
        skill_root = workspace / ".nanoassistant/skills"
        skill = skill_root / "new-review-skill/SKILL.md"
        skill.parent.mkdir(parents=True)
        skill.write_text(
            "---\nname: new-review-skill\ndescription: Newly learned workflow.\n---\nUse this workflow.\n"
        )
        sync_task = asyncio.create_task(
            asyncio.to_thread(
                sync.handle_skill_created,
                agent.agent_id,
                {
                    "name": "new-review-skill",
                    "scope": "agent",
                    "skill_root": str(skill_root),
                },
            )
        )
        assert await asyncio.to_thread(published.wait, 3)
        during_patch = catalog.require(agent.agent_id)
        assert not sync_task.done()
        await dispatch("during-patch")
        assert client.requests[-1].messages[0].content == before
        assert store.pending_boundaries() == ()
        assert during_patch.auto_enabled_skills == frozenset({"new-review-skill"})
    finally:
        release_response.set()
        if sync_task is not None:
            await asyncio.wait_for(sync_task, 3)
        sync.close()
        await kernel.aclose()
