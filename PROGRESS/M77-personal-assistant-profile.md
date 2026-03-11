# PROGRESS/M77 personal-assistant-profile

## Overview
milestone_id: M77
branch: milestone/M77
worktree: /Users/czj/Repos/nano-multiagent/.nano_multiagent/worktrees/M77

## Baseline
- pytest -q: 520 passed, 5 failed (pre-existing from M76 baseline), 4 skipped
- 预存失败：test_llm_generate_response_contract / test_cli_repl_http_chain_surfaces_retry_progress_events / test_task_continuation_can_skip_selector / test_builtin_bash_risk_hook_allows_unlisted_command_after_safe_review（+1 更多，共 5 failed）
- M77 目标：保持 520 passed 不减少

## Key Design Decisions
- PERSONAL_ASSISTANT_PROFILE 完全在 platform/products/personal_assistant.py 内定义
- default_tool_ids = ["read", "task"]（保守集：无 write/edit/bash；`send_message` 作为 optional tool，不默认开启）
- default_hook_modules = ["default_status", "usage_metrics"]（无 bash_risk_gate，因为无 bash 工具）
- capabilities = {"im": True, "heartbeat": True, "memory": True}（声明式能力标记，无业务逻辑实现）
- 不添加任何 if product == ... 分支：bootstrap 是通用的，profile 声明驱动行为
- runtime/server 不复制：create_app(product_profile=PERSONAL_ASSISTANT_PROFILE) 复用同一入口

---

### R77.1 完善 PERSONAL_ASSISTANT_PROFILE 字段

- Context: M75 stub 中 PERSONAL_ASSISTANT_PROFILE 所有可选字段为 None/空（default_system_prompt/default_tool_ids/default_hook_modules/capabilities 均未填充）。M77 要求填充完整字段，不添加业务逻辑。
- Decision: 填充 default_system_prompt（IM/协作导向）、default_tool_ids=["read","task"]、optional_tool_ids=["send_message"]、default_hook_modules=["default_status","usage_metrics"]、capabilities={"im":True,"heartbeat":True,"memory":True}
- Rationale: 保守工具集（无 write/edit/bash，`send_message` 需显式启用时再暴露）；无 bash_risk_gate（因为无 bash 工具，添加会有无效 hook）；capabilities 纯声明式，不含业务实现
- Evidence:
  - Tests: 532 passed, 5 failed (pre-existing), 4 skipped — 新增 12 个 unit 测试全绿
  - Entry: pytest tests/unit/test_personal_assistant_profile.py — 12/12 passed
- Rollback: 回退到 plan commit cd1fddb
- Commits: C1=eed4621, C2=91e0ad8, C3=（待填）
- Next: R77.2 — bootstrap_product(PERSONAL_ASSISTANT_PROFILE) 集成验证

---

### R77.2 bootstrap_product(PERSONAL_ASSISTANT_PROFILE) 集成验证

- Context: 验证完整 bootstrap 链路（profile → tool_registry/hook_registry/resolved_system_prompt/ConfigResolver 路径）正确工作，同时覆盖 LOCAL_CODING_PROFILE 回归。
- Decision: 集成测试覆盖 10 个场景：ResolvedProductConfig 类型、product_id、system_prompt 非空、tool_names=={read,task} 且 `send_message` 保持 optional、hook 无 bash_risk_gate、hook 有 default_status/usage_metrics、ConfigResolver session_db_path、global_config_root、LOCAL_CODING_PROFILE 回归（工具集/hook_registry）
- Rationale: R77.1 实现已足够驱动 R77.2 测试全绿；R77.2 的价值在于覆盖完整链路（bootstrap → resolver → registry），不只是字段值检查
- Evidence:
  - Tests: 542 passed, 5 failed (pre-existing), 4 skipped
  - Entry: pytest tests/integration/test_personal_assistant_bootstrap_integration.py — 10/10 passed
- Rollback: 回退到 R77.1 的 C3 commit 4b323a1
- Commits: C1=ba109d9, C2=a9eb96f, C3=（待填）
- Next: R77.3 — server/app 以 PERSONAL_ASSISTANT_PROFILE 启动，/v1/capabilities 返回正确工具子集

---

### R77.3 server/app 以 PERSONAL_ASSISTANT_PROFILE 启动的集成验证

- Context: 验证 create_app(product_profile=PERSONAL_ASSISTANT_PROFILE) 端到端链路——/v1/capabilities 只返回 read/task，/v1/sessions 正常工作，无 if-product 分支。
- Decision: 6 个 HTTP 集成测试（TestClient）：FastAPI 返回值类型、capabilities 集合仅默认工具、capabilities 排除 write/edit/bash/send_message、sessions endpoint 200、LOCAL_CODING_PROFILE 5 工具回归、双产品无分支验证
- Rationale: TestClient 覆盖了 HTTP 入口；无需 subprocess e2e（HTTP 层已足够）；sessions endpoint 返回字段是 items 而非 sessions（已通过 debug 修正）
- Evidence:
  - Tests: 548 passed, 5 failed (pre-existing), 4 skipped
  - Entry: pytest tests/integration/test_personal_assistant_server_integration.py — 6/6 passed
- Rollback: 回退到 R77.2 的 C3 commit c345af6
- Commits: C1=c09f878, C2=af348f4, C3=（待填）
- Next: 全部 Roadpoints DONE，进入 Milestone 收口
