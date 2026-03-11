from agent.core.agent.prompting import CODING_SYSTEM_PROMPT, build_prompt_messages


def test_system_prompt_contract_matches_runtime_template_sections() -> None:
    # CODING_SYSTEM_PROMPT must be passed explicitly; DEFAULT_SYSTEM_PROMPT is now "".
    system_prompt = build_prompt_messages(
        history_messages=(), user_text="ping", system_prompt=CODING_SYSTEM_PROMPT
    )[0].content

    assert "You are an expert coding assistant operating inside a coding agent harness." in system_prompt
    assert "Available tools:" in system_prompt
    assert "In addition to the tools above" in system_prompt
    assert "Guidelines:" in system_prompt
    assert "Current date and time:" in system_prompt
    assert "Current working directory:" in system_prompt
    assert "<RUNTIME_FILL:" not in system_prompt
    assert "input_schema" not in system_prompt
    assert "read" in system_prompt
    assert "bash" in system_prompt
