# TASKS (Milestone: M36)

- Test command: `PYTHONPATH=src pytest -q tests/im_service && cd src/IM/frontend && npm run test && npm run build`
- Branch: `milestone/M36`
- Milestone status: `DONE`
- Scope guard:
  - Allowed: `src/IM/**`、`tests/im_service/**`、`TASKS/**`、`PROGRESS/**`、`LOGBOOK.md`、`data/dev-tasks.json（仅脚本）`。
  - Forbidden: `src/nano_multiagent/**`、`ROADMAP.md`、与任务无关 tests。

## [DONE] R36.1 IM服务人聊事件流与持久化契约
- Acceptance:
  - IM 服务新增 `GET /im/v1/conversations/{id}/events` SSE 端点，支持按 event_id 顺序消费。
  - 发送消息后会写入消息历史（SQLite）并产出可用于 UI 状态驱动的事件（`message_created` / `text_delta` / `turn_end` / `message_status`）。
  - 刷新后会话与消息历史仍可通过现有 conversations/messages API 恢复。
  - 不新增任何 Agent 后端接口，仅保持人和人聊天语义。
- Tests Plan:
  - `unit`: 选。补 repository/schema 对 event 存储与查询的边界测试。
  - `contract`: 选。补 app route 注册与事件字段契约检查。
  - `integration`: 选。补 HTTP 级 messages+events roundtrip/SSE 输出验证。
  - `e2e`: 不选。该点聚焦后端能力，浏览器端放在 R36.3。
- Expected Tests:
  - `tests/im_service/unit/test_db_init.py`
  - `tests/im_service/unit/test_repositories.py`
  - `tests/im_service/unit/test_message_repo.py`
  - `tests/im_service/integration/test_messages_api.py`
- DoD:
  - `PYTHONPATH=src pytest -q tests/im_service` 全绿。
  - C1/C2/C3 齐全，PROGRESS 记录决策与证据。
- Commits:
  - C1: `8435abd`
  - C2: `16ee8eb`
  - C3: `790ed56`
- Status: DONE

## [DONE] R36.2 P1/P2 前端接入独立IM服务（settings 保持 mock）
- Acceptance:
  - `/chat`、`/chat/:conversationId` 改为接入独立 IM 服务接口，不再使用 chat mock 数据源。
  - 会话列表与消息历史基于后端数据展示，刷新后可恢复。
  - 发送消息后可接收 SSE 事件并在 UI 稳定渲染（增量文本 + 状态反馈）。
  - `/settings/*` 仍全部使用 `mock-settings-api` 读写，不接入后端真实 settings。
- Tests Plan:
  - `unit`: 选。补聊天组件对事件状态渲染、消息去重/更新逻辑测试。
  - `contract`: 选。补前端 chat API 事件解析字段契约测试。
  - `integration`: 选。补 chat workspace 在路由下的发送与流式回显行为测试。
  - `e2e`: 不选。真实浏览器验收放到 R36.3。
- Expected Tests:
  - `src/IM/frontend/src/features/chat/*.test.tsx`（新增/更新）
  - `cd src/IM/frontend && npm run test`
- DoD:
  - `cd src/IM/frontend && npm run test && npm run build` 全绿。
  - C1/C2/C3 齐全，PROGRESS 记录决策与证据。
- Commits:
  - C1: `939af42`
  - C2: `cdc4d06`
  - C3: `4006d1d`
- Status: DONE

## [DONE] R36.3 联调收口、Playwright 真浏览器验收、主干集成
- Acceptance:
  - 前后端完整门禁命令全绿。
  - Playwright 在真实浏览器完成 chat 页关键流（加载会话、发送、SSE 回显、状态变化）检查并留证。
  - settings 页仍可完整交互并保持 mock 体验。
  - 文档与 dev-tasks 状态更新完整。
- Tests Plan:
  - `unit`: 不选。前两点已覆盖，收口阶段不新增单测目标。
  - `contract`: 不选。契约在 R36.1/R36.2 已落地。
  - `integration`: 选。跑全量 milestone test command。
  - `e2e`: 选。Playwright CLI 真实浏览器验收。
- Expected Tests:
  - `PYTHONPATH=src pytest -q tests/im_service && cd src/IM/frontend && npm run test && npm run build`
  - Playwright CLI 命令与截图（桌面+手机）
- DoD:
  - 全量门禁通过 + Playwright 验收完成。
  - C1/C2/C3 齐全，PROGRESS 记录证据与回滚点。
- Commits:
  - C1: `b810984`
  - C2: `b296d2c`
  - C3: `0774005`
- Status: DONE
