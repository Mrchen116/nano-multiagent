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

```bash
python3 -m nano_multiagent.cli.main \
  --base-url http://127.0.0.1:8000 \
  --token test-token
```

If you are not using editable install, run with `PYTHONPATH=src`:

```bash
PYTHONPATH=src python3 -m nano_multiagent.cli.main --base-url http://127.0.0.1:8000 --token test-token
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

### Non-interactive commands

```bash
python3 -m nano_multiagent.cli.main --base-url http://127.0.0.1:8000 --token test-token health
python3 -m nano_multiagent.cli.main --base-url http://127.0.0.1:8000 --token test-token create-session --title "demo"
python3 -m nano_multiagent.cli.main --base-url http://127.0.0.1:8000 --token test-token send-message --session-id <session_id> --text "hello"
```

### Environment variables

- `NANO_MULTIAGENT_API_BASE_URL` (default `http://127.0.0.1:8000`)
- `NANO_MULTIAGENT_API_TOKEN` (required for protected endpoints)
- `NANO_MULTIAGENT_REQUEST_ID` (optional)
- `NANO_MULTIAGENT_SESSION_ID` (optional default session for `send-message` and REPL startup)
- `NANO_MULTIAGENT_API_TIMEOUT_SECONDS` (default `30`)

### Troubleshooting

If your shell has `http_proxy`/`https_proxy` set, local API calls to `127.0.0.1` may fail via proxy.
For this CLI, localhost/127.0.0.1 is automatically treated as direct connection.
If needed, also set:

```bash
export NO_PROXY=127.0.0.1,localhost
```
