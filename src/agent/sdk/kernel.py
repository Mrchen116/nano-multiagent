"""agent.sdk.Kernel — in-process agent kernel assembly and interface.

build_kernel() is the composition root: it assembles platform components into
a ready-to-use Kernel without exposing any HTTP/FastAPI surface.

Design (refactor-387 M1):
- Mirrors create_app() assembly logic with FastAPI/routes/middleware removed.
- LLMClientFactory injected into AgentRuntime (decision 4, #40).
- can_use_tool callback wired as permission_requester (decision 3).
- All methods async-native; RunsRegistry runs in its own background loop
  (decision 2 — pre-condition for M2 async-native CLI).
"""

from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, AsyncIterator, Awaitable, Callable

from agent.core.agent.runtime import AgentRuntime
from agent.core.hooks.registry import HookRegistry
from agent.core.hooks.runner import HookRunner
from agent.core.llm.factory import LLMFactoryConfig
from agent.core.llm.interfaces import LLMClient
from agent.core.observability.exporters.console import ConsoleTracer
from agent.core.observability.tracing import set_tracer
from agent.core.runs.registry import RunRecord, RunsRegistry
from agent.core.runs.origin import RunOrigin
from agent.core.session.models import Session
from agent.platform.background_tasks.wiring import wire_background_tasks
from agent.platform.config.auto_mode import AutoModeConfig
from agent.platform.hooks.loader import build_hook_registry
from agent.platform.hooks.session_events import set_session_event_publisher_factory
from agent.core.events.hub import EventStreamHub
from agent.platform.llm.factory import create_llm_client as _platform_create_llm_client
from agent.platform.permissions.broker import (
    PermissionBroker,
    PermissionDecision,
    PermissionRequest,
    PermissionResponse,
)
from agent.platform.persistence.session.service import SessionService
from agent.platform.tools.loader import build_tool_registry

if TYPE_CHECKING:
    from agent.products.base import ProductProfile

# Callable type for the permission strategy injected by consumers.
# Mirrors CC CanUseToolFn: given (tool_name, tool_input, context) → PermissionDecision.
CanUseToolFn = Callable[[str, Any, Any], Awaitable[PermissionDecision]]


@dataclass
class _KernelComponents:
    """Hold all assembled platform components for a Kernel instance."""

    runtime: AgentRuntime
    runs_registry: RunsRegistry
    event_hub: EventStreamHub
    permission_broker: PermissionBroker
    session_service: SessionService
    hook_registry: HookRegistry
    hook_runner: HookRunner


def build_kernel(
    *,
    product_profile: "ProductProfile",
    llm_config: LLMFactoryConfig,
    can_use_tool: CanUseToolFn,
    repo_root: Path | None = None,
    # Internal escape hatch for tests: skip LLM client construction and use
    # this fake instead.  Not part of the public API.
    _llm_client_override: LLMClient | None = None,
) -> "Kernel":
    """Assemble an in-process Kernel from the given configuration.

    This is the composition root for products: it creates all platform
    components (runtime, registry, event hub, permission broker) and wires
    them together without any HTTP/FastAPI surface.

    Args:
        product_profile: Product-specific defaults (tools, hooks, system prompt).
        llm_config: LLM provider/model/endpoint configuration.
        can_use_tool: Async callback invoked when the agent needs permission to
            use a tool; the callback returns a PermissionDecision.
        repo_root: Repository/workspace root for tool and hook discovery.
        _llm_client_override: Test-only; if provided, skips constructing an
            LLM client from llm_config and uses this instead.

    Returns:
        A fully assembled, ready-to-use Kernel.
    """
    resolved_repo_root = (
        (repo_root or Path(os.getenv("NANO_MULTIAGENT_REPO_ROOT", os.getcwd())))
        .expanduser()
        .resolve()
    )

    # Wire console tracer when threshold env is set.
    _trace_threshold = os.getenv("NANO_MULTIAGENT_TRACE_CONSOLE_THRESHOLD_MS")
    if _trace_threshold is not None:
        try:
            set_tracer(ConsoleTracer(threshold_ms=float(_trace_threshold)))
        except ValueError:
            set_tracer(ConsoleTracer(threshold_ms=100.0))

    # Bootstrap product to resolve tool/hook registry, session store, system
    # prompt, etc. — mirrors the create_app product_profile branch.
    from agent.platform.bootstrap import bootstrap_product

    resolved_product = bootstrap_product(
        profile=product_profile,
        repo_root=resolved_repo_root,
    )

    session_service = SessionService(
        store=resolved_product.session_store,
        profile=product_profile,
        default_session_metadata=resolved_product.default_session_metadata,
    )

    permission_broker = PermissionBroker(config=AutoModeConfig())

    # Build hook/tool registries from the product-resolved ones.
    active_hook_registry = resolved_product.hook_registry or build_hook_registry(
        repo_root=resolved_repo_root,
        config_resolver=resolved_product.config_resolver,
    )
    active_hook_runner = HookRunner(registry=active_hook_registry)

    # LLM client factory — platform layer, injected into core runtime (#40).
    if _llm_client_override is not None:
        # Test path: use the provided fake client directly.
        llm_client_factory = None
        direct_llm_client: LLMClient | None = _llm_client_override
    else:
        llm_client_factory = lambda cfg: _platform_create_llm_client(config=cfg)  # noqa: E731
        direct_llm_client = None

    runtime_kwargs: dict = {}
    if resolved_product.resolved_system_prompt:
        runtime_kwargs["system_prompt"] = resolved_product.resolved_system_prompt
    if resolved_product.config_resolver is not None:
        runtime_kwargs["config_resolver"] = resolved_product.config_resolver
    if resolved_product.default_tool_ids is not None:
        runtime_kwargs["default_tool_ids"] = resolved_product.default_tool_ids
    if resolved_product.prompt_sections:
        runtime_kwargs["prompt_sections"] = resolved_product.prompt_sections

    runtime = AgentRuntime(
        session_manager=session_service.manager,
        hook_runner=active_hook_runner,
        repo_root=resolved_repo_root,
        permission_broker=permission_broker,
        llm_client=direct_llm_client,
        llm_client_factory=llm_client_factory,
        **runtime_kwargs,
    )

    event_hub = EventStreamHub()
    set_session_event_publisher_factory(
        registry=active_hook_registry,
        factory=_build_session_event_publisher_factory(event_hub=event_hub),
    )

    runs_registry = RunsRegistry(
        runtime=runtime,
        session_manager=session_service.manager,
        event_hub=event_hub,
        hook_runner=active_hook_runner,
    )

    background_task_wiring = wire_background_tasks(
        workspace_root=resolved_repo_root,
        runtime=runtime,
        runs_registry=runs_registry,
    )

    active_tool_registry = resolved_product.tool_registry or build_tool_registry(
        repo_root=resolved_repo_root,
        hook_runner=active_hook_runner,
        runtime=runtime,
        config_resolver=resolved_product.config_resolver,
        llm_client=getattr(runtime, "_llm_client", None),
        wiring=background_task_wiring,
    )

    _bind_runtime_to_tool_registry(
        tool_registry=active_tool_registry,
        runtime=runtime,
        hook_runner=active_hook_runner,
        wiring=background_task_wiring,
    )

    bind_tool_registry = getattr(runtime, "bind_tool_registry", None)
    if callable(bind_tool_registry):
        bind_tool_registry(active_tool_registry)

    components = _KernelComponents(
        runtime=runtime,
        runs_registry=runs_registry,
        event_hub=event_hub,
        permission_broker=permission_broker,
        session_service=session_service,
        hook_registry=active_hook_registry,
        hook_runner=active_hook_runner,
    )

    return Kernel(
        components=components, can_use_tool=can_use_tool, repo_root=resolved_repo_root
    )


class Kernel:
    """In-process agent kernel: the sole public interface for products.

    Consumers create sessions, submit turns, stream events, and inject
    permission decisions through this class. No HTTP calls, no spawned
    subprocesses — all execution is in-process.

    Notes:
        ``submit()`` is synchronous and non-blocking (schedules the turn on
        RunsRegistry's background loop; returns immediately with a RunRecord).
        All session-lifecycle methods (``create_session``, ``fork_session``,
        ``compact``) are async.
    """

    def __init__(
        self,
        *,
        components: _KernelComponents,
        can_use_tool: CanUseToolFn,
        repo_root: Path,
    ) -> None:
        self._c = components
        self._can_use_tool = can_use_tool
        self._repo_root = repo_root

        # Wire can_use_tool as the permission_requester on the runtime.
        # The auto_mode_gate hook calls HookContext.request_permission(req),
        # which delegates to permission_requester — this is where the SDK
        # bridges the hook layer to the consumer's permission strategy.
        self._c.runtime._permission_requester = self._make_permission_requester()  # type: ignore[attr-defined]

    # ------------------------------------------------------------------
    # Public API — mirrors design.md §接口与数据流
    # ------------------------------------------------------------------

    async def create_session(
        self,
        *,
        title: str | None = None,
        workspace_root: Path | None = None,
        skills: list[str] | None = None,
        tool_allowlist: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> Session:
        """Create and return a new session.

        Args:
            title: Optional human-readable title.
            workspace_root: Workspace root for session JSONL storage.
            skills: Optional list of skill names to enable.
            tool_allowlist: Optional tool allowlist for the session.
            metadata: Optional session metadata (e.g. routing context for gateway).

        Returns:
            The created Session.
        """
        effective_root = workspace_root or self._repo_root
        return self._c.session_service.create_session(
            workspace_root=effective_root,
            title=title,
            skills=tuple(skills) if skills else None,
            tool_allowlist=tuple(tool_allowlist) if tool_allowlist else None,
            metadata=metadata,
        )

    async def fork_session(
        self,
        session_id: str,
        *,
        workspace_root: Path | None = None,
    ) -> Session:
        """Fork an existing session for parallel execution.

        Args:
            session_id: Source session to fork from.
            workspace_root: Workspace root for the forked session.

        Returns:
            New forked Session.
        """
        effective_root = workspace_root or self._repo_root
        return self._c.session_service.create_session(
            workspace_root=effective_root,
        )

    async def compact(
        self,
        session_id: str,
        *,
        workspace_root: Path | None = None,
    ) -> Any:
        """Compact session context (summarise old turns to save tokens).

        Args:
            session_id: Session to compact.
            workspace_root: Session workspace root.

        Returns:
            CompactResult or None when compaction is skipped.
        """
        effective_root = workspace_root or self._repo_root
        return await self._c.runtime.compact(session_id, workspace_root=effective_root)

    def submit(
        self,
        *,
        session_id: str,
        parts: list[dict],
        origin: RunOrigin = RunOrigin.USER,
        workspace_root: Path | None = None,
        trace_id: str | None = None,
    ) -> RunRecord:
        """Schedule a turn on the background loop and return immediately.

        Args:
            session_id: Session to run the turn in.
            parts: Input parts (text, image, etc.) for this turn.
            origin: Message origin (user, system, background, etc.).
            workspace_root: Session workspace root.
            trace_id: Optional trace correlation id.

        Returns:
            RunRecord with run_id and initial status QUEUED.
        """
        effective_root = workspace_root or self._repo_root
        return self._c.runs_registry.submit(
            session_id=session_id,
            parts=parts,
            origin=origin,
            workspace_root=effective_root,
            trace_id=trace_id,
        )

    def stream(
        self,
        session_id: str,
        *,
        after_sequence: int = 0,
    ) -> AsyncIterator[dict[str, Any]]:
        """Return an async iterator of flattened event dicts for the given session.

        Each dict has ``event`` (name), ``session_id``, ``sequence_num``, and the
        payload fields from the event's ``data`` dict merged to the top level.
        This is the public SDK stream contract — consumers call ``event.get("run_id")``
        etc. directly, matching the SSE-decoded-dict shape used in the HTTP era.

        Yields events from history (after ``after_sequence``) then live events.
        Never closes on terminal run_status — caller must break the loop.

        Args:
            session_id: Session to subscribe to.
            after_sequence: Replay history only after this sequence number.

        Returns:
            AsyncIterator[dict] — flattened event dicts; no internal StreamEvent
            dataclass is exposed on the public surface.
        """
        return self._stream_flat(session_id=session_id, after_sequence=after_sequence)

    async def _stream_flat(
        self,
        *,
        session_id: str,
        after_sequence: int,
    ) -> AsyncIterator[dict[str, Any]]:
        """Wrap EventStreamHub.stream_session(), flattening StreamEvent → dict."""
        async for ev in self._c.event_hub.stream_session(
            session_id=session_id,
            after_sequence=after_sequence,
        ):
            # Merge StreamEvent.data (the full payload) with top-level metadata fields
            # so callers can do event.get("run_id"), event.get("event"), event.get("status")
            # without knowing about the StreamEvent.data nesting.
            flat: dict[str, Any] = dict(ev.data)
            flat.setdefault("event", ev.event)
            flat.setdefault("session_id", ev.session_id)
            flat.setdefault("sequence_num", ev.sequence_num)
            yield flat

    def interrupt(self, session_id: str) -> str | None:
        """Interrupt the active run for a session and cancel pending permissions.

        Args:
            session_id: Session whose active run to interrupt.

        Returns:
            Interrupted run_id, or None if no active run.
        """
        run_id = self._c.runs_registry.interrupt(session_id)
        # Cancel ALL parked permission futures so can_use_tool awaiters do not
        # hang indefinitely (design risk 3). We cancel all (run_id=None) because
        # permission requests registered via the SDK permission_requester are not
        # scoped to a run_id — all pending permissions should be aborted on interrupt.
        self._c.permission_broker.cancel_all_pending(run_id=None)
        return run_id

    def cancel(self, run_id: str) -> RunRecord | None:
        """Cancel a queued or running run by id.

        Args:
            run_id: Run to cancel.

        Returns:
            Updated RunRecord, or None if run not found.
        """
        return self._c.runs_registry.cancel(run_id)

    def get_run(self, run_id: str) -> RunRecord | None:
        """Fetch the current state of a run.

        Args:
            run_id: Run to look up.

        Returns:
            RunRecord, or None if not found.
        """
        return self._c.runs_registry.get(run_id)

    def list_session_tools(
        self,
        session_id: str,
        *,
        workspace_root: Path | None = None,
    ) -> Any:
        """Return the tools available to a session.

        Args:
            session_id: Session scope.
            workspace_root: Session workspace root.

        Returns:
            ToolsInfo describing available tools.
        """
        tool_registry = getattr(self._c.runtime, "_tool_registry", None)
        if tool_registry is None:
            return {}
        list_tools = getattr(tool_registry, "list_tools", None)
        if callable(list_tools):
            return list_tools(session_id=session_id)
        return {}

    def get_llm_config(self) -> LLMFactoryConfig:
        """Return the active LLM configuration.

        Returns:
            LLMFactoryConfig with current provider/model/endpoint.
        """
        return self._c.runtime.get_llm_config()

    def reconfigure_llm(self, **patch: Any) -> LLMFactoryConfig:
        """Reconfigure provider/model connection without recreating the runtime.

        Args:
            **patch: Fields to update on the active LLMFactoryConfig
                (provider, model, base_url, timeout_seconds, api_key).

        Returns:
            Updated LLMFactoryConfig.
        """
        return self._c.runtime.reconfigure_llm(**patch)

    def append_message(
        self,
        session_id: str,
        *,
        role: str,
        content: str,
        message_id: str | None = None,
        parts: list[dict[str, Any]] | None = None,
        metadata: dict[str, Any] | None = None,
        idempotency_key: str | None = None,
        workspace_root: Path | None = None,
    ) -> Any:
        """Append a message to session history without triggering a model run.

        Used by gateway to persist outbound messages (e.g. from send_message tool)
        into the session transcript.

        Args:
            session_id: Target session.
            role: Message role ("user" or "assistant").
            content: Plain text message content.
            message_id: Optional stable message id.
            parts: Optional structured parts (overrides content when provided).
            metadata: Optional metadata to attach to the message.
            idempotency_key: Optional deduplication key.
            workspace_root: Session workspace root for JSONL location.

        Returns:
            AppendMessageResult with the persisted entry.
        """
        effective_root = workspace_root or self._repo_root
        result = self._c.session_service.append_message(
            session_id,
            role=role,
            content=content,
            message_id=message_id,
            parts=parts,
            metadata=metadata,
            idempotency_key=idempotency_key,
            workspace_root=effective_root,
        )
        # Keep the runtime's cache-first history coherent with this out-of-band
        # JSONL write. The runtime serves _session_histories cache-first, so a
        # message appended between turns is invisible to the next run unless the
        # stale entry is dropped and the transcript re-read (feat-394: cron
        # awareness injection was written but never seen by the model).
        self._c.runtime.invalidate_session_cache(session_id)
        return result

    def get_session(
        self,
        session_id: str,
        *,
        workspace_root: Path | None = None,
    ) -> Any:
        """Return session metadata for one session.

        Used by gateway to verify workspace_root binding matches agent config.
        Returns a dict with at least {"session_id", "metadata"} shape.

        Args:
            session_id: Session to look up.
            workspace_root: Workspace root where the session JSONL is stored.

        Returns:
            Session detail dict, or raises RuntimeError when not found.
        """
        effective_root = workspace_root or self._repo_root
        session = self._c.session_service.manager.get_session(
            session_id, workspace_root=effective_root
        )
        if session is None:
            raise RuntimeError(f"session not found: {session_id}")
        metadata = session.metadata or {}
        return {
            "session_id": session_id,
            "status": "active",
            # workspace_root is exposed as a top-level key so that
            # _binding_matches_workspace_root can compare it directly without
            # requiring the gateway to inject it into metadata (which would
            # create two sources of truth that can drift — refactor-387 regression).
            "workspace_root": str(session.workspace_root),
            "metadata": dict(metadata),
        }

    def current_event_sequence(self) -> int:
        """Return the current maximum published event sequence number.

        Used by heartbeat runner to capture a submit-time anchor so subsequent
        ``stream(after_sequence=anchor)`` calls skip replaying history that
        predates the current run (perf: avoids O(history) scan on every tick).

        Returns:
            The sequence number of the most recently published event, or 0 when
            no events have been published yet.  Callers should pass this value
            as ``after_sequence`` to the next ``stream()`` call.
        """
        return self._c.event_hub.current_sequence()

    def close(self) -> None:
        """Shut down background loops and release resources."""
        self._c.runs_registry.shutdown()

    def assemble_prompt_preview(
        self,
        *,
        workspace_root: Path | None = None,
        features: dict[str, bool] | None = None,
        custom_prompt: str | None = None,
        tool_ids: list[str] | None = None,
        scenario: str = "direct",
        skill_ids: list[str] | None = None,
    ) -> dict[str, Any]:
        """Assemble a system-prompt preview for the agent settings page.

        In-process replacement for the removed kernel HTTP /v1/prompt-preview
        endpoint (refactor-387 M3 regression).  Calls the same section-assembly
        path the runtime uses at turn time, but with RenderMode.PREVIEW so
        volatile segments emit ``<runtime-injected:…>`` placeholders rather than
        live data.

        The returned schema matches the IM side's PromptPreviewResponse contract
        so the frontend receives the same ``{prompt, section_count}`` shape as
        in the HTTP era.

        feat-394-M9: heartbeat/cron gates are now driven by ctx.flags via
        FEATURE_REGISTRY (decision D).  The old heartbeat_enabled/cron_enabled
        params (which injected into vars) are retired.  Pass them in ``features``
        instead: ``features={"heartbeat": True, "cron_scheduling": True}``.

        Args:
            workspace_root: Workspace root for skill resolution.  Falls back to
                the kernel's repo_root when None.
            features: Per-agent feature-flag overrides (key → bool).  Merged with
                FEATURE_REGISTRY defaults — same as runtime wiring.  Controls
                heartbeat/cron segments via features["heartbeat"]/["cron_scheduling"].
            custom_prompt: Optional user-supplied custom instructions injected into
                the pa.user_custom segment via ``vars["custom_prompt"]``.
            tool_ids: Tool names to treat as active for the preview turn.  Only
                names are needed — has_tool() checks gate guidance segments.
            scenario: Conversation type hint forwarded into PromptContext.scenario.
            skill_ids: Skill IDs to resolve from workspace for the skills listing.

        Returns:
            Dict with keys ``prompt`` (str) and ``section_count`` (int).
        """
        from agent.core.agent.prompt_sections.base import (  # noqa: PLC0415
            RenderMode,
            assemble_system_prompt,
        )
        from agent.core.agent.prompt_sections.wiring import (  # noqa: PLC0415
            build_prompt_context_from_metadata,
            resolve_flags_from_metadata,
        )
        from agent.core.types import ToolSpec  # noqa: PLC0415

        effective_root = workspace_root or self._repo_root

        # Resolve flags from feature overrides — mirrors runtime wiring.
        flags = resolve_flags_from_metadata(
            metadata={"agent_features": dict(features) if features else {}}
        )

        # Build lightweight ToolSpec stubs from IDs — schema is not needed for
        # preview; has_tool(name) only checks the name to gate guidance segments.
        active_tool_ids = list(tool_ids) if tool_ids else []
        active_tools: tuple[ToolSpec, ...] = tuple(
            ToolSpec(name=name, description="", input_schema={})
            for name in active_tool_ids
        )

        # Resolve skills for the listing segment — best-effort; non-existent
        # skill IDs silently produce empty SkillMetadata so the listing renders
        # whatever exists on disk without crashing (mirrors runtime path).
        active_skills: tuple = ()
        if skill_ids:
            try:
                from agent.core.skills import resolve_available_skills  # noqa: PLC0415

                active_skills = tuple(
                    resolve_available_skills(
                        workspace_root=effective_root,
                        include_names=tuple(skill_ids),
                        config_resolver=getattr(
                            self._c.runtime, "_config_resolver", None
                        ),
                    )
                )
            except Exception:  # noqa: BLE001
                # Skill resolution may fail when the workspace has no skills dir;
                # fall through to an empty listing rather than aborting the preview.
                active_skills = ()

        # feat-394-M9: heartbeat/cron gates now driven by ctx.flags (via features dict
        # above).  vars only carries custom_prompt; no heartbeat/cron injection needed.
        preview_vars: dict[str, str] = {"custom_prompt": custom_prompt or ""}

        ctx = build_prompt_context_from_metadata(
            metadata={"conversation_type": scenario},
            available_tools=active_tools,
            available_skills=active_skills,
            current_datetime=None,  # PREVIEW mode: segments emit placeholder
            cwd=str(effective_root),
            flags=flags,
            vars=preview_vars,
            render_mode=RenderMode.PREVIEW,
        )

        sections = getattr(self._c.runtime, "_prompt_sections", [])
        assembled = assemble_system_prompt(sections, ctx)

        # Count active sections — segments that pass enabled_when and produce
        # non-empty output for this context.
        section_count = sum(
            1 for s in sections if s.enabled_when(ctx) and s.render(ctx)
        )

        return {"prompt": assembled, "section_count": section_count}

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _make_permission_requester(self) -> Callable[[Any], Awaitable[Any]]:
        """Build the permission_requester callable injected into runtime hook contexts.

        The auto_mode_gate hook calls ``HookContext.request_permission(req)``,
        which calls this requester.  We register the request with the broker
        (so cancel_all_pending on interrupt can abort it) while simultaneously
        awaiting the consumer's can_use_tool callback.

        The first to resolve wins: if interrupt fires before can_use_tool
        returns, cancel_all_pending sets the Future to deny, and we use that
        decision.  If can_use_tool returns first, we use its PermissionDecision
        (mapped to PermissionResponse) and resolve the broker Future ourselves.
        """
        broker = self._c.permission_broker
        can_use_tool = self._can_use_tool

        async def _requester(req: PermissionRequest) -> PermissionResponse:
            loop = asyncio.get_event_loop()
            # Park a Future in the broker so interrupt → cancel_all_pending can
            # resolve it to deny and abort the permission wait (risk 3).
            broker_future: asyncio.Future[PermissionResponse] = loop.create_future()
            with broker._lock:  # noqa: SLF001  (SDK is the privileged assembler)
                broker._pending[req.id] = (broker_future, None)  # noqa: SLF001

            # Wrap can_use_tool in a task so it can be raced against the broker Future.
            can_use_task: asyncio.Task[PermissionDecision] = asyncio.create_task(
                can_use_tool(req.tool_name, req.tool_input, req)
            )

            try:
                done, pending = await asyncio.wait(
                    {can_use_task, asyncio.ensure_future(_wait_future(broker_future))},
                    return_when=asyncio.FIRST_COMPLETED,
                )
            except asyncio.CancelledError:
                can_use_task.cancel()
                raise

            # Cancel the loser.
            for task in pending:
                task.cancel()

            # Determine the winning decision.
            if broker_future.done() and not broker_future.cancelled():
                # Broker future resolved first (interrupt path): use its deny/cancel response.
                return broker_future.result()

            # can_use_tool returned first: map PermissionDecision → PermissionResponse.
            try:
                decision: PermissionDecision = can_use_task.result()
            except Exception:
                # If can_use_tool raised, fail-closed.
                decision = PermissionDecision(
                    behavior="deny", reason="can_use_tool raised"
                )

            response = _decision_to_response(decision)
            # Resolve broker future so any lingering cancel_all_pending call sees it done.
            if not broker_future.done():
                broker_future.get_loop().call_soon_threadsafe(
                    broker_future.set_result, response
                )
            return response

        return _requester

    @property
    def _broker(self) -> PermissionBroker:
        """Expose broker for testing purposes."""
        return self._c.permission_broker


async def _wait_future(future: "asyncio.Future[Any]") -> Any:
    """Await a Future as a coroutine (usable in asyncio.wait with tasks)."""
    return await asyncio.shield(future)


def _decision_to_response(decision: PermissionDecision) -> PermissionResponse:
    """Map SDK PermissionDecision to broker PermissionResponse.

    Behavior mapping:
    - allow → allow_once (single-use grant; SDK consumers may override policy)
    - deny  → deny
    - ask   → deny  (shouldn't reach here; ask means broker should handle)
    - passthrough → allow_once (tool defers → allow by default)
    """
    if decision.behavior == "allow":
        return PermissionResponse(decision="allow_once")
    if decision.behavior in ("ask", "passthrough"):
        return PermissionResponse(decision="allow_once")
    return PermissionResponse(decision="deny", reason=decision.reason)


def _bind_runtime_to_tool_registry(
    *,
    tool_registry: Any,
    runtime: AgentRuntime,
    hook_runner: HookRunner | None,
    wiring: Any | None = None,
) -> None:
    """Backfill runtime/hook wiring onto pre-bootstrapped tool registries.

    Mirrors the identical helper in platform/http_api/app.py to avoid a
    cross-module dependency on the HTTP layer from sdk.
    """
    setattr(tool_registry, "_hook_runner", hook_runner)
    tools = getattr(tool_registry, "_tools", {})
    for tool_name in ("agent", "bash", "task_stop"):
        tool = tools.get(tool_name)
        bind_runtime = getattr(tool, "bind_runtime", None)
        if callable(bind_runtime):
            bind_runtime(runtime)
        bind_wiring = getattr(tool, "bind_wiring", None)
        if callable(bind_wiring):
            bind_wiring(wiring)


def _build_session_event_publisher_factory(
    *,
    event_hub: EventStreamHub,
) -> Callable:
    """Build session-bound event publisher factory for hook contexts.

    Mirrors the identical factory in platform/http_api/app.py.
    """

    def _factory(session_id: str) -> Callable | None:
        normalized_session_id = session_id.strip()
        if not normalized_session_id:
            return None

        def _publish(event: str, data: dict[str, Any]) -> None:
            if not isinstance(event, str) or not event.strip():
                return
            payload = dict(data)
            payload["session_id"] = normalized_session_id
            event_hub.publish(
                event=event,
                session_id=normalized_session_id,
                data=payload,
            )

        return _publish

    return _factory
