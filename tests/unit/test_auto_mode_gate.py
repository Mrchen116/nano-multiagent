"""Tests for auto_mode_gate: system prompt assembly, transcript construction, XML parsing.

Allowlist, tool projection, gate setup, hook logic are in separate files:
- test_auto_mode_gate_allowlist.py
- test_auto_mode_gate_hook.py
"""

from __future__ import annotations

import re
from typing import Any, Mapping
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agent.platform.config.auto_mode import AutoModeConfig
from agent.platform.hooks.builtins.auto_mode_gate import (
    BASE_PROMPT,
    EXTERNAL_PERMISSIONS_TEMPLATE,
    SAFE_TOOL_ALLOWLIST,
    TOOL_PROJECTIONS,
    build_transcript_entries,
    build_yolo_system_prompt,
    is_safe_tool,
    parse_xml_block,
    parse_xml_reason,
    project_tool_input,
    setup as gate_setup,
    strip_thinking,
)
from agent.platform.permissions.broker import PermissionBroker


# ---------------------------------------------------------------------------
# System prompt three-layer assembly
# ---------------------------------------------------------------------------

class TestBuildYoloSystemPrompt:
    def test_base_prompt_embedded_in_output(self):
        cfg = AutoModeConfig()
        prompt = build_yolo_system_prompt(cfg)
        # The base prompt contains the core classification instruction
        assert "automated security classifier" in prompt
        assert "BLOCK" in prompt
        assert "ALLOW" in prompt

    def test_permissions_template_substituted(self):
        cfg = AutoModeConfig()
        prompt = build_yolo_system_prompt(cfg)
        # permissions_template placeholder should be replaced
        assert "<permissions_template>" not in prompt
        # Default rules from external permissions template should appear
        assert "Allow Rules" in prompt
        assert "Deny Rules" in prompt

    def test_user_allow_rules_replace_defaults(self):
        cfg = AutoModeConfig(allow=("my custom allow rule",))
        prompt = build_yolo_system_prompt(cfg)
        assert "my custom allow rule" in prompt
        # The tags themselves should be gone
        assert "<user_allow_rules_to_replace>" not in prompt

    def test_user_deny_rules_replace_defaults(self):
        cfg = AutoModeConfig(soft_deny=("never delete production db",))
        prompt = build_yolo_system_prompt(cfg)
        assert "never delete production db" in prompt

    def test_user_environment_replaces_defaults(self):
        cfg = AutoModeConfig(environment=("Rust project using cargo",))
        prompt = build_yolo_system_prompt(cfg)
        assert "Rust project using cargo" in prompt

    def test_empty_user_rules_keep_defaults(self):
        """Empty user rules should preserve the default text in the template."""
        cfg = AutoModeConfig()  # no user rules
        prompt = build_yolo_system_prompt(cfg)
        # Default allow rule from permissions_external template
        assert "Running read-only shell commands" in prompt or "read-only" in prompt.lower()

    def test_xml_output_format_replaces_tool_use_line(self):
        """The classify_result tool line must be replaced with XML format."""
        cfg = AutoModeConfig()
        prompt = build_yolo_system_prompt(cfg)
        assert "classify_result" not in prompt
        assert "<block>yes</block>" in prompt
        assert "<block>no</block>" in prompt
        assert "## Output Format" in prompt

    def test_classify_result_line_not_present(self):
        cfg = AutoModeConfig()
        prompt = build_yolo_system_prompt(cfg)
        assert "Use the classify_result tool" not in prompt


# ---------------------------------------------------------------------------
# Transcript construction
# ---------------------------------------------------------------------------

class TestBuildTranscriptEntries:
    def _make_user_msg(self, text: str) -> dict:
        return {"role": "user", "content": text}

    def _make_assistant_text_msg(self, text: str) -> dict:
        return {"role": "assistant", "content": text}

    def _make_assistant_tool_use(self, name: str, inp: dict) -> dict:
        return {
            "role": "assistant",
            "content": [{"type": "tool_use", "id": "t1", "name": name, "input": inp}],
        }

    def _make_assistant_mixed(self, text: str, tool_name: str, tool_inp: dict) -> dict:
        return {
            "role": "assistant",
            "content": [
                {"type": "text", "text": text},
                {"type": "tool_use", "id": "t2", "name": tool_name, "input": tool_inp},
            ],
        }

    def test_user_text_included(self):
        msgs = [self._make_user_msg("please list files")]
        entries = build_transcript_entries(msgs)
        assert len(entries) == 1
        assert entries[0]["role"] == "user"
        assert entries[0]["content"] == "please list files"

    def test_assistant_text_excluded(self):
        """Assistant text blocks must be excluded (prevents prompt injection)."""
        msgs = [self._make_assistant_text_msg("I will now run ls")]
        entries = build_transcript_entries(msgs)
        assert len(entries) == 0

    def test_assistant_tool_use_included(self):
        msgs = [self._make_assistant_tool_use("bash", {"command": "ls"})]
        entries = build_transcript_entries(msgs)
        assert len(entries) == 1
        assert entries[0]["role"] == "assistant"
        assert entries[0]["content"][0]["name"] == "bash"

    def test_assistant_mixed_content_only_tool_use(self):
        """Mixed assistant message: only tool_use should appear in transcript."""
        msgs = [self._make_assistant_mixed("thinking text", "bash", {"command": "ls -la"})]
        entries = build_transcript_entries(msgs)
        assert len(entries) == 1
        assert entries[0]["role"] == "assistant"
        # Only tool_use block
        for block in entries[0]["content"]:
            assert block["type"] == "tool_use"

    def test_list_content_user_message(self):
        """User messages with list content extract text blocks."""
        msgs = [
            {"role": "user", "content": [{"type": "text", "text": "hello world"}, {"type": "image", "source": {}}]}
        ]
        entries = build_transcript_entries(msgs)
        # Should get user entry with text
        user_entries = [e for e in entries if e["role"] == "user"]
        assert len(user_entries) == 1
        assert "hello world" in user_entries[0]["content"]

    def test_tool_results_excluded(self):
        """Tool result messages (role='tool') are not included."""
        msgs = [
            {"role": "tool", "content": "output", "tool_use_id": "t1"}
        ]
        entries = build_transcript_entries(msgs)
        assert len(entries) == 0

    def test_ordering_preserved(self):
        msgs = [
            self._make_user_msg("first"),
            self._make_assistant_tool_use("bash", {"command": "ls"}),
            self._make_user_msg("second"),
        ]
        entries = build_transcript_entries(msgs)
        assert entries[0]["role"] == "user"
        assert entries[1]["role"] == "assistant"
        assert entries[2]["role"] == "user"


# ---------------------------------------------------------------------------
# Two-stage XML classification helpers
# ---------------------------------------------------------------------------

class TestXmlParsing:
    def test_parse_block_no(self):
        assert parse_xml_block("<block>no</block>") is False

    def test_parse_block_yes(self):
        assert parse_xml_block("<block>yes</block>") is True

    def test_parse_block_yes_no_close_tag(self):
        # CC uses stop_sequences=['</block>'] so stage 1 may lack closing tag
        assert parse_xml_block("<block>no") is False
        assert parse_xml_block("<block>yes") is True

    def test_parse_block_case_insensitive(self):
        assert parse_xml_block("<block>YES</block>") is True
        assert parse_xml_block("<block>NO</block>") is False

    def test_parse_block_none_on_missing(self):
        assert parse_xml_block("No tags here") is None
        assert parse_xml_block("") is None

    def test_strip_thinking_removes_thinking_block(self):
        text = "<thinking>this should be removed</thinking><block>no</block>"
        stripped = strip_thinking(text)
        assert "thinking" not in stripped
        assert "<block>no</block>" in stripped

    def test_parse_block_skips_thinking_content(self):
        """Tags inside <thinking> must not be matched."""
        text = "<thinking><block>yes</block></thinking><block>no</block>"
        assert parse_xml_block(text) is False

    def test_parse_reason(self):
        text = "<block>yes</block><reason>deletes important files</reason>"
        assert parse_xml_reason(text) == "deletes important files"

    def test_parse_reason_none_on_missing(self):
        assert parse_xml_reason("<block>no</block>") is None

    def test_parse_reason_strips_thinking(self):
        text = "<thinking><reason>fake</reason></thinking><reason>real reason</reason>"
        assert parse_xml_reason(text) == "real reason"
