"""Coalesce global Inbox signals without injecting conversation bodies into runs."""

from __future__ import annotations

import asyncio
from dataclasses import asdict
from datetime import datetime, timezone
import logging
from typing import Any, Mapping
from uuid import NAMESPACE_URL, uuid5

from agent.sdk import RunOrigin, TERMINAL_RUN_STATUSES
from personal_assistant.channels.base import InboundMessage
from personal_assistant.config.local_store import resolve_run_model
from personal_assistant.gateway.inbound_models import (
    PipelineResult,
    RelayLifecycleUpdate,
    RoutedInbound,
)
from personal_assistant.gateway.model_fallback import failover_unattended_run
from personal_assistant.gateway.runtime_delivery.stream import StreamRunOutcome
from personal_assistant.gateway.session_keys import build_reply_context

_log = logging.getLogger(__name__)


class GlobalRunCoordinator:
    """Own per-Agent wake admission, controls and recovery over public SDK calls.

    Args:
        kernel: Process-local SDK Kernel.
        kernel_client: Shared complete-runtime/model adapter.
        catalog: Live Agent config owner.
        binder: Durable main-session identity owner.
        inbox: Inbox service admitting channel messages.
        store: Durable signals and bindings.
        recorder: The sole global work-event observer.
        outbound_router: Existing channel control-feedback delivery.
        image_resolver: Existing bounded authenticated image materializer.
        sticky_store: Shared fallback model state keyed by main Session.
        product_default_model: Product default model.
        reasoning_catalog: Per-model effort catalog.
        time_context: Frozen Gateway timezone context.
        relay_lifecycle_callback: Existing ingress acceptance reporting.
    """

    def __init__(
        self,
        *,
        kernel: Any,
        kernel_client: Any,
        catalog: Any,
        binder: Any,
        inbox: Any,
        store: Any,
        recorder: Any,
        outbound_router: Any,
        image_resolver: Any,
        sticky_store: Any,
        product_default_model: str,
        reasoning_catalog: Any = None,
        time_context: Any = None,
        relay_lifecycle_callback: Any = None,
        bg_reply_sender: Any = None,
    ) -> None:
        self.kernel = kernel
        self.kernel_client = kernel_client
        self.catalog = catalog
        self.binder = binder
        self.inbox = inbox
        self.store = store
        self.recorder = recorder
        self.outbound_router = outbound_router
        self.image_resolver = image_resolver
        self.sticky_store = sticky_store
        self.product_default_model = product_default_model
        self.reasoning_catalog = reasoning_catalog
        self.time_context = time_context
        self.relay_lifecycle_callback = relay_lifecycle_callback
        self.bg_reply_sender = bg_reply_sender
        self._locks: dict[str, asyncio.Lock] = {}
        self._drains: dict[str, asyncio.Task] = {}
        self._again: set[str] = set()
        self._monitors: dict[str, asyncio.Task] = {}
        self._runs: dict[str, str] = {}
        self._retry_handles: dict[str, asyncio.TimerHandle] = {}
        self._retry_attempts: dict[str, int] = {}
        self._closed = False

    def start(self) -> None:
        """Recover retained signals after observation has been installed."""
        for agent in self.catalog.values_snapshot():
            if agent.config.work_mode == "global":
                self.notify(agent.agent_id)

    def seal(self) -> None:
        """Stop new admission and outstanding retry timers."""
        self._closed = True
        for handle in self._retry_handles.values():
            handle.cancel()
        self._retry_handles.clear()

    async def settle_admission(self, deadline: float) -> None:
        """Settle or cancel pending runtime/admission boundaries by one deadline."""
        tasks = list(self._drains.values())
        if tasks:
            _, pending = await asyncio.wait(
                tasks, timeout=max(0, deadline - asyncio.get_running_loop().time())
            )
            for task in pending:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)

    async def close(self, deadline: float) -> None:
        """Drain monitoring only after Kernel shutdown settles accepted runs."""
        self.seal()
        await self.settle_admission(deadline)
        tasks = list(self._monitors.values())
        for task in tasks:
            if not task.done():
                task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)

    def _lock(self, agent_id: str) -> asyncio.Lock:
        return self._locks.setdefault(agent_id, asyncio.Lock())

    async def resolve(self, agent: Any) -> Any:
        """Ensure main-session ownership is recorded before its first run."""
        binding = await self.binder.resolve_global(agent)
        self.recorder.register(
            agent_id=agent.agent_id,
            session_id=binding.kernel_session_id,
            scope="global_main",
            workspace_root=binding.workspace_root,
            description=agent.config.title,
        )
        return binding

    def notify(self, agent_id: str) -> None:
        """Schedule one drain on new input, actual idle or connection recovery."""
        if self._closed:
            return
        if agent_id in self._drains:
            self._again.add(agent_id)
            return
        if agent_id in self._retry_handles:
            return
        task = asyncio.create_task(
            self._drain(agent_id), name=f"global-inbox:{agent_id}"
        )
        self._drains[agent_id] = task
        task.add_done_callback(lambda done: self._drain_done(agent_id, done))

    def _drain_done(self, agent_id: str, task: asyncio.Task) -> None:
        self._drains.pop(agent_id, None)
        if task.cancelled():
            return
        error = task.exception()
        if error is None or self._closed:
            if not self._closed and agent_id in self._again:
                self._again.discard(agent_id)
                self.notify(agent_id)
            return
        self._schedule_retry(agent_id, error)

    def _schedule_retry(self, agent_id: str, error: Exception) -> None:
        if self._closed or agent_id in self._retry_handles:
            return
        attempt = self._retry_attempts.get(agent_id, 0)
        self._retry_attempts[agent_id] = attempt + 1
        delay = (1, 5, 30)[min(attempt, 2)]
        self.store.update_signal_state(
            agent_id,
            last_error=str(error),
            retry_at=datetime.fromtimestamp(
                datetime.now(timezone.utc).timestamp() + delay, timezone.utc
            ).isoformat(),
        )
        _log.warning(
            "global Inbox admission retry agent=%s delay=%s: %s", agent_id, delay, error
        )

        def retry() -> None:
            self._retry_handles.pop(agent_id, None)
            self.notify(agent_id)

        self._retry_handles[agent_id] = asyncio.get_running_loop().call_later(
            delay, retry
        )

    async def _drain(self, agent_id: str) -> None:
        async with self._lock(agent_id):
            if self._closed:
                return
            agent = self.catalog.require(agent_id)
            binding = await self.resolve(agent)
            session_id = binding.kernel_session_id
            state = self.store.get_signal_state(agent_id)
            pending_id = state["pending_submission_id"]
            if pending_id:
                receipt = self.kernel.get_submission_receipt(
                    session_id=session_id,
                    submission_id=pending_id,
                    workspace_root=binding.workspace_root,
                )
                if receipt and receipt.get("input_committed"):
                    self._confirm_signal(agent_id, state, pending_id)
                    state = self.store.get_signal_state(agent_id)
                elif receipt and receipt.get("status") in {"queued", "running"}:
                    return
            if session_id in self._monitors:
                return
            through = state["latest_signal_seq"]
            if through <= max(state["signaled_through_seq"], state["stop_through_seq"]):
                return
            scenario = {"agent_id": agent_id, "pa_work_scope": "global_main"}
            prepared = await self.kernel_client.ensure_agent_runtime(
                session_id=session_id,
                agent_snapshot=agent,
                workspace_root=binding.workspace_root,
                metadata=scenario,
                only_if_idle=True,
            )
            if not prepared:
                return
            if self._closed or not self.catalog.is_current(agent):
                return
            submission_id = f"inbox:{agent_id}:{through}"
            self.store.update_signal_state(
                agent_id,
                pending_submission_id=submission_id,
                pending_through_seq=through,
            )
            run = self.kernel.try_submit_idle(
                session_id=session_id,
                workspace_root=binding.workspace_root,
                submission_id=submission_id,
                origin=RunOrigin.HUMAN,
                revalidate_output=True,
                parts=[
                    {
                        "type": "text",
                        "text": (
                            "<system-reminder>\n"
                            "New messages have arrived in your Inbox. "
                            "This notification does not contain their contents. "
                            'Use inbox(action="check") to see which chats have unread messages, '
                            'then inbox(action="read", target=...) to read the relevant messages '
                            "before deciding what to do.\n"
                            "</system-reminder>"
                        ),
                    }
                ],
            )
            if run is None:
                return
            self._runs[agent_id] = run.run_id
            self.recorder.record(
                agent_id=agent_id,
                session_id=session_id,
                event_type="inbox_wake_admitted",
                event_id=f"wake:{run.run_id}",
                payload={
                    "submission_id": submission_id,
                    "through_seq": through,
                    "run_id": run.run_id,
                },
            )
            task = asyncio.create_task(
                self._monitor(agent, binding, run), name=f"global-work:{run.run_id}"
            )
            self._monitors[session_id] = task

    def _confirm_signal(
        self, agent_id: str, state: Mapping[str, Any], submission_id: str
    ) -> None:
        if state["pending_submission_id"] != submission_id:
            return
        self._retry_attempts.pop(agent_id, None)
        self.store.update_signal_state(
            agent_id,
            signaled_through_seq=max(
                state["signaled_through_seq"], state["pending_through_seq"]
            ),
            pending_submission_id=None,
            pending_through_seq=0,
            retry_at=None,
            last_error=None,
        )

    def observe_event(self, event: Mapping[str, Any]) -> None:
        """Handle lifecycle notifications outside the synchronous SDK callback."""
        owner = self.store.get_work_session(str(event.get("session_id") or ""))
        if not owner or owner["scope"] != "global_main":
            return
        agent_id = owner["root_agent_id"]
        kind = event.get("event")
        if kind == "turn_input_committed" and event.get("submission_id"):
            self._confirm_signal(
                agent_id,
                self.store.get_signal_state(agent_id),
                str(event["submission_id"]),
            )
        if kind == "session_idle":
            self.notify(agent_id)

    async def _consume(
        self,
        session_id: str,
        run_id: str,
        stream_anchor: int = 0,
        before_flush: Any = None,
    ) -> StreamRunOutcome:
        final_text = ""
        async for event in self.kernel.stream(session_id, after_sequence=stream_anchor):
            if event.get("run_id") != run_id:
                continue
            if event.get("event") == "assistant_message":
                final_text = str(event.get("content") or "")
            if (
                event.get("event") == "run_status"
                and event.get("status") in TERMINAL_RUN_STATUSES
            ):
                if before_flush is not None:
                    await before_flush()
                error = event.get("error") or {}
                return StreamRunOutcome(
                    status=str(event["status"]),
                    final_text=final_text,
                    delivery=None,
                    error=str(error) if error else None,
                    error_kind=error.get("kind")
                    if isinstance(error, Mapping)
                    else None,
                )
        raise RuntimeError("global run stream ended without terminal state")

    async def _monitor(self, agent: Any, binding: Any, run: Any) -> None:
        session_id = binding.kernel_session_id
        try:
            outcome = await self._consume(
                session_id, run.run_id, int(getattr(run, "start_sequence", 0) or 0)
            )
            if not self._closed:

                async def consume_replay(
                    *, run_id: str, stream_anchor: int, before_flush: Any
                ) -> StreamRunOutcome:
                    self._runs[agent.agent_id] = run_id
                    return await self._consume(
                        session_id, run_id, stream_anchor, before_flush
                    )

                async def notice(model: str) -> None:
                    self.recorder.record(
                        agent_id=agent.agent_id,
                        session_id=session_id,
                        event_type="model_fallback",
                        payload={
                            "model": model,
                            "run_id": self._runs.get(agent.agent_id),
                        },
                    )

                sticky = self.sticky_store.get(session_id)
                await failover_unattended_run(
                    kernel=self.kernel,
                    session_id=session_id,
                    workspace_root=binding.workspace_root,
                    agent_snapshot=agent,
                    sticky_store=self.sticky_store,
                    product_default=self.product_default_model,
                    reasoning_catalog=self.reasoning_catalog,
                    time_context=self.time_context,
                    current_model=sticky.model
                    if sticky
                    else resolve_run_model(
                        agent.config, product_default=self.product_default_model
                    ),
                    outcome=outcome,
                    origin=RunOrigin.HUMAN,
                    consume_replay=consume_replay,
                    deliver_notice=notice,
                    scenario={
                        "agent_id": agent.agent_id,
                        "pa_work_scope": "global_main",
                    },
                    revalidate_output=True,
                )
        except asyncio.CancelledError:
            raise
        except Exception:
            _log.exception("global run observation failed agent=%s", agent.agent_id)
        finally:
            self._monitors.pop(session_id, None)
            self._runs.pop(agent.agent_id, None)
            state = self.store.get_signal_state(agent.agent_id)
            pending = state["pending_submission_id"]
            receipt = (
                self.kernel.get_submission_receipt(
                    session_id=session_id,
                    submission_id=pending,
                    workspace_root=binding.workspace_root,
                )
                if pending
                else None
            )
            if pending and not (receipt and receipt.get("input_committed")):
                self._schedule_retry(
                    agent.agent_id, RuntimeError("run ended before input commit")
                )
            else:
                self.notify(agent.agent_id)

    async def receive(
        self,
        *,
        message: InboundMessage,
        agent: Any,
        shadow: Any,
        should_process: bool,
        sender_label: str,
        command: str | None = None,
        focus: str | None = None,
        operation_id: str | None = None,
    ) -> PipelineResult:
        """Persist channel input before acceptance, or apply a scoped control."""
        if self._closed:
            raise RuntimeError("Gateway is shutting down")
        async with self._lock(agent.agent_id):
            binding = await self.resolve(agent)
            if command:
                result = await self._control(
                    message, agent, binding, command, focus, operation_id
                )
                if self.relay_lifecycle_callback is not None:
                    for phase in ("accepted", "completed"):
                        await self.relay_lifecycle_callback(
                            RoutedInbound(message=message, shadow=shadow),
                            RelayLifecycleUpdate(
                                phase=phase,
                                agent_id=agent.agent_id,
                                session_key=f"global:{agent.agent_id}",
                            ),
                        )
                return result
            relay = message.ingress.im_relay
            external = message.ingress.external_event
            if relay:
                source_id = relay.im_message_id
                ingress_key = f"im:{source_id or relay.idempotency_key}"
            elif external:
                source_id = external.provider_event_id
                ingress_key = f"external:{external.connector_account_id}:{source_id}"
            else:
                source_id = message.metadata.get("message_id")
                if not source_id:
                    raise ValueError(
                        "global Inbox requires a stable ingress message identity"
                    )
                ingress_key = f"{message.channel_name}:{source_id}"
            conversation_id = (
                shadow.ref.conversation_id
                if shadow.ref
                else (message.external_chat_id if relay else None)
            )
            local_key = (
                f"{message.channel_name}:{message.external_chat_id}:{agent.agent_id}"
            )
            target = conversation_id or f"local:{uuid5(NAMESPACE_URL, local_key)}"
            reply = build_reply_context(message)
            reply_payload = asdict(reply)
            if shadow.saga_id:
                reply_payload["metadata"]["global_shadow_saga_id"] = shadow.saga_id
            content = await self._content(message)
            reasons = []
            if not message.is_group:
                reasons.append("direct")
            if agent.agent_id in (message.metadata.get("mentioned_agent_ids") or []):
                reasons.append("mention")
            if message.metadata.get("reply_to_agent_id") == agent.agent_id:
                reasons.append("reply")
            if should_process and not reasons:
                reasons.append("group_policy")
            async with self.inbox.target_lock(agent.agent_id, target):
                self.inbox.receive(
                    agent_id=agent.agent_id,
                    target=target,
                    ingress_key=ingress_key,
                    source_message_id=source_id,
                    sender={
                        "id": message.metadata.get("sender_agent_id")
                        or message.external_user_id,
                        "name": sender_label,
                        "kind": message.metadata.get("sender_type", "user"),
                    },
                    content=content,
                    channel=message.channel_name,
                    kind="group" if message.is_group else "direct",
                    name=str(
                        message.metadata.get("conversation_title")
                        or message.metadata.get("chat_name")
                        or target
                    ),
                    conversation_id=conversation_id,
                    reply_context=reply_payload,
                    source_time=message.source_timestamp.isoformat()
                    if message.source_timestamp
                    else None,
                    attention_reasons=reasons,
                    should_process=should_process,
                    normal_live_input=not any(
                        message.metadata.get(key) is True
                        for key in ("sync_only", "history_catchup")
                    ),
                    self_echo=message.metadata.get("sender_agent_id") == agent.agent_id
                    or message.external_user_id == agent.agent_id
                    or message.metadata.get("self_echo") is True,
                )
        if self.relay_lifecycle_callback is not None:
            for phase in ("accepted", "completed"):
                await self.relay_lifecycle_callback(
                    RoutedInbound(message=message, shadow=shadow),
                    RelayLifecycleUpdate(
                        phase=phase,
                        agent_id=agent.agent_id,
                        session_key=f"global:{agent.agent_id}",
                        kernel_session_id=binding.kernel_session_id,
                    ),
                )
        self.notify(agent.agent_id)
        return PipelineResult(
            agent.agent_id,
            f"global:{agent.agent_id}",
            binding.kernel_session_id,
            "",
            "",
            None,
        )

    async def _content(self, message: InboundMessage) -> list[dict[str, Any]]:
        parts = [{"type": "text", "text": message.text}]
        input_parts = message.metadata.get("kernel_input_parts")
        images = [
            dict(part)
            for part in input_parts or []
            if isinstance(part, Mapping) and part.get("type") == "image"
        ]
        if not images:
            for attachment in message.metadata.get("attachments") or []:
                if not isinstance(attachment, Mapping):
                    continue
                mime = str(attachment.get("content_type") or "")
                if mime and not mime.startswith("image/"):
                    continue
                resolution = await self.image_resolver.resolve([dict(attachment)])
                if resolution.failure:
                    parts.append(
                        {
                            "type": "image",
                            "attachment": dict(attachment),
                            "error": resolution.failure,
                        }
                    )
                else:
                    images.extend(resolution.parts)
        for part in images:
            if part.get("source"):
                parts.append(part)
                continue
            url = str(part.get("image_url") or "")
            if url.startswith("data:"):
                header, _, data = url.partition(",")
                parts.append(
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": header[5:].split(";")[0],
                            "data": data,
                        },
                    }
                )
            elif url:
                parts.append({"type": "image", "source": {"type": "url", "url": url}})
        for attachment in message.metadata.get("attachments") or []:
            if isinstance(attachment, Mapping) and not str(
                attachment.get("content_type") or ""
            ).startswith("image/"):
                parts.append({"type": "attachment", **dict(attachment)})
        return parts

    async def _control(
        self,
        message: InboundMessage,
        agent: Any,
        binding: Any,
        command: str,
        focus: str | None,
        operation_id: str | None,
    ) -> PipelineResult:
        event_id = (
            f"control:{agent.agent_id}:{operation_id}:{command}"
            if operation_id
            else None
        )
        prior = self.store.get_work_event(event_id) if event_id else None
        if prior is not None:
            text = prior["payload"]["text"]
        elif command == "new":
            text = (
                "全局 Agent 使用持续主会话，不支持 /new。可使用 /compact 压缩上下文。"
            )
        elif command == "stop":
            state = self.store.get_signal_state(agent.agent_id)
            self.store.update_signal_state(
                agent.agent_id, stop_through_seq=state["latest_signal_seq"]
            )
            run_id = self._runs.get(agent.agent_id)
            if run_id:
                self.kernel.cancel(run_id)
            self.kernel.interrupt(binding.kernel_session_id)
            text = "已停止全局 Agent 当前执行，Inbox 消息仍保留。"
        elif command == "compact":
            await self.kernel.compact(
                binding.kernel_session_id,
                workspace_root=binding.workspace_root,
                focus=focus,
                idempotency_key=operation_id,
            )
            text = "已压缩全局 Agent 主会话上下文。"
        else:
            raise ValueError(f"unsupported global control: {command}")
        self.recorder.record(
            agent_id=agent.agent_id,
            session_id=binding.kernel_session_id,
            event_type="control_result",
            event_id=event_id,
            payload={
                "command": command,
                "text": text,
                "source_conversation_id": message.external_chat_id,
            },
        )
        outbound = None
        if self.bg_reply_sender is not None:
            from personal_assistant.gateway.session_run_coordinator import (
                _control_ack_from_session_id,
            )

            from_session_id = _control_ack_from_session_id(
                agent_id=agent.agent_id,
                kernel_session_id=binding.kernel_session_id,
                ack_tag=command,
                source_message=message,
                operation_id=operation_id,
            )
            await self.bg_reply_sender(
                text, build_reply_context(message), from_session_id
            )
        else:
            outbound = await self.outbound_router.send_text_async(
                text=text, reply_context=build_reply_context(message)
            )
        return PipelineResult(
            agent.agent_id,
            f"global:{agent.agent_id}",
            binding.kernel_session_id,
            "",
            text,
            outbound,
        )
