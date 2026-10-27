# Runtime Test Fixtures

## Recording Anthropic stub

`anthropic_sse_ok_recording.py` is the deterministic fake-LLM process used by
the shared `tests/e2e/critical_paths/_recording.py` stack. It accepts Anthropic
`/messages` requests, records each request body to `NANO_FIXTURE_RECORD_PATH`, and
returns a valid streaming response without contacting a real provider.

Run it only through the owning critical-path fixture. The fixture allocates an
isolated port, redirects a copied Gateway config, owns the process lifetime, and
removes its runtime state after the test. The critical-path suite uses local recording providers throughout. These tests
prove system contracts, not model comprehension or autonomous planning.

## Tool approval routing stub

`anthropic_sse_tool_approval_recording.py` is owned by
`test_tool_approval_model_critical_path.py`. It records each request together with
whether it is a normal Agent call or an auto-permission classifier call, returns a
deterministic `write` tool use for each new user turn, and returns a final ACK after
the tool result. Native Guardian calls normally return `{"outcome":"allow"}`; model
`approval-fail` returns unparseable content so the real attended permission path can
be tested without an alternate-model fallback.

## Knowledge regression

The retired Python kernel replay fixtures were removed with that runtime.
`scripts/e2e-self-evolution.sh` now runs the real native DSH profile and product
handoff regressions. It does not start a full IM stack. Actual full-stack and
external-channel evidence is recorded in the change acceptance record.

## Deterministic critical-path responses

- `anthropic_sse_compaction_recording.py`: actual read result, tool pairing, summary
  request, and context after compaction/restart. The test verifies the file result
  independently of the fixture's final text.
- `anthropic_sse_group_recording.py`: fixed A-to-B mention and a non-mention reply;
  real IM/Node admission determines which Agent actually calls the provider.
- `anthropic_sse_send_revalidation_recording.py`: concurrent model-response gates
  hold stale group sends while actual peer messages arrive. Counts are derived
  only from real Inbox tool results; the test checks held/sent results, message
  IDs and bodies in subsequent provider requests, including repeated invalidation.
- `anthropic_sse_events_recording.py`: real shell jobs, cancellation, one-shot
  schedule and heartbeat delivery. Only provider responses are scripted.
- `anthropic_sse_collaboration_recording.py`: real child execution/failure and
  cross-chat Inbox amendment forwarding to the same child, followed by delivery.

Each case owns its isolated processes and captures actual HTTP requests. Fixtures
never forward to an upstream provider, mutate product databases, or fabricate Work
records. Manual real-model acceptance remains separate (`e2e-up.sh --profile daily`).
