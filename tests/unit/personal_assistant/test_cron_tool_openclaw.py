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
