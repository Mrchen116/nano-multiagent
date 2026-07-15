# nano-multiagent

## Quick start
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## Start Here: 先启动 IM，再启动 Gateway，然后打开聊天

默认用户路径只需要一条链路：先启动 IM 服务，再启动 Gateway；如果浏览器出现绑定页就完成绑定；最后回到 Web IM 发起第一条聊天消息。

首次启动时，你只需要关心三件事：
- IM 是否已经可打开：浏览器访问 `http://127.0.0.1:8011/` 能进入聊天入口。
- Gateway 是否已经 ready：终端出现绑定下一步，或保持常驻等待消息。
- 接下来该做什么：未绑定就完成绑定；已绑定就直接聊天。

### 1. 启动 IM 服务

```bash
cd <repo>
PYTHONPATH=src python -m uvicorn IM.app:app \
  --host 0.0.0.0 --port 8011
```

默认 Web IM 入口：
- `http://127.0.0.1:8011/`：推荐入口
- `http://127.0.0.1:8011/chat`：直接进入聊天页

你会看到的 ready 信号：
- 打开 `http://127.0.0.1:8011/` 时，页面会进入 Web IM，而不是要求你先知道前端 dev server。
- 如果仓内已带 `src/IM/frontend/dist`，IM host 会直接服务 `/`、`/chat`、`/settings/*`、`/bind/confirm`。

### 2. 准备最小 Gateway 配置

```yaml
node:
  node_id: my-macbook

agents:
  - agent_id: assistant
    title: My Assistant

channels:
  - name: web_relay
    enabled: true

im_service:
  url: http://<im-host>:8011

llm:
  default_model: kimiCoding:K2.6
  providers:
    - name: anthropic
      base_url: http://127.0.0.1:4000
      models:
        - name: kimiCoding:K2.6
```

说明：
- `im_service.url` 应填写 Gateway 实际要连接的 IM 服务地址；可以是本机，也可以是远端内网/公网地址。
- 临时覆盖某次启动的 IM 地址时，可在命令行追加 `--im-service-url http://<im-host>:8011`。
- 省略 `agents[].workspace_root` 时，默认使用 `~/nano-assistant/workspace/<agent_id>/`，并在首次加载配置时自动创建目录。
- `llm` 段为必填；上例假定本机已有 LLM 代理监听在 `127.0.0.1:4000`。

### 3. 启动 Gateway

```bash
cd <repo>
PYTHONPATH=src python -m personal_assistant.main
# 或显式指定远端 IM
PYTHONPATH=src python -m personal_assistant.main --im-service-url http://<im-host>:8011
```

默认命令会把 Gateway 放到后台，并立即返回：

```text
Gateway started (pid=<pid>)
IM service:      http://<im-host>:8011  [connected|unavailable (running offline, will retry)]
Log:             <config目录>/gateway.log
```

这只确认后台子进程已写出带 process birth 的运行态并仍存活，不代表 runtime/channel ready。
IM 连接、节点绑定和 channel 启动结果仍需查看 `gateway.log` 或 Web IM 节点状态。

启动后的预期行为：
- 未绑定节点：Gateway 会把 `ACTION ...` / `NEXT ...` 写入 `gateway.log`，并尝试打开绑定页；默认绑定页位于 `http://127.0.0.1:8011/bind/confirm?token=...`。
- 已绑定节点：Gateway 保持后台运行，等待 Web IM 消息。
- 启动失败或 IM bootstrap 失败：Gateway 会输出明确的 `ERROR ...` / `NEXT ...`；同样的可执行提示会回写到 IM 节点板 `last_error`。

停止当前配置对应的后台 Gateway：

```bash
PYTHONPATH=src python -m personal_assistant.main stop
```

重启（stop + start）：

```bash
PYTHONPATH=src python -m personal_assistant.main restart
# 或显式指定远端 IM
PYTHONPATH=src python -m personal_assistant.main restart --im-service-url http://<im-host>:8011
```

**单实例保护**：同一 config 同一时刻只允许运行一个 Gateway 实例。`start` / `stop` / `restart`
由 config 同目录的一把 lifecycle lock 串行化；PID 和 birth identity 原子记录在唯一的
`.gateway-state.json` 中。若已有实例在运行，`start` 会拒绝启动并提示当前 PID：

```text
ERROR gateway already running (pid=<pid>). Run `stop` first or `restart` to replace it.
```

stop 反馈语义：
- `STOPPED ...`：后台 Gateway 已关闭；若优雅等待超时会额外显示 `forced=true`。
- `NOT RUNNING ...`：没有可用运行态记录，可直接重新 start。
- `STALE ...`：记录里的 pid 已失效；CLI 会自动清掉陈旧状态文件，然后你可以重新 start。

你会看到的 ready 信号：
- 默认路径下，终端先打印 `Gateway started (pid=...)` 并返回；随后可查看 `gateway.log` 或 Web IM/绑定页确认 Gateway 已 ready。
- 若使用 `--foreground` 调试路径，终端会保持常驻，并直接显示 `ACTION ...` / `NEXT ...`。
- 如果终端打印 `ERROR ...` / `NEXT ...`，不要先翻代码；直接按 `NEXT` 的动作处理即可。

### 4. 进入 Web IM 并发起聊天

- 打开 `http://127.0.0.1:8011/`。IM host 会提供 Web IM 壳，并在浏览器里落到 `/chat`。
- Web IM 会自动准备本地 `You` 用户和默认 starter conversation；正常用户不需要手工创建用户、会话或拼 `message` API。
- 如果未绑定，composer 会直接禁用，并显示统一的 `Chat unavailable` 卡片，提示先完成 Gateway 绑定。
- 如果已绑定但 Gateway 离线，composer 仍会保持禁用，并显示同一套 `Chat unavailable` 卡片，明确要求 bring the node online or bind another online node。
- 如果页面已可发送但目标节点在提交瞬间不可用，发送区会保留草稿，并显示同样的 `Chat unavailable` 失败提示；用户无需查看终端日志即可理解问题。
- 如果刚完成绑定，刷新 `/` 或重新打开 `/chat` 即可开始聊天。

到这里你只需要按页面提示判断下一步：
- 看到可输入的 composer：可以直接发第一条消息。
- 看到 `Chat unavailable` + `Next: Open bind flow`：先完成绑定。
- 看到 `Chat unavailable` + `Next: Bring Gateway online`：先把 Gateway 恢复到在线状态。

更完整的启动、Feishu channel 配置、状态说明与调试附录见 `docs/operator-runbook.md`。前端开发模式、Mock/真实 IM 边界见 `src/IM/frontend/README.md`。

## CLI

### Start CLI (interactive REPL)

Start the in-process REPL:

```bash
PYTHONPATH=src python3 -m coding_cli.main
```

Or specify a model:

```bash
PYTHONPATH=src python3 -m coding_cli.main --model volcanoArk:doubao-seed-2-0-code-preview-260215
```

If you are not using editable install, run with `PYTHONPATH=src`:

```bash
PYTHONPATH=src python3 -m coding_cli.main
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
- `commands.py`: 稳定入口编排层（参数解析、进程内 Kernel 装配、REPL 主循环、错误分层）。
- `repl_input.py` (`coding_cli/input/repl_input.py`): 可编辑输入与历史回填实现（行内编辑、方向键、草稿恢复）。
- `repl_commands.py` (`coding_cli/input/repl_commands.py`): REPL 斜杠命令路由与参数校验（`/help /new /use ...`）。
- `text_runner.py`: `--text` 非交互执行路径，输出 NDJSON 事件直到 run 终态。

开发约定（收口门禁）：

- CLI 进程内通过 `agent.sdk` 构建 Kernel；不要恢复 `--mode` / `--base-url` / HTTP API 子命令。
- 避免空转发层：不要在 `commands.py` 里重新导出输入、渲染或 REPL 命令模块的内部实现。
- 保持脚本机读稳定：`--text` stdout 保持 NDJSON 事件流；不要再把它描述为 single final JSON object on stdout。

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
from coding_cli.release_observability import summarize_perf_metrics, build_guardrail_hints

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

### Non-interactive commands

```bash
PYTHONPATH=src python3 -m coding_cli.main --text "hello"
PYTHONPATH=src python3 -m coding_cli.main --resume <session_id> --text "continue"
PYTHONPATH=src python3 -m coding_cli.main --model kimiCoding:K2.6 --text "hello"
PYTHONPATH=src python3 -m coding_cli.main llm-config get
```

### Environment variables

- `NANO_MULTIAGENT_REQUEST_ID` (optional)
- `NANO_MULTIAGENT_SESSION_ID` (optional default session for REPL or `--text` startup)
- LLM overrides are per process: `--provider`, `--model`, `--llm-base-url`, `--api-key`, `--timeout-seconds`

### Troubleshooting

- `unknown argument: --mode` / `--base-url`: these belonged to the removed HTTP API architecture; use the in-process REPL or `--text`.
- LLM connection failures: verify the configured provider, model, base URL and API key for the current process.
- `--text` exits non-zero: inspect the emitted NDJSON `run_status` event for the terminal status and reason.
