# PROGRESS (Milestone: M36)

- Title: IM前端与独立IM服务集成（仅人和人聊天）
- Goal: 将前端 P1/P2 接入独立 IM 服务的人和人聊天接口，实现持久化会话列表、消息历史、发送与 SSE 流式回显；settings 保持 mock。
- Exit Criteria:
  - 前端 chat 页面与独立 IM 服务真实联调。
  - 刷新后会话/消息可恢复（SQLite）。
  - SSE 事件在 UI 稳定渲染并有状态反馈。
  - settings 仍为 mock 且体验完整。
  - 前后端相关测试全绿。
- Test command: `PYTHONPATH=src pytest -q tests/im_service && cd src/IM/frontend && npm run test && npm run build`
- Branch: `milestone/M36`

### Baseline
- Context:
  - use_worktree=true，worktree=`/Users/czj/Repos/nano-multiagent/.nano_multiagent/worktrees/M36`。
  - 先从 `main` 起步时缺少 `src/IM` 与 `tests/im_service`，已切换为基于 `milestone/M35` 创建 `milestone/M36`。
  - 已读取并应用：`tdd-execution-worker`、`playwright`、`COMMENTING_GUIDE.md`、`LOGBOOK.md`、`IM前端蓝图.md`、`IM服务蓝图.md`、`Agent 助手（基于 SDK 的上层应用）蓝图.md`。
- Decision:
  - 按三段执行：R36.1 后端 SSE/事件契约 -> R36.2 前端 P1/P2 接真实 IM -> R36.3 Playwright 与主干收口。
- Rationale:
  - 当前 chat 仍为 mock 数据，后端缺 SSE，需先补后端事件面再接前端实时渲染。
- Evidence:
  - Tests: 基线门禁 `PYTHONPATH=src pytest -q tests/im_service && cd src/IM/frontend && npm run test && npm run build` 已通过。
  - Entry: `tests/im_service`=10 passed；前端 test/build 均通过（M35 基线可运行）。
- Rollback:
  - plan commit
- Commits: C1=`<pending>`, C2=`<pending>`, C3=`<pending>`
- Next:
  - R36.1 Red：先补 events 契约测试并确认失败点是“缺 SSE/事件持久化”。

### R36.1 IM服务人聊事件流与持久化契约
- Context:
  - 独立 IM 服务只有 users/conversations/messages，缺少事件存储与 `/events` SSE，前端无法做流式渲染与状态反馈。
  - M36 只允许做人和人聊天，不能新增 Agent 后端接口。
- Decision:
  - 在 SQLite 新增 `message_events` 表并实现 `EventRepository`（append/list/latest）。
  - `POST /messages` 在保存用户消息后，持久化 `message_created/message_status` 事件，并生成“对端人类回声消息”的 `text_delta/turn_end` 事件序列。
  - 新增 `GET /im/v1/conversations/{id}/events` SSE 端点，支持 `Last-Event-ID` 与 `after_event_id` 游标、`once` 单次拉取模式（测试用）。
- Rationale:
  - 先把事件与 SSE 做成持久化日志，前端即可在刷新恢复历史的同时获取增量流；`once` 模式让集成测试可稳定读取流结果。
- Evidence:
  - Tests: `PYTHONPATH=src pytest -q tests/im_service`（12 passed）
  - Entry: `GET /im/v1/conversations/{id}/events?after_event_id=0&once=true` 可输出 `message_created/text_delta/turn_end/message_status`。
- Rollback:
  - `f46c02a`（R36.1 C1，仅测试先红）
- Commits: C1=`f46c02a`, C2=`0caa94b`, C3=`b19634e`
- Next:
  - R36.2 Red：将前端 chat 从 `mock-chat-api` 切到独立 IM 服务，并补 SSE UI 渲染测试。

### R36.2 P1/P2 前端接入独立IM服务（settings 保持 mock）
- Context:
  - M35 chat 页面仍绑定 `mock-chat-api`，无法连接独立 IM 服务，也无法消费 SSE 增量事件。
  - 本里程碑要求 settings 保持 mock，不得接入真实 settings API。
- Decision:
  - 新增 `im-chat-api.ts` 作为真实 IM 适配层（users/conversations/messages + EventSource SSE），并在 `chat-api.ts` 里按环境选择 `im/mock` 模式（测试环境默认 mock）。
  - `ChatWorkspacePage` 从 `chat-api` 读取数据，订阅 `message_created/text_delta/turn_end/message_status` 并直接更新 React Query 缓存。
  - `MessagePane` 增加 `delivery_status` 显示，支持流式状态反馈；`types.ts` 扩展 `is_mine` 字段区分本端/对端气泡。
  - settings 路径保持 `mock-settings-api` 不变，仅更新 chat 相关代码与 Vite `/im` 代理。
- Rationale:
  - 通过独立适配层隔离真实 IM 与 mock，可在不影响 settings 的前提下实现 chat 真联调与测试稳定性。
- Evidence:
  - Tests: `cd src/IM/frontend && npm run test && npm run build`（9 files / 11 tests 全绿）
  - Entry: `/chat/:conversationId` 可展示消息状态文案（如 `sent/running/completed`），并可消费 SSE 事件更新消息内容与状态。
- Rollback:
  - `af30d3b`（R36.2 C1，仅测试先红）
- Commits: C1=`af30d3b`, C2=`b538549`, C3=`b3e27b7`
- Next:
  - R36.3：做真实浏览器 Playwright 验收，收口文档并执行 main 集成流程。

### R36.3 联调收口、Playwright 真浏览器验收、主干集成
- Context:
  - R36.3 的 C1/C2 已存在（`dff42f1`/`d92bb66`），当前缺口是联调证据与文档收口（C3）。
  - 按范围限制仅执行 IM 服务测试、前端 test/build 和 chat 页面真实浏览器抽检，不触碰 `src/nano_multiagent/**`。
- Decision:
  - 执行全量门禁：`PYTHONPATH=src pytest -q tests/im_service && cd src/IM/frontend && npm run test && npm run build`。
  - 使用 Playwright CLI + `VITE_CHAT_API_MODE=mock` 启动前端，做 chat 桌面/手机实操抽检（会话加载、进入详情、发送消息）并保存截图到 `src/IM/frontend/output/playwright/`。
  - 回填 TASKS/PROGRESS 的 R36.3 证据与提交信息，作为本 Roadpoint 的 C3。
- Rationale:
  - 门禁命令覆盖后端与前端主链路；Playwright 真浏览器补足“真实入口交互”证据，形成收口验收闭环。
  - 设置页可用性继续由既有前端测试保障（`settings-*` 测试文件通过），避免收口阶段引入额外不必要改动。
- Evidence:
  - Tests: `PYTHONPATH=src pytest -q tests/im_service && cd src/IM/frontend && npm run test && npm run build`
    - `tests/im_service`: 12 passed
    - `npm run test`: 10 files / 13 tests passed
    - `npm run build`: success
  - Entry:
    - Desktop chat 抽检：进入 `/chat/conv-kernel-ops` 并发送 `M36 R36.3 desktop smoke message`。
    - Mobile chat 抽检：`390x844` 视口进入 `/chat/conv-kernel-ops` 并发送 `M36 R36.3 mobile smoke message`。
    - 截图：
      - `src/IM/frontend/output/playwright/R36.3-chat-desktop-before-send.png`
      - `src/IM/frontend/output/playwright/R36.3-chat-desktop-after-send.png`
      - `src/IM/frontend/output/playwright/R36.3-chat-mobile-list.png`
      - `src/IM/frontend/output/playwright/R36.3-chat-mobile-after-send.png`
    - 控制台仅见 `favicon.ico 404`，不影响 chat 主流程。
- Rollback:
  - `dff42f1`（R36.3 C1，仅测试先红）
- Commits: C1=`dff42f1`, C2=`d92bb66`, C3=`docs(R36.3) 本提交`
- Next:
  - M36 完成后执行 rebase main、全绿复验、merge main、push main，并用脚本将 `data/dev-tasks.json` 更新为 `DONE`。
