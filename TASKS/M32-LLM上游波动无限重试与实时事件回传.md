# TASKS (Milestone: M32)

- Test command: `PYTHONPATH=src pytest -q`
- Branch: `milestone/M32`
- Milestone status: `RUNNING`
- Scope guard:
  - Allowed: `src/nano_multiagent/runs/**`、`src/nano_multiagent/agent/**`、`src/nano_multiagent/hooks/**`、`src/nano_multiagent/server/**`、`src/nano_multiagent/cli/**`、`tests/**`、`TASKS/PROGRESS`。
  - Forbidden: `ROADMAP.md`、与 M32 无关重构、删除既有契约语义。

## [TODO] R32.1 异步 run 引入无限重试节奏与取消保持
- Acceptance:
  - 对 `ModelError(retryable=True)`（openai_compat/anthropic 上游瞬时失败）进入无限循环重试，不直接 failed。
  - 重试短退避严格按 `0.5s -> 1s -> 2s` 循环；每连续 5 次失败额外冷却 `30s`，并重置短退避节奏。
  - 取消优先：run 被 `cancel` 后应尽快停止重试，不再推进到 failed/completed。
  - run 成功后仍保持既有 `completed` 语义；非可重试异常维持既有失败语义。
- Tests Plan:
  - `unit`: 选。验证重试节奏、冷却、取消与终态机约束。
  - `contract`: 不选。本 Roadpoint 不扩 HTTP 顶层 schema，仅增强运行态事件数据。
  - `integration`: 选。验证 run_status 事件落盘/链路中可见重试字段。
  - `e2e`: 不选。真实入口留到 R32.2 覆盖 CLI->HTTP。
- Expected Tests:
  - `tests/unit/test_runs_registry.py`
  - `tests/unit/test_run_cancel.py`
  - `tests/integration/test_runs_store_integration.py`
- DoD:
  - `PYTHONPATH=src pytest -q` 全绿（基于当前分支状态；若存在基线失败需在 PROGRESS 标注差异）。
  - C1/C2/C3 提交齐全。
  - PROGRESS 记录决策/证据/回滚点/提交哈希。
- Commits:
  - C1: `<pending>`
  - C2: `<pending>`
  - C3: `<pending>`
- Status: TODO

## [TODO] R32.2 事件契约扩展与 CLI 实时重试反馈
- Acceptance:
  - 重试中持续产生可消费事件，至少含 `attempt`、`next_delay`、`cooldown`、`last_error` 摘要。
  - CLI REPL 在异步轮询中实时展示“正在重试”信息，用户可区分“重试中”与“卡死无输出”。
  - 保持 REPL 既有防串线：`event_id` 去重 + `run_id` 过滤。
  - 终态后不做补发兜底，事件仅来自执行期实时产出。
- Tests Plan:
  - `unit`: 选。验证 CLI 事件预览渲染与字段容错。
  - `contract`: 选。验证 SSE/run_status 事件中重试字段契约。
  - `integration`: 选。至少覆盖 `CLI -> HTTP async` 主链路，验证重试事件实时可见并最终成功。
  - `e2e`: 视集成覆盖可不选。本需求核心为 CLI/HTTP 链路，integration 已覆盖真实入口。
- Expected Tests:
  - `tests/unit/test_cli_main.py`
  - `tests/contract/test_sse_event_contract.py`（或新增 runs async contract）
  - `tests/integration/test_cli_async_retry_integration.py`（新增）
- DoD:
  - `PYTHONPATH=src pytest -q` 全绿（基于当前分支状态；若存在基线失败需在 PROGRESS 标注差异）。
  - C1/C2/C3 提交齐全。
  - PROGRESS 记录决策/证据/回滚点/提交哈希。
- Commits:
  - C1: `<pending>`
  - C2: `<pending>`
  - C3: `<pending>`
- Status: TODO
