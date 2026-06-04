"""Personal-assistant cron tool — manage gateway cron jobs.

This tool is PA-exclusive (feat-394 decision 7). It must never appear in coding_cli.
Job definitions are persisted to <workspace>/.nanoassistant/cron/jobs.json.
Immediate-run requests are forwarded to the gateway via gateway_cron_url in session metadata.

Provenance: openclaw/src/agents/tools/cron-tool.ts:524-598 — description, JOB SCHEMA,
SCHEDULE TYPES, PAYLOAD TYPES, and CRITICAL CONSTRAINTS are copied verbatim from that
function's description string, trimmed to the nano fixed-isolated + owner-direct-chat model
(removed: wake action, sessionTarget variants other than isolated, multi-channel delivery,
webhook, contextMessages). feat-394 decision 6.

Arch note: this file intentionally does not import from `personal_assistant.*`.
The canonical CronJobStore and CronJob live in personal_assistant.scheduler.cron_scheduler;
the lightweight read/write helpers below are inlined here to respect the agent→personal_assistant
import boundary (AGENTS.md dependency direction rule).
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any, Mapping, NamedTuple

from agent.core.tools.base import ToolContext


# ---------------------------------------------------------------------------
# Lightweight permission result (inlined to avoid platform layer import)
# ---------------------------------------------------------------------------
# feat-394-M5 R3-1 fix: CronTool needs a check_permissions return value.
# The platform-layer PermissionDecision class cannot be imported here
# (AGENTS.md dependency direction: products must not import platform internals).
# auto_mode_gate only reads getattr(result, "behavior", "passthrough"), so a minimal
# object with a "behavior" attribute satisfies the protocol.


class _AllowDecision:
    """Minimal permission-allow result for CronTool.check_permissions.

    auto_mode_gate dispatches on result.behavior; "allow" bypasses the classifier
    (Step 5 in auto_mode_gate.on_tool_call).
    """

    behavior: str = "allow"
    reason: str = "cron tool: authorized at registration time (cron_enabled gate)"


_CRON_TOOL_ALLOW = _AllowDecision()


# ---------------------------------------------------------------------------
# Lightweight job types (inlined due to agent→personal_assistant boundary)
# ---------------------------------------------------------------------------

_CRON_SUBDIR = ".nanoassistant/cron"
_JOBS_FILENAME = "jobs.json"


class _CronJob(NamedTuple):
    """Lightweight mirror of CronJob for use within agent.products boundary."""

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


# ---------------------------------------------------------------------------
# Tool description (verbatim from openclaw cron-tool.ts:527-595, trimmed)
# ---------------------------------------------------------------------------
# Provenance: openclaw/src/agents/tools/cron-tool.ts:527-595
# Trimmed: wake action, sessionTarget variants, multi-channel delivery, webhook,
# contextMessages, status action — not applicable in nano's single-channel model.
# Remaining text is verbatim.
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


# ---------------------------------------------------------------------------
# Input schema (adapted from openclaw CronToolSchema)
# ---------------------------------------------------------------------------
# Provenance: openclaw/src/agents/tools/cron-tool.ts:278-296 CronToolSchema
# Trimmed: gatewayUrl, gatewayToken, timeoutMs, text (wake), mode (wake),
# runMode, contextMessages — not applicable in nano.
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


# ---------------------------------------------------------------------------
# CronTool implementation
# ---------------------------------------------------------------------------


class CronTool:
    """Manage cron jobs for the personal assistant agent.

    Jobs are persisted to <workspace>/.nanoassistant/cron/jobs.json.
    The scheduler polls this file periodically and submits due jobs
    to the kernel as isolated runs (origin=cron), delivering results
    to the owner's canonical direct chat.

    Raises:
        ValueError: When required arguments are missing or malformed.
        RuntimeError: When session metadata required for run action is absent.
    """

    name = "cron"
    # Provenance: openclaw/src/agents/tools/cron-tool.ts:527-595 (trimmed, see module docstring)
    description = _DESCRIPTION
    input_schema = _INPUT_SCHEMA

    def check_permissions(
        self,
        tool_input: Mapping[str, Any],
        ctx: Any,
    ) -> _AllowDecision:
        """Allow all cron tool calls unconditionally.

        Authorization happens at tool registration time: cron tool is only injected
        into an agent's tool table when cron_enabled=True (enforced by toolsets.py).
        An agent that has cron in its tool table has already been authorized by the user.

        Without this method, auto_mode_gate falls through to the classifier (Step 7),
        which denies cron calls as "Unauthorized Persistence" (the classifier sees
        "modify cron jobs" and blocks it regardless of the agent's configuration).

        feat-394-M5 R3-1 fix: closes acceptance.md Round 3 Issue R3-1.

        Args:
            tool_input: Cron tool arguments (action, job definition, etc.).
            ctx: Tool execution context (not used; authorization is static).

        Returns:
            _AllowDecision with behavior="allow" so auto_mode_gate bypasses classifier.
        """
        return _CRON_TOOL_ALLOW

    def run(self, args: Mapping[str, Any], ctx: ToolContext) -> Mapping[str, Any]:
        """Execute one cron action.

        Args:
            args: Tool arguments; must contain 'action'.
            ctx: Execution context; repo_root is the agent workspace root.

        Returns:
            Dict with action result.

        Raises:
            ValueError: When 'action' is missing or unknown, or required fields absent.
            RuntimeError: When 'run' action gateway URL is not configured.
        """
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

    def _action_list(
        self, args: Mapping[str, Any], workspace_root: Path
    ) -> dict[str, Any]:
        include_disabled = bool(args.get("includeDisabled", False))
        jobs = _read_jobs(workspace_root)
        if not include_disabled:
            jobs = [j for j in jobs if j.enabled]
        return {
            "ok": True,
            "jobs": [_job_to_api_dict(j) for j in jobs],
            "count": len(jobs),
        }

    def _action_add(
        self, args: Mapping[str, Any], workspace_root: Path
    ) -> dict[str, Any]:
        job_raw = args.get("job")
        if not isinstance(job_raw, dict):
            raise ValueError("cron add: 'job' field is required and must be an object")
        schedule = job_raw.get("schedule")
        if not isinstance(schedule, dict) or not schedule.get("kind"):
            raise ValueError(
                "cron add: job.schedule is required and must include 'kind'"
            )
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
        return {
            "ok": True,
            "jobId": job.id,
            "job": _job_to_api_dict(job),
        }

    def _action_update(
        self, args: Mapping[str, Any], workspace_root: Path
    ) -> dict[str, Any]:
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
        return {
            "ok": True,
            "jobId": updated.id,
            "job": _job_to_api_dict(updated),
        }

    def _action_remove(
        self, args: Mapping[str, Any], workspace_root: Path
    ) -> dict[str, Any]:
        job_id = _resolve_job_id(args)
        jobs = _read_jobs(workspace_root)
        if not any(j.id == job_id for j in jobs):
            raise LookupError(f"cron remove: job not found: {job_id!r}")
        filtered = [j for j in jobs if j.id != job_id]
        _write_jobs(workspace_root, filtered)
        return {"ok": True, "jobId": job_id, "removed": True}

    def _action_run(
        self,
        args: Mapping[str, Any],
        workspace_root: Path,
        ctx: ToolContext,
    ) -> dict[str, Any]:
        """Trigger a job immediately via gateway cron dispatch endpoint."""
        job_id = _resolve_job_id(args)
        jobs = _read_jobs(workspace_root)
        if not any(j.id == job_id for j in jobs):
            raise LookupError(f"cron run: job not found: {job_id!r}")
        cron_dispatch_url = ctx.session_metadata.get("gateway_cron_url")
        if not isinstance(cron_dispatch_url, str) or not cron_dispatch_url.strip():
            raise RuntimeError(
                "cron run: gateway_cron_url is not configured in session metadata. "
                "Ensure the Gateway inbound pipeline injects gateway_cron_url."
            )
        import httpx  # noqa: PLC0415 — deferred: avoids import cost on list/add/update

        agent_id = str(ctx.session_metadata.get("agent_id", ""))
        payload = {"agent_id": agent_id, "job_id": job_id}
        timeout = httpx.Timeout(connect=3.0, write=10.0, read=None, pool=3.0)
        response = httpx.post(cron_dispatch_url.strip(), json=payload, timeout=timeout)
        try:
            body = response.json()
        except ValueError as exc:
            raise RuntimeError("cron run: gateway returned non-JSON response") from exc
        if response.status_code >= 400 or (
            isinstance(body, dict) and body.get("ok") is not True
        ):
            error = body.get("error") if isinstance(body, dict) else None
            if isinstance(error, str) and error.strip():
                raise RuntimeError(f"cron run: {error.strip()}")
            raise RuntimeError(
                f"cron run: gateway returned status {response.status_code}"
            )
        return {"ok": True, "jobId": job_id, "triggered": True}

    def _action_runs(self, args: Mapping[str, Any], ctx: ToolContext) -> dict[str, Any]:
        """Return job run history from state store."""
        job_id = _resolve_job_id(args)
        state_path_str = ctx.session_metadata.get("cron_state_path")
        if not isinstance(state_path_str, str) or not state_path_str.strip():
            return {
                "ok": True,
                "jobId": job_id,
                "runs": [],
                "note": "no run state available",
            }
        state_path = Path(state_path_str.strip())
        if not state_path.exists():
            return {"ok": True, "jobId": job_id, "runs": []}
        try:
            raw = json.loads(state_path.read_text(encoding="utf-8"))
        except (ValueError, TypeError):
            return {"ok": True, "jobId": job_id, "runs": []}
        jobs_state = raw.get("jobs", {}) if isinstance(raw, dict) else {}
        run_entry = jobs_state.get(job_id, {}) if isinstance(jobs_state, dict) else {}
        runs = []
        if isinstance(run_entry, dict) and run_entry.get("last_due_at"):
            runs.append({"last_due_at": run_entry["last_due_at"]})
        return {"ok": True, "jobId": job_id, "runs": runs}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


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
    """Extract the instruction/message from an agentTurn payload."""
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


def get_tool() -> CronTool:
    """Return a fresh CronTool instance for tool loader discovery."""
    return CronTool()
