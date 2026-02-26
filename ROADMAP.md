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

## Milestone M1（当前）: core 契约层实现与冻结
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
  - C3: PENDING-C3-R1.1（本次 docs 提交后回填为真实 hash）
- Evidence:
  - `pytest -q`: `19 passed in 0.51s`
  - 入口级契约验证: `tests/e2e/test_core_contract_entry_e2e.py::test_create_session_entry_respects_core_id_contract` 通过

## Milestone M2: 工具/技能/Hook 扩展（仅占位）
Goal:
- 接入工具注册、技能选择与 Hook 机制
Exit Criteria:
- 关键扩展点可加载并在最小场景可验证
