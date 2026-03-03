# TASKS (Milestone: M30)

- Test command: `PYTHONPATH=src pytest -q`
- Branch: `milestone/M30`
- Milestone status: `RUNNING`
- Refactor boundaries:
  - Must keep unchanged: 运行时行为、HTTP 路由语义、CLI/SDK 调用链、SSE 事件结构与错误码映射。
  - Allowed to change: `server/cli/sdk/observability` 的入口 docstring、协议/边界意图注释、Milestone 文档。

## [TODO] R30.1 补齐 server/cli/sdk/observability 入口契约注释
- Acceptance:
  - `server` 入口与 route handler 补齐 docstring，明确鉴权前置、HTTP 状态码与错误映射语义。
  - `server.sse` 与 SSE 路由补齐流式事件语义注释（历史回放窗口、session 过滤、编码约束）。
  - `cli/sdk` 入口 API docstring 明确 HTTP-only 边界，不引入 runtime 直连语义。
  - `observability` public API docstring 说明关联字段传播、日志捕获行为与约束。
  - 注释仅解释“为什么/约束/边界/代价”，不复述代码流程。
- Tests Plan:
  - `unit`: 不新增。当前 Milestone 仅注释改进且 scope 不含 `tests/**`。
  - `contract`: 不新增。协议行为不变，仅补充契约文档化。
  - `integration`: 不新增。通过全量门禁验证无行为漂移。
  - `e2e`: 不新增。真实入口语义不改，沿用现有 e2e 门禁。
- Expected Tests:
  - `PYTHONPATH=src pytest -q`
- DoD:
  - `PYTHONPATH=src pytest -q` 全绿。
  - C1/C2/C3 提交齐全。
  - `PROGRESS` 记录决策/证据/回滚点/提交哈希。
- Commits:
  - C1: `<pending>`
  - C2: `<pending>`
  - C3: `<pending>`
- Status: TODO
