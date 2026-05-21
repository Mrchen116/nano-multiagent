# M4-unit-kernel Progress

> branch: milestone/refactor-372-M4
> base: unit/refactor-372

---

### R1 — 修漂移：create_app/run_cancel/task_tool/app_factory

- Context: 4 个测试文件共 8 个用例因产品接口演进而漂移
- Decision:
  - `test_server_global_routes`: 去掉 `create_app(auth_token=...)` 参数；初始 provider 检查改为环境无关断言
  - `test_run_cancel`: 等待条件加 `RunStatus.CANCELLED`（abort 后产品置为 CANCELLED，stop_reason="aborted"）
  - `test_task_tool_with_resolver`: `_RuntimeStub.create_session()` 补 `parent_session_id` 参数
  - `test_app_factory_with_profile`: 改为验证 `config_resolver.user_skill_roots()` 返回 workspace 路径，而非检查已不存在的 `_loop._available_skills`（技能现在运行时按需解析）
- Rationale: 产品主动演进，测试期望旧接口；改测试对齐现码，不放宽契约
- Evidence:
  - Tests: `pytest tests/unit/{test_server_global_routes,test_run_cancel,test_app_factory_with_profile,test_task_tool_with_resolver}.py` → 22 passed
  - Full scope: `pytest tests/unit -m "not e2e" --ignore=tests/unit/personal_assistant --ignore=tests/unit/IM --ignore=tests/unit/test_m170_runtime.py -k "not (cli or sdk_client or managed_server or refactor_boundaries)"` → 1154 passed
  - Entry: N/A（纯测试修复，无产品行为变更）
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: N/A
  - Visual/Interaction: N/A
- Rollback: `git revert 99f53a64`
- Commits: C1+C2=99f53a64, C3=8981c9d5
- Next: R2 删一次性快照

---

### R2 — 删一次性快照：test_rerun + test_m170_runtime

- Context: 两个文件均为 importlib-exec 或直接导入 ACCEPTANCE 脚本的一次性快照，TESTING_GUIDE §6 明确禁止。`test_m170_runtime.py` 从 `scripts.acceptance.m170_runtime` 导入脚本函数（需要 websockets 等运行时依赖），`test_rerun_acceptance_runtime_helpers.py` 用 importlib.exec 执行 `ACCEPTANCE/m170-runtime/` 脚本
- Decision: 删除两个文件；确认 ACCEPTANCE 脚本是 playwright 验收脚本 + 运行时布局助手，无产品逻辑需提进 `src/`
- Rationale: 这类脚本测的是验收场景，不是产品逻辑；维持这类测试会因外部文件变化而炸收集
- Evidence:
  - Tests: 1154 passed → 1141 passed（减少 2 个文件的用例，均为被删内容）
  - Full scope: `pytest tests/unit -m "not e2e" --ignore=tests/unit/personal_assistant --ignore=tests/unit/IM -k "not (cli or sdk_client or managed_server or refactor_boundaries)"` → 1141 passed
  - Entry: N/A
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: N/A
  - Visual/Interaction: N/A
- Rollback: `git revert c699e6ab`
- Commits: C1+C2=c699e6ab, C3=（本 docs commit）
- Commits: C1+C2=c699e6ab, C3=64b38544
- Next: R3 去流水号

---

### R3 — 去流水号重命名：m236 / refactor353

- Context: 两个文件用 milestone 编号命名，违反 TESTING_GUIDE §3
- Decision:
  - `test_m236_session_metadata_hookcontext.py` → `test_session_metadata_hookcontext.py`（模块注释去掉 "M236:" 前缀）
  - `test_refactor353_corrigendum.py` → `test_path_sandbox_corrigendum_docs.py`（描述测试的文档契约）
- Rationale: 语义名让文件内容一目了然，不依赖读者记住 milestone 历史
- Evidence:
  - Tests: 11 passed for renamed files
  - Entry: N/A
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: N/A
  - Visual/Interaction: N/A
- Rollback: `git revert cbf7b866`
- Commits: C1+C2=cbf7b866
- Next: R4 拆 test_tools_builtins

---

### R4 — 拆 test_tools_builtins (923→≤400)

- Context: 单文件 923 行，混合了 5 类工具的 64 个测试用例
- Decision: 拆为 4 个文件，按工具行为分组
  - `test_tools_builtins.py` (148): descriptions + param schemas + safety constants
  - `test_tools_read.py` (274): ReadTool 全部测试
  - `test_tools_write_edit.py` (269): WriteTool + EditTool
  - `test_tools_bash_task.py` (343): BashTool + TaskTool
- Evidence: 64 tests collected, 64 passed
- Commits: efa6d722

---

### R5 — 拆 test_background_hook_fork (843→≤400)

- Context: 843 行，23 个测试，跨 5 个关注点（enum、fire-and-forget、fork_conversation、turn_meta、bind_tool_registry）
- Decision: 拆为 3 个文件
  - `test_background_hook_fork.py` (207): enum + dispatch_background (11 tests)
  - `test_background_hook_fork_conversation.py` (284): fork_conversation + anti-recursion + tool allowlist (6 tests)
  - `test_background_hook_turn_meta.py` (373): turn_meta + agent_end + bg context + bind_tool_registry (6 tests)
- Evidence: 23 tests collected, 23 passed
- Commits: a2c9a084

---

### R6 — 拆 test_agent_loop (723→≤400)

- Context: 723 行，13 个测试，3 个行为集群（基础执行、并发/压缩、策略回归）
- Decision: 拆为 3 个文件
  - `test_agent_loop.py` (366): 7 个基础 + usage + hooks 测试
  - `test_agent_loop_parallel_budget.py` (367): parallel tool_calls + 3 个 result compression 测试
  - `test_agent_loop_policies.py` (116): R2 policy 回归（turn_count/history）2 个测试
- Evidence: 13 tests collected, 13 passed
- Commits: a2c9a084

---

### R7 — 拆 test_auto_mode_gate (698→≤400)

- Context: 698 行，59 个测试，5 个关注点（prompt、transcript、XML、allowlist/projection/setup、hook logic）
- Decision: 拆为 3 个文件
  - `test_auto_mode_gate.py` (226): system prompt + transcript + XML parsing (26 tests)
  - `test_auto_mode_gate_allowlist.py` (123): allowlist + projection + gate setup (20 tests)
  - `test_auto_mode_gate_hook.py` (363): hook logic + M6 bash regressions (13 tests)
- Evidence: 59 tests collected, 59 passed
- Full scope exit: 1141 passed, 0 failed
- Commits: a2c9a084
