# M60 - Session内系统提示词时间戳固定（避免KV Cache失效）

## Milestone Contract
- Milestone: `M60`
- Title: `Session内系统提示词时间戳固定（避免KV Cache失效）`
- Goal: 修复同一 session 多轮消息时系统提示词 `CURRENT_DATETIME` 每轮变化的问题，确保 session 内时间戳稳定不变。
- Execution: `parallel` + `use_worktree=true`
- Worktree: `/Users/czj/Repos/nano-multiagent/.nano_multiagent/worktrees/M60`
- Branch: `milestone/M60`
- Scope:
  - Allowed:
    - `src/nano_multiagent/agent/runtime.py`
    - `src/nano_multiagent/agent/loop.py`
    - `src/nano_multiagent/agent/prompting.py`（仅必要时）
    - `tests/integration/test_agent_runtime_integration.py`
    - `tests/integration/test_prompt_runtime_fill_integration.py`（仅必要时）
    - `tests/e2e/test_system_prompt_render_e2e.py`（仅必要时）
    - `TASKS/PROGRESS/LOGBOOK` 本 Milestone 文档
  - Forbidden:
    - CLI 渲染、工具契约、IM 模块、server 非相关路由
- Prevention Rules:
  - 必须先写失败测试证明“同一 session 两轮时间戳会漂移/应固定”。
  - 优先使用 session 级稳定来源（`session.created_at`）而不是全局缓存。
  - 保持跨 session 行为可区分，避免把所有 session 固定到同一个进程时间。

## Startup Notes
- 已阅读：`LOGBOOK.md`、`COMMENTING_GUIDE.md`。
- 本 Milestone 相关注意事项：
  - 时间戳稳定性应在 session 维度收口，避免跨会话污染。
  - 仅做 agent/session prompt 路径改动，不扩散到 CLI/server 非相关层。

## Baseline Gate
- Command:
  - `PYTHONPATH=src pytest -q tests/unit/test_agent_prompting.py tests/integration/test_prompt_runtime_fill_integration.py tests/integration/test_agent_runtime_integration.py tests/e2e/test_system_prompt_render_e2e.py tests/contract/test_system_prompt_contract.py`
- Result:
  - `9 passed, 4 warnings`（2026-03-04）

## Roadpoints

### R1 会话级时间戳稳定化（同 session 固定、跨 session 区分）
- Acceptance:
  - 同一 session 连续两次 `runtime.run`，LLM 接收的 system prompt 中 `Current date and time:` 行保持一致。
  - 新建 session 的 system prompt 时间戳独立，不与其他 session 共享。
  - 仅调整 agent/session prompt 时间注入链路，不改外部 API 契约。
  - 门禁测试集全绿。
- Tests Plan:
  - unit: 选（执行门禁中的 `test_agent_prompting.py`，保障基础模板填充行为不回归）。
  - contract: 选（执行 `test_system_prompt_contract.py`，确保系统提示词契约不回归）。
  - integration: 选（在 `test_agent_runtime_integration.py` 先补红测，锁定 same-session 稳定与 cross-session 区分）。
  - e2e: 选（执行 `test_system_prompt_render_e2e.py`，验证真实 HTTP 入口链路仍正确渲染系统提示词）。
- Expected Tests:
  - `tests/integration/test_agent_runtime_integration.py::<new same-session timestamp stability test>`
  - `tests/integration/test_agent_runtime_integration.py::<new cross-session timestamp isolation test>`
  - `PYTHONPATH=src pytest -q tests/unit/test_agent_prompting.py tests/integration/test_prompt_runtime_fill_integration.py tests/integration/test_agent_runtime_integration.py tests/e2e/test_system_prompt_render_e2e.py tests/contract/test_system_prompt_contract.py`
- DoD:
  - Red 先失败、C1/C2/C3 完整。
  - `test_command` 全绿。
  - `PROGRESS` 记录决策、证据、回滚点、提交哈希。
- Status: `TODO`
