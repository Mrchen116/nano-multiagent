# ROADMAP

## Project Conventions
- 入口类型: HTTP API (`FastAPI`), app factory 为 `nano_multiagent.server.app:create_app`
- 测试命令: `pytest -q`
- tests 映射:
  - `tests/unit`: 纯逻辑与边界（ID、异常、核心数据类型）
  - `tests/contract`: 稳定契约冻结（类型字段/事件枚举/HTTP 结构）
  - `tests/integration`: 组件串联（app -> service -> core）
  - `tests/e2e`: 从真实入口验证主流程契约

## Milestone M0（已完成）: 工程骨架 + 最小可用 HTTP
Exit Criteria:
- Python 项目骨架与依赖配置可运行
- `pytest -q` 全绿
- 最小 e2e 覆盖 `GET /v1/health` 与 `POST /v1/sessions`
- 每个 Roadpoint 完成 C1/C2/C3 三次提交并有证据链

### Roadpoint R0.1: 建立工程骨架与测试基线
- Public Surface:
  - `nano_multiagent.server.app:create_app`
  - `GET /v1/health`
- Acceptance:
  - 存在 `src/nano_multiagent` 包与基础入口
  - 健康检查端点可返回 `healthy/version/node_id`
  - `pytest -q` 能运行并覆盖 unit/contract/integration/e2e 的最小用例
- Tests Plan:
  - unit: app factory 可导入
  - contract: health 响应字段
  - integration: app 装配与路由可用
  - e2e: 通过 HTTP 客户端调用 health
- Commit Plan:
  - C1: `test(R0.1): ...（先红）`
  - C2: `feat(R0.1): ...（全绿）`
  - C3: `docs(R0.1): ...（记录hash/证据/下一步）`
- Commits:
  - C1: a004a39
  - C2: 2f3d783
  - C3: e407f14
- Evidence:
  - `pytest -q`: `4 passed in 0.32s`
  - 入口验证: `GET /v1/health -> 200`, body 包含 `healthy=true, version=0.1.0, node_id=local-dev`

### Roadpoint R0.2: 新建会话接口与最小 e2e 闭环
- Public Surface:
  - `POST /v1/sessions`
  - `tests/e2e/test_minimal_flow.py::test_health_then_create_session`
- Acceptance:
  - 支持创建 session 并返回 `session_id/status/created_at`
  - contract 测试锁定返回字段与类型
  - e2e 串联 health + create session 一次通过
  - `pytest -q` 全绿
- Tests Plan:
  - unit: session id 生成与创建逻辑
  - contract: `/v1/sessions` 响应结构
  - integration: app->service->store 链路
  - e2e: health + create session 主流程
- Commit Plan:
  - C1: `test(R0.2): ...（先红）`
  - C2: `feat(R0.2): ...（全绿）`
  - C3: `docs(R0.2): ...（记录hash/证据/下一步）`
- Commits:
  - C1: 123cbae
  - C2: db3c09f
  - C3: b8f1446
- Evidence:
  - `pytest -q`: `8 passed in 0.34s`
  - 入口验证: `tests/e2e/test_minimal_flow.py::test_health_then_create_session` 通过（health=200, create-session=201）

## Milestone M1（已完成）: core 契约层实现与冻结
Goal:
- 新增并冻结 `core/types/events/errors/ids` 稳定契约
- 完成最小 `server/session -> core.ids` 接入，不扩展业务能力
Exit Criteria:
- `src/nano_multiagent/core/` 契约可导入且通过四类测试验证
- `pytest -q` 全绿
- R1.1 完成 C1/C2/C3 并记录证据

### Roadpoint R1.1: core 稳定契约实现与入口级校验
- Public Surface:
  - `nano_multiagent.core.types`: `Message/ToolSpec/ToolCall/ToolResult/TurnResult`
  - `nano_multiagent.core.events`: `RuntimeEventType/RuntimeEvent/new_runtime_event`
  - `nano_multiagent.core.errors`: `NanoMultiAgentError/ModelError/ToolError/PolicyViolation`
  - `nano_multiagent.core.ids`: `IdGenerator` 与 `make_*_id` 工厂
  - `nano_multiagent.session.service:SessionService.create_session`（最小接入 `core.ids`）
- Acceptance:
  - core 契约文件齐备：`types.py/events.py/errors.py/ids.py/__init__.py`
  - contract 测试锁定核心类型字段与事件枚举，防止后续无意破坏
  - integration 测试证明 app/session 链路使用 `core.ids` 生成 session id
  - 至少一个 e2e 入口级契约验证通过
  - `pytest -q` 全绿
- Tests Plan:
  - unit: `tests/unit/test_core_ids.py`, `tests/unit/test_core_errors.py`
  - contract: `tests/contract/test_core_types_contract.py`, `tests/contract/test_core_events_contract.py`
  - integration: `tests/integration/test_core_id_wiring_integration.py`
  - e2e: `tests/e2e/test_core_contract_entry_e2e.py`
- Commit Plan:
  - C1: `test(R1.1): ...（先红）`
  - C2: `feat(R1.1): ...（全绿）`
  - C3: `docs(R1.1): ...（记录hash/证据/下一步）`
- Commits:
  - C1: 87b119e
  - C2: 0efbd91
  - C3: 0236df1
- Evidence:
  - `pytest -q`: `19 passed in 0.51s`
  - 入口级契约验证: `tests/e2e/test_core_contract_entry_e2e.py::test_create_session_entry_respects_core_id_contract` 通过

## Milestone M2（已完成）: session 事件源与 sqlite 存储
Goal:
- 完成 session 事件定义、版本化序列化与可持久化存储（sqlite 默认 + jsonl 调试）
- 将 `session.manager` 与当前 server/service 最小接线，保证状态变更落事件并可重建
Exit Criteria:
- `session/entries.py`、`session/stores/{base,sqlite_store,jsonl_store}.py`、`session/serializers.py` 可用
- `session/manager.py` 与 server 接线完成，创建会话会写入事件存储
- 覆盖 unit/contract/integration/e2e，至少验证“创建会话后重启/重建可读”
- `pytest -q` 全绿

### Roadpoint R2.1: session 事件模型与双存储实现
- Public Surface:
  - `nano_multiagent.session.entries`
  - `nano_multiagent.session.serializers`
  - `nano_multiagent.session.stores.base`
  - `nano_multiagent.session.stores.sqlite_store`
  - `nano_multiagent.session.stores.jsonl_store`
- Acceptance:
  - 定义基础 session 事件类型，并预留 `CompactionEntry`
  - 提供最小版本化序列化/反序列化（entry + snapshot）
  - sqlite/jsonl store 支持 `append_event/load_session/save_snapshot`
  - 集成测试验证 sqlite/jsonl 在重新打开存储后可读取事件与快照
  - `pytest -q` 全绿
- Tests Plan:
  - unit: `tests/unit/test_session_entries.py`
  - contract: `tests/contract/test_session_serializers_contract.py`
  - integration: `tests/integration/test_session_store_persistence_integration.py`
  - e2e: 在 R2.2 统一验证入口级重建能力
- Commit Plan:
  - C1: `test(R2.1): ...（先红）`
  - C2: `feat(R2.1): ...（全绿）`
  - C3: `docs(R2.1): ...（记录hash/证据/下一步）`
- Commits:
  - C1: c76fb5b
  - C2: fc4dbdc
  - C3: 5dfaced
- Evidence:
  - `pytest -q tests/unit/test_session_entries.py tests/contract/test_session_serializers_contract.py tests/integration/test_session_store_persistence_integration.py`: `6 passed`
  - `pytest -q`: `25 passed in 0.93s`

### Roadpoint R2.2: manager/服务接线与可重建验证
- Public Surface:
  - `nano_multiagent.session.manager: SessionManager`
  - `nano_multiagent.session.service: SessionService`（接线 manager/store）
  - `nano_multiagent.server.app:create_app`（最小依赖注入）
- Acceptance:
  - `create_session` 状态变更通过 `SessionStore.append_event` 落盘
  - `SessionManager.load_session/get_session` 可基于事件流重建会话
  - 服务重建（新 manager + 同一 store）后可读取已创建会话
  - 至少 1 个 e2e 验证 HTTP 入口触发后重建仍可读
  - `pytest -q` 全绿
- Tests Plan:
  - unit: `tests/unit/test_session_manager.py`
  - contract: `tests/contract/test_sessions_contract.py`（持续冻结创建响应）
  - integration: `tests/integration/test_session_manager_wiring_integration.py`
  - e2e: `tests/e2e/test_session_rebuild_e2e.py`
- Commit Plan:
  - C1: `test(R2.2): ...（先红）`
  - C2: `feat(R2.2): ...（全绿）`
  - C3: `docs(R2.2): ...（记录hash/证据/下一步）`
- Commits:
  - C1: b1ac468
  - C2: 75087c6
  - C3: 164ef59
- Evidence:
  - `pytest -q tests/unit/test_session_manager.py tests/integration/test_session_manager_wiring_integration.py tests/e2e/test_session_rebuild_e2e.py`: `4 passed`
  - `pytest -q`: `29 passed in 0.33s`

## Milestone M3（已完成）: LLM 抽象层 + openai_compat provider
Goal:
- 落地运行时唯一 LLM 抽象接口与 provider 工厂切换能力
- 实现 `openai_compat` 协议适配，并完成一次非流式文本生成最小接线
- 保证所有发往 LLM provider 的请求携带 `X-Session-Id`
Exit Criteria:
- `llm/interfaces.py`、`factory.py`、`model_registry.py`、`translator.py` 与 `protocols/openai_compat/*` 可用
- provider/model 可通过配置切换，默认 `codexOAuth:gpt-5.2-codex @ http://127.0.0.1:4000`
- 覆盖 unit/contract/integration/e2e 四类测试并通过 `pytest -q`
- 回填 M2 文档中的 `R2.2 C3` 占位为真实 hash

### Roadpoint R3.1: LLM 抽象接口与 openai_compat 非流式链路
- Public Surface:
  - `nano_multiagent.llm.interfaces`
  - `nano_multiagent.llm.model_registry`
  - `nano_multiagent.llm.factory`
  - `nano_multiagent.llm.translator`
  - `nano_multiagent.llm.protocols.openai_compat.{mapper,client}`
- Acceptance:
  - 运行时依赖统一 `LLMClient` 抽象，不直接依赖 provider 细节
  - factory 支持 provider/model/base_url 默认配置与显式配置
  - openai_compat 支持非流式文本生成并返回统一响应结构
  - translator 统一映射请求/响应并注入 `X-Session-Id`
  - 目标测试全绿
- Tests Plan:
  - unit: `tests/unit/test_llm_model_registry.py`
  - contract: `tests/contract/test_llm_interfaces_contract.py`
  - integration: `tests/integration/test_openai_compat_generation_integration.py`
  - e2e: 在 R3.2 验证真实代理调用
- Commit Plan:
  - C1: `test(R3.1): ...（先红）`
  - C2: `feat(R3.1): ...（全绿）`
  - C3: `docs(R3.1): ...（记录hash/证据/下一步）`
- Commits:
  - C1: 3937147
  - C2: 92344bc
  - C3: ece29e6
- Evidence:
  - `pytest -q tests/unit/test_llm_model_registry.py tests/contract/test_llm_interfaces_contract.py tests/integration/test_openai_compat_generation_integration.py`: `7 passed in 0.14s`
  - 集成断言: 请求路径为 `/v1/chat/completions`，并包含 `x-session-id=sess_integration`

### Roadpoint R3.2: 本地 LLM_PROXY e2e 与文档纠偏
- Public Surface:
  - `tests/e2e/test_openai_compat_generate_e2e.py`
  - M3 文档证据链（含 M2 占位回填）
- Acceptance:
  - 通过 `create_llm_client` + `LLMGenerateRequest` 触发真实非流式文本生成
  - 默认模型与 base_url 可直接命中本地代理（`codexOAuth:gpt-5.2-codex`, `http://127.0.0.1:4000`）
  - e2e 中验证请求头包含 `X-Session-Id`（可通过代理日志或 mock 证据）
  - 回填 `R2.2 C3` 与 `R3.1 C3`
  - `pytest -q` 全绿
- Tests Plan:
  - unit: 复用 R3.1
  - contract: 复用 R3.1
  - integration: 复用 R3.1
  - e2e: `tests/e2e/test_openai_compat_generate_e2e.py`
- Commit Plan:
  - C1: `test(R3.2): ...（先红）`
  - C2: `feat(R3.2): ...（全绿）`
  - C3: `docs(R3.2): ...（记录hash/证据/下一步）`
- Commits:
  - C1: 58e5048
  - C2: fd859fe
  - C3: dd714a8
- Evidence:
  - `pytest -q tests/e2e/test_openai_compat_generate_e2e.py`: `1 passed in 2.58s`
  - `pytest -q`: `37 passed in 1.76s`
  - `X-Session-Id` 验证: `tests/integration/test_openai_compat_generation_integration.py` 断言请求头 `x-session-id=sess_integration`

## Milestone M4（已完成）: agent 最小闭环（无工具）
Goal:
- 实现 `agent/runtime.py`、`agent/loop.py`、`agent/state.py`、`agent/policies.py`、`agent/prompting.py` 最小可用版
- 先支持 `text` 输入，并对 `image` 输入保留占位契约，完成“构建上下文 -> 调用 LLM -> 返回 assistant 文本”闭环
- 运行结果通过现有 `session manager/store` 落为 session 事件
Exit Criteria:
- `AgentRuntime.run(session_id, parts)` 可在无 tools/hooks/skills 的前提下完成一轮文本问答
- `TURN_APPENDED` 事件可落盘并在重建时用于恢复历史上下文
- 覆盖 unit/contract/integration/e2e 并通过 `pytest -q` 全绿
- 不进入 M5 server 主入口扩展与 M6+ 能力

### Roadpoint R4.1: agent 核心状态机模块最小实现
- Public Surface:
  - `nano_multiagent.agent.state`
  - `nano_multiagent.agent.policies`
  - `nano_multiagent.agent.prompting`
  - `nano_multiagent.agent.loop`
- Acceptance:
  - 输入 parts 可解析 `text/image`，并把 image 转为占位文本参与上下文
  - policy 支持最大轮次与上下文消息裁剪
  - prompt 构建包含 system + history + user
  - loop 能调用 `LLMClient.generate` 并返回 `TurnResult` assistant 文本
  - 目标测试全绿
- Tests Plan:
  - unit: `tests/unit/test_agent_state.py`, `tests/unit/test_agent_policies.py`, `tests/unit/test_agent_prompting.py`, `tests/unit/test_agent_loop.py`
  - contract: `tests/contract/test_agent_state_contract.py`
  - integration: 在 R4.2 执行
  - e2e: 在 R4.2 执行
- Commit Plan:
  - C1: `test(R4.1): ...（先红）`
  - C2: `feat(R4.1): ...（全绿）`
  - C3: `docs(R4.1): ...（记录hash/证据/下一步）`
- Commits:
  - C1: 2fc990e
  - C2: aa455be
  - C3: 132604e
- Evidence:
  - `pytest -q tests/unit/test_agent_state.py tests/unit/test_agent_policies.py tests/unit/test_agent_prompting.py tests/unit/test_agent_loop.py tests/contract/test_agent_state_contract.py`: `10 passed in 0.13s`

### Roadpoint R4.2: runtime 接线与事件落盘闭环验证
- Public Surface:
  - `nano_multiagent.agent.runtime`
  - `nano_multiagent.session.entries`（TURN_APPENDED 事件构造）
  - `nano_multiagent.session.manager`（turn 事件追加与历史重建接口）
- Acceptance:
  - `AgentRuntime.run` 支持 text 输入最小闭环（context -> llm -> assistant text）
  - image 输入保留占位契约且不触发工具链
  - user/assistant 结果写入 session 事件并可重建为历史消息
  - 提供 integration/e2e 证据验证“事件落盘 + 重开可读 + runtime 可调用”
  - `pytest -q` 全绿
- Tests Plan:
  - unit: `tests/unit/test_agent_runtime.py`, `tests/unit/test_session_manager.py`（增补 turn 事件场景）
  - contract: `tests/contract/test_agent_runtime_contract.py`
  - integration: `tests/integration/test_agent_runtime_integration.py`
  - e2e: `tests/e2e/test_agent_runtime_e2e.py`
- Commit Plan:
  - C1: `test(R4.2): ...（先红）`
  - C2: `feat(R4.2): ...（全绿）`
  - C3: `docs(R4.2): ...（记录hash/证据/下一步）`
- Commits:
  - C1: 6912f2f
  - C2: f60f488
  - C3: ce43210
- Evidence:
  - `pytest -q tests/unit/test_agent_runtime.py tests/contract/test_agent_runtime_contract.py tests/integration/test_agent_runtime_integration.py tests/e2e/test_agent_runtime_e2e.py`: `7 passed in 3.16s`
  - 事件落盘验证: `tests/integration/test_agent_runtime_integration.py` 断言 sqlite 中存在 4 条 `session.turn.appended` 事件，且第二轮请求上下文 roles 为 `system,user,assistant,user`
  - `pytest -q`: `54 passed in 3.33s`

## Milestone M5（已完成）: server 主入口（同步优先）
Goal:
- 完成 `server` 分层（`app.py`、`deps.py`、`auth.py`、`routes/*`）最小可用骨架
- 提供同步会话入口前置能力：鉴权、请求追踪、统一错误映射、会话 create/get/list
- 为 `POST /v1/sessions/{session_id}/messages` 同步主入口准备依赖装配（不进入 async/runs/SSE）
Exit Criteria:
- 会话接口最小可用：`POST /v1/sessions`、`GET /v1/sessions/{id}`、`GET /v1/sessions`（最小分页）
- 支持 `Authorization: Bearer` 与 `X-Request-Id`，响应回传 trace header
- 错误统一格式：`{error:{code,message,retryable,trace_id}}`
- 同步 `messages` 主入口完成（R5.2），并通过 `pytest -q` 全绿

### Roadpoint R5.1: server 分层骨架 + 会话接口最小完善
- Public Surface:
  - `nano_multiagent.server.app:create_app`
  - `nano_multiagent.server.deps`
  - `nano_multiagent.server.auth`
  - `nano_multiagent.server.routes.{global_routes,session}`
  - `POST /v1/sessions`、`GET /v1/sessions/{session_id}`、`GET /v1/sessions`
- Acceptance:
  - `server/` 按分层文件拆分，`app` 仅做装配与中间件/异常映射
  - 会话接口支持最小分页参数 `limit/offset`
  - 受保护接口要求 `Authorization: Bearer <token>`
  - 支持 `X-Request-Id` 透传并在错误体中回显 `trace_id`
  - 目标测试全绿
- Tests Plan:
  - unit: `tests/unit/test_server_auth.py`
  - contract: `tests/contract/test_sessions_contract.py`
  - integration: `tests/integration/test_app_bootstrap.py`
  - e2e: `tests/e2e/test_minimal_flow.py`, `tests/e2e/test_session_rebuild_e2e.py`, `tests/e2e/test_core_contract_entry_e2e.py`
- Commit Plan:
  - C1: `test(R5.1): ...（先红）`
  - C2: `feat(R5.1): ...（全绿）`
  - C3: `docs(R5.1): ...（记录hash/证据/下一步）`
- Commits:
  - C1: 807e366
  - C2: dfc66b0
  - C3: bf653a4
- Evidence:
  - `pytest -q tests/unit/test_server_auth.py tests/contract/test_sessions_contract.py tests/integration/test_app_bootstrap.py tests/e2e/test_minimal_flow.py tests/e2e/test_core_contract_entry_e2e.py tests/e2e/test_session_rebuild_e2e.py`: `9 passed in 0.48s`
  - 追踪回传验证: `tests/contract/test_sessions_contract.py::test_sessions_require_bearer_auth_and_use_unified_error_shape` 断言 `error.trace_id=req-auth-missing` 且响应头 `x-request-id=req-auth-missing`

### Roadpoint R5.2: 同步消息主入口接线（route -> runtime -> session）
- Public Surface:
  - `POST /v1/sessions/{session_id}/messages`
  - `nano_multiagent.server.routes.session`（同步消息处理）
  - `nano_multiagent.server.deps.get_agent_runtime`
- Acceptance:
  - 同步入口调用 `AgentRuntime.run(session_id, parts, stream=False)` 返回最终答复
  - 失败场景统一映射到标准 error 格式并携带 `trace_id`
  - 明确不实现 `messages:async` 与 `runs/*`
  - `pytest -q` 全绿
- Tests Plan:
  - unit: `tests/unit/test_server_message_route.py`
  - contract: `tests/contract/test_message_sync_contract.py`
  - integration: `tests/integration/test_message_sync_runtime_wiring.py`
  - e2e: `tests/e2e/test_message_sync_e2e.py`
- Commit Plan:
  - C1: `test(R5.2): ...（先红）`
  - C2: `feat(R5.2): ...（全绿）`
  - C3: `docs(R5.2): ...（记录hash/证据/下一步）`
- Commits:
  - C1: 6b7dfe6
  - C2: aa42097
  - C3: 本次文档提交
- Evidence:
  - `pytest -q tests/unit/test_server_message_route.py tests/contract/test_message_sync_contract.py tests/integration/test_message_sync_runtime_wiring.py tests/e2e/test_message_sync_e2e.py`: `6 passed in 0.35s`
  - `pytest -q`: `64 passed in 4.14s`
  - 调用链验证: `tests/integration/test_message_sync_runtime_wiring.py` 断言 `POST /messages` 后 sqlite 出现 user/assistant 两条 `session.turn.appended`
  - 错误与 trace 验证: `tests/contract/test_message_sync_contract.py::test_sync_message_not_found_uses_unified_error_with_trace_id` 断言 `error.trace_id=req-message-missing` 且响应头 `x-request-id=req-message-missing`
