"""Adapt the in-process Kernel to legacy Gateway consumer protocols."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from personal_assistant.config.local_store import resolve_model_candidates, resolve_run_model
from personal_assistant.config.model_reasoning import ModelReasoningCatalog
from personal_assistant.gateway.agent_catalog import LiveAgentCatalog, LiveAgentSnapshot
from personal_assistant.gateway.session_binder import GatewaySessionBinder
from personal_assistant.gateway.session_composition import (
    project_agent_runtime,
    project_agent_session_capabilities,
)
from personal_assistant.gateway.human_message_context import PaTimeContext
from personal_assistant.gateway.model_fallback import ModelStickyStore

if TYPE_CHECKING:
    from agent.sdk import Kernel


class InProcessKernelClient:
    """Adapt agent.sdk.Kernel to the kernel_client protocol.

    HeartbeatScheduler and InternalDispatchHandler use the old kernel_client
    interface (create_session/submit_message/append_message).  This adapter bridges them to the in-process Kernel SDK.

    create_session is async so it can be properly awaited from the gateway's
    async event loop — run_until_complete on an already-running loop raises
    RuntimeError (refactor-387 M4 fix; previously the adapter used that approach
    which silently prevented all heartbeat/cron runs from being submitted).
    """

    def __init__(
        self,
        kernel: "Kernel",
        *,
        agent_catalog: LiveAgentCatalog | None = None,
        session_binder: GatewaySessionBinder | None = None,
        product_default_model: str | None = None,
        reasoning_catalog: ModelReasoningCatalog | None = None,
        time_context: PaTimeContext | None = None,
        sticky_store: ModelStickyStore | None = None,
    ) -> None:
        self._kernel = kernel
        # refactor-406-M1 R6: per-agent config for building PromptSlots at
        # session-open (决策 8).  heartbeat/cron sessions look up the agent by
        # metadata["agent_id"] and assemble the PA prompt via prompt_for.
        self._agent_catalog = agent_catalog
        self._session_binder = session_binder
        # bugfix-429 决策2: product default model for the heartbeat/cron path.
        # Callers pass the agent's selected model (may be None); the adapter falls
        # back to this so unattended runs use the same default as user turns.
        self._product_default_model = product_default_model
        self._reasoning_catalog = reasoning_catalog
        self._time_context = time_context
        self._sticky_store = sticky_store or ModelStickyStore()

    async def create_session(
        self,
        *,
        workspace_root: str,
        product_id: str,
        title: str | None = None,
        metadata: dict[str, object] | None = None,
        agent_snapshot: LiveAgentSnapshot | None = None,
    ) -> dict[str, object]:
        prompt = None
        enabled_tools = None
        features = None
        skills = None
        runtime = None
        agent_id = (metadata or {}).get("agent_id")
        snapshot = agent_snapshot
        if snapshot is None:
            snapshot = (
                self._agent_catalog.get(agent_id)
                if self._agent_catalog is not None and isinstance(agent_id, str)
                else None
            )
        if snapshot is not None:
            model = self._first_candidate(snapshot, session_id=None)
            chain_head = resolve_run_model(
                snapshot.config, product_default=self._product_default_model
            )
            if model is not None:
                runtime = project_agent_runtime(
                    snapshot,
                    scenario=metadata or {},
                    resolved_model=model,
                    reasoning_catalog=self._reasoning_catalog,
                    time_context=self._time_context,
                    apply_saved_reasoning=chain_head is None or model == chain_head,
                ).runtime
            else:
                capabilities = project_agent_session_capabilities(
                    snapshot,
                    scenario=metadata or {},
                    time_context=self._time_context,
                )
                prompt = capabilities.prompt
                enabled_tools = capabilities.enabled_tools
                features = capabilities.features
                skills = capabilities.skills
        session = await self._kernel.create_session(
            title=title,
            workspace_root=Path(workspace_root),
            metadata=metadata,
            runtime=runtime,
            prompt=prompt,
            skills=skills,
            enabled_tools=enabled_tools,
            features=features,
        )
        if snapshot is not None and self._session_binder is not None:
            self._session_binder.register_session_provenance(
                snapshot,
                kernel_session_id=session.session_id,
            )
        return {"session_id": session.session_id}

    async def create_agent_session(
        self,
        *,
        agent_snapshot: LiveAgentSnapshot,
        workspace_root: str,
        product_id: str,
        title: str | None = None,
        metadata: dict[str, object] | None = None,
    ) -> dict[str, object]:
        """Create an unattended session from one captured Agent revision."""

        return await self.create_session(
            workspace_root=workspace_root,
            product_id=product_id,
            title=title,
            metadata=metadata,
            agent_snapshot=agent_snapshot,
        )

    async def ensure_agent_runtime(
        self,
        *,
        session_id: str,
        agent_snapshot: LiveAgentSnapshot,
        workspace_root: str,
        metadata: dict[str, object] | None = None,
    ) -> None:
        """Align a reused unattended session before its next background run."""

        model = self._first_candidate(agent_snapshot, session_id=session_id)
        if model is None:
            return
        chain_head = resolve_run_model(
            agent_snapshot.config, product_default=self._product_default_model
        )
        runtime = project_agent_runtime(
            agent_snapshot,
            scenario=metadata or {"agent_id": agent_snapshot.agent_id},
            resolved_model=model,
            reasoning_catalog=self._reasoning_catalog,
            time_context=self._time_context,
            apply_saved_reasoning=chain_head is None or model == chain_head,
        ).runtime
        desired = self._kernel.identify_runtime(runtime=runtime)
        current = await self._kernel.get_session_runtime(
            session_id=session_id,
            workspace_root=Path(workspace_root),
        )
        if (
            current is None
            or current.identity.fingerprint_schema != desired.fingerprint_schema
            or current.identity.runtime_fingerprint != desired.runtime_fingerprint
        ):
            await self._kernel.reconfigure_session(
                session_id=session_id,
                workspace_root=Path(workspace_root),
                runtime=runtime,
            )

    def submit_message(
        self,
        *,
        session_id: str,
        texts: list[str],
        image_urls: list[dict[str, object]] | None = None,
        workspace_root: str | None = None,
        origin: str | None = None,
        model: str | None = None,
        agent_id: str | None = None,
        **_kwargs: object,
    ) -> dict[str, object]:
        from agent.sdk import RunOrigin as _RunOrigin  # refactor-387-M4

        parts: list[dict] = [{"type": "text", "text": t} for t in texts]
        for img in image_urls or []:
            url = img.get("url")
            if isinstance(url, str) and url.strip():
                img_part: dict = {"type": "image", "image_url": url.strip()}
                mime = img.get("content_type")
                if isinstance(mime, str) and mime.strip():
                    img_part["mime_type"] = mime.strip()
                parts.append(img_part)
        # Map string origin → RunOrigin enum.
        # feat-394-M7 R5-1 fix: cron is an unattended isolated origin (no user present);
        # RunOrigin.SYSTEM does not exist — use per-origin explicit mapping.
        if origin == "heartbeat":
            run_origin: _RunOrigin = _RunOrigin.HEARTBEAT
        elif origin == "cron":
            run_origin = _RunOrigin.CRON
        else:
            run_origin = _RunOrigin.USER
        # 心跳/cron 必须显式传入 candidates[0]。shim 无论是否传 model 都会
        # 再走 resolve_run_model；省略会把备用粘性打回链头。内核不持备用链。
        snapshot = (
            self._agent_catalog.get(agent_id)
            if self._agent_catalog is not None and isinstance(agent_id, str)
            else None
        )
        resolved_agent = snapshot.config if snapshot is not None else None
        resolved_model = resolve_run_model(
            resolved_agent,
            product_default=self._product_default_model,
            explicit=model,
        )
        run_record = self._kernel.submit(
            session_id=session_id,
            parts=parts,
            origin=run_origin,
            workspace_root=Path(workspace_root) if workspace_root else None,
            model=resolved_model,
        )
        return {"run_id": run_record.run_id, "anchor_sequence": 0, "status": "queued"}

    def _first_candidate(
        self, snapshot: LiveAgentSnapshot, *, session_id: str | None
    ) -> str | None:
        sticky = self._sticky_store.get(session_id)
        candidates = resolve_model_candidates(
            snapshot.config,
            product_default=self._product_default_model,
            sticky=sticky.model if sticky is not None else None,
        )
        return candidates[0] if candidates else None

    def admit_model(self, *, agent_id: str, session_id: str | None) -> str | None:
        """Return the first candidate that heartbeat/cron must pass to submit_message."""

        if self._agent_catalog is None:
            return None
        snapshot = self._agent_catalog.get(agent_id)
        if snapshot is None:
            return None
        return self._first_candidate(snapshot, session_id=session_id)

    def current_event_sequence(self) -> int:
        """Return the kernel's current max event sequence for use as a stream anchor.

        Delegated to Kernel.current_event_sequence() which reads the EventStreamHub
        without requiring access to agent.core internals.
        """
        return self._kernel.current_event_sequence()

    def append_message(
        self,
        *,
        session_id: str,
        role: str,
        content: str,
        message_id: str | None = None,
        workspace_root: str | None = None,
        idempotency_key: str | None = None,
        metadata: dict[str, object] | None = None,
        **_kwargs: object,
    ) -> dict[str, object]:
        self._kernel.append_message(
            session_id,
            role=role,
            content=content,
            message_id=message_id,
            workspace_root=Path(workspace_root) if workspace_root else None,
            idempotency_key=idempotency_key,
            metadata=metadata,
        )
        return {"status": "appended"}

    def get_session(
        self, *, session_id: str, workspace_root: str | None = None
    ) -> dict[str, object]:
        return self._kernel.get_session(
            session_id,
            workspace_root=Path(workspace_root) if workspace_root else None,
        )

    def close(self) -> None:
        pass
