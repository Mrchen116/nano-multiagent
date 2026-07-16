# M8 live evidence — cron failed terminal

Date: 2026-07-16

## Scope and boundary

This run validates the live-critical M8 cron failure path with the real product composition: isolated IM, foreground Gateway, in-process Kernel, Gateway polling, `CronExecutionService`, stream delivery, and owner-direct IM persistence. The only fake component is the documented `scripts/fixtures/anthropic_sse_error.py` upstream, used to deterministically produce a provider failure; it is not presented as a successful LLM run.

The evidence worktree started from `origin/unit/refactor-463` at `efd9d2d19`. That unit head contained M7 and M8. M6 was still an independent pending milestone branch, so this run does not claim M6 combination coverage.

No private service call or direct runs database write was used for sign-off. Job creation/history used the product `CronTool` `add`/`runs` actions; user-visible state used authenticated IM HTTP APIs.

## Isolated topology

| Component | Endpoint / PID | Evidence |
|---|---|---|
| Failure fixture | `127.0.0.1:65446`, PID `9706` | `anthropic_sse_error.py`; Anthropic SSE `event: error` |
| IM | `127.0.0.1:49277`, PID `22814` | real `python -m uvicorn IM.app:app` |
| Gateway + Kernel | PID `22851` | real `python -m personal_assistant.main --foreground --auto-bind`; Kernel is in-process |
| Owner direct conversation | `c584a3f0cba04591bc2bbbb77f5d8d8d` | authenticated IM conversation/messages APIs |

The runtime used a worktree-local config and workspace. The Anthropic provider base URL was changed only in the isolated config. The IM mirror initially published empty feature overrides, so cron was enabled through the public agent-config PATCH (`features.cron_scheduling=true`, profile version `1 -> 2`); a subsequent `source=live` GET returned the same enabled feature.

## Commands

Start the deterministic fixture and real stack:

```bash
/Users/czj/Repos/nano-multiagent/.venv/bin/python \
  scripts/fixtures/anthropic_sse_error.py 65446

PATH=/Users/czj/Repos/nano-multiagent/.venv/bin:$PATH \
  ./scripts/e2e-up.sh --main-config \
  /Users/czj/Repos/nano-multiagent/.worktrees/refactor-463-M8-evidence/.fixture-main-config.yaml
```

The stack reported IM port `49277`; `ps` and `lsof` confirmed both product processes and both listening ports before the run.

An authenticated IM POST created the owner/`default-agent` direct conversation. A normal user-message POST established its canonical Gateway session. The fixture made that seed run visibly fail, so it could not create a false successful baseline.

Create the scheduled job through the product cron tool:

```python
from pathlib import Path
from personal_assistant.tools.cron import make_cron_tool

class Ctx:
    repo_root = Path(".gateway-workspace/default-agent").resolve()
    session_metadata = {"agent_id": "default-agent"}
    session_id = "live-evidence-add"

make_cron_tool({}).run(
    {
        "action": "add",
        "job": {
            "name": "M8 deterministic failed cron",
            "schedule": {"kind": "every", "everyMs": 600000},
            "payload": {
                "kind": "agentTurn",
                "message": "Return a visible cron result; fixture will fail deterministically.",
            },
            "enabled": True,
        },
    },
    Ctx(),
)
```

The `add` result was:

```json
{"jobId":"4ae226db064f4e9cabf506abea0ca506","ok":true}
```

The authenticated public cron-jobs GET returned that exact enabled job. The real Gateway polling loop admitted it on the next tick; `CronTool` `runs` first returned `status="running"` with `trigger="scheduled"` and a real Kernel run ID, then the terminal condition poll returned the record below.

## Public terminal history

`make_cron_tool({}).run({"action":"runs","jobId":...}, Ctx())` returned:

```json
{
  "jobId": "4ae226db064f4e9cabf506abea0ca506",
  "ok": true,
  "runs": [
    {
      "accepted_at": "2026-07-16T09:00:33.665031+00:00",
      "error": "anthropic: model overloaded - anthropic_sse_error.py fixture (refactor-381)",
      "finished_at": "2026-07-16T09:02:53.819818+00:00",
      "job_id": "4ae226db064f4e9cabf506abea0ca506",
      "kernel_run_id": "run_b33c25fcd10a6bd9",
      "request_id": "99842e667dbd4008a7fa8d41303aecc6",
      "result_summary": "⚠️ 模型调用失败:anthropic: model overloaded - anthropic_sse_error.py fixture (refactor-381)",
      "started_at": "2026-07-16T09:00:33.665340+00:00",
      "status": "failed",
      "target_conversation_id": null,
      "trigger": "scheduled"
    }
  ]
}
```

This is a real failed terminal, not a stream exception converted to completed and not a pending run left behind.

## Owner-visible result and awareness guard

After the cron record reached `failed`, authenticated `GET /im/v1/conversations` returned the direct conversation as `run_state="idle"`. `GET /im/v1/conversations/c584a3f0cba04591bc2bbbb77f5d8d8d/messages` returned exactly:

```json
[
  {
    "id": "ffeabfbe2d614a19952f2184214e44df",
    "sender_type": "user",
    "content": "seed canonical direct session; deterministic fixture failure expected",
    "delivery_status": "failed"
  },
  {
    "id": "324494a7785548718ad925afa5e9ab74",
    "sender_type": "agent",
    "content": "⚠️ 模型调用失败:anthropic: model overloaded - anthropic_sse_error.py fixture (refactor-381)",
    "delivery_status": "failed"
  },
  {
    "id": "b7e12133913f422095ee0c8cf91a31b7",
    "sender_type": "agent",
    "content": "⚠️ 模型调用失败:anthropic: model overloaded - anthropic_sse_error.py fixture (refactor-381)",
    "delivery_status": "failed"
  }
]
```

The last agent row is the cron delivery. There is no completed/sent success bubble and no successful cron-awareness message in the owner direct conversation; the only cron-visible result is explicitly failed.

## Other M8 controlled evidence

Typed shadow identity and unattended skill-scope regression evidence was refreshed on the same unit head:

```bash
PYTHONPATH=src /Users/czj/Repos/nano-multiagent/.venv/bin/python -m pytest -q \
  tests/unit/personal_assistant/test_gateway_shadow_sync.py \
  tests/unit/personal_assistant/test_inbound_shadow_identity_guard.py \
  tests/unit/personal_assistant/test_unattended_session_skills.py
```

Result: `8 passed`. The shadow cases cover typed-only external sync, adapter-level IM-origin guard, runtime-metadata stripping, and legacy fallback. No live Feishu dependency is needed for those deterministic adapter boundaries.

## Cleanup evidence

The evidence job was removed through the authenticated public cron-jobs DELETE path; the following public GET reported `remaining_matching_jobs=0`. Then `scripts/e2e-down.sh` stopped Gateway before IM, and the fixture foreground process received `SIGINT`.

Final checks:

```text
port_49277=closed
port_65446=closed
pid_22814=stopped
pid_22851=stopped
pid_9706=stopped
.im.pid=removed
.gateway.pid=removed
.e2e-ports.env=removed
.gateway-config.yaml=removed
```

The generated fixture config, logs, databases, and isolated agent workspace were removed before committing this evidence.

