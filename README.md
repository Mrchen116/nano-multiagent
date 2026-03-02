# nano-multiagent

## Quick start

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

```bash
export NANO_MULTIAGENT_API_TOKEN=test-token
uvicorn nano_multiagent.server.app:app --reload
```

If you are not using editable install, run server with:

```bash
PYTHONPATH=src uvicorn nano_multiagent.server.app:app --reload
```

## CLI

### Start CLI (interactive REPL)

Managed mode (CLI starts/stops local API automatically):

```bash
python3 -m nano_multiagent.cli.main \
  --mode managed \
  --base-url http://127.0.0.1:8000 \
  --token test-token
```

Managed mode can inject LLM runtime config into the managed API process:

```bash
python3 -m nano_multiagent.cli.main \
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
python3 -m nano_multiagent.cli.main \
  --mode remote \
  --base-url http://127.0.0.1:8000 \
  --token test-token
```

If you are not using editable install, run with `PYTHONPATH=src`:

```bash
PYTHONPATH=src python3 -m nano_multiagent.cli.main --mode remote --base-url http://127.0.0.1:8000 --token test-token
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

REPL will also print session context budget after each message turn and after `/compact`:

- `Context budget: <used>/<max> (<ratio>%)`
- threshold hints at `>=70%`, `>=85%`, `>=95%` to suggest compaction timing
- budget fetch failures are fail-open (`Context budget: unavailable ...`) and do not interrupt chat flow

### Non-interactive commands

```bash
python3 -m nano_multiagent.cli.main --mode remote --base-url http://127.0.0.1:8000 --token test-token health
python3 -m nano_multiagent.cli.main --mode remote --base-url http://127.0.0.1:8000 --token test-token create-session --title "demo"
python3 -m nano_multiagent.cli.main --mode remote --base-url http://127.0.0.1:8000 --token test-token send-message --session-id <session_id> --text "hello"
python3 -m nano_multiagent.cli.main --mode remote --base-url http://127.0.0.1:8000 --token test-token llm-config get
python3 -m nano_multiagent.cli.main --mode remote --base-url http://127.0.0.1:8000 --token test-token llm-config set --provider anthropic --model claude-3-5-sonnet-20241022 --base-url http://127.0.0.1:4100 --timeout-seconds 60
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
