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
- Decision:
- Rationale:
- Evidence:
  - Tests: `PYTHONPATH=src pytest -q tests/im_service`
  - Entry:
- Rollback:
- Commits: C1=`<pending>`, C2=`<pending>`, C3=`<pending>`
- Next:

### R36.2 P1/P2 前端接入独立IM服务（settings 保持 mock）
- Context:
- Decision:
- Rationale:
- Evidence:
  - Tests: `cd src/IM/frontend && npm run test && npm run build`
  - Entry:
- Rollback:
- Commits: C1=`<pending>`, C2=`<pending>`, C3=`<pending>`
- Next:

### R36.3 联调收口、Playwright 真浏览器验收、主干集成
- Context:
- Decision:
- Rationale:
- Evidence:
  - Tests: `PYTHONPATH=src pytest -q tests/im_service && cd src/IM/frontend && npm run test && npm run build`
  - Entry:
- Rollback:
- Commits: C1=`<pending>`, C2=`<pending>`, C3=`<pending>`
- Next:
