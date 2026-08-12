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

## Self-evolution acceptance fixtures

`openai_self_evolution_recording.py` drives the two deterministic real-stack
self-evolution journeys owned by `scripts/e2e-self-evolution.sh`. It selects
responses only from explicit fixture state, request index, message roles, and the
latest tool result ID; it never matches the private review prompt text. Its control
state proves that a review branch ran, while product assertions come from the real
IM HTTP/WebSocket relay.

`self_evolution_gateway_replay_fault.py` delegates to the production Gateway entry
after installing one fixture-process-only stream fault. The fault occurs before the
marked self-evolution `skill_created` event is yielded, so the persistent subscriber
must reconnect and replay the same sequence. It does not change production routing
or expose user-visible diagnostics.
