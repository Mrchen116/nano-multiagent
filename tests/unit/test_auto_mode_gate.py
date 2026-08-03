"""Tests for auto_mode_gate: system prompt assembly, transcript construction, XML parsing.

Allowlist, tool projection, gate setup, hook logic are in separate files:
- test_auto_mode_gate_allowlist.py
- test_auto_mode_gate_hook.py
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from agent.core.llm.interfaces import LLMMessage, LLMToolCall
from agent.platform.config.auto_mode import AutoModeConfig
from agent.platform.hooks.builtins.auto_mode_gate import (
    build_transcript_entries,
    build_yolo_system_prompt,
    parse_xml_block,
    parse_xml_reason,
    strip_thinking,
)


# ---------------------------------------------------------------------------
# System prompt three-layer assembly
# ---------------------------------------------------------------------------


class TestBuildYoloSystemPrompt:
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
        assert (
            "Running read-only shell commands" in prompt
            or "read-only" in prompt.lower()
        )

    def test_xml_output_format_replaces_tool_use_line(self):
        """The classify_result tool line must be replaced with XML format."""
        cfg = AutoModeConfig()
        prompt = build_yolo_system_prompt(cfg)
        assert "classify_result" not in prompt
        assert "<block>yes</block>" in prompt
        assert "<block>no</block>" in prompt
        assert "## Output Format" in prompt

# ---------------------------------------------------------------------------
# Transcript construction
# ---------------------------------------------------------------------------


class TestBuildTranscriptEntries:
    """Transcript construction fed the *real* kernel format.

    bugfix-410 #99: the prior fixtures fed Anthropic-shaped dicts
    (`content:[{type:tool_use}]`) which matched the old code and stayed green,
    but the runtime feeds `message_history` real `LLMMessage` objects whose tool
    calls live in the separate `tool_calls` field (`loop.py:359`). These fixtures
    use the kernel format so a regression to "only read content blocks" goes red.
    """

    def _make_user_msg(self, text: str) -> LLMMessage:
        return LLMMessage(role="user", content=text)

    def _make_assistant_text_msg(self, text: str) -> LLMMessage:
        return LLMMessage(role="assistant", content=text)

    def _make_assistant_tool_use(self, name: str, inp: dict) -> LLMMessage:
        # Kernel format: assistant text in `content`, calls in `tool_calls`.
        return LLMMessage(
            role="assistant",
            content="",
            tool_calls=(LLMToolCall(call_id="t1", name=name, arguments=inp),),
        )

    def _make_assistant_mixed(
        self, text: str, tool_name: str, tool_inp: dict
    ) -> LLMMessage:
        # Kernel format: free text coexists with the tool call on the same turn.
        return LLMMessage(
            role="assistant",
            content=text,
            tool_calls=(LLMToolCall(call_id="t2", name=tool_name, arguments=tool_inp),),
        )

    def test_user_text_included(self):
        msgs = [self._make_user_msg("please list files")]
        entries = build_transcript_entries(msgs)
        assert len(entries) == 1
        assert entries[0]["role"] == "user"
        assert entries[0]["content"] == "please list files"

    def test_assistant_text_excluded(self):
        """Assistant text-only turn must be excluded (prevents prompt injection)."""
        msgs = [self._make_assistant_text_msg("I will now run ls")]
        entries = build_transcript_entries(msgs)
        assert len(entries) == 0

    def test_assistant_tool_use_included(self):
        msgs = [self._make_assistant_tool_use("bash", {"command": "ls"})]
        entries = build_transcript_entries(msgs)
        assert len(entries) == 1
        assert entries[0]["role"] == "assistant"
        assert entries[0]["content"][0]["name"] == "bash"
        assert entries[0]["content"][0]["input"] == {"command": "ls"}

    def test_assistant_mixed_content_only_tool_use(self):
        """Mixed turn (text + tool call): only the tool call enters the transcript."""
        msgs = [
            self._make_assistant_mixed("thinking text", "bash", {"command": "ls -la"})
        ]
        entries = build_transcript_entries(msgs)
        assert len(entries) == 1
        assert entries[0]["role"] == "assistant"
        # Only tool_use block, and the free text must not leak in
        for block in entries[0]["content"]:
            assert block["type"] == "tool_use"
        assert "thinking text" not in str(entries)

    def test_kernel_tool_calls_field_extracted(self):
        """#99 regression: tool calls in the kernel `tool_calls` field must project.

        This is the exact false-green the prior Anthropic-shaped fixtures hid:
        a real assistant turn keeps its calls in `tool_calls`, with `content` as
        plain text. Reading only `content` would yield an empty transcript here.
        """
        msgs = [
            LLMMessage(
                role="assistant",
                content="let me read then edit",
                tool_calls=(
                    LLMToolCall(
                        call_id="c1", name="read", arguments={"file_path": "a.py"}
                    ),
                    LLMToolCall(
                        call_id="c2",
                        name="edit",
                        arguments={"file_path": "a.py", "new_string": "x"},
                    ),
                ),
            )
        ]
        entries = build_transcript_entries(msgs)
        assert len(entries) == 1
        blocks = entries[0]["content"]
        assert [b["name"] for b in blocks] == ["read", "edit"]
        assert blocks[0]["input"] == {"file_path": "a.py"}
        assert blocks[1]["input"]["new_string"] == "x"

    def test_anthropic_content_format_still_supported(self):
        """CC-shaped `content:[{type:tool_use}]` path remains authoritative."""
        msgs = [
            {
                "role": "assistant",
                "content": [
                    {
                        "type": "tool_use",
                        "id": "t1",
                        "name": "bash",
                        "input": {"command": "ls"},
                    },
                ],
            }
        ]
        entries = build_transcript_entries(msgs)
        assert len(entries) == 1
        assert entries[0]["content"][0]["name"] == "bash"

    def test_list_content_user_message(self):
        """User messages with list content extract text blocks."""
        msgs = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "hello world"},
                    {"type": "image", "source": {}},
                ],
            }
        ]
        entries = build_transcript_entries(msgs)
        # Should get user entry with text
        user_entries = [e for e in entries if e["role"] == "user"]
        assert len(user_entries) == 1
        assert "hello world" in user_entries[0]["content"]

    def test_tool_results_excluded(self):
        """Tool result messages (role='tool') are not included."""
        msgs = [{"role": "tool", "content": "output", "tool_use_id": "t1"}]
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
# bugfix-456: tool-owned classifier projection
# ---------------------------------------------------------------------------


class TestToolOwnedClassifierProjection:
    """Classifier prompt must use registered tool projection, not a central table."""

    def test_skill_manage_create_current_action_is_projected(self):
        from agent.platform.hooks.builtins.auto_mode_gate import (
            _build_transcript_user_message,
        )
        from agent.platform.tools.builtins.bash import BashTool
        from agent.platform.tools.builtins.skill_manage import SkillManageTool

        bash_tool = BashTool()
        skill_tool = SkillManageTool(
            skill_root=Path("/tmp/skills"), registry=MagicMock()
        )

        class Registry:
            def get(self, name: str):
                return {"bash": bash_tool, "skill_manage": skill_tool}.get(name)

        ctx = MagicMock()
        ctx.metadata = {"tool_registry": Registry()}
        ctx.message_history = (
            LLMMessage(
                role="assistant",
                content="",
                tool_calls=(
                    LLMToolCall(
                        call_id="old-danger",
                        name="bash",
                        arguments={"command": "rm -rf cold-joke-on-insult"},
                    ),
                ),
            ),
        )

        current_projection = skill_tool.to_auto_classifier_input(
            {
                "action": "create",
                "name": "cold-joke-on-insult",
                "scope": "workspace",
                "content": "---\nname: cold-joke-on-insult\n---\n\n# Body",
            }
        )
        prompt = _build_transcript_user_message(ctx, "skill_manage", current_projection)

        assert '"command": "rm -rf cold-joke-on-insult"' in prompt
        assert "skill_manage" in prompt
        assert "action=create" in prompt
        assert "name=cold-joke-on-insult" in prompt
        assert "scope=workspace" in prompt


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


# ---------------------------------------------------------------------------
# bugfix-369: 门禁分类器不得继承主 agent thinking
# ---------------------------------------------------------------------------


class TestClassifyActionThinkingDisabled:
    """_classify_action 的 call_model 调用必须显式关闭 thinking。

    根因：model_registry 将 thinking: adaptive 挂在模型元数据上，client.generate
    对所有调用无差别 merge，导致门禁 stage-1 64-token 被 reasoning 吃空。
    修复方向：门禁调用显式传 extra_body={"thinking": {"type": "disabled"}}。
    """

    def _make_ctx(self, stage1_content: str = "<block>no</block>") -> MagicMock:
        ctx = MagicMock()
        ctx.session_id = "test-session"
        ctx.call_model = AsyncMock(return_value=MagicMock(content=stage1_content))
        return ctx

    @pytest.mark.asyncio
    async def test_stage1_call_model_passes_thinking_disabled_extra_body(self):
        """stage-1 call_model 必须携带 extra_body 显式关闭 thinking（bugfix-369 不变性）。"""
        from agent.platform.hooks.builtins.auto_mode_gate import _classify_action

        ctx = self._make_ctx(stage1_content="<block>no</block>")
        await _classify_action(ctx, "sys", "user")

        call_kwargs = ctx.call_model.call_args_list[0]
        extra_body = call_kwargs.kwargs.get("extra_body")
        assert extra_body is not None, (
            "stage-1 call_model 没有传 extra_body，thinking 未被显式关闭"
        )
        thinking = extra_body.get("thinking", {})
        assert thinking.get("type") == "disabled", (
            f"stage-1 extra_body.thinking.type 应为 'disabled'，实际为 {thinking!r}"
        )

    @pytest.mark.asyncio
    async def test_stage2_call_model_passes_thinking_disabled_extra_body(self):
        """stage-2 call_model 也必须携带 extra_body 关闭 thinking。"""
        from agent.platform.hooks.builtins.auto_mode_gate import _classify_action

        ctx = self._make_ctx()
        # stage-1 返回 yes → 触发 stage-2
        ctx.call_model = AsyncMock(return_value=MagicMock(content="<block>yes</block>"))
        await _classify_action(ctx, "sys", "user")

        assert ctx.call_model.call_count == 2, "stage-1 block 应触发 stage-2"
        for i, call in enumerate(ctx.call_model.call_args_list):
            extra_body = call.kwargs.get("extra_body")
            assert extra_body is not None, f"stage-{i + 1} call_model 没有传 extra_body"
            thinking = extra_body.get("thinking", {})
            assert thinking.get("type") == "disabled", (
                f"stage-{i + 1} extra_body.thinking.type 应为 'disabled'，实际 {thinking!r}"
            )

    @pytest.mark.asyncio
    async def test_stage1_empty_content_fails_closed_ask(self):
        """stage-1 content 为空（thinking 吃光 token 时的现象）→ fail-closed → ask。

        这是 bugfix-369 的 regression 测试：确保空 content 不会绕过门禁。
        """
        from agent.platform.hooks.builtins.auto_mode_gate import _classify_action

        ctx = self._make_ctx(stage1_content="")
        decision = await _classify_action(ctx, "sys", "user")
        assert decision.behavior == "ask", (
            "stage-1 content 为空应 fail-closed → ask，但实际返回了 allow/deny"
        )
