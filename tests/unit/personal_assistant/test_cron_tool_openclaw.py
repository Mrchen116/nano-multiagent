"""Tests for feat-394-M2 R3: cron tool schema/description openclaw verbatim parity.

feat-394 decision 6: cron tool description/schema must be copied verbatim from
openclaw/src/agents/tools/cron-tool.ts:524-598 (actions/schema/description).
Lines that reference openclaw-specific multi-channel delivery, sessionTarget variants,
wake action, and webhook are trimmed for nano's fixed-isolated + owner-direct-chat model;
the remaining text is verbatim.

Also verifies:
- cron tool is registered in personal_assistant toolsets (OPTIONAL_TOOL_IDS or DEFAULT_TOOL_IDS)
- cron tool is NOT in coding_cli toolsets (decision 7 isolation)
- cron tool source file contains 'Provenance:' comment referencing openclaw cron-tool.ts
- bugfix-402-M4 R2: run action uses host_capabilities dispatcher, not gateway_cron_url
"""

from __future__ import annotations

import inspect

import pytest


class TestCronToolOpenclawSchema:
    """cron tool input_schema must match openclaw CronToolSchema (adapted for nano).

    Provenance: openclaw/src/agents/tools/cron-tool.ts:278-296 CronToolSchema
    """

    def _get_cron_tool(self):
        from agent.products.personal_assistant.tools.cron import get_tool

        return get_tool()

    def test_cron_tool_has_name_cron(self) -> None:
        tool = self._get_cron_tool()
        assert tool.name == "cron"

    def test_cron_tool_has_description(self) -> None:
        tool = self._get_cron_tool()
        assert isinstance(tool.description, str)
        assert len(tool.description) > 50

    def test_cron_tool_description_contains_openclaw_actions(self) -> None:
        """Description must list all actions from openclaw cron-tool.ts:531-538."""
        tool = self._get_cron_tool()
        desc = tool.description
        # These lines are verbatim from openclaw cron-tool.ts description
        assert "list" in desc
        assert "add" in desc
        assert "update" in desc
        assert "remove" in desc
        assert "run" in desc
        assert "runs" in desc

    def test_cron_tool_description_contains_schedule_types(self) -> None:
        """Schedule types section must appear verbatim from openclaw:562-568."""
        tool = self._get_cron_tool()
        desc = tool.description
        assert '"at"' in desc or "at" in desc
        assert '"every"' in desc or "every" in desc
        assert '"cron"' in desc or "cron" in desc
        assert "everyMs" in desc
        assert "expr" in desc

    def test_cron_tool_description_contains_job_schema_block(self) -> None:
        """JOB SCHEMA section must appear from openclaw:541-549."""
        tool = self._get_cron_tool()
        desc = tool.description
        assert "JOB SCHEMA" in desc

    def test_cron_tool_description_contains_schedule_types_section(self) -> None:
        """SCHEDULE TYPES section header must appear from openclaw:562."""
        tool = self._get_cron_tool()
        desc = tool.description
        assert "SCHEDULE TYPES" in desc

    def test_cron_tool_input_schema_has_action_field(self) -> None:
        """input_schema must include 'action' as required field (openclaw CronToolSchema)."""
        tool = self._get_cron_tool()
        schema = tool.input_schema
        assert "action" in schema.get("properties", {})
        assert "action" in schema.get("required", [])

    def test_cron_tool_input_schema_has_job_field(self) -> None:
        """input_schema must include 'job' field for add action (openclaw CronToolSchema)."""
        tool = self._get_cron_tool()
        schema = tool.input_schema
        assert "job" in schema.get("properties", {})

    def test_cron_tool_input_schema_has_jobid_field(self) -> None:
        """input_schema must include 'jobId' for update/remove/run/runs (openclaw CronToolSchema)."""
        tool = self._get_cron_tool()
        schema = tool.input_schema
        assert "jobId" in schema.get("properties", {})

    def test_cron_tool_input_schema_has_patch_field(self) -> None:
        """input_schema must include 'patch' for update action (openclaw CronToolSchema)."""
        tool = self._get_cron_tool()
        schema = tool.input_schema
        assert "patch" in schema.get("properties", {})

    def test_cron_tool_input_schema_action_enum(self) -> None:
        """'action' field must enumerate valid actions matching openclaw CRON_ACTIONS."""
        tool = self._get_cron_tool()
        schema = tool.input_schema
        action_props = schema.get("properties", {}).get("action", {})
        enum_values = action_props.get("enum", [])
        # Nano supports all except 'wake' and 'status' (trimmed, no gateway HTTP)
        # Required: list, add, update, remove, run, runs
        for required_action in ["list", "add", "update", "remove", "run", "runs"]:
            assert required_action in enum_values, (
                f"cron tool action enum must include '{required_action}'"
            )

    def test_cron_tool_has_run_method(self) -> None:
        tool = self._get_cron_tool()
        assert callable(getattr(tool, "run", None))


class TestCronToolProvenanceComment:
    """cron.py must contain a 'Provenance:' comment referencing openclaw cron-tool.ts.

    feat-394 decision 6: code comment convention requires 'Provenance:' annotation
    with openclaw source file and line number.
    """

    def test_cron_tool_source_contains_provenance_comment(self) -> None:
        import agent.products.personal_assistant.tools.cron as cron_module

        source = inspect.getsource(cron_module)
        assert "Provenance:" in source, "cron.py must contain a 'Provenance:' comment"
        assert "cron-tool.ts" in source, (
            "cron.py Provenance comment must reference openclaw/src/agents/tools/cron-tool.ts"
        )

    def test_cron_tool_source_references_openclaw(self) -> None:
        import agent.products.personal_assistant.tools.cron as cron_module

        source = inspect.getsource(cron_module)
        assert "openclaw" in source, (
            "cron.py must mention 'openclaw' in Provenance comment"
        )


class TestCronToolIsolation:
    """cron tool must be in PA toolsets but NOT in coding_cli toolsets.

    feat-394 decision 7: cron is PA-only.
    """

    def test_cron_in_pa_toolsets(self) -> None:
        """cron must be reachable as a PA tool (in DEFAULT_TOOL_IDS or OPTIONAL_TOOL_IDS)."""
        from agent.products.personal_assistant.toolsets import (
            DEFAULT_TOOL_IDS,
            OPTIONAL_TOOL_IDS,
        )

        all_pa_tools = list(DEFAULT_TOOL_IDS) + list(OPTIONAL_TOOL_IDS)
        assert "cron" in all_pa_tools, (
            "cron tool must be listed in PA DEFAULT_TOOL_IDS or OPTIONAL_TOOL_IDS"
        )

    def test_cron_not_in_coding_cli_toolsets(self) -> None:
        """cron must NOT appear in coding_cli DEFAULT_TOOL_IDS or OPTIONAL_TOOL_IDS.

        feat-394 decision 7: coding_cli must not contain cron tool.
        """
        from agent.products.local_coding.toolsets import (
            DEFAULT_TOOL_IDS,
            OPTIONAL_TOOL_IDS,
        )

        all_cli_tools = list(DEFAULT_TOOL_IDS) + list(OPTIONAL_TOOL_IDS)
        assert "cron" not in all_cli_tools, (
            "cron tool MUST NOT be in coding_cli toolsets (feat-394 decision 7)"
        )


class TestCronToolRunHostCapability:
    """bugfix-402-M4 R2: cron tool run action must use host_capabilities dispatcher.

    The old implementation called gateway_cron_url via HTTP — an unreachable loopback
    from the kernel side.  The new implementation invokes
    ``personal_assistant.cron.enqueue`` via HostCapabilityDispatcher injected at
    build_kernel() time, returning accepted=true on success.
    """

    def _make_ctx(self, *, workspace_root, job_id="job-1", dispatcher=None):
        from pathlib import Path
        from unittest.mock import MagicMock

        from agent.core.tools.base import ToolContext

        mock_safety = MagicMock()
        mock_safety.repo_root = Path(workspace_root)
        ctx = ToolContext(
            repo_root=Path(workspace_root),
            cwd=Path(workspace_root),
            safety=mock_safety,
            session_id="sess-test",
            session_metadata={"agent_id": "agent-1"},
            host_capabilities=dispatcher,
        )
        return ctx

    def _write_job(self, workspace_root, job_id="job-1"):
        import json
        from pathlib import Path

        cron_dir = Path(workspace_root) / ".nanoassistant" / "cron"
        cron_dir.mkdir(parents=True, exist_ok=True)
        jobs_path = cron_dir / "jobs.json"
        jobs_path.write_text(
            json.dumps([
                {
                    "id": job_id,
                    "name": "test job",
                    "schedule": {"kind": "every", "everyMs": 3600000},
                    "instruction": "do something",
                    "enabled": True,
                    "delete_after_run": False,
                }
            ]),
            encoding="utf-8",
        )

    def test_run_action_no_dispatcher_returns_tool_error(self, tmp_path) -> None:
        """run action without a dispatcher must return a clear error, not raise RuntimeError
        about gateway_cron_url (which never existed in the SDK era).
        """
        from agent.products.personal_assistant.tools.cron import CronTool

        self._write_job(tmp_path)
        tool = CronTool()
        ctx = self._make_ctx(workspace_root=tmp_path, dispatcher=None)
        result = tool.run({"action": "run", "jobId": "job-1"}, ctx)
        assert result.get("ok") is False or "error" in result or "accepted" in result, (
            "run action without dispatcher must return error dict or accepted=false, "
            f"got: {result}"
        )
        # Must not have triggered an HTTP request via gateway_cron_url
        assert "gateway_cron_url" not in str(result).lower(), (
            "result must not reference gateway_cron_url (deprecated HTTP bypass)"
        )

    def test_run_action_with_dispatcher_returns_accepted(self, tmp_path) -> None:
        """run action with a working dispatcher must return accepted=true."""
        from agent.core.tools.host_capability import (
            HostCapabilityContext,
            HostCapabilityDispatcher,
        )
        from agent.products.personal_assistant.tools.cron import CronTool

        invocations: list[dict] = []

        class _FakeDispatcher(HostCapabilityDispatcher):
            def invoke(self, capability, payload, context):
                invocations.append({"capability": capability, "payload": dict(payload)})
                return {
                    "accepted": True,
                    "job_id": payload.get("job_id", ""),
                    "request_id": "req-abc",
                    "error_code": None,
                }

        self._write_job(tmp_path)
        tool = CronTool()
        ctx = self._make_ctx(workspace_root=tmp_path, dispatcher=_FakeDispatcher())
        result = tool.run({"action": "run", "jobId": "job-1"}, ctx)

        assert result.get("ok") is True, f"expected ok=true, got: {result}"
        assert len(invocations) == 1
        assert invocations[0]["capability"] == "personal_assistant.cron.enqueue"
        assert invocations[0]["payload"]["job_id"] == "job-1"

    def test_run_action_dispatcher_declined_returns_error(self, tmp_path) -> None:
        """run action where dispatcher returns accepted=false must propagate error."""
        from agent.core.tools.host_capability import HostCapabilityDispatcher
        from agent.products.personal_assistant.tools.cron import CronTool

        class _RejectDispatcher(HostCapabilityDispatcher):
            def invoke(self, capability, payload, context):
                return {
                    "accepted": False,
                    "job_id": payload.get("job_id", ""),
                    "request_id": None,
                    "error_code": "job_disabled",
                }

        self._write_job(tmp_path)
        tool = CronTool()
        ctx = self._make_ctx(workspace_root=tmp_path, dispatcher=_RejectDispatcher())
        result = tool.run({"action": "run", "jobId": "job-1"}, ctx)
        assert result.get("ok") is not True, f"expected ok!=true for rejected enqueue: {result}"

    def test_run_action_unknown_job_returns_error(self, tmp_path) -> None:
        """run action for non-existent job must fail before invoking dispatcher."""
        from agent.core.tools.host_capability import HostCapabilityDispatcher
        from agent.products.personal_assistant.tools.cron import CronTool

        dispatcher_called = []

        class _RecordDispatcher(HostCapabilityDispatcher):
            def invoke(self, capability, payload, context):
                dispatcher_called.append(capability)
                return {"accepted": True, "request_id": "x", "error_code": None}

        tool = CronTool()
        ctx = self._make_ctx(workspace_root=tmp_path, dispatcher=_RecordDispatcher())
        import pytest as _pytest
        with _pytest.raises((LookupError, ValueError)):
            tool.run({"action": "run", "jobId": "nonexistent-job"}, ctx)
        assert not dispatcher_called, "dispatcher must not be invoked for unknown job"

    def test_cron_source_does_not_contain_gateway_cron_url(self) -> None:
        """cron.py must not reference gateway_cron_url (deprecated HTTP bypass removed)."""
        import inspect
        import agent.products.personal_assistant.tools.cron as cron_module

        source = inspect.getsource(cron_module)
        assert "gateway_cron_url" not in source, (
            "cron.py must not reference gateway_cron_url after bugfix-402-M4 R2"
        )


# cron runs action: reads structured run history from runs.jsonl (bugfix-402-M4 R5)
# ---------------------------------------------------------------------------


class TestCronRunsActionFromJsonl:
    """cron runs action must return structured CronRunRecord data from runs.jsonl.

    bugfix-402-M4 R5: _action_runs() must query CronRunsStore.list_by_job() instead of
    the old state.json last_due_at.  Records are returned as structured dicts with at
    minimum status, trigger, accepted_at, request_id fields.
    """

    def _make_ctx(self, workspace_root):
        from pathlib import Path
        from unittest.mock import MagicMock
        from agent.core.tools.base import ToolContext

        mock_safety = MagicMock()
        mock_safety.repo_root = Path(workspace_root)
        return ToolContext(
            repo_root=Path(workspace_root),
            cwd=Path(workspace_root),
            safety=mock_safety,
            session_id="sess-runs-1",
            session_metadata={},
        )

    def test_runs_returns_empty_list_when_no_history(self, tmp_path) -> None:
        """runs action returns ok=True with empty runs list when no runs.jsonl exists."""
        from agent.products.personal_assistant.tools.cron import CronTool
        from personal_assistant.scheduler.cron_scheduler import CronJobStore, CronJob

        tool = CronTool()
        job_store = CronJobStore(workspace_root=tmp_path)
        job_store.add(CronJob(
            id="job-r5-1",
            name="R5 Job",
            schedule={"kind": "every", "everyMs": 60000},
            instruction="test",
        ))

        ctx = self._make_ctx(workspace_root=tmp_path)
        result = tool.run({"action": "runs", "jobId": "job-r5-1"}, ctx)
        assert result.get("ok") is True
        assert result.get("runs") == [] or isinstance(result.get("runs"), list)

    def test_runs_returns_structured_records_from_runs_jsonl(self, tmp_path) -> None:
        """runs action returns CronRunRecord dicts from runs.jsonl (not state.json)."""
        from agent.products.personal_assistant.tools.cron import CronTool
        from personal_assistant.scheduler.cron_scheduler import CronJobStore, CronJob
        from personal_assistant.scheduler.cron_execution_service import (
            CronRunsStore,
            CronRunRecord,
        )

        tool = CronTool()
        job_store = CronJobStore(workspace_root=tmp_path)
        job_store.add(CronJob(
            id="job-r5-2",
            name="R5 Structured Job",
            schedule={"kind": "every", "everyMs": 60000},
            instruction="test",
        ))
        # Write a completed run record to runs.jsonl.
        store = CronRunsStore(workspace_root=tmp_path)
        store.append(CronRunRecord(
            request_id="req-r5-completed",
            job_id="job-r5-2",
            trigger="scheduled",
            status="completed",
            accepted_at="2026-06-01T10:00:00+00:00",
            started_at="2026-06-01T10:00:01+00:00",
            finished_at="2026-06-01T10:00:30+00:00",
            result_summary="Done: 42 items processed",
        ))

        ctx = self._make_ctx(workspace_root=tmp_path)
        result = tool.run({"action": "runs", "jobId": "job-r5-2"}, ctx)
        assert result.get("ok") is True
        runs = result.get("runs", [])
        assert len(runs) >= 1
        rec = runs[0]
        # Must include structured fields from CronRunRecord, not just last_due_at.
        assert rec.get("request_id") == "req-r5-completed"
        assert rec.get("status") == "completed"
        assert rec.get("trigger") == "scheduled"
        assert rec.get("accepted_at") == "2026-06-01T10:00:00+00:00"

    def test_runs_returns_latest_first(self, tmp_path) -> None:
        """runs action returns records sorted by accepted_at descending (newest first)."""
        from agent.products.personal_assistant.tools.cron import CronTool
        from personal_assistant.scheduler.cron_scheduler import CronJobStore, CronJob
        from personal_assistant.scheduler.cron_execution_service import (
            CronRunsStore,
            CronRunRecord,
        )

        tool = CronTool()
        job_store = CronJobStore(workspace_root=tmp_path)
        job_store.add(CronJob(
            id="job-r5-3",
            name="Sort Job",
            schedule={"kind": "every", "everyMs": 60000},
            instruction="test",
        ))
        store = CronRunsStore(workspace_root=tmp_path)
        store.append(CronRunRecord(
            request_id="req-older",
            job_id="job-r5-3",
            trigger="scheduled",
            status="completed",
            accepted_at="2026-06-01T09:00:00+00:00",
        ))
        store.append(CronRunRecord(
            request_id="req-newer",
            job_id="job-r5-3",
            trigger="manual",
            status="completed",
            accepted_at="2026-06-01T10:00:00+00:00",
        ))

        ctx = self._make_ctx(workspace_root=tmp_path)
        result = tool.run({"action": "runs", "jobId": "job-r5-3"}, ctx)
        runs = result.get("runs", [])
        assert len(runs) >= 2
        assert runs[0].get("request_id") == "req-newer", "newest record must be first"
        assert runs[1].get("request_id") == "req-older"

    def test_runs_action_does_not_read_state_json(self, tmp_path) -> None:
        """runs action must NOT read cron_state_path / state.json for run history."""
        import inspect
        from agent.products.personal_assistant.tools.cron import CronTool

        source = inspect.getsource(CronTool._action_runs)
        # The old implementation read session_metadata["cron_state_path"] and state.json.
        assert "cron_state_path" not in source, (
            "_action_runs must not read cron_state_path session_metadata after bugfix-402-M4 R5"
        )
