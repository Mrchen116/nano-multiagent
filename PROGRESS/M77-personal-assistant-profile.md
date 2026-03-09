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
- default_tool_ids = ["read", "task"]（保守集：无 write/edit/bash，不处理文件系统/执行命令）
- default_hook_modules = ["default_status", "usage_metrics"]（无 bash_risk_gate，因为无 bash 工具）
- capabilities = {"im": True, "heartbeat": True, "memory": True}（声明式能力标记，无业务逻辑实现）
- 不添加任何 if product == ... 分支：bootstrap 是通用的，profile 声明驱动行为
- runtime/server 不复制：create_app(product_profile=PERSONAL_ASSISTANT_PROFILE) 复用同一入口

---

### R77.1 完善 PERSONAL_ASSISTANT_PROFILE 字段

- Context: M75 stub 中 PERSONAL_ASSISTANT_PROFILE 所有可选字段为 None/空（default_system_prompt/default_tool_ids/default_hook_modules/capabilities 均未填充）。M77 要求填充完整字段，不添加业务逻辑。
- Decision: 填充 default_system_prompt（IM/协作导向）、default_tool_ids=["read","task"]、default_hook_modules=["default_status","usage_metrics"]、capabilities={"im":True,"heartbeat":True,"memory":True}
- Rationale: 保守工具集（无 write/edit/bash）；无 bash_risk_gate（因为无 bash 工具，添加会有无效 hook）；capabilities 纯声明式，不含业务实现
- Evidence:
  - Tests: 532 passed, 5 failed (pre-existing), 4 skipped — 新增 12 个 unit 测试全绿
  - Entry: pytest tests/unit/test_personal_assistant_profile.py — 12/12 passed
- Rollback: 回退到 plan commit cd1fddb
- Commits: C1=eed4621, C2=91e0ad8, C3=（待填）
- Next: R77.2 — bootstrap_product(PERSONAL_ASSISTANT_PROFILE) 集成验证

---

### R77.2 bootstrap_product(PERSONAL_ASSISTANT_PROFILE) 集成验证

- Context: 验证完整 bootstrap 链路（profile → tool_registry/hook_registry/resolved_system_prompt/ConfigResolver 路径）正确工作，同时覆盖 LOCAL_CODING_PROFILE 回归。
- Decision: 集成测试覆盖 10 个场景：ResolvedProductConfig 类型、product_id、system_prompt 非空、tool_names=={read,task}、hook 无 bash_risk_gate、hook 有 default_status/usage_metrics、ConfigResolver session_db_path、global_config_root、LOCAL_CODING_PROFILE 回归（工具集/hook_registry）
- Rationale: R77.1 实现已足够驱动 R77.2 测试全绿；R77.2 的价值在于覆盖完整链路（bootstrap → resolver → registry），不只是字段值检查
- Evidence:
  - Tests: 542 passed, 5 failed (pre-existing), 4 skipped
  - Entry: pytest tests/integration/test_personal_assistant_bootstrap_integration.py — 10/10 passed
- Rollback: 回退到 R77.1 的 C3 commit 4b323a1
- Commits: C1=ba109d9, C2=a9eb96f, C3=（待填）
- Next: R77.3 — server/app 以 PERSONAL_ASSISTANT_PROFILE 启动，/v1/capabilities 返回正确工具子集

---

### R77.3 server/app 以 PERSONAL_ASSISTANT_PROFILE 启动的集成验证

- Context:
- Decision:
- Rationale:
- Evidence:
  - Tests:
  - Entry:
- Rollback:
- Commits: C1=, C2=, C3=
- Next:
