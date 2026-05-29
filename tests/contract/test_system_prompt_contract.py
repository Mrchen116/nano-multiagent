from agent.core.agent.prompting import DEFAULT_SYSTEM_PROMPT, build_prompt_messages

# CODING_SYSTEM_PROMPT retired: coding content now assembled from prompt_sections
# in agent/products/local_coding/prompt_sections.py (segment-based assembly).

_FIXTURE = (
    "You are an expert coding assistant operating inside a coding agent harness.\n\n"
    "Available tools:\n<RUNTIME_FILL:AVAILABLE_TOOLS>\n\n"
    "In addition to the tools above, you may have access to other custom tools.\n\n"
    "Guidelines:\n- Be helpful\n\n"
    "Current date and time: <RUNTIME_FILL:CURRENT_DATETIME>\n"
    "Current working directory: <RUNTIME_FILL:CURRENT_WORKING_DIRECTORY>"
)


def test_default_system_prompt_is_empty_string_after_feat385() -> None:
    # Empty string is the sentinel for segment assembly; ProductProfile sets this
    # and the runtime detects it to switch from the legacy string-template path.
    assert DEFAULT_SYSTEM_PROMPT == ""


def test_system_prompt_contract_build_prompt_messages_renders_fixture() -> None:
    # Verify build_prompt_messages still renders RUNTIME_FILL placeholders and
    # strips input_schema — the contract is on build_prompt_messages, not the constant.
    system_prompt = build_prompt_messages(
        history_messages=(), user_text="ping", system_prompt=_FIXTURE
    )[0].content

    assert "You are an expert coding assistant operating inside a coding agent harness." in system_prompt
    assert "Available tools:" in system_prompt
    assert "Guidelines:" in system_prompt
    assert "Current date and time:" in system_prompt
    assert "Current working directory:" in system_prompt
    assert "<RUNTIME_FILL:" not in system_prompt
    assert "input_schema" not in system_prompt
