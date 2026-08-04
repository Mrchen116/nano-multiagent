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
