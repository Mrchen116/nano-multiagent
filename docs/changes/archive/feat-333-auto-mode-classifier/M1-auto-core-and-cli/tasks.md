# feat-333-M1: auto-core-and-cli — Tasks

> 对齐: ../design.md v1

## 目标

实现 auto_mode_gate hook（替换 bash_risk_gate）、分类器像素级复刻 CC yoloClassifier.ts、AutoModeConfig + config 加载、request_permission 暂停原语 + PermissionBroker、deny-limit escalation、无人值守短路、hook 框架 timeout_ms=None 支持、RunRecord.origin thread-through；以及 CLI SSE drain 检测 + repl_input picker + POST 决策。

## 退出标准

- [x] `pytest tests/unit/test_auto_mode_gate.py tests/unit/test_auto_mode_config.py tests/unit/test_permission_broker.py` 全绿
- [x] `pytest -m "not e2e"` 不比 baseline 新增失败
- [x] 分类器 system prompt 三层组装 / transcript 投影 / 两阶段 XML / safe-tool allowlist / 工具投影 与 CC yoloClassifier.ts 逐字一致（单测覆盖）
- [x] repl_input picker 在 drain 中途打断场景有真实入口自测证据（progress.md 记录）

## 测试策略

后端/API：新增三个测试文件作为主测试对象，涵盖分类器核心逻辑、config 加载、broker 状态机。
CLI picker：纯后端逻辑路径（picker 调用链），通过 CLI session_stream 注入模拟事件自测。
入口验证：`PYTHONPATH=src python3 -m coding_cli.main --mode managed` 启动后，手工触发 review 级命令，观察 hook 路径被正确调用（日志验证）。

**UI 状态矩阵**：N/A（本 milestone 无前端改动，CLI picker 为终端交互）

**用户路径分类**：纯后端/API + CLI 终端交互，无前端 UI 变更。

**测试与验收映射**：

| 风险点 | 验收方式 | 是否落库 |
|---|---|---|
| 系统 prompt 三层组装与 CC 一致 | `test_auto_mode_gate.py` 单测覆盖 build_yolo_system_prompt | 是 |
| transcript 投影排除 assistant text | `test_auto_mode_gate.py` 单测覆盖 build_transcript_entries | 是 |
| 两阶段 XML 分类逻辑 | `test_auto_mode_gate.py` mock call_model 测 allow/deny/ask 路径 | 是 |
| safe-tool allowlist | `test_auto_mode_gate.py` 测 is_safe_tool | 是 |
| 工具投影 | `test_auto_mode_gate.py` 测 project_tool_input | 是 |
| AutoModeConfig global/workspace 两级加载 | `test_auto_mode_config.py` 测 load_auto_mode_config | 是 |
| PermissionBroker deny-count / session-allowlist 状态 | `test_permission_broker.py` | 是 |
| hook 框架 timeout_ms=None | 已有 `tests/contract/test_hooks_contract.py` 可扩展 | 是 |
| request_permission fail-closed | `test_permission_broker.py` | 是 |

## Roadpoints

### R1 — 类型层：AutoModeConfig + PermissionDecision + PermissionRequest/Response/Broker [DONE]

- 步骤: 新建 `src/agent/platform/config/auto_mode.py`（AutoModeConfig dataclass + load_auto_mode_config 函数），新建 `src/agent/platform/permissions/broker.py`（PermissionBroker + PermissionDecision/Request/Response/Option）
- 验证: `pytest tests/unit/test_auto_mode_config.py tests/unit/test_permission_broker.py -x`

### R2 — hook 框架扩展：timeout_ms=None 支持 [DONE]

- 步骤: 修改 `src/agent/core/hooks/runner.py`（_execute_handler 支持 None timeout_ms），修改 `src/agent/core/hooks/types.py`（HookRegistration.timeout_ms: int | None）
- 验证: `pytest tests/unit/test_hooks_runner.py`

### R3 — HookContext 扩展：message_history + permission_requester + request_permission [DONE]

- 步骤: 修改 `src/agent/core/hooks/context.py`（新增 message_history / permission_requester 字段 + request_permission async 方法）
- 验证: `pytest tests/unit/test_hooks_runner.py`

### R4 — RunRecord.origin thread-through + runtime 注入 [DONE]

- 步骤: 修改 `src/agent/core/runs/registry.py`（_run_worker_async 传 origin 到 runtime.run），修改 `src/agent/core/agent/runtime.py`（run 协议加 origin 参，写入 hook_metadata["run_origin"]）
- 验证: `pytest tests/unit/agent/runs/test_run_origin.py tests/unit/agent/runs/test_abort_priority.py`

### R5 — 分类器核心：auto_mode_gate hook（替换 bash_risk_gate）[DONE]

- 步骤: 新建 `src/agent/platform/hooks/builtins/auto_mode_gate.py`（SAFE_TOOL_ALLOWLIST + TOOL_PROJECTIONS + build_yolo_system_prompt + build_transcript_entries + two-stage XML classify + deny-limit escalation + unattended short-circuit + session-allowlist）；删除 bash_risk_gate.py
- 验证: `pytest tests/unit/test_auto_mode_gate.py tests/unit/test_hook_builtin_bash_risk_gate.py`

### R6 — inbound 端点：POST /v1/sessions/{sid}/permissions/{request_id} [DONE]

- 步骤: 修改 `src/agent/platform/http_api/routes/session.py`（新增 permissions 路由），修改 `src/agent/platform/http_api/deps.py`（注入 PermissionBroker），新增 `tests/unit/test_permission_inbound_endpoint.py`
- 验证: `pytest tests/unit/test_permission_inbound_endpoint.py tests/unit/test_permission_broker.py`

### R7 — CLI：SSE drain 检测 + repl_input picker + POST 决策 [DONE]

- 步骤: 修改 `src/coding_cli/session_stream.py`（drain_run 新增 on_permission_request callback），修改 `src/coding_cli/commands.py`（新增 _handle_permission_request + 接入 drain_run），新增 `src/coding_cli/input/repl_input.py`（PermissionOption + read_permission_choice），新增 `src/coding_cli/client.py`（submit_permission_decision）
- 验证: `pytest tests/unit/test_session_stream.py` 全绿（10/10）
