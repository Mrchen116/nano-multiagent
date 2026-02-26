# ROADMAP

## Project Conventions
- 入口类型: HTTP API (`FastAPI`), app factory 为 `nano_multiagent.server.app:create_app`
- 测试命令: `pytest -q`
- tests 映射:
  - `tests/unit`: 纯逻辑与边界
  - `tests/contract`: HTTP 返回结构与字段契约
  - `tests/integration`: 组件串联（应用装配/存储交互）
  - `tests/e2e`: 从真实入口验证最小主流程

## Milestone M0（当前）: 工程骨架 + 最小可用 HTTP
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
  - C3: PENDING-C3-R0.2
- Evidence:
  - `pytest -q`: `8 passed in 0.33s`
  - 入口验证: `tests/e2e/test_minimal_flow.py::test_health_then_create_session` 通过（health=200, create-session=201）

## Milestone M1: Runtime Loop 与消息处理（仅占位）
Goal:
- 完成基础会话消息写入与运行时调度骨架
Exit Criteria:
- `sessions/{id}/messages` 最小闭环可测

## Milestone M2: 工具/技能/Hook 扩展（仅占位）
Goal:
- 接入工具注册、技能选择与 Hook 机制
Exit Criteria:
- 关键扩展点可加载并在最小场景可验证
