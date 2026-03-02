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

### R17.1 会话级 `/compact` 与 `/tools` HTTP API
- Context:
  - M17 需要新增会话级能力端点；现状仅有全局 `/v1/tools`，且 session routes 没有手动压缩入口。
  - 要求保持统一错误形状与 `session_not_found` 语义，同时不引入无关工具语义改造。
- Decision:
  - 在 `session` 路由新增 `GET /v1/sessions/{session_id}/tools` 与 `POST /v1/sessions/{session_id}:compact`。
  - `/tools` 复用 `ToolRegistry.list_specs()`，`/compact` 复用 `runtime.compact()` 并映射为稳定响应模型。
  - 端点先通过 `SessionService` 校验会话存在性，不存在时统一返回 `session_not_found`。
- Rationale:
  - 会话存在性前置校验可让 `/tools` 与 `/compact` 保持同一 404 语义，避免出现框架默认 404/500 的不一致。
  - 将响应模型固定在 `session.py` 内，便于后续 CLI `/tools` 与 `/compact` 直接消费。
- Evidence:
  - Tests:
    - Red: `pytest -q tests/contract/test_sessions_contract.py tests/integration/test_session_flow_integration.py tests/e2e/test_message_sync_e2e.py` -> `4 failed`（新端点 404，缺口与目标一致）
    - Green: 同命令 -> `9 passed`
    - Gate: `pytest -q` -> `230 passed, 3 skipped`
  - Entry:
    - `GET /v1/sessions/{id}/tools` 返回 `{session_id, tools}`；
    - `POST /v1/sessions/{id}:compact` 返回 `{session_id, compacted, result}`，并支持 `result=null`。
- Rollback:
  - `684ed01`（R17.1 C1）
- Commits: C1=`684ed01`, C2=`848b229`, C3=<pending>
- Next:
  - R17.2 Red
