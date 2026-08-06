# Runtime Test Fixtures

## Recording Anthropic stub

`anthropic_sse_ok_recording.py` is the deterministic fake-LLM process used by
`test_agent_config_context_continuity_critical_path.py`. It accepts Anthropic
`/messages` requests, records each request body to `NANO_FIXTURE_RECORD_PATH`, and
returns a valid streaming response without contacting a real provider.

Run it only through the owning critical-path fixture. The fixture allocates an
isolated port, redirects a copied Gateway config, owns the process lifetime, and
removes its runtime state after the test. It is not a substitute for the live-proxy
critical-path suite.

## Tool approval routing stub

`anthropic_sse_tool_approval_recording.py` is owned by
`test_tool_approval_model_critical_path.py`. It records each request together with
whether it is a normal Agent call or an auto-permission classifier call, returns a
deterministic `write` tool use for each new user turn, and returns a final ACK after
the tool result. Classifier calls normally return `<block>no</block>`; model
`approval-fail` returns unparseable content so the real attended permission path can
be tested without an alternate-model fallback.
