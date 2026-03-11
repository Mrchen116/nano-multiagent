# nano-multiagent

## Quick start

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## IM Frontend

- 运行说明、API/Mock 边界、M38 验收截图索引见：`src/IM/frontend/README.md`

```bash
export NANO_MULTIAGENT_API_TOKEN=test-token
uvicorn agent.platform.http_api.app:app --reload
```

If you are not using editable install, run server with:

```bash
PYTHONPATH=src uvicorn agent.platform.http_api.app:app --reload
```

## CLI

### Start CLI (interactive REPL)

Managed mode (CLI starts/stops local API automatically):

```bash
python3 -m coding_cli.coding_cli.main \
  --mode managed \
  --base-url http://127.0.0.1:8000 \
  --token test-token
```

Managed mode can inject LLM runtime config into the managed API process:

```bash
python3 -m coding_cli.coding_cli.main \
  --mode managed \
  --base-url http://127.0.0.1:8000 \
  --token test-token \
  --llm-provider anthropic \
  --llm-model claude-3-5-sonnet-20241022 \
  --llm-base-url http://127.0.0.1:4100 \
  --llm-api-key <key> \
  --llm-timeout-seconds 60
```

`managed` mode uses a higher default API timeout (`120s`) to reduce false timeouts during real agent turns. Override with `--api-timeout-seconds`.

Remote mode (connect existing API, never starts local process):

```bash
python3 -m coding_cli.coding_cli.main \
  --mode remote \
  --base-url http://127.0.0.1:8000 \
  --token test-token
```

If you are not using editable install, run with `PYTHONPATH=src`:

```bash
PYTHONPATH=src python3 -m coding_cli.coding_cli.main --mode remote --base-url http://127.0.0.1:8000 --token test-token
```

### REPL commands

- `/help`
- `/new`
- `/use <session_id>`
- `/session`
- `/tools`
- `/compact`
- `/history [n]`
- `/exit`

### CLI module boundary

- `main.py`: 仅负责 CLI 进程入口（调用 `run_cli`）。
- `commands.py`: 稳定入口编排层（参数解析、模式决策、REPL 主循环、错误分层）。
- `repl_input.py`: 可编辑输入与历史回填实现（行内编辑、方向键、草稿恢复）。
- `repl_commands.py`: REPL 斜杠命令路由与参数校验（`/help /new /use ...`）。
- `http_client.py`: 唯一 HTTP 边界（CLI 不直接依赖 runtime/tool/session/llm 内核实现）。

开发约定（收口门禁）：

- 保持 HTTP-only：CLI 只能通过 `ServerClient` 访问 API。
- 避免空转发层：不要在 `commands.py` 里重新导出 `repl_input/repl_commands` 的内部实现。
- 保持脚本机读稳定：非交互子命令 stdout 必须输出 single final JSON object on stdout。

Interactive input ergonomics:

- inline editing with `←/→` + Backspace
- history recall with `↑/↓` (session-scoped), and draft restore when navigating back down
- type `/` to open command dropdown, use `↑/↓` to switch, press `Enter` to fill selected command

REPL will also print session context budget after each message turn and after `/compact`:

- `Context budget: <used>/<max> (<ratio>%)`
- `Context budget (after /compact): <used>/<max> (<ratio>%)`
- threshold hints at `>=70%`, `>=85%`, `>=95%` to suggest compaction timing
- budget fetch failures are fail-open (`Context budget: unavailable ...`) and do not interrupt chat flow

Error output is layered and actionable:

- REPL errors include `Layer: input|network|runtime` plus `Suggestion`
- non-interactive command failures keep JSON shape and include `layer`, e.g. `{"error":"...","layer":"network","suggestion":"..."}`.

### Release observability helpers

Use `release_observability` to translate perf snapshots into actionable diagnostics:

```bash
PYTHONPATH=src python3 - <<'PY'
from coding_cli.coding_cli.release_observability import summarize_perf_metrics, build_guardrail_hints

metrics = {
    "batches": 3,
    "polled_events": 120,
    "consumed_events": 96,
    "preview_emitted": 12,
    "run_filtered": 18,
    "dedupe_dropped": 6,
    "throughput_ratio": 0.8,
    "redraw_ratio": 0.125,
    "sample_ready": True,
    "throughput_ok": True,
    "redraw_ratio_ok": True,
    "stable": True,
    "guardrail_reason": "ok",
}
print("\n".join(summarize_perf_metrics(metrics)))
print("\n".join(build_guardrail_hints(metrics)))
PY
```

### Release acceptance & rollback playbook

Render release steps without executing them:

```bash
PYTHONPATH=src python3 -m coding_cli.coding_cli.release_playbook \
  --base-url http://127.0.0.1:8003 \
  --token test-token
```

Execute acceptance steps (CLI gate + managed smoke):

```bash
PYTHONPATH=src python3 -m coding_cli.coding_cli.release_playbook \
  --base-url http://127.0.0.1:8003 \
  --token test-token \
  --execute
```

Playbook output is JSON and includes:

- `acceptance_steps`: required pre-release checks.
- `rollback_steps`: rollback command template list.
- `status`: `pending` / `passed` / `failed`.
- `execution`: per-step return code and captured stdout/stderr when `--execute` is set.

### Non-interactive commands

```bash
python3 -m coding_cli.coding_cli.main --mode remote --base-url http://127.0.0.1:8000 --token test-token health
python3 -m coding_cli.coding_cli.main --mode remote --base-url http://127.0.0.1:8000 --token test-token create-session --title "demo"
python3 -m coding_cli.coding_cli.main --mode remote --base-url http://127.0.0.1:8000 --token test-token send-message --session-id <session_id> --text "hello"
python3 -m coding_cli.coding_cli.main --mode remote --base-url http://127.0.0.1:8000 --token test-token llm-config get
python3 -m coding_cli.coding_cli.main --mode remote --base-url http://127.0.0.1:8000 --token test-token llm-config set --provider anthropic --model claude-3-5-sonnet-20241022 --base-url http://127.0.0.1:4100 --timeout-seconds 60
```

### Environment variables

- `NANO_MULTIAGENT_CLI_MODE` (`managed` or `remote`, default `remote`)
- `NANO_MULTIAGENT_API_BASE_URL` (default `http://127.0.0.1:8000`)
- `NANO_MULTIAGENT_API_TOKEN` (required for protected endpoints)
- `NANO_MULTIAGENT_REQUEST_ID` (optional)
- `NANO_MULTIAGENT_SESSION_ID` (optional default session for `send-message` and REPL startup)
- `NANO_MULTIAGENT_API_TIMEOUT_SECONDS` (default `30`)
- `--api-timeout-seconds <float>` (CLI override for current run)
- managed startup LLM overrides: `--llm-provider`, `--llm-model`, `--llm-base-url`, `--llm-api-key`, `--llm-timeout-seconds`

### Troubleshooting

If your shell has `http_proxy`/`https_proxy` set, local API calls to `127.0.0.1` may fail via proxy.
For this CLI, localhost/127.0.0.1 is automatically treated as direct connection.
If needed, also set:

```bash
export NO_PROXY=127.0.0.1,localhost
```

Common mode-specific diagnostics:

- `managed` + `port ... already in use`:
  - Free the port, use another local `--base-url` port, or switch to `--mode remote`.
- `managed` + startup timeout / startup failed:
  - Check local uvicorn/python environment and startup logs, then retry.
- `remote` + `connection refused`:
  - Verify `--base-url` points to a running remote API and that the endpoint is reachable from your machine.
