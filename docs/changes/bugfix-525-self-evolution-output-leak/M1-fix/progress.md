# bugfix-525-M1 — Progress

## 启动基线

- Unit head at dispatch: `57b7aec1d`。
- Scope confirmation: 只隔离 self-evolution fork 的 raw session events；普通 background Agent result 与既有 `self_evolution_review` 展示路径保持不变。
- Existing baseline: `51 passed`，命令见 R2 完成记录。
- Production evidence read-only locators:
  - Kernel session: `sess_5f9eeb9f7479dd13`
  - LLM request/tool call: `/Users/czj/Repos/LLM_PROXY/logs/session/2026-08-09_20-27-23_509_sess_5f9eeb9f7479dd13/2026-08-10_09-41-03_357-req-anthropic_messages.json`
  - LLM raw completion: `/Users/czj/Repos/LLM_PROXY/logs/session/2026-08-09_20-27-23_509_sess_5f9eeb9f7479dd13/2026-08-10_09-41-09_400-non-stream-res-anthropic_messages.json`
  - User-visible screenshot: `/var/folders/mf/fxm1x6xs7pbf34h6rnmvjz1c0000gn/T/codex-clipboard-ea146fbc-d9d7-41d9-aded-947376fc38e4.png`

## R1 — 真实 fork session-event 红测与隔离修复

- Context: 父 HookContext 中的 `_workspace_execution_scope` 会让 `AgentContextFork` 继续执行 workspace-scoped observe hooks；同时继承的 parent session-event publisher 把 fork 的 realtime assistant/tool/turn events 写回原 session。
- Decision: 保留完整父 HookContext 与 background origin，只在 `make_fork_conversation()` 构造 side-chain context 时把 `session_event_publisher` 换为 no-op。最终 structured notice 仍由 fork 返回后的父 background hook context 发布。
- Rationale: 这是已有 compaction side-chain 使用的隔离模式，边界正好位于坏值源头；不修改 `RunOrigin.BACKGROUND_TASK` 的全局投递规则，也不移除 workspace hook runner、model caller、permission requester 或 tool registry。
- Evidence:
  - Tests: 红测 `pytest -q tests/integration/test_self_evolution_output_visibility.py -vv` 在修复前稳定得到 `assistant_contents == ['Foreground answer', 'Saved: ...']`；修复后 `1 passed`。
  - Entry: 测试经 public `build_kernel/create_session/submit/stream` 入口触发第二轮真实 self-improvement background hook；fork 真执行 `memory(add)`，父 session stream 只剩 foreground assistant/turn 与一条 `self_evolution_review`。
  - Frontend State Matrix: N/A。
  - Browser QA: N/A。
  - E2E/Regression: `tests/integration/test_self_evolution_output_visibility.py::test_self_evolution_raw_output_stays_out_of_parent_session_events`；同时断言 raw assistant、memory tool start/end、额外 turn_end 均不可见。
  - Visual/Interaction: N/A。
  - Prototype Comparison: N/A。
- Rollback: revert `de432ddd1`。
- Commits: `de432ddd1`
- Next: 维护继承不变量断言并扩大相关门禁。

## R2 — 继承不变量与既有测试维护

- Context: 修复不能以删除 execution scope 或按 `background_task` 全局过滤完成，否则会破坏 workspace tool/hook、unattended permission，或普通后台 Agent 结果。
- Decision: 扩展既有 `test_fork_inherits_parent_execution_context`，明确 workspace execution scope 继续继承、parent publisher 不再复用；保留既有 structured notice 与普通 background result consumer tests。
- Rationale: integration regression 拥有跨 seam 风险，unit test 只保护被最小变更触及的 context capability selection；两者不重复同一失败原因。
- Evidence:
  - Tests: `/Users/czj/Repos/nano-multiagent/.venv/bin/pytest -q tests/integration/test_self_evolution_output_visibility.py tests/unit/test_background_hook_fork.py tests/unit/test_self_improvement_hook.py tests/unit/platform/hooks/test_realtime_stream_events.py tests/unit/personal_assistant/test_background_session_events.py tests/unit/personal_assistant/test_pipeline_kernel_event_observer.py` → `52 passed, 2 warnings`。
  - Entry: integration test 的四次模型请求（两个前台 turn + 两轮 review）全部使用 `test-model`，且 workspace `USER.md` 含新增 sentinel。
  - Frontend State Matrix: N/A。
  - Browser QA: N/A。
  - E2E/Regression: `test_bg_subscriber_routes_background_task_assistant_message_to_callback` 继续证明普通 background Agent assistant output 被路由；`TestSessionEventPublish` 与 background subscriber tests 继续证明 structured notice 单独送达。
  - Visual/Interaction: N/A。
  - Prototype Comparison: N/A。
- Rollback: revert `de432ddd1`。
- Commits: `de432ddd1`
- Next: 运行比例门禁并回填 Bugfix lite 修复/验证段。

## R3 — 比例门禁与 Bugfix lite 证据闭环

- Context: 这是 kernel side-chain session-event capability 变更，需要同时守住 core fork、Gateway background consumer、文档与全仓非 E2E 套件。
- Decision: 用 integration regression 作为最低层永久入口保护；生产 LLM 日志与截图只读引用，不向真实飞书会话发送测试消息或改生产配置。
- Rationale: 测试从 public Kernel SDK 真触发 fork、tool side effect 与 session-event hub，直接覆盖生产坏值进入 Gateway observer 前的最早稳定 seam；再跑现有 Gateway consumer tests 证明 structured notice 与普通 background result 路由未被改变。
- Evidence:
  - Tests: `/Users/czj/Repos/nano-multiagent/.venv/bin/pytest -q -m 'not e2e'` → `3182 passed, 26 deselected, 22 warnings in 392.79s`。
  - Entry: `tests/integration/test_self_evolution_output_visibility.py` 通过 `build_kernel/create_session/submit/stream` 跑两轮前台 turn + 两轮真实 memory review，`USER.md` 写入成功；可投递 stream 只有 `Foreground answer`、一个前台 `turn_end` 与一个 structured `self_evolution_review`。
  - Frontend State Matrix: N/A。
  - Browser QA: N/A。
  - E2E/Regression: 永久 integration regression 已落库；生产原始症状基线由 `09:41:03` memory tool request、`09:41:09` raw `Saved: ...` completion 与飞书截图三者交叉证明。
  - Visual/Interaction: N/A；不修改 UI，生产截图仅作修前症状 locator。
  - Prototype Comparison: N/A。
- Additional gates:
  - `/Users/czj/Repos/nano-multiagent/.venv/bin/ruff check .` → passed。
  - `/Users/czj/Repos/nano-multiagent/.venv/bin/ruff format --check .` → `876 files already formatted`。
  - `PATH=/Users/czj/Repos/nano-multiagent/.venv/bin:$PATH ./scripts/docs-check` → `documentation integrity passed: 217 maintained Markdown sources, 67 required routes`。
  - `git diff --check` → passed。
- Rollback: revert `de432ddd1`；plan/docs commits 可独立回退，不影响产品行为。
- Commits: `de432ddd1`
- Next: rebase 到最新 `origin/unit/bugfix-525`，复跑 focused gate，合并并推送 unit branch。

## Promotion Candidates

None.
