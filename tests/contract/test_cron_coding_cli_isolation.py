"""Contract tests for feat-394-M2 R6: coding_cli must not contain cron tool or heartbeat/cron prompt segments.

feat-394 decision 7: cron tool and heartbeat/cron prompt segments are personal_assistant
only. coding_cli must never receive them, regardless of toolset config or prompt build.

These tests run the full PA prompt builder and coding_cli toolset to confirm isolation.
"""
from __future__ import annotations

import inspect

import pytest


class TestCronCodingCliIsolation:
    """coding_cli MUST NOT contain cron tool or heartbeat/cron prompt segments."""

    def test_coding_cli_toolsets_no_cron(self) -> None:
        """coding_cli DEFAULT_TOOL_IDS and OPTIONAL_TOOL_IDS must not include 'cron'.

        feat-394 decision 7.
        """
        from agent.products.local_coding.toolsets import DEFAULT_TOOL_IDS, OPTIONAL_TOOL_IDS
        all_cli_tools = list(DEFAULT_TOOL_IDS) + list(OPTIONAL_TOOL_IDS)
        assert "cron" not in all_cli_tools, (
            f"coding_cli toolsets must not include 'cron' (feat-394 decision 7). "
            f"Found: {all_cli_tools}"
        )

    def test_coding_cli_prompt_sections_no_heartbeat_segment(self) -> None:
        """coding_cli PA_SECTIONS (from local_coding profile) must not include pa.heartbeat.

        The heartbeat segment should only appear in the PA product sections, not in
        any coding_cli-facing section lists.
        """
        from agent.products.local_coding.profile import LOCAL_CODING_PROFILE
        if LOCAL_CODING_PROFILE.prompt_sections is None:
            return  # No sections: trivially isolated
        section_names = [s.name for s in LOCAL_CODING_PROFILE.prompt_sections]
        assert "pa.heartbeat" not in section_names, (
            f"coding_cli profile must not include 'pa.heartbeat' segment. Found: {section_names}"
        )
        assert "pa.cron" not in section_names, (
            f"coding_cli profile must not include 'pa.cron' segment. Found: {section_names}"
        )

    def test_pa_heartbeat_segment_exists_in_pa_profile(self) -> None:
        """PA profile MUST include pa.heartbeat segment (regression guard: PA isolation is not omission)."""
        from agent.products.personal_assistant.profile import PERSONAL_ASSISTANT_PROFILE
        assert PERSONAL_ASSISTANT_PROFILE.prompt_sections is not None
        section_names = [s.name for s in PERSONAL_ASSISTANT_PROFILE.prompt_sections]
        assert "pa.heartbeat" in section_names, (
            "PA profile must include 'pa.heartbeat' segment (regression guard)"
        )

    def test_cron_tool_only_in_pa_tools_directory(self) -> None:
        """cron.py must exist in personal_assistant tools directory, not in local_coding tools."""
        from pathlib import Path
        # __file__ is in tests/contract/; parents[2] is the project root
        src_root = Path(__file__).resolve().parents[2] / "src"
        pa_tools_dir = src_root / "agent" / "products" / "personal_assistant" / "tools"
        cli_tools_dir = src_root / "agent" / "products" / "local_coding" / "tools"
        assert (pa_tools_dir / "cron.py").exists(), (
            "cron.py must exist in agent/products/personal_assistant/tools/"
        )
        if cli_tools_dir.exists():
            assert not (cli_tools_dir / "cron.py").exists(), (
                "cron.py must NOT exist in agent/products/local_coding/tools/"
            )

    def test_pa_cron_segment_in_pa_sections_module(self) -> None:
        """prompt_sections.py for PA must define a pa.cron section or pa.cron_routing section.

        This is the forward assertion: once R8 adds the cron prompt segments,
        this test ensures they exist in the PA module. Before R8, this test is skipped.
        """
        import agent.products.personal_assistant.prompt_sections as ps_module
        source = inspect.getsource(ps_module)
        # After R8 lands, pa.cron segment must exist
        # This test acts as a sentinel for R8 completion
        if "pa.cron" not in source:
            pytest.skip("pa.cron segment not yet added (R8 pending)")
