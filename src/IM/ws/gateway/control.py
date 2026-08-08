from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from uuid import uuid4


from .protocol import (
    _require_dict,
    _require_text,
)

_logger = logging.getLogger(__name__)

from .sessions import GatewaySessions


def _config_operation_result(
    *,
    payload: dict[str, object],
    expected_operation_id: str,
    expected_candidate_fingerprint: str,
) -> dict[str, object]:
    """Validate and copy one correlated Gateway config operation result."""
    operation_id = _require_text(payload.get("operation_id"), field_name="operation_id")
    if operation_id != expected_operation_id:
        raise ValueError("operation_id does not match request")
    result_status = _require_text(payload.get("status"), field_name="status")
    if result_status not in {"applied", "rejected", "pending"}:
        raise ValueError("status must be applied, rejected, or pending")
    agent = payload.get("agent")
    if result_status == "applied" and not isinstance(agent, dict):
        raise ValueError("applied result requires an agent object")
    if agent is not None and not isinstance(agent, dict):
        raise ValueError("agent must be an object when provided")
    fingerprint = payload.get("candidate_fingerprint")
    if result_status != "pending" or fingerprint is not None:
        fingerprint = _require_text(fingerprint, field_name="candidate_fingerprint")
        if fingerprint != expected_candidate_fingerprint:
            raise ValueError("candidate_fingerprint does not match request")
    return dict(payload)


@dataclass(frozen=True, slots=True)
class SessionLogResolution:
    """Describe whether a Gateway could make a transcript available now."""

    source_jsonl_path: str | None
    status: str


class GatewayControl:
    """Own Gateway control RPC request/result correlation and waiters."""

    def __init__(self, *, sessions: GatewaySessions, lock: asyncio.Lock) -> None:
        self._sessions = sessions
        self._lock = lock
        self._agent_config_waiters = {}
        self._agent_create_waiters = {}
        self._agent_config_apply_waiters = {}
        self._agent_config_operation_status_waiters = {}
        self._agent_capabilities_waiters = {}
        self._node_capabilities_waiters = {}
        self._prompt_preview_waiters = {}
        self._node_prompt_preview_waiters = {}
        self._heartbeat_md_waiters = {}
        self._cron_jobs_waiters = {}
        self._cron_delete_waiters = {}
        self._skills_usage_waiters = {}
        self._session_fork_waiters = {}
        self._config_operation_locks: dict[str, asyncio.Lock] = {}
        self._session_log_waiters = {}

    async def config_operation_lock(self, *, agent_id: str) -> asyncio.Lock:
        """Return the app-scoped serialization lock for one Agent config mutation."""
        async with self._lock:
            lock = self._config_operation_locks.get(agent_id)
            if lock is None:
                lock = asyncio.Lock()
                self._config_operation_locks[agent_id] = lock
            return lock

    async def push_heartbeat_trigger(
        self, *, target_node_id: str, agent_id: str, reason: str
    ) -> bool:
        """Push one heartbeat.trigger notification to a connected gateway node."""
        return await self._sessions.send(
            target_node_id=target_node_id,
            message_type="heartbeat.trigger",
            payload={"agent_id": agent_id, "reason": reason},
        )

    async def push_permission_response(
        self,
        *,
        target_node_id: str,
        message_id: str,
        request_id: str,
        decision: str,
        reason: str | None = None,
    ) -> bool:
        """Push a permission_response frame to the gateway node hosting the parked run.

        The PA side consumes this frame and forwards the decision to the agent inbound
        endpoint so the parked hook can resume.

        Args:
            target_node_id: Node that owns the agent run awaiting the decision.
            message_id: Agent message that embeds the permission request.
            request_id: Stable permission request identifier.
            decision: User-chosen option (e.g. ``"allow_once"``, ``"deny"``).
            reason: feat-440-M1 — optional free-text deny reason. Normalized to ""
                here (single normalization point) so old callers / allow decisions
                produce a stable frame and PermissionResponse.reason ends up empty.

        Returns:
            ``True`` when the node was connected and the frame was sent.
        """
        return await self._sessions.send(
            target_node_id=target_node_id,
            message_type="node.streaming_delta",
            payload={
                "kind": "permission_response",
                "message_id": message_id,
                "request_id": request_id,
                "decision": decision,
                "reason": reason or "",
            },
        )

    async def push_config_sync(
        self, *, target_node_id: str, agent_id: str, profile_version: int
    ) -> bool:
        """Push one config.sync notification to a connected gateway node."""
        return await self._sessions.send(
            target_node_id=target_node_id,
            message_type="config.sync",
            payload={"agent_id": agent_id, "profile_version": profile_version},
        )

    async def request_agent_config(
        self,
        *,
        target_node_id: str,
        agent_id: str,
        timeout_seconds: float = 5.0,
    ) -> dict[str, object] | None:
        """Request one live agent config snapshot from a connected gateway node."""
        request_id = f"agent-config-{uuid4().hex}"
        loop = asyncio.get_running_loop()
        waiter: asyncio.Future[dict[str, object] | None] = loop.create_future()
        async with self._lock:
            self._agent_config_waiters[request_id] = waiter
        try:
            pushed = await self._sessions.send(
                target_node_id=target_node_id,
                message_type="agent.config.get",
                payload={"request_id": request_id, "agent_id": agent_id},
            )
            if not pushed:
                return None
            return await asyncio.wait_for(waiter, timeout=timeout_seconds)
        except asyncio.TimeoutError:
            return None
        finally:
            async with self._lock:
                self._agent_config_waiters.pop(request_id, None)

    async def request_agent_create(
        self,
        *,
        target_node_id: str,
        payload: dict[str, object],
        operation_id: str | None = None,
        candidate_fingerprint: str | None = None,
        timeout_seconds: float = 5.0,
    ) -> dict[str, object] | None:
        """Request Gateway creation, optionally using the durable operation protocol."""
        request_id = f"agent-create-{uuid4().hex}"
        loop = asyncio.get_running_loop()
        waiter: asyncio.Future[dict[str, object] | None] = loop.create_future()
        async with self._lock:
            self._agent_create_waiters[request_id] = (
                operation_id,
                candidate_fingerprint,
                waiter,
            )
        request_payload: dict[str, object] = {
            "request_id": request_id,
            "agent": dict(payload),
        }
        if operation_id is not None:
            request_payload.update(
                {
                    "operation_id": operation_id,
                    "candidate_fingerprint": candidate_fingerprint or "",
                    "expected_previous_fingerprint": None,
                }
            )
        try:
            pushed = await self._sessions.send(
                target_node_id=target_node_id,
                message_type="agent.create",
                payload=request_payload,
            )
            if not pushed:
                return None
            return await asyncio.wait_for(waiter, timeout=timeout_seconds)
        except asyncio.TimeoutError:
            return None
        finally:
            async with self._lock:
                self._agent_create_waiters.pop(request_id, None)

    async def request_agent_config_apply(
        self,
        *,
        target_node_id: str,
        operation_id: str,
        candidate_fingerprint: str,
        expected_previous_fingerprint: str,
        payload: dict[str, object],
        timeout_seconds: float = 5.0,
    ) -> dict[str, object] | None:
        """Apply a complete Agent config and await its terminal Gateway result."""
        request_id = f"agent-config-apply-{uuid4().hex}"
        loop = asyncio.get_running_loop()
        waiter: asyncio.Future[dict[str, object] | None] = loop.create_future()
        async with self._lock:
            self._agent_config_apply_waiters[request_id] = (
                operation_id,
                candidate_fingerprint,
                waiter,
            )
        try:
            pushed = await self._sessions.send(
                target_node_id=target_node_id,
                message_type="agent.config.apply",
                payload={
                    "request_id": request_id,
                    "operation_id": operation_id,
                    "candidate_fingerprint": candidate_fingerprint,
                    "expected_previous_fingerprint": expected_previous_fingerprint,
                    "agent": dict(payload),
                },
            )
            if not pushed:
                return None
            return await asyncio.wait_for(waiter, timeout=timeout_seconds)
        except asyncio.TimeoutError:
            return None
        finally:
            async with self._lock:
                self._agent_config_apply_waiters.pop(request_id, None)

    async def request_agent_config_operation_status(
        self,
        *,
        target_node_id: str,
        operation_id: str,
        candidate_fingerprint: str,
        timeout_seconds: float = 5.0,
    ) -> dict[str, object] | None:
        """Recover the canonical result of a previously submitted config operation."""
        request_id = f"agent-config-operation-status-{uuid4().hex}"
        loop = asyncio.get_running_loop()
        waiter: asyncio.Future[dict[str, object] | None] = loop.create_future()
        async with self._lock:
            self._agent_config_operation_status_waiters[request_id] = (
                operation_id,
                candidate_fingerprint,
                waiter,
            )
        try:
            pushed = await self._sessions.send(
                target_node_id=target_node_id,
                message_type="agent.config.operation.status",
                payload={"request_id": request_id, "operation_id": operation_id},
            )
            if not pushed:
                return None
            return await asyncio.wait_for(waiter, timeout=timeout_seconds)
        except asyncio.TimeoutError:
            return None
        finally:
            async with self._lock:
                self._agent_config_operation_status_waiters.pop(request_id, None)

    async def request_agent_capabilities(
        self,
        *,
        target_node_id: str,
        agent_id: str,
        workspace_root: str,
        timeout_seconds: float = 5.0,
    ) -> dict[str, object] | None:
        """Request one gateway node to resolve runtime capabilities for an agent workspace."""
        request_id = f"agent-capabilities-{uuid4().hex}"
        loop = asyncio.get_running_loop()
        waiter: asyncio.Future[dict[str, object] | None] = loop.create_future()
        async with self._lock:
            self._agent_capabilities_waiters[request_id] = waiter
        try:
            pushed = await self._sessions.send(
                target_node_id=target_node_id,
                message_type="agent.capabilities.resolve",
                payload={
                    "request_id": request_id,
                    "agent_id": agent_id,
                    "workspace_root": workspace_root,
                },
            )
            if not pushed:
                return None
            return await asyncio.wait_for(waiter, timeout=timeout_seconds)
        except asyncio.TimeoutError:
            return None
        finally:
            async with self._lock:
                self._agent_capabilities_waiters.pop(request_id, None)

    async def request_fork_session(
        self,
        *,
        target_node_id: str,
        source_conversation_id: str,
        new_conversation_id: str,
        agent_id: str,
        fork_message_id: str,
        source_external_source: str | None = None,
        source_external_chat_id: str | None = None,
        timeout_seconds: float = 10.0,
    ) -> dict[str, object] | None:
        """Delegate a session fork to one gateway node and await its result.

        feat-445-M1 (decision 2): the gateway holds the conversation↔session binding, so
        IM can only fork by asking it. Returns the result dict ({ok, new_session_id?,
        error?}) or ``None`` when the node is not connected / times out (the caller then
        rolls back the half-built conversation).
        """
        request_id = f"session-fork-{uuid4().hex}"
        loop = asyncio.get_running_loop()
        waiter: asyncio.Future[dict[str, object] | None] = loop.create_future()
        async with self._lock:
            self._session_fork_waiters[request_id] = waiter
        payload: dict[str, object] = {
            "request_id": request_id,
            "source_conversation_id": source_conversation_id,
            "new_conversation_id": new_conversation_id,
            "agent_id": agent_id,
            "fork_point": {"message_id": fork_message_id},
        }
        if source_external_source:
            payload["source_external_source"] = source_external_source
        if source_external_chat_id:
            payload["source_external_chat_id"] = source_external_chat_id
        try:
            pushed = await self._sessions.send(
                target_node_id=target_node_id,
                message_type="session.fork.request",
                payload=payload,
            )
            if not pushed:
                return None
            return await asyncio.wait_for(waiter, timeout=timeout_seconds)
        except asyncio.TimeoutError:
            return None
        finally:
            async with self._lock:
                self._session_fork_waiters.pop(request_id, None)

    async def request_session_log_path(
        self,
        *,
        target_node_id: str,
        agent_id: str,
        conversation_id: str,
        timeout_seconds: float = 5.0,
    ) -> SessionLogResolution:
        """Ask the owning Gateway for its exact conversation transcript binding."""
        request_id = f"session-log-{uuid4().hex}"
        loop = asyncio.get_running_loop()
        waiter: asyncio.Future[SessionLogResolution] = loop.create_future()
        async with self._lock:
            self._session_log_waiters[request_id] = waiter
        try:
            pushed = await self._sessions.send(
                target_node_id=target_node_id,
                message_type="session.log.resolve",
                payload={
                    "request_id": request_id,
                    "agent_id": agent_id,
                    "conversation_id": conversation_id,
                },
            )
            if not pushed:
                return SessionLogResolution(None, "unavailable")
            return await asyncio.wait_for(waiter, timeout=timeout_seconds)
        except asyncio.TimeoutError:
            return SessionLogResolution(None, "unavailable")
        finally:
            async with self._lock:
                self._session_log_waiters.pop(request_id, None)

    async def _handle_session_fork_result(
        self, *, payload: dict[str, object]
    ) -> dict[str, object]:
        request_id = _require_text(payload.get("request_id"), field_name="request_id")
        node_id = _require_text(payload.get("node_id"), field_name="node_id")
        # Echo through the gateway's reported result (ok / new_session_id / error).
        result = {k: v for k, v in payload.items() if k not in {"node_id"}}
        async with self._lock:
            waiter = self._session_fork_waiters.get(request_id)
        if waiter is not None and not waiter.done():
            waiter.set_result(result)
        return {
            "type": "ack",
            "payload": {
                "message_type": "session.fork.result",
                "request_id": request_id,
                "node_id": node_id,
            },
        }

    async def _handle_session_log_resolved(
        self, *, payload: dict[str, object]
    ) -> dict[str, object]:
        """Resolve one opaque session-log path returned by the owning Gateway."""
        request_id = _require_text(payload.get("request_id"), field_name="request_id")
        node_id = _require_text(payload.get("node_id"), field_name="node_id")
        agent_id = _require_text(payload.get("agent_id"), field_name="agent_id")
        conversation_id = _require_text(
            payload.get("conversation_id"), field_name="conversation_id"
        )
        raw_path = payload.get("source_jsonl_path")
        source_jsonl_path = (
            raw_path.strip() if isinstance(raw_path, str) and raw_path.strip() else None
        )
        raw_status = payload.get("status")
        if raw_status in {"ready", "missing", "unavailable"}:
            resolution_status = raw_status
        else:
            resolution_status = "ready" if source_jsonl_path else "missing"
        if resolution_status == "ready" and source_jsonl_path is None:
            resolution_status = "unavailable"
        async with self._lock:
            waiter = self._session_log_waiters.get(request_id)
        if waiter is not None and not waiter.done():
            waiter.set_result(
                SessionLogResolution(source_jsonl_path, resolution_status)
            )
        return {
            "type": "ack",
            "payload": {
                "message_type": "session.log.resolved",
                "request_id": request_id,
                "node_id": node_id,
                "agent_id": agent_id,
                "conversation_id": conversation_id,
            },
        }

    async def request_node_capabilities(
        self,
        *,
        target_node_id: str,
        timeout_seconds: float = 15.0,
    ) -> dict[str, object] | None:
        """请求网关节点当场解析 models/skills/tools 等（不从 IM 数据库读取）。"""
        request_id = f"node-capabilities-{uuid4().hex}"
        loop = asyncio.get_running_loop()
        waiter: asyncio.Future[dict[str, object] | None] = loop.create_future()
        async with self._lock:
            self._node_capabilities_waiters[request_id] = waiter
        try:
            pushed = await self._sessions.send(
                target_node_id=target_node_id,
                message_type="node.capabilities.resolve",
                payload={"request_id": request_id},
            )
            if not pushed:
                return None
            return await asyncio.wait_for(waiter, timeout=timeout_seconds)
        except asyncio.TimeoutError:
            return None
        finally:
            async with self._lock:
                self._node_capabilities_waiters.pop(request_id, None)

    async def request_prompt_preview(
        self,
        *,
        target_node_id: str,
        agent_id: str,
        workspace_root: str,
        features: dict[str, bool],
        custom_prompt: str | None,
        tool_ids: list[str],
        scenario: str,
        skill_ids: list[str] | None = None,
        timeout_seconds: float = 10.0,
        heartbeat_enabled: bool | None = None,
        cron_enabled: bool | None = None,
    ) -> dict[str, object] | None:
        """Send an agent.prompt.preview.request frame and await the assembled result.

        feat-379-M2 R5: IM proxy path — IM sends this request to the Gateway
        which calls agent HTTP /v1/prompt-preview and returns the result.
        feat-383-M1: skill_ids forwarded so Gateway→kernel can resolve real skills.
        feat-394-M4 R2-2: heartbeat_enabled/cron_enabled forwarded so preview
        correctly reflects the agent's heartbeat/cron toggle state.

        Returns:
            Preview payload dict or None when the node is not connected or times out.
        """
        request_id = f"prompt-preview-{uuid4().hex}"
        loop = asyncio.get_running_loop()
        waiter: asyncio.Future[dict[str, object] | None] = loop.create_future()
        async with self._lock:
            self._prompt_preview_waiters[request_id] = waiter
        payload: dict[str, object] = {
            "request_id": request_id,
            "agent_id": agent_id,
            "workspace_root": workspace_root,
            "features": features,
            "custom_prompt": custom_prompt,
            "tool_ids": tool_ids,
            "skill_ids": skill_ids or [],
            "scenario": scenario,
        }
        # feat-394-M4 R2-2: include heartbeat/cron flags only when provided so
        # the gateway-side handler can forward them to assemble_prompt_preview.
        if heartbeat_enabled is not None:
            payload["heartbeat_enabled"] = heartbeat_enabled
        if cron_enabled is not None:
            payload["cron_enabled"] = cron_enabled
        try:
            pushed = await self._sessions.send(
                target_node_id=target_node_id,
                message_type="agent.prompt.preview.request",
                payload=payload,
            )
            if not pushed:
                return None
            return await asyncio.wait_for(waiter, timeout=timeout_seconds)
        except asyncio.TimeoutError:
            return None
        finally:
            async with self._lock:
                self._prompt_preview_waiters.pop(request_id, None)

    async def request_node_prompt_preview(
        self,
        *,
        target_node_id: str,
        features: dict[str, bool],
        custom_prompt: str | None,
        tool_ids: list[str],
        scenario: str,
        workspace_mode: str,
        agent_id_hint: str | None,
        workspace_root: str | None,
        skill_ids: list[str] | None = None,
        timeout_seconds: float = 10.0,
    ) -> dict[str, object] | None:
        """Send a node.prompt.preview.request frame and await the assembled result.

        feat-379-M9 (決策 11): node-level preview path used by the agent-create page
        before an agent exists.
        Workspace intent is forwarded unchanged so the target Gateway resolves its
        own filesystem path before asking the kernel for a preview.

        Returns:
            Preview payload dict or None when the node is not connected or times out.
        """
        request_id = f"node-prompt-preview-{uuid4().hex}"
        loop = asyncio.get_running_loop()
        waiter: asyncio.Future[dict[str, object] | None] = loop.create_future()
        async with self._lock:
            self._node_prompt_preview_waiters[request_id] = waiter
        try:
            pushed = await self._sessions.send(
                target_node_id=target_node_id,
                message_type="node.prompt.preview.request",
                payload={
                    "request_id": request_id,
                    "workspace_mode": workspace_mode,
                    "agent_id_hint": agent_id_hint,
                    "workspace_root": workspace_root,
                    "features": features,
                    "custom_prompt": custom_prompt,
                    "tool_ids": tool_ids,
                    "skill_ids": skill_ids or [],
                    "scenario": scenario,
                },
            )
            if not pushed:
                return None
            return await asyncio.wait_for(waiter, timeout=timeout_seconds)
        except asyncio.TimeoutError:
            return None
        finally:
            async with self._lock:
                self._node_prompt_preview_waiters.pop(request_id, None)

    async def request_node_heartbeat_md(
        self,
        *,
        target_node_id: str,
        agent_id: str,
        workspace_root: str,
        timeout_seconds: float = 10.0,
    ) -> str | None:
        """Send a node.heartbeat.md.request frame and await the HEARTBEAT.md content.

        feat-394-M13 (决策 G): IM must never directly read gateway workspace files.
        This RPC asks the target gateway node to read <workspace>/HEARTBEAT.md and
        return its raw content.  The IM host and gateway may run on different machines,
        so direct file access from IM is not viable.

        Returns:
            Raw HEARTBEAT.md text, empty string when the file does not exist, or None
            when the node is not connected / times out (graceful degradation).
        """
        request_id = f"heartbeat-md-{uuid4().hex}"
        loop = asyncio.get_running_loop()
        waiter: asyncio.Future[str | None] = loop.create_future()
        async with self._lock:
            self._heartbeat_md_waiters[request_id] = waiter
        try:
            pushed = await self._sessions.send(
                target_node_id=target_node_id,
                message_type="node.heartbeat.md.request",
                payload={
                    "request_id": request_id,
                    "agent_id": agent_id,
                    "workspace_root": workspace_root,
                },
            )
            if not pushed:
                return None
            return await asyncio.wait_for(waiter, timeout=timeout_seconds)
        except asyncio.TimeoutError:
            return None
        finally:
            async with self._lock:
                self._heartbeat_md_waiters.pop(request_id, None)

    async def request_node_cron_jobs(
        self,
        *,
        target_node_id: str,
        agent_id: str,
        workspace_root: str,
        timeout_seconds: float = 10.0,
    ) -> list | None:
        """Send a node.cron.jobs.request frame and await the job list.

        feat-394-M13 (决策 G): replaces direct IM-side read of
        <workspace>/.nanoassistant/cron/jobs.json.  The gateway reads its own file
        and returns the job list; IM never touches the workspace directory.

        Returns:
            List of job dicts, empty list when no jobs file exists yet, or None when
            the node is not connected / times out (graceful degradation).
        """
        request_id = f"cron-jobs-{uuid4().hex}"
        loop = asyncio.get_running_loop()
        waiter: asyncio.Future[list | None] = loop.create_future()
        async with self._lock:
            self._cron_jobs_waiters[request_id] = waiter
        try:
            pushed = await self._sessions.send(
                target_node_id=target_node_id,
                message_type="node.cron.jobs.request",
                payload={
                    "request_id": request_id,
                    "agent_id": agent_id,
                    "workspace_root": workspace_root,
                },
            )
            if not pushed:
                return None
            return await asyncio.wait_for(waiter, timeout=timeout_seconds)
        except asyncio.TimeoutError:
            return None
        finally:
            async with self._lock:
                self._cron_jobs_waiters.pop(request_id, None)

    async def request_node_cron_delete(
        self,
        *,
        target_node_id: str,
        agent_id: str,
        workspace_root: str,
        job_id: str,
        timeout_seconds: float = 10.0,
    ) -> bool | None:
        """Send a node.cron.delete.request frame and await the deletion result.

        feat-394-M13 (决策 G): replaces direct IM-side write of
        <workspace>/.nanoassistant/cron/jobs.json.  The gateway performs the delete
        on its own filesystem and reports whether the job was found and removed.

        Returns:
            True when the job was found and deleted, False when job_id was not found,
            or None when the node is not connected / times out (graceful degradation).
        """
        request_id = f"cron-delete-{uuid4().hex}"
        loop = asyncio.get_running_loop()
        waiter: asyncio.Future[bool | None] = loop.create_future()
        async with self._lock:
            self._cron_delete_waiters[request_id] = waiter
        try:
            pushed = await self._sessions.send(
                target_node_id=target_node_id,
                message_type="node.cron.delete.request",
                payload={
                    "request_id": request_id,
                    "agent_id": agent_id,
                    "workspace_root": workspace_root,
                    "job_id": job_id,
                },
            )
            if not pushed:
                return None
            return await asyncio.wait_for(waiter, timeout=timeout_seconds)
        except asyncio.TimeoutError:
            return None
        finally:
            async with self._lock:
                self._cron_delete_waiters.pop(request_id, None)

    async def request_node_skills_usage(
        self,
        *,
        target_node_id: str,
        agent_id: str,
        workspace_root: str,
        timeout_seconds: float = 10.0,
    ) -> dict[str, object] | None:
        """Send a node.skills.usage.request frame and await usage stats.

        feat-446-M4: the authoritative ``.usage.json`` file is stored in the
        gateway-side workspace.  IM delegates the read/aggregation over WS RPC
        so IM and gateway can run on different hosts.
        """
        request_id = f"skills-usage-{uuid4().hex}"
        loop = asyncio.get_running_loop()
        waiter: asyncio.Future[dict[str, object] | None] = loop.create_future()
        async with self._lock:
            self._skills_usage_waiters[request_id] = waiter
        try:
            pushed = await self._sessions.send(
                target_node_id=target_node_id,
                message_type="node.skills.usage.request",
                payload={
                    "request_id": request_id,
                    "agent_id": agent_id,
                    "workspace_root": workspace_root,
                },
            )
            if not pushed:
                return None
            return await asyncio.wait_for(waiter, timeout=timeout_seconds)
        except asyncio.TimeoutError:
            return None
        finally:
            async with self._lock:
                self._skills_usage_waiters.pop(request_id, None)

    async def _handle_agent_config(
        self, *, payload: dict[str, object]
    ) -> dict[str, object]:
        request_id = _require_text(payload.get("request_id"), field_name="request_id")
        agent_id = _require_text(payload.get("agent_id"), field_name="agent_id")
        agent_payload = payload.get("agent")
        if agent_payload is not None and not isinstance(agent_payload, dict):
            raise ValueError("agent must be an object when provided")
        async with self._lock:
            waiter = self._agent_config_waiters.get(request_id)
        if waiter is not None and not waiter.done():
            waiter.set_result(
                dict(agent_payload) if isinstance(agent_payload, dict) else None
            )
        return {
            "type": "ack",
            "payload": {
                "message_type": "agent.config",
                "request_id": request_id,
                "agent_id": agent_id,
            },
        }

    async def _handle_agent_created(
        self, *, payload: dict[str, object]
    ) -> dict[str, object]:
        request_id = _require_text(payload.get("request_id"), field_name="request_id")
        node_id = _require_text(payload.get("node_id"), field_name="node_id")
        async with self._lock:
            waiter_entry = self._agent_create_waiters.get(request_id)
        if waiter_entry is not None:
            expected_operation_id, expected_fingerprint, waiter = waiter_entry
            if expected_operation_id is None:
                agent_payload = _require_dict(payload.get("agent"), field_name="agent")
                error_payload = payload.get("error")
                if error_payload is not None and not isinstance(error_payload, dict):
                    raise ValueError("error must be an object when provided")
                if not waiter.done():
                    waiter.set_result(
                        {"error": dict(error_payload)}
                        if isinstance(error_payload, dict)
                        else dict(agent_payload)
                    )
            else:
                result = _config_operation_result(
                    payload=payload,
                    expected_operation_id=expected_operation_id,
                    expected_candidate_fingerprint=expected_fingerprint,
                )
                if not waiter.done():
                    waiter.set_result(result)
        return {
            "type": "ack",
            "payload": {
                "message_type": "agent.created",
                "request_id": request_id,
                "node_id": node_id,
            },
        }

    async def _handle_agent_config_apply_result(
        self, *, payload: dict[str, object]
    ) -> dict[str, object]:
        """Resolve an ``agent.config.apply`` request by request and operation id."""
        return await self._handle_config_operation_result(
            payload=payload,
            waiters=self._agent_config_apply_waiters,
            message_type="agent.config.apply.result",
        )

    async def _handle_agent_config_operation_status_result(
        self, *, payload: dict[str, object]
    ) -> dict[str, object]:
        """Resolve an operation-status recovery request."""
        return await self._handle_config_operation_result(
            payload=payload,
            waiters=self._agent_config_operation_status_waiters,
            message_type="agent.config.operation.status.result",
        )

    async def _handle_config_operation_result(
        self,
        *,
        payload: dict[str, object],
        waiters: dict[str, object],
        message_type: str,
    ) -> dict[str, object]:
        request_id = _require_text(payload.get("request_id"), field_name="request_id")
        node_id = _require_text(payload.get("node_id"), field_name="node_id")
        async with self._lock:
            waiter_entry = waiters.get(request_id)
        if waiter_entry is not None:
            expected_operation_id, expected_fingerprint, waiter = waiter_entry
            result = _config_operation_result(
                payload=payload,
                expected_operation_id=expected_operation_id,
                expected_candidate_fingerprint=expected_fingerprint,
            )
            if not waiter.done():
                waiter.set_result(result)
        return {
            "type": "ack",
            "payload": {
                "message_type": message_type,
                "request_id": request_id,
                "node_id": node_id,
            },
        }

    async def _handle_agent_capabilities(
        self, *, payload: dict[str, object]
    ) -> dict[str, object]:
        request_id = _require_text(payload.get("request_id"), field_name="request_id")
        node_id = _require_text(payload.get("node_id"), field_name="node_id")
        agent_id = _require_text(payload.get("agent_id"), field_name="agent_id")
        # Validate workspace_root is present even though this handler doesn't use it directly.
        _require_text(payload.get("workspace_root"), field_name="workspace_root")
        capabilities = _require_dict(
            payload.get("capabilities"), field_name="capabilities"
        )
        async with self._lock:
            waiter = self._agent_capabilities_waiters.get(request_id)
        if waiter is not None and not waiter.done():
            waiter.set_result(dict(capabilities))
        return {
            "type": "ack",
            "payload": {
                "message_type": "agent.capabilities",
                "request_id": request_id,
                "node_id": node_id,
                "agent_id": agent_id,
            },
        }

    async def _handle_node_capabilities(
        self, *, payload: dict[str, object]
    ) -> dict[str, object]:
        request_id = _require_text(payload.get("request_id"), field_name="request_id")
        node_id = _require_text(payload.get("node_id"), field_name="node_id")
        capabilities = _require_dict(
            payload.get("capabilities"), field_name="capabilities"
        )
        async with self._lock:
            waiter = self._node_capabilities_waiters.get(request_id)
        if waiter is not None and not waiter.done():
            waiter.set_result(dict(capabilities))
        return {
            "type": "ack",
            "payload": {
                "message_type": "node.capabilities",
                "request_id": request_id,
                "node_id": node_id,
            },
        }

    async def _handle_prompt_preview(
        self, *, payload: dict[str, object]
    ) -> dict[str, object]:
        """Resolve prompt-preview waiter when Gateway returns assembled preview text.

        feat-379-M2 R5: Gateway calls agent HTTP /v1/prompt-preview and sends
        ``agent.prompt.preview`` back with {request_id, node_id, preview}.
        """
        request_id = _require_text(payload.get("request_id"), field_name="request_id")
        node_id = _require_text(payload.get("node_id"), field_name="node_id")
        preview = payload.get("preview")
        if not isinstance(preview, dict):
            preview = {}
        async with self._lock:
            waiter = self._prompt_preview_waiters.get(request_id)
        if waiter is not None and not waiter.done():
            waiter.set_result(dict(preview))
        return {
            "type": "ack",
            "payload": {
                "message_type": "agent.prompt.preview",
                "request_id": request_id,
                "node_id": node_id,
            },
        }

    async def _handle_node_prompt_preview(
        self, *, payload: dict[str, object]
    ) -> dict[str, object]:
        """Resolve node-level prompt-preview waiter when Gateway returns assembled preview.

        feat-379-M9 (決策 11): Gateway sends ``node.prompt.preview`` in response to
        ``node.prompt.preview.request``.  No per-agent context is required.
        """
        request_id = _require_text(payload.get("request_id"), field_name="request_id")
        node_id = _require_text(payload.get("node_id"), field_name="node_id")
        preview = payload.get("preview")
        if not isinstance(preview, dict):
            preview = {}
        async with self._lock:
            waiter = self._node_prompt_preview_waiters.get(request_id)
        if waiter is not None and not waiter.done():
            waiter.set_result(dict(preview))
        return {
            "type": "ack",
            "payload": {
                "message_type": "node.prompt.preview",
                "request_id": request_id,
                "node_id": node_id,
            },
        }

    async def _handle_heartbeat_md(
        self, *, payload: dict[str, object]
    ) -> dict[str, object]:
        """Resolve heartbeat-md waiter when gateway returns HEARTBEAT.md content.

        feat-394-M13 (决策 G): gateway sends ``node.heartbeat.md`` in response to
        ``node.heartbeat.md.request`` with {request_id, content}.
        Empty string signals file does not exist; both are valid.
        """
        request_id = _require_text(payload.get("request_id"), field_name="request_id")
        content_raw = payload.get("content")
        content = content_raw if isinstance(content_raw, str) else ""
        async with self._lock:
            waiter = self._heartbeat_md_waiters.get(request_id)
        if waiter is not None and not waiter.done():
            waiter.set_result(content)
        return {
            "type": "ack",
            "payload": {
                "message_type": "node.heartbeat.md",
                "request_id": request_id,
            },
        }

    async def _handle_cron_jobs(
        self, *, payload: dict[str, object]
    ) -> dict[str, object]:
        """Resolve cron-jobs waiter when gateway returns the job list.

        feat-394-M13 (决策 G): gateway sends ``node.cron.jobs`` in response to
        ``node.cron.jobs.request`` with {request_id, jobs:[...]}.
        """
        request_id = _require_text(payload.get("request_id"), field_name="request_id")
        jobs_raw = payload.get("jobs")
        jobs: list = jobs_raw if isinstance(jobs_raw, list) else []
        async with self._lock:
            waiter = self._cron_jobs_waiters.get(request_id)
        if waiter is not None and not waiter.done():
            waiter.set_result(jobs)
        return {
            "type": "ack",
            "payload": {
                "message_type": "node.cron.jobs",
                "request_id": request_id,
            },
        }

    async def _handle_cron_delete(
        self, *, payload: dict[str, object]
    ) -> dict[str, object]:
        """Resolve cron-delete waiter when gateway reports deletion result.

        feat-394-M13 (决策 G): gateway sends ``node.cron.delete`` in response to
        ``node.cron.delete.request`` with {request_id, deleted: bool}.
        deleted=True means job was found and removed; False means not found.
        """
        request_id = _require_text(payload.get("request_id"), field_name="request_id")
        deleted_raw = payload.get("deleted")
        deleted: bool = bool(deleted_raw)
        async with self._lock:
            waiter = self._cron_delete_waiters.get(request_id)
        if waiter is not None and not waiter.done():
            waiter.set_result(deleted)
        return {
            "type": "ack",
            "payload": {
                "message_type": "node.cron.delete",
                "request_id": request_id,
            },
        }

    async def _handle_skills_usage(
        self, *, payload: dict[str, object]
    ) -> dict[str, object]:
        """Resolve skills-usage waiter when gateway returns the dashboard payload."""
        request_id = _require_text(payload.get("request_id"), field_name="request_id")
        usage_raw = payload.get("usage")
        usage: dict[str, object] = usage_raw if isinstance(usage_raw, dict) else {}
        async with self._lock:
            waiter = self._skills_usage_waiters.get(request_id)
        if waiter is not None and not waiter.done():
            waiter.set_result(dict(usage))
        return {
            "type": "ack",
            "payload": {
                "message_type": "node.skills.usage",
                "request_id": request_id,
            },
        }
