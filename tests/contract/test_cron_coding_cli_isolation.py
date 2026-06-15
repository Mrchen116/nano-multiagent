"""Contract: coding_cli must not contain the cron tool or heartbeat/cron prompt segments.

feat-394 decision 7: cron tool and heartbeat/cron prompt segments are personal_assistant
only. coding_cli must never receive them. refactor-406-M2: products/ dissolved — the
isolation is now checked against the production factories (coding_cli.product /
personal_assistant.product) and the live tool name sources.
"""

from __future__ import annotations

from pathlib import Path


class TestCronCodingCliIsolation:
    """coding_cli MUST NOT contain cron tool or heartbeat/cron prompt segments."""

    def test_coding_cli_toolset_no_cron(self) -> None:
        """coding_cli enabled tools must not include 'cron' (feat-394 decision 7)."""
        from coding_cli.product import DEFAULT_ENABLED_TOOLS

        assert "cron" not in list(DEFAULT_ENABLED_TOOLS), (
            f"coding_cli toolset must not include 'cron' (decision 7). "
            f"Found: {list(DEFAULT_ENABLED_TOOLS)}"
        )

    def test_coding_cli_prompt_no_heartbeat_or_cron_segment(self) -> None:
        """coding_cli production PromptSlots must not contain pa.heartbeat / pa.cron text."""
        from coding_cli.product import cli_prompt_slots

        slots = cli_prompt_slots()
        names = {
            pt.name
            for group in (slots.head, slots.body, slots.custom, slots.tail)
            for pt in group
        }
        assert "pa.heartbeat" not in names, (
            f"coding_cli prompt must not include 'pa.heartbeat' segment. Found: {names}"
        )
        assert "pa.cron" not in names, (
            f"coding_cli prompt must not include 'pa.cron' segment. Found: {names}"
        )

    def test_pa_heartbeat_segment_present_in_pa_prompt(self) -> None:
        """PA prompt MUST include pa.heartbeat when heartbeat is enabled (isolation ≠ omission)."""
        from personal_assistant.product import prompt_for

        class _Agent:
            cron_enabled = True
            heartbeat_enabled = True
            custom_prompt = None

        slots = prompt_for(_Agent())
        names = {pt.name for pt in slots.body}
        assert "pa.heartbeat" in names, (
            "PA prompt must include 'pa.heartbeat' segment when heartbeat enabled "
            "(regression guard)"
        )

    def test_cron_tool_only_in_pa_tools_directory(self) -> None:
        """cron.py must live in src/personal_assistant/tools/, not under src/coding_cli/.

        refactor-406-M1 R7 (决策 9): PA's cron tool is supplied via build_kernel(tools=…).
        """
        src_root = Path(__file__).resolve().parents[2] / "src"
        pa_tools_dir = src_root / "personal_assistant" / "tools"
        cli_dir = src_root / "coding_cli"
        assert (pa_tools_dir / "cron.py").exists(), (
            "cron.py must exist in src/personal_assistant/tools/"
        )
        assert not (cli_dir / "tools" / "cron.py").exists(), (
            "cron.py must NOT exist under src/coding_cli/"
        )
