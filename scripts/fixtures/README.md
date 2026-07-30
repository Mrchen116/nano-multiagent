# Runtime Failure Fixtures

Small deterministic harnesses used to drive failure paths without damaging a real provider or relying on timing races. HTTP fixtures use only the Python stdlib; the Gateway wrapper uses the repository environment.

Each HTTP script binds 127.0.0.1:`<port>`, handles a single request, and exits on Ctrl-C. None of them require dependencies beyond Python stdlib.

## Available stubs

| Script | Failure mode | Resulting `ModelError` |
|---|---|---|
| `anthropic_sse_error.py` | Anthropic-format `event: error\ndata: {"type":"error",...}` SSE frame | `retryable=False`, ~1s fail |
| `anthropic_sse_ok_recording.py` | Anthropic-format happy-path SSE; records each POST body to `NANO_FIXTURE_RECORD_PATH` | none (returns `ACK-<n>` text) |
| `openai_compat_error.py` | OpenAI-format top-level `data: {"error":{...}}` SSE frame | `retryable=False`, ~1s fail |
| `http_error.py <port> <code>` | HTTP 401 / 403 / 429 / 500 / 502 / 503 response | `retryable=False`(non-2xx),~1s fail |
| `slow_stream.py <port> truncate` | Opens stream, writes partial `message_start`, closes before `message_stop` | `retryable=True`("stream ended without terminal event"),进 retry 循环 |
| `slow_stream.py <port> hang` | Holds socket open without writing — triggers client read timeout | `retryable=True`,进 retry 循环 |
| `channel_cache_commit_failure.py <Gateway args>` | First channel-removal cache commit fails; same-process retry is normal | Removal remains failed/retryable until the real retry endpoint replays the same revision |

## Wiring into a product runtime

```bash
# 1. Start fixture (default port shown; pass arg to override)
python3 scripts/fixtures/anthropic_sse_error.py 19998 &

# 2. Copy the persistent config so the validation run stays isolated
cp ~/.nano-assistant/config.yaml .fixture-gateway-config.yaml

# 3. Point an Anthropic provider in that copy at the fixture
yq -i '(.llm.providers[] | select(.name == "anthropic") | .base_url) = "http://127.0.0.1:19998"' \
  .fixture-gateway-config.yaml

# 4. Start a real product entry and send a user message
PYTHONPATH=src python -m personal_assistant.main \
  --config .fixture-gateway-config.yaml --foreground
# The fixture replies with an error and the product surfaces it to IM.
```

## Why this exists

bugfix-380 retro(`docs/changes/archive/bugfix-380-llm-upstream-error-visible/retro.md`) showed worker/reviewer wasted ~30% of fix-worker-r3 wall-clock试错 anthropic SSE error frame format. Specifically, naive stubs would emit `data: {"error": ...}` without the leading `event: error` line, and the kernel client treats the chunk as an unknown frame type → falls through to "stream ended without terminal event" (`retryable=True`) → 20-retry storm → false impression that the fix is broken.

These stubs encode the correct wire-protocol shape so any e2e scenario can trigger the exact `ModelError` variant it wants without re-discovering the spec each time.

`channel_cache_commit_failure.py` is additionally gated by `NANO_MULTIAGENT_TEST_ALLOW_FAULT_INJECTION=1`. It monkeypatches only the Gateway cache-store seam before delegating to the production entrypoint, and only for the first manifest containing a removal. Use it with a worktree-local config and database; a disabled channel is sufficient, so no real provider is contacted.

## What this is not

- **Not** a load-test tool. Single-shot serve, then idle.
- **Not** a substitute for the live-proxy critical-path suite. Happy-path recording lives in ``anthropic_sse_ok_recording.py`` for deterministic process-level e2e that must inspect request bodies without burning tokens.
- **Not** automatically wired by `scripts/e2e-up.sh`. The e2e bootstrap scripts start IM/Gateway only; fixtures are independent tools you start manually when you want to inject failures.
