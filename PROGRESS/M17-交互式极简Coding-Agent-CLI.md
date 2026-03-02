# PROGRESS (Milestone: M17)

- Title: 交互式极简 Coding Agent CLI（含 /compact 与 /tools）
- Goal: 提供可持续对话 REPL CLI，并支持会话级 `/compact` 与 `/tools`，目录对齐 `cli/main.py + cli/commands.py + cli/http_client.py`。
- Exit Criteria:
  - CLI 启动进入持续交互提示符，支持普通文本多轮对话。
  - 支持 `/help /new /use <session_id> /session /tools /compact /exit`。
  - 新增 HTTP API：`POST /v1/sessions/{session_id}:compact` 与 `GET /v1/sessions/{session_id}/tools`。
  - CLI 仅通过 HTTP API（无 `agent.runtime` 直连 import）。
  - `pytest -q` 全绿。
- Test command: `pytest -q`
- Branch: `milestone/M17`

### Baseline
- Context:
  - 启动动作已完成：读取 `LOGBOOK.md`，核对 `data/dev-tasks.json` 中 M17 为 READY。
  - `execution_mode=serial`，`use_worktree=false`，当前分支 `milestone/M17`。
  - 允许范围：`src/nano_multiagent/cli/**`、`src/nano_multiagent/server/routes/session.py`、`src/nano_multiagent/sdk/**(必要最小)`、对应 tests 与任务文档。
  - 禁止范围：与 M17 无关的 provider/tool 语义重构；优先交互 CLI，不做复杂 TUI。
- Decision:
  - 先拆 3 个 Roadpoint：R17.1 API 契约、R17.2 CLI 目录重构、R17.3 REPL 交互命令。
- Rationale:
  - 先稳住后端契约，再做 CLI 分层与交互，可减少返工并让 REPL 测试只关注行为。
- Evidence:
  - Tests: `pytest -q` -> `226 passed, 3 skipped`
  - Entry: 基线全绿，可进入 Red 测试驱动。
- Rollback:
  - Plan commit
- Commits: C1=<pending>, C2=<pending>, C3=<pending>
- Next:
  - R17.1 Red
