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
- Commits: C1+C2=99f53a64, C3=（本 docs commit）
- Next: R2 删一次性快照
