# PROGRESS (Milestone: M14)

- Title: 工具执行语义细化对齐（read/bash）
- Goal: 将 `read` 与 `bash` 的执行/返回语义补齐到《内核设计细化/工具设计细化.md》要求，消除图片读取、输出截断与 fullOutputPath 等高风险偏差。
- Exit Criteria:
  - `read` 支持图片输入并返回 `text+image` 结构；文本截断与 offset 提示语义通过 contract/integration 验证。
  - `tool_result` 对 list content 透传语义稳定，不再破坏 `read` 图片 parts。
  - `bash` 对齐“无默认超时”与“截断落盘 + fullOutputPath”契约，并覆盖超大输出/超时/中断测试。
  - `pytest -q` 全绿，且工具相关 e2e/contract 回归通过。
- Test command: `pytest -q`
- Branch: `milestone/M14`

### Baseline
- Context:
  - 按执行要求先读取 `LOGBOOK.md`，当前仅有 hook 加载断言稳健性规则，与 M14 直接冲突为无。
  - M14 允许改动范围：`src/nano_multiagent/tools/**`、`src/nano_multiagent/agent/runtime.py` 中 `tool_result` 相关最小改动、M14 相关 tests 与文档。
  - M14 禁止范围：与 M14 无关的 provider/runtime/session 大范围改动。
- Evidence:
  - Tests: `pytest -q` -> `177 passed, 2 skipped`
  - Entry: 当前基线全绿，可直接进入 Roadpoint 红测驱动。
- Next:
  - R14.1

### R14.1 read 语义补齐（图片输入 + 文本截断/offset 提示）
- Context:
- Decision:
- Rationale:
- Evidence:
  - Tests:
  - Entry:
- Rollback:
- Commits: C1=<pending>, C2=<pending>, C3=<pending>
- Next:

### R14.2 tool_result list content 保真透传
- Context:
- Decision:
- Rationale:
- Evidence:
  - Tests:
  - Entry:
- Rollback:
- Commits: C1=<pending>, C2=<pending>, C3=<pending>
- Next:

### R14.3 bash 语义对齐（无默认超时 + 截断落盘 fullOutputPath）
- Context:
- Decision:
- Rationale:
- Evidence:
  - Tests:
  - Entry:
- Rollback:
- Commits: C1=<pending>, C2=<pending>, C3=<pending>
- Next:
