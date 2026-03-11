"""Verify core/agent is the canonical home for shared agent runtime modules."""

from importlib.util import find_spec

from agent.core.agent import (
    AgentLoop,
    AgentPolicies,
    AgentRuntime,
    AgentState,
    DEFAULT_SYSTEM_PROMPT,
    InputPart,
    build_prompt_messages,
    parse_input_parts,
    render_user_text,
)
from agent.core.agent.loop import AgentLoop as CoreAgentLoop
from agent.core.agent.policies import AgentPolicies as CoreAgentPolicies
from agent.core.agent.prompting import (
    DEFAULT_SYSTEM_PROMPT as CoreDefaultSystemPrompt,
)
from agent.core.agent.prompting import build_prompt_messages as CoreBuildPromptMessages
from agent.core.agent.runtime import AgentRuntime as CoreAgentRuntime
from agent.core.agent.state import AgentState as CoreAgentState
from agent.core.agent.state import InputPart as CoreInputPart
from agent.core.agent.state import parse_input_parts as CoreParseInputParts
from agent.core.agent.state import render_user_text as CoreRenderUserText


def test_core_agent_is_canonical_home() -> None:
    assert AgentLoop is CoreAgentLoop
    assert AgentPolicies is CoreAgentPolicies
    assert AgentRuntime is CoreAgentRuntime
    assert AgentState is CoreAgentState
    assert InputPart is CoreInputPart
    assert DEFAULT_SYSTEM_PROMPT == CoreDefaultSystemPrompt
    assert build_prompt_messages is CoreBuildPromptMessages
    assert parse_input_parts is CoreParseInputParts
    assert render_user_text is CoreRenderUserText

    assert AgentLoop.__module__ == "agent.core.agent.loop"
    assert AgentPolicies.__module__ == "agent.core.agent.policies"
    assert AgentRuntime.__module__ == "agent.core.agent.runtime"
    assert AgentState.__module__ == "agent.core.agent.state"
    assert InputPart.__module__ == "agent.core.agent.state"
    assert build_prompt_messages.__module__ == "agent.core.agent.prompting"
    assert parse_input_parts.__module__ == "agent.core.agent.state"
    assert render_user_text.__module__ == "agent.core.agent.state"


def test_legacy_nano_multiagent_root_is_removed() -> None:
    assert find_spec("nano_multiagent") is None
