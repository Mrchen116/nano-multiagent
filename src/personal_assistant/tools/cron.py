"""Personal-assistant cron tool — closure-direct form (refactor-406 决策 9).

This is the migrated cron tool: it lives in the consumer package
(``src/personal_assistant/``) and is passed into the kernel via
``build_kernel(tools=…)``. Its immediate-run action talks **directly** to the
per-agent ``CronExecutionService`` held in the factory closure — there is no
``HostCapabilityDispatcher`` round-trip back through the kernel (决策 9: side-effect
tools close over their own subsystem; the kernel offers no回桥).

``make_cron_tool(cron_services)`` binds the per-agent services map (the same
``agent_id → CronExecutionService`` map the Gateway maintains). At run time the
tool routes by ``ctx.session_metadata["agent_id"]`` — preserving the per-agent
routing the old ``GatewayCronDispatcher`` provided, now без the bridge.

Job persistence (list/add/update/remove/runs) is identical to the pre-migration
tool: jobs live in ``<workspace>/.nanoassistant/cron/jobs.json``; the scheduler
polls them. Behaviour is byte-for-byte preserved (the cron unit tests guard it);
only the immediate-run dispatch path changed from dispatcher to closure.

Provenance: description / JOB SCHEMA / SCHEDULE TYPES / PAYLOAD TYPES / CRITICAL
CONSTRAINTS copied verbatim from the pre-migration tool
(``agent/products/personal_assistant/tools/cron.py``), which itself traces to
openclaw/src/agents/tools/cron-tool.ts:524-598. feat-394 decision 6.
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any, Mapping, NamedTuple

from agent.sdk import ToolContext

# Same-package import is allowed (no agent→personal_assistant boundary here): the
# tool now lives in the consumer package and may use the Gateway's own types.
from personal_assistant.scheduler.cron_execution_service import CronExecutionService


# ---------------------------------------------------------------------------
# Lightweight permission-allow result (mirrors auto_mode_gate's duck contract)
# ---------------------------------------------------------------------------
# auto_mode_gate only reads getattr(result, "behavior", "passthrough"); "allow"
# bypasses the classifier so cron calls (authorized at registration time via the
# cron_enabled gate) are not denied as "Unauthorized Persistence".


class _AllowDecision:
    behavior: str = "allow"
    reason: str = "cron tool: authorized at registration time (cron_enabled gate)"


_CRON_TOOL_ALLOW = _AllowDecision()


_CRON_SUBDIR = ".nanoassistant/cron"
_JOBS_FILENAME = "jobs.json"


class _CronJob(NamedTuple):
    """Lightweight job record persisted to jobs.json."""

    id: str
    name: str
    schedule: dict
    instruction: str
    enabled: bool = True
    delete_after_run: bool = False


def _read_jobs(workspace_root: Path) -> list[_CronJob]:
    jobs_path = workspace_root / _CRON_SUBDIR / _JOBS_FILENAME
    if not jobs_path.exists():
        return []
    try:
        data = json.loads(jobs_path.read_text(encoding="utf-8"))
    except (ValueError, TypeError):
        return []
    if not isinstance(data, list):
        return []
    result: list[_CronJob] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        try:
            result.append(
                _CronJob(
                    id=str(item["id"]),
                    name=str(item.get("name", "")),
                    schedule=dict(item["schedule"])
                    if isinstance(item.get("schedule"), dict)
                    else {},
                    instruction=str(item.get("instruction", "")),
                    enabled=bool(item.get("enabled", True)),
                    delete_after_run=bool(item.get("delete_after_run", False)),
                )
            )
        except (KeyError, TypeError, ValueError):
            continue
    return result


def _write_jobs(workspace_root: Path, jobs: list[_CronJob]) -> None:
    cron_dir = workspace_root / _CRON_SUBDIR
    cron_dir.mkdir(parents=True, exist_ok=True)
    serialized = [
        {
            "id": j.id,
            "name": j.name,
            "schedule": dict(j.schedule),
            "instruction": j.instruction,
            "enabled": j.enabled,
            "delete_after_run": j.delete_after_run,
        }
        for j in jobs
    ]
    (cron_dir / _JOBS_FILENAME).write_text(
        json.dumps(serialized, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def _make_job_id() -> str:
    return uuid.uuid4().hex


# Provenance: openclaw/src/agents/tools/cron-tool.ts:527-595 (trimmed verbatim).
_DESCRIPTION = """Manage Gateway cron jobs (list/add/update/remove/run/runs). Use this for reminders, "check back later" requests, delayed follow-ups, and recurring tasks. Do not emulate scheduling with exec sleep or process polling.

Isolated cron jobs create background task runs that deliver results to the owner's direct chat.

ACTIONS:
- list: List jobs (use includeDisabled:true to include disabled)
- add: Create job (requires job object, see schema below)
- update: Modify job (requires jobId + patch object)
- remove: Delete job (requires jobId)
- run: Trigger job immediately (requires jobId)
- runs: Get job run history (requires jobId)

JOB SCHEMA (for add action):
{
  "name": "string (optional)",
  "schedule": { ... },      // Required: when to run
  "payload": { ... },       // Required: what to execute
  "enabled": true | false   // Optional, default true
}

SCHEDULE TYPES (schedule.kind):
- "at": One-shot at absolute time
  { "kind": "at", "at": "<ISO-8601 timestamp>" }
- "every": Recurring interval
  { "kind": "every", "everyMs": <interval-ms>, "anchorMs": <optional-start-ms> }
- "cron": Cron expression
  { "kind": "cron", "expr": "<cron-expression>", "tz": "<optional-timezone>" }

ISO timestamps without an explicit timezone are treated as UTC.

PAYLOAD TYPES (payload.kind):
- "agentTurn": Runs agent with message (isolated sessions only)
  { "kind": "agentTurn", "message": "<prompt>", "model": "<optional>", "thinking": "<optional>", "timeoutSeconds": <optional, 0 means no timeout> }

CRITICAL CONSTRAINTS:
- All cron jobs run in isolated sessions (no conversation context).
- Results are delivered to the owner's direct chat automatically.
- Use jobId as the canonical identifier; id is accepted for compatibility."""


_INPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "action": {
            "type": "string",
            "enum": ["list", "add", "update", "remove", "run", "runs"],
            "description": "Cron action to perform.",
        },
        "includeDisabled": {
            "type": "boolean",
            "description": "When true, list also returns disabled jobs.",
        },
        "job": {
            "type": "object",
            "description": "Job definition for add action (see JOB SCHEMA).",
            "properties": {
                "name": {"type": "string", "description": "Job name"},
                "schedule": {
                    "type": "object",
                    "description": "Schedule descriptor (see SCHEDULE TYPES).",
                    "properties": {
                        "kind": {
                            "type": "string",
                            "enum": ["at", "every", "cron"],
                            "description": "Schedule type",
                        },
                        "at": {
                            "type": "string",
                            "description": "ISO-8601 timestamp (kind=at)",
                        },
                        "everyMs": {
                            "type": "number",
                            "description": "Interval in milliseconds (kind=every)",
                        },
                        "anchorMs": {
                            "type": "number",
                            "description": "Optional start anchor in ms (kind=every)",
                        },
                        "expr": {
                            "type": "string",
                            "description": "Cron expression (kind=cron)",
                        },
                        "tz": {
                            "type": "string",
                            "description": "IANA timezone (kind=cron)",
                        },
                    },
                    "additionalProperties": True,
                },
                "payload": {
                    "type": "object",
                    "description": "Payload descriptor (see PAYLOAD TYPES).",
                    "properties": {
                        "kind": {
                            "type": "string",
                            "enum": ["agentTurn"],
                            "description": "Payload type (agentTurn only)",
                        },
                        "message": {
                            "type": "string",
                            "description": "Agent instruction/prompt",
                        },
                        "model": {
                            "type": "string",
                            "description": "Optional model override",
                        },
                        "thinking": {
                            "type": "string",
                            "description": "Optional thinking mode",
                        },
                        "timeoutSeconds": {
                            "type": "number",
                            "description": "Timeout; 0 = no timeout",
                        },
                    },
                    "additionalProperties": True,
                },
                "enabled": {"type": "boolean"},
                "deleteAfterRun": {
                    "type": "boolean",
                    "description": "Delete after first execution",
                },
            },
            "additionalProperties": True,
        },
        "jobId": {
            "type": "string",
            "description": "Job identifier for update/remove/run/runs.",
        },
        "id": {
            "type": "string",
            "description": "Job identifier alias (accepted for compatibility).",
        },
        "patch": {
            "type": "object",
            "description": "Partial update fields for update action.",
            "properties": {
                "name": {"type": "string"},
                "schedule": {"type": "object", "additionalProperties": True},
                "payload": {"type": "object", "additionalProperties": True},
                "enabled": {"type": "boolean"},
                "deleteAfterRun": {"type": "boolean"},
            },
            "additionalProperties": True,
        },
    },
    "required": ["action"],
    "additionalProperties": True,
}


class CronTool:
    """Manage cron jobs for the personal assistant agent (closure-direct form).

    Jobs are persisted to ``<workspace>/.nanoassistant/cron/jobs.json``. The
    immediate-run action calls the per-agent ``CronExecutionService.enqueue``
    directly via the factory closure (决策 9), routed by ``agent_id`` from session
    metadata — no ``HostCapabilityDispatcher``.
    """

    name = "cron"
    description = _DESCRIPTION
    input_schema = _INPUT_SCHEMA

    def __init__(self, cron_services: Mapping[str, CronExecutionService]) -> None:
        # Per-agent services map (agent_id → CronExecutionService). Held by closure;
        # the immediate-run action looks up the requesting agent's service at run time.
        self._cron_services = cron_services

    def check_permissions(self, tool_input: Mapping[str, Any], ctx: Any) -> _AllowDecision:
        """Allow all cron calls (authorized at registration time via cron_enabled).

        Without this, auto_mode_gate falls through to the classifier which denies
        cron calls as "Unauthorized Persistence" (feat-394-M5 R3-1).
        """
        return _CRON_TOOL_ALLOW

    def run(self, args: Mapping[str, Any], ctx: ToolContext) -> Mapping[str, Any]:
        action = _require_str(args.get("action"), field_name="action")
        workspace_root = ctx.repo_root

        if action == "list":
            return self._action_list(args, workspace_root)
        elif action == "add":
            return self._action_add(args, workspace_root)
        elif action == "update":
            return self._action_update(args, workspace_root)
        elif action == "remove":
            return self._action_remove(args, workspace_root)
        elif action == "run":
            return self._action_run(args, workspace_root, ctx)
        elif action == "runs":
            return self._action_runs(args, ctx)
        else:
            raise ValueError(
                f"cron: unknown action {action!r}. Valid: list, add, update, remove, run, runs"
            )

    # ------------------------------------------------------------------
    # Action handlers
    # ------------------------------------------------------------------

    def _action_list(self, args: Mapping[str, Any], workspace_root: Path) -> dict[str, Any]:
        include_disabled = bool(args.get("includeDisabled", False))
        jobs = _read_jobs(workspace_root)
        if not include_disabled:
            jobs = [j for j in jobs if j.enabled]
        return {
            "ok": True,
            "jobs": [_job_to_api_dict(j) for j in jobs],
            "count": len(jobs),
        }

    def _action_add(self, args: Mapping[str, Any], workspace_root: Path) -> dict[str, Any]:
        job_raw = args.get("job")
        if not isinstance(job_raw, dict):
            raise ValueError("cron add: 'job' field is required and must be an object")
        schedule = job_raw.get("schedule")
        if not isinstance(schedule, dict) or not schedule.get("kind"):
            raise ValueError("cron add: job.schedule is required and must include 'kind'")
        payload = job_raw.get("payload")
        if not isinstance(payload, dict):
            raise ValueError("cron add: job.payload is required")
        instruction = _build_instruction_from_payload(payload)
        job = _CronJob(
            id=_make_job_id(),
            name=str(job_raw.get("name", "")),
            schedule=dict(schedule),
            instruction=instruction,
            enabled=bool(job_raw.get("enabled", True)),
            delete_after_run=bool(job_raw.get("deleteAfterRun", False)),
        )
        existing = _read_jobs(workspace_root)
        existing.append(job)
        _write_jobs(workspace_root, existing)
        return {"ok": True, "jobId": job.id, "job": _job_to_api_dict(job)}

    def _action_update(self, args: Mapping[str, Any], workspace_root: Path) -> dict[str, Any]:
        job_id = _resolve_job_id(args)
        patch = args.get("patch")
        if not isinstance(patch, dict):
            raise ValueError("cron update: 'patch' field is required")
        jobs = _read_jobs(workspace_root)
        idx = next((i for i, j in enumerate(jobs) if j.id == job_id), None)
        if idx is None:
            raise LookupError(f"cron update: job not found: {job_id!r}")
        existing = jobs[idx]
        new_schedule = (
            dict(patch["schedule"])
            if isinstance(patch.get("schedule"), dict)
            else existing.schedule
        )
        new_name = (
            str(patch["name"]) if isinstance(patch.get("name"), str) else existing.name
        )
        new_enabled = (
            bool(patch["enabled"])
            if isinstance(patch.get("enabled"), bool)
            else existing.enabled
        )
        new_delete_after = (
            bool(patch["deleteAfterRun"])
            if isinstance(patch.get("deleteAfterRun"), bool)
            else existing.delete_after_run
        )
        new_instruction = (
            _build_instruction_from_payload(patch["payload"])
            if isinstance(patch.get("payload"), dict)
            else existing.instruction
        )
        updated = _CronJob(
            id=existing.id,
            name=new_name,
            schedule=new_schedule,
            instruction=new_instruction,
            enabled=new_enabled,
            delete_after_run=new_delete_after,
        )
        jobs[idx] = updated
        _write_jobs(workspace_root, jobs)
        return {"ok": True, "jobId": updated.id, "job": _job_to_api_dict(updated)}

    def _action_remove(self, args: Mapping[str, Any], workspace_root: Path) -> dict[str, Any]:
        job_id = _resolve_job_id(args)
        jobs = _read_jobs(workspace_root)
        if not any(j.id == job_id for j in jobs):
            raise LookupError(f"cron remove: job not found: {job_id!r}")
        filtered = [j for j in jobs if j.id != job_id]
        _write_jobs(workspace_root, filtered)
        return {"ok": True, "jobId": job_id, "removed": True}

    def _action_run(
        self, args: Mapping[str, Any], workspace_root: Path, ctx: ToolContext
    ) -> dict[str, Any]:
        """Trigger a job immediately via the per-agent CronExecutionService (决策 9).

        Routes by ``agent_id`` (session metadata) to the closure-held services map,
        then calls ``enqueue(job_id=…, trigger="manual")`` directly. ``enqueue``
        handles cross-thread marshalling onto the Gateway loop internally and returns
        a synchronous accepted ack (it does not block for completion). No host-capability
        dispatcher round-trip.
        """
        job_id = _resolve_job_id(args)
        jobs = _read_jobs(workspace_root)
        if not any(j.id == job_id for j in jobs):
            raise LookupError(f"cron run: job not found: {job_id!r}")

        agent_id = str(ctx.session_metadata.get("agent_id") or "")
        service = self._cron_services.get(agent_id)
        if service is None:
            return {
                "ok": False,
                "jobId": job_id,
                "error": (
                    "cron run: no cron execution service for this agent. "
                    "The cron execution service is only available in the personal assistant gateway."
                ),
            }

        try:
            ack = service.enqueue(job_id=job_id, trigger="manual")
        except Exception as exc:  # noqa: BLE001 — surface as a tool-level error dict
            return {"ok": False, "jobId": job_id, "error": f"cron run: enqueue error: {exc}"}

        if not ack.get("accepted"):
            error_code = ack.get("error_code")
            msg = {
                "job_not_found": "job not found on gateway side",
                "job_disabled": "job is disabled",
                "cron_unavailable": "cron execution service is unavailable",
            }.get(error_code or "", f"enqueue declined (error_code={error_code!r})")
            return {"ok": False, "jobId": job_id, "error": f"cron run: {msg}"}

        return {
            "ok": True,
            "jobId": job_id,
            "accepted": True,
            "requestId": ack.get("request_id"),
        }

    def _action_runs(self, args: Mapping[str, Any], ctx: ToolContext) -> dict[str, Any]:
        job_id = _resolve_job_id(args)
        workspace_root = ctx.repo_root if ctx.repo_root else None
        if workspace_root is None:
            return {"ok": True, "jobId": job_id, "runs": []}
        runs_path = workspace_root / _CRON_SUBDIR / "runs.jsonl"
        if not runs_path.exists():
            return {"ok": True, "jobId": job_id, "runs": []}
        records = _read_runs_for_job(runs_path, job_id, limit=20)
        return {"ok": True, "jobId": job_id, "runs": records}


def make_cron_tool(cron_services: Mapping[str, CronExecutionService]) -> CronTool:
    """Build a cron tool bound to the Gateway's per-agent CronExecutionService map.

    Passed into ``build_kernel(tools=…)`` by the personal-assistant factory. The
    tool routes immediate-run requests to ``cron_services[agent_id]`` (决策 9: closure
    direct to the application subsystem, no kernel host-capability bridge).

    Args:
        cron_services: Mutable ``agent_id → CronExecutionService`` map maintained by
            the Gateway (services may be registered after build_kernel; the map is
            shared by reference so late registrations are visible).

    Returns:
        A CronTool instance.
    """
    return CronTool(cron_services)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _read_runs_for_job(runs_path: Path, job_id: str, *, limit: int = 20) -> list[dict[str, Any]]:
    try:
        raw = runs_path.read_text(encoding="utf-8")
    except OSError:
        return []
    latest: dict[str, dict[str, Any]] = {}
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            data = json.loads(line)
        except (ValueError, TypeError):
            continue
        if not isinstance(data, dict):
            continue
        rid = data.get("request_id")
        if not isinstance(rid, str) or not rid:
            continue
        if data.get("job_id") != job_id:
            continue
        latest[rid] = data
    records = list(latest.values())
    records.sort(key=lambda r: r.get("accepted_at") or "", reverse=True)
    return records[:limit]


def _require_str(value: object, *, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"cron: '{field_name}' must be a non-empty string")
    return value.strip()


def _resolve_job_id(args: Mapping[str, Any]) -> str:
    """Accept jobId or id (openclaw compatibility)."""
    job_id = args.get("jobId") or args.get("id")
    if not isinstance(job_id, str) or not job_id.strip():
        raise ValueError("cron: 'jobId' is required for this action")
    return job_id.strip()


def _build_instruction_from_payload(payload: dict[str, Any]) -> str:
    message = payload.get("message", "")
    if not isinstance(message, str):
        message = str(message)
    return message.strip()


def _job_to_api_dict(job: _CronJob) -> dict[str, Any]:
    return {
        "id": job.id,
        "name": job.name,
        "schedule": dict(job.schedule),
        "instruction": job.instruction,
        "enabled": job.enabled,
        "deleteAfterRun": job.delete_after_run,
    }
