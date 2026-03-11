# TASKS/M77 personal-assistant-profile

## Goal
在同一 bootstrap 路径上增加 personal_assistant 产品配置，验证多产品共用同一 core/platform 装配链路，不复制 runtime/server。

## Roadpoints

---

### R77.1 完善 PERSONAL_ASSISTANT_PROFILE 字段

**Status**: DONE

**Acceptance**:
- `default_system_prompt` 为非空字符串（个人助手人格，非 coding）
- `default_tool_ids = ["read", "task"]`（保守集，无 write/edit/bash；`send_message` 为 optional）
- `default_hook_modules = ["default_status", "usage_metrics"]`（无 bash_risk_gate）
- `capabilities = {"im": True, "heartbeat": True, "memory": True}`
- `compat_skill_roots = []`（已是空列表，保持）

**Tests Plan**:
- unit: 断言各字段值
- contract: 通过 ProductProfile 结构校验
- integration: 不需（字段值已有 unit 覆盖）
- e2e: 不需（在 R77.2/R77.3 覆盖）

**Expected Tests**:
- `tests/unit/test_personal_assistant_profile.py`

**DoD**: `pytest -q` 全绿 + C1/C2/C3 齐全 + PROGRESS 写清证据

---

### R77.2 bootstrap_product(PERSONAL_ASSISTANT_PROFILE) 集成验证

**Status**: DONE

**Acceptance**:
- `bootstrap_product(PERSONAL_ASSISTANT_PROFILE, repo_root)` 返回 `ResolvedProductConfig`
- `resolved_system_prompt` 非空且包含个人助手语义
- `tool_registry` 只含 `{"read", "task"}`（不含 write/edit/bash；`send_message` 仍作为 optional tool 被产品识别）
- `hook_registry` 不含 `bash_risk_gate`，但包含 `default_status` 和 `usage_metrics`
- `ConfigResolver(profile=PERSONAL_ASSISTANT_PROFILE)` 路径正确（global_config_home/session_db_path）
- LOCAL_CODING_PROFILE 回归不受影响

**Tests Plan**:
- unit: 不需（bootstrap 已有通用单测）
- contract: 不需
- integration: bootstrap_product 链路集成验证
- e2e: 不需（R77.3 覆盖 HTTP 入口）

**Expected Tests**:
- `tests/integration/test_personal_assistant_bootstrap_integration.py`

**DoD**: `pytest -q` 全绿 + C1/C2/C3 齐全

---

### R77.3 server/app 以 PERSONAL_ASSISTANT_PROFILE 启动，/v1/capabilities 返回正确工具子集

**Status**: DONE

**Acceptance**:
- `create_app(product_profile=PERSONAL_ASSISTANT_PROFILE)` 成功返回 FastAPI app
- GET /v1/capabilities 返回 tools 只含 `read` 和 `task`（不含 write/edit/bash；不默认暴露 `send_message`）
- POST /v1/sessions 端点可工作（sessions 路由正确）
- LOCAL_CODING_PROFILE 创建的 app /v1/capabilities 仍返回 5 个 coding 工具（回归）
- 代码中无 `if product == ...` 或 `if product_id == ...` 分支（确认门禁）

**Tests Plan**:
- unit: 不需
- contract: 不需
- integration: HTTP 测试客户端验证 /v1/capabilities 与 /v1/sessions
- e2e: 不需（已通过集成 TestClient 覆盖）

**Expected Tests**:
- `tests/integration/test_personal_assistant_server_integration.py`

**DoD**: `pytest -q` 全绿 + C1/C2/C3 齐全
