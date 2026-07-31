# M60 - Session内系统提示词时间戳固定（避免KV Cache失效）

## Baseline
- Tests:
  - `PYTHONPATH=src pytest -q tests/unit/test_agent_prompting.py tests/integration/test_prompt_runtime_fill_integration.py tests/integration/test_agent_runtime_integration.py tests/e2e/test_system_prompt_render_e2e.py tests/contract/test_system_prompt_contract.py`
- Result:
  - `9 passed, 4 warnings`（2026-03-04）

### Plan（一次性拆分）
- Context:
  - 当前 `CURRENT_DATETIME` 在 prompt 构建阶段按 `datetime.now()` 实时注入，存在同一 session 多轮时间漂移风险。
  - 本 Milestone 只允许改 agent/session 相关链路，且必须避免全局缓存导致跨 session 污染。
- Decision:
  - 单 Roadpoint 收口：先加集成红测锁定 same-session 稳定 + cross-session 隔离，再最小改动把时间来源切到 session 级（优先 `session.created_at`）。
- Rationale:
  - 先红后绿可直接证明缺陷与修复有效性，并将“跨 session 可区分”写成回归约束，防止后续回退到进程级常量。
- Evidence:
  - Tests: 基线门禁全绿（`9 passed, 4 warnings`）。
  - Entry: 时间占位填充位于 `agent/prompting.py`，调用入口链路为 `runtime -> loop -> build_prompt_messages`。
- Rollback:
  - 回退到计划提交前的稳定点。
- Commits: C1=`TBD`, C2=`TBD`, C3=`TBD`
- Next:
  - 执行 R1 Red：补“同 session 固定 / 跨 session 隔离”失败测试。

### R1.1 会话级时间戳稳定化（同 session 固定、跨 session 区分）
- Context:
  - `CURRENT_DATETIME` 默认在 prompt 填充时按 `datetime.now()` 动态生成，导致同一 session 多轮调用的 system prompt 时间线漂移，影响 cache 命中。
  - 约束是只能改 agent/session 相关链路，且必须保证跨 session 可区分。
- Decision:
  - 在 `AgentRuntime.run` 入口读取当前 session 的 `created_at`，并沿 `runtime -> loop -> prompting` 显式透传。
  - `prompting` 支持把字符串时间戳作为优先值填充 `<RUNTIME_FILL:CURRENT_DATETIME>`，优先使用 `session.created_at`，未提供时保持原有 `now()` 回退。
- Rationale:
  - 以 session 自身创建时间作为稳定源可天然满足“同 session 固定、跨 session 区分”，避免进程级全局缓存污染。
- Evidence:
  - Tests: `PYTHONPATH=src pytest -q tests/unit/test_agent_prompting.py tests/integration/test_prompt_runtime_fill_integration.py tests/integration/test_agent_runtime_integration.py tests/e2e/test_system_prompt_render_e2e.py tests/contract/test_system_prompt_contract.py` -> `11 passed, 4 warnings`（2026-03-04）。
  - Entry: 新增红测断言同一 session 两次 run 的 `Current date and time` 相等；跨 session 两次 run 分别等于各自 `session.created_at` 且彼此不等。
- Rollback:
  - 若需重做，可回退到 C1 `26d2759`（仅红测，未引入实现变更）。
- Commits: C1=`26d2759`, C2=`637d421`, C3=`TBD`
- Next:
  - 提交文档 C3，并执行 Milestone 集成流程（rebase/merge/main 推送/dev-tasks 更新/清理 worktree）。
