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

## Automatic review recovery faults and trace export

`anthropic_sse_auto_review_retry.py` is owned by
`tests/e2e/critical_paths/test_auto_review_retry_critical_path.py`. The owning test
allocates a loopback port, passes `NANO_FIXTURE_RECORD_PATH`, creates its own
IM/Node/DSH runtime through `e2e-up.sh --main-config`, and always stops both stack
and fixture. The `RETRY_CASE=<nano|codex>-<fault>` user marker selects the case;
`main` emits one `bash` append and then an ACK, while `review` injects actual HTTP
503/429 (seconds/date), socket disconnect, invalid verdict, 401, excessive delay,
persistent/mixed failure, cancellation or production-budget timeout. `nano` is
the existing audit rule label for the CC strategy, not a new selectable policy.
CC-only `stage2-service`, `stage2-timeout` and `stage-exhaust` exercise valid stage
advancement without resetting the shared quota. `config-request` and
`config-backoff` expose actual configuration-transaction release barriers.

Run from the unit checkout after the normal build (Python 3.11+ dev environment):

```bash
# No live-provider opt-in is needed: the fixture never contacts a real vendor.
env -u ALL_PROXY -u HTTP_PROXY -u HTTPS_PROXY -u all_proxy -u http_proxy -u https_proxy \
  NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 \
  .venv/bin/python -m pytest \
  tests/e2e/critical_paths/test_auto_review_retry_critical_path.py -q
```

The tests use complete default 30/60/90-second review budgets and a 420-second
per-journey observation window; their 1800-second suite allowance is intentional.
They are a deterministic supplement, not the real-provider `daily` journey.
Request records may contain test prompts and stay local/ignored.

`export_review_trace.py --runtime <explicit-isolated-root> --sha <build-sha>
[--call-id <id>] [--session <id>]` reads only that root's `nano_approval` v1 JSON
domain tables, including old rows without recovery fields. It exports allowlisted
audit facts and relative source locators, not verdict reasons, prompt entries,
configuration, credentials or delegated evidence. It does not connect to a live
Session or restore it. The caller supplies the exact build SHA; the diagnostic
cannot attest a build by itself. Exported data is evidence, never authorization.

## Knowledge regression

The retired Python kernel replay fixtures were removed with that runtime.
`scripts/e2e-self-evolution.sh` now runs the real native DSH profile and product
handoff regressions. It does not start a full IM stack. Actual full-stack and
external-channel evidence is recorded in the change acceptance record.
