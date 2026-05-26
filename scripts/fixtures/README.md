# LLM Upstream Fixtures

Tiny single-file HTTP stubs used to drive nano-multiagent's "LLM upstream
error → user-readable" code paths(bugfix-380)without burning real provider
quota or rigging a flaky proxy.

Each script binds 127.0.0.1:`<port>`,handles a single request, and exits on
Ctrl-C. None of them require dependencies beyond Python stdlib.

## Available stubs

| Script | Failure mode | Resulting `ModelError` |
|---|---|---|
| `anthropic_sse_error.py` | Anthropic-format `event: error\ndata: {"type":"error",...}` SSE frame | `retryable=False`, ~1s fail |
| `openai_compat_error.py` | OpenAI-format top-level `data: {"error":{...}}` SSE frame | `retryable=False`, ~1s fail |
| `http_error.py <port> <code>` | HTTP 401 / 403 / 429 / 500 / 502 / 503 response | `retryable=False`(non-2xx),~1s fail |
| `slow_stream.py <port> truncate` | Opens stream, writes partial `message_start`, closes before `message_stop` | `retryable=True`("stream ended without terminal event"),进 retry 循环 |
| `slow_stream.py <port> hang` | Holds socket open without writing — triggers client read timeout | `retryable=True`,进 retry 循环 |

## Wiring into kernel

```bash
# 1. Start fixture (default port shown; pass arg to override)
python3 scripts/fixtures/anthropic_sse_error.py 19998 &

# 2. Point kernel LLM at it
export NANO_MULTIAGENT_LLM_PROVIDER=anthropic
export NANO_MULTIAGENT_LLM_BASE_URL=http://127.0.0.1:19998
# (model name can be any string — the fixture ignores it)

# 3. Start kernel API
PYTHONPATH=src python -m uvicorn agent.platform.http_api.app:app --port 8000

# 4. Any kernel chat → fixture replies error → agent surfaces ⚠️ to IM/CLI
```

## Why this exists

bugfix-380 retro(`docs/changes/bugfix-380-llm-upstream-error-visible/retro.md`)
showed worker/reviewer wasted ~30% of fix-worker-r3 wall-clock试错 anthropic
SSE error frame format. Specifically, naive stubs would emit `data: {"error": ...}`
without the leading `event: error` line, and the kernel client treats the
chunk as an unknown frame type → falls through to "stream ended without
terminal event" (`retryable=True`) → 20-retry storm → false impression that
the fix is broken.

These stubs encode the correct wire-protocol shape so any e2e scenario can
trigger the exact `ModelError` variant it wants without re-discovering the
spec each time.

## What this is not

- **Not** a load-test tool. Single-shot serve, then idle.
- **Not** a happy-path mock. If you need to test successful streaming,
  write a fixture provider that produces real `content_block_*` / `message_stop`
  frames — that's a different artifact.
- **Not** automatically wired by `scripts/e2e-up.sh`. The e2e bootstrap
  scripts start IM/Kernel/Gateway only; fixtures are independent tools you
  start manually when you want to inject failures.
