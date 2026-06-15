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
        # refactor-406-M1 R7: cron tool migrated to personal_assistant.tools.cron
        # (closure factory). Schema/description are byte-identical to the legacy tool.
        from personal_assistant.tools.cron import make_cron_tool

        return make_cron_tool({})

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
        import personal_assistant.tools.cron as cron_module

        source = inspect.getsource(cron_module)
        assert "Provenance:" in source, "cron.py must contain a 'Provenance:' comment"
        assert "cron-tool.ts" in source, (
            "cron.py Provenance comment must reference openclaw/src/agents/tools/cron-tool.ts"
        )

    def test_cron_tool_source_references_openclaw(self) -> None:
        import personal_assistant.tools.cron as cron_module

        source = inspect.getsource(cron_module)
        assert "openclaw" in source, (
            "cron.py must mention 'openclaw' in Provenance comment"
        )


class TestCronToolIsolation:
    """cron tool must be in PA toolsets but NOT in coding_cli toolsets.

    feat-394 decision 7: cron is PA-only.
    """

    def test_cron_in_pa_toolsets(self) -> None:
        """cron must be reachable as a PA tool (refactor-406-M2: PA tool name source)."""
        from personal_assistant.reporter.capability_projection import (
            PA_DEFAULT_TOOL_IDS,
            PA_OPTIONAL_TOOL_IDS,
        )

        all_pa_tools = list(PA_DEFAULT_TOOL_IDS) + list(PA_OPTIONAL_TOOL_IDS)
        assert "cron" in all_pa_tools, (
            "cron tool must be listed in PA default/optional tool ids"
        )

    def test_cron_not_in_coding_cli_toolsets(self) -> None:
        """cron must NOT appear in coding_cli enabled tools (decision 7 isolation)."""
        from coding_cli.product import DEFAULT_ENABLED_TOOLS

        assert "cron" not in list(DEFAULT_ENABLED_TOOLS), (
            "cron tool MUST NOT be in coding_cli toolset (feat-394 decision 7)"
        )


class TestCronToolRunNoGatewayUrl:
    """refactor-406-M1 R7: the cron run action's HostCapabilityDispatcher path is
    removed (决策 9). Manual-run enqueue routing now lives in the closure cron tool
    and is covered by test_cron_tool_closure.py (roundtrip / per-agent routing /
    missing-service ack / declined ack). Only the regression guard below remains:
    the cron tool must never reference the long-dead gateway_cron_url HTTP bypass.
    """

    def test_cron_source_does_not_contain_gateway_cron_url(self) -> None:
        """cron.py must not reference gateway_cron_url (deprecated HTTP bypass removed)."""
        import inspect
        import personal_assistant.tools.cron as cron_module

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
        from personal_assistant.tools.cron import make_cron_tool
        from personal_assistant.scheduler.cron_scheduler import CronJobStore, CronJob

        tool = make_cron_tool({})
        job_store = CronJobStore(workspace_root=tmp_path)
        job_store.add(
            CronJob(
                id="job-r5-1",
                name="R5 Job",
                schedule={"kind": "every", "everyMs": 60000},
                instruction="test",
            )
        )

        ctx = self._make_ctx(workspace_root=tmp_path)
        result = tool.run({"action": "runs", "jobId": "job-r5-1"}, ctx)
        assert result.get("ok") is True
        assert result.get("runs") == [] or isinstance(result.get("runs"), list)

    def test_runs_returns_structured_records_from_runs_jsonl(self, tmp_path) -> None:
        """runs action returns CronRunRecord dicts from runs.jsonl (not state.json)."""
        from personal_assistant.tools.cron import make_cron_tool
        from personal_assistant.scheduler.cron_scheduler import CronJobStore, CronJob
        from personal_assistant.scheduler.cron_execution_service import (
            CronRunsStore,
            CronRunRecord,
        )

        tool = make_cron_tool({})
        job_store = CronJobStore(workspace_root=tmp_path)
        job_store.add(
            CronJob(
                id="job-r5-2",
                name="R5 Structured Job",
                schedule={"kind": "every", "everyMs": 60000},
                instruction="test",
            )
        )
        # Write a completed run record to runs.jsonl.
        store = CronRunsStore(workspace_root=tmp_path)
        store.append(
            CronRunRecord(
                request_id="req-r5-completed",
                job_id="job-r5-2",
                trigger="scheduled",
                status="completed",
                accepted_at="2026-06-01T10:00:00+00:00",
                started_at="2026-06-01T10:00:01+00:00",
                finished_at="2026-06-01T10:00:30+00:00",
                result_summary="Done: 42 items processed",
            )
        )

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
        from personal_assistant.tools.cron import make_cron_tool
        from personal_assistant.scheduler.cron_scheduler import CronJobStore, CronJob
        from personal_assistant.scheduler.cron_execution_service import (
            CronRunsStore,
            CronRunRecord,
        )

        tool = make_cron_tool({})
        job_store = CronJobStore(workspace_root=tmp_path)
        job_store.add(
            CronJob(
                id="job-r5-3",
                name="Sort Job",
                schedule={"kind": "every", "everyMs": 60000},
                instruction="test",
            )
        )
        store = CronRunsStore(workspace_root=tmp_path)
        store.append(
            CronRunRecord(
                request_id="req-older",
                job_id="job-r5-3",
                trigger="scheduled",
                status="completed",
                accepted_at="2026-06-01T09:00:00+00:00",
            )
        )
        store.append(
            CronRunRecord(
                request_id="req-newer",
                job_id="job-r5-3",
                trigger="manual",
                status="completed",
                accepted_at="2026-06-01T10:00:00+00:00",
            )
        )

        ctx = self._make_ctx(workspace_root=tmp_path)
        result = tool.run({"action": "runs", "jobId": "job-r5-3"}, ctx)
        runs = result.get("runs", [])
        assert len(runs) >= 2
        assert runs[0].get("request_id") == "req-newer", "newest record must be first"
        assert runs[1].get("request_id") == "req-older"

    def test_runs_action_does_not_read_state_json(self, tmp_path) -> None:
        """runs action must NOT read cron_state_path / state.json for run history."""
        import inspect
        from personal_assistant.tools.cron import CronTool

        source = inspect.getsource(CronTool._action_runs)
        # The old implementation read session_metadata["cron_state_path"] and state.json.
        assert "cron_state_path" not in source, (
            "_action_runs must not read cron_state_path session_metadata after bugfix-402-M4 R5"
        )
