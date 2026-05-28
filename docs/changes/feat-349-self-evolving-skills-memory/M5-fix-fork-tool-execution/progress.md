# feat-349-M5: fix-fork-tool-execution — Progress

## R1 — 失败测试

- Context: fork loop 在 tool_registry=None 时走 tool_registry_unavailable 出口；background_runs.py echo 读错 key 层级
- Decision:
  1. `tests/unit/test_background_hook_fork.py` 新增 `test_bind_tool_registry_propagates_to_context_fork` + `test_fork_loop_executes_tools_after_bind_tool_registry`（直接复现 tool_registry=None 导致 round 2 缺失）
  2. `tests/unit/test_cli_background_runs.py` 新增 `test_format_self_evolution_review_flat_event_reviewed_skills` + `test_format_self_evolution_review_flat_event_reviewed_memory`（复现 flat event wording bug）
- Rationale: 最窄复现路径，直接针对两个根因，在现有测试文件追加，不引入新文件
- Evidence:
  - Tests: pytest 四个新 test → FAILED（Red 确认）
  - Entry: N/A（单元测试阶段）
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: N/A
  - Visual/Interaction: N/A
- Rollback: 3763e609（unit/feat-349 HEAD at start）
- Commits: C1=5ae67eda
- Next: R2 实现修复

## R2 — 修复实现

- Context: bind_tool_registry 只更新 self._loop，遗漏 self._context_fork._loop；background_runs.py 读错 dict 层级
- Decision:
  1. `context_fork.py` AgentContextFork: 新增 `bind_tool_registry` 方法，委托 `self._loop.bind_tool_registry`
  2. `runtime.py` `bind_tool_registry`: 同时调 `self._context_fork.bind_tool_registry(tool_registry)`
  3. `background_runs.py` `_format_self_evolution_review`: 直接从 `event` 顶层读取 `reviewed_skills`/`reviewed_memory`（去掉 event.get("data", {}) 中间层）
- Rationale: 最小修改，不改 AgentContextFork 构造接口，不改 app.py 构造顺序；background_runs 修复直接
- Evidence:
  - Tests: pytest 4 个新 test → PASSED；全量 tests/unit/（826 tests passed，33 pre-existing failures 与本 M5 无关）→ 无新增失败
  - Entry: N/A（单元测试阶段）
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: 见 R3
  - Visual/Interaction: N/A
- Rollback: C1=5ae67eda
- Commits: C1=5ae67eda, C2=91e584fe
- Next: R3 文档 + E2E

## R3 — 文档 + 全量回归

- Context: 全量单测 + E2E 验证 fork loop 确实进入 round 2 执行工具
- Decision: 跑 pytest tests/unit/ 全量；通过 HTTP API 创建 skill_nudge_interval=1 的 session，发 1 条消息，监听 SSE 确认 self_evolution_review 事件 + tool_names_called 包含 skill_manage
- Rationale: skill_nudge_interval=1 可在最少消息后触发 review，加速 E2E 循环；通过 SSE 事件 payload 验证 tool_names_called 比等待文件落盘更可靠（文件落盘路径受 workspace 配置影响）
- Evidence:
  - Tests: pytest tests/unit/ — 826 passed, 33 failed（33 全部为 M5 开始前已存在的 pre-existing failures，见 test_llm_model_registry.py / test_run_cancel.py / test_sdk_client.py / test_server_global_routes.py / test_task_tool_with_resolver.py 等）；无新增失败
  - Entry: HTTP API + SSE stream 真实入口验证（见 E2E/Regression）
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: |
      服务端口: 8992（managed mode，PYTHONPATH=src）
      会话: sess_52882c41b6fe15e5，skill_nudge_interval=1（通过 POST /agent/v1/sessions metadata 注入）
      操作: POST /agent/v1/sessions/{id}/runs 发送 "say hello briefly"
      结果: SSE stream 收到 self_evolution_review 事件，payload:
        {
          "session_id": "sess_52882c41b6fe15e5",
          "reviewed_skills": true,
          "reviewed_memory": false,
          "tool_names_called": ["skill_manage", "skill_manage", "skill_manage", "skill_manage", "bash", "read"],
          "completed": true,
          "event": "self_evolution_review"
        }
      结论: fork loop 成功进入 round 2+，skill_manage 实际执行 4 次（Bug 1 已修复）；
            SSE event 是 flat dict 结构（reviewed_skills 在顶层），background_runs formatter 正确读取（Bug 2 已修复）
  - Visual/Interaction: N/A
- Rollback: C2=91e584fe
- Commits: C2=91e584fe, C3=<pending>
- Next: 合并到 unit/feat-349，清理 worktree
