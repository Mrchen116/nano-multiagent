# M2 — Progress

> 本页当前只记录前端切片；Gateway / IM backend / 飞书进展由同 milestone 的其他实施者补充。

## Frontend baseline

- Context: approved design 只扩展既有 Web IM surface，不新增 Workflow 页面、进度面板、详情页、终态卡或专属批准卡。
- Decision: 复用 `MessageBubble -> ToolCallsPanel -> ToolDetailBody`，并给 `SlashPicker` 增加动态 command candidate 输入接口。
- Evidence:
  - Tests: TDD 第一轮 9 条新断言按预期因 sidecar/renderer 缺失而红；动态 command union 第二轮 2 条断言按预期因 helper 缺失而红。
  - Entry: production Web IM direct-agent chat；prototype 仅作 must-match 状态契约。
  - Frontend State Matrix: 见 `tasks.md`。
  - Browser QA: 隔离 IM/Gateway/Vite 真栈，真实登录后由 production REST history 加载验收消息；desktop `1440x1000` 与 mobile `390x844` 均完成展开交互和刷新恢复，browser console 0 error / 0 warning。
  - E2E/Regression: `e2e-up.sh` 使用 worktree 私有 DB/config/node/ports；验收结束已执行 `e2e-down.sh`，无 PID/state/config/ports 残留。
  - Visual/Interaction: [`evidence/`](evidence/) 保存 permission、running、launched、denied、Workflow/Agent completed、failed、stopped/empty-text 的 desktop/mobile 截图。
  - Prototype Comparison: must-match 项全部通过，详见下表。
- Rollback: revert 本前端 scoped commit；无需数据迁移。
- Commits: 本前端 scoped commit。

## Frontend F1 — typed sidecar 与 reducer/history merge

- Context: `background_returns` 要同时穿过 canonical WS、created/reconciled reducer 与 REST-history refetch，不能让较慢历史覆盖较新的 live terminal projection。
- Decision: 在 `Message` / `WsEvent` 建立精确 union；canonical 边界校验枚举、可选字段和非负数；history 以 `task_id` 合并，重复项由 live 值覆盖并按 `seq` 排序。
- Rationale: IM 只保存 message-owned sidecar，不建立 Workflow run projection；同 task 的 realtime/history 重放保持一条。
- Evidence: `chat-stream-reducer.test.ts` 与 `background-return-history.test.ts` 覆盖 created/reconciled、非法 payload、server/live 乱序及幂等合并；浏览器 reload 后 7 条消息及 4 条后台返回完整恢复。
- Rollback: 回退 typed sidecar、canonical/reducer/history merge 同一组改动。
- Commits: 本前端 scoped commit。

## Frontend F2 — Workflow detail 与 background process item

- Context: Workflow launch 和后台终态是两个生命周期；后台返回还必须与 Agent 后台结果采用同一种归因呈现。
- Decision: `WorkflowCard` 只读 `description/source/guideline/script_preview/status/name/runId/taskId/scriptPath/transcriptDir/error`，固定输入在结果前；`BackgroundReturnRow` 成为 thinking/tool 之外第三类 process item。
- Rationale: launch tool completed 只代表成功后台启动，终态继续留在后续普通消息；background-return 不污染工具、running 或批准计数。
- Evidence: `workflow-surfaces.test.tsx` 覆盖 running 无结果、launch 顺序、deny 未执行且无 run/task/duration、共享 seq、独立计数、Workflow/Agent 原始返回、failed/stopped partial result 和 empty-text 可见；截图见 `desktop-workflow-*.png` 与 `mobile-workflow-*.png`。
- Rollback: 回退 renderer/process/i18n/CSS 与对应 tests。
- Commits: 本前端 scoped commit。

## Frontend F3 — dynamic slash candidate UI seam

- Context: `/workflows`、`/deep-research`、saved/plugin workflows 与 `/config` 必须随同一个 active Workflow snapshot 出现或消失。
- Decision: frontend 只消费 Agent capability 的可选 `commands: [{name, description}]`；conversation agents 做 name union/dedupe 后传给既有 `SlashPicker`，不本地检查 tool allowlist，也不硬编码 Workflow 命令。
- Rationale: Gateway 是 active snapshot 与 saved discovery 的 owner；前端仅复用 command candidate 的过滤和插入行为，避免第二能力开关。
- Evidence: `slash-candidates.test.ts` 覆盖多 Agent union/dedupe 与空列表；`slash-picker.test.tsx`、`message-pane.test.tsx` 覆盖动态候选过滤、选择和 `/name ` 插入；TypeScript build 验证从 capability wire 到 `ChatWorkspacePage -> MessagePane` 的完整接线。
- Rollback: 回退 capability command 类型、assembly helper 与 props 接线。
- Commits: 本前端 scoped commit。

## Frontend F4 — browser / gates

- Context: unit/component tests不能证明真实历史 API、消息滚动容器和 mobile 布局的组合结果。
- Decision: 用 production repository 给隔离 DB 写入合法 domain records，再经真实 IM REST history 与 Web frontend 加载；交互全部在真实 Playwright 浏览器完成。
- Rationale: 既不发明测试 wire，也不依赖 Luna 成本；相同记录覆盖 prototype 的全部 frontend must-match 状态。
- Evidence:
  - Tests: final focused frontend regression `7 files / 233 tests` passed；`npm run build` passed（仅保留既有 chunk-size warning）；`.venv/bin/python scripts/docs_check.py` 与 `git diff --check` passed；TDD red/green 如 F1/F3。
  - Entry: `http://127.0.0.1:<vite>/chat/<ephemeral-conversation>`，后端为 `e2e-up.sh` 生成的私有 IM/Gateway。
  - Frontend State Matrix: default/loading/empty/error/disabled/denied/nullable/mobile/desktop 均由自动测试或截图覆盖；PermissionCard submitting 复用既有实现，本切片未改。
  - Browser QA: desktop `1440x1000`、mobile `390x844`；真实点击逐层展开；reload 后 background-return 仍显示且计数不变；console 0 error / 0 warning。
  - E2E/Regression: API history 返回 7 条真实消息：3 个 Workflow launch 状态、2 个 completed background returns（Workflow + Agent）、1 个 failed、1 个 empty-text stopped。
  - Visual/Interaction: process summary 保持轻量；详情仍在现有折叠块内；窄屏无水平溢出或独立 Workflow surface。
  - Prototype Comparison: 见下表；字段文案采用当前产品 i18n，允许 may-adapt。
- Rollback: 删除 frontend scoped commit 与 `evidence/`；无持久化迁移。
- Commits: 本前端 scoped commit。

Prototype Comparison:

| Reference | Required contract | Actual evidence | Viewport / state | Result | Deviation rationale |
|---|---|---|---|---|---|
| `prototype.html` Workflow running/launched | must-match | [`desktop-workflow-running.png`](evidence/desktop-workflow-running.png)、[`desktop-workflow-launched.png`](evidence/desktop-workflow-launched.png)、[`mobile-workflow-launched.png`](evidence/mobile-workflow-launched.png) | desktop/mobile；pending/terminal | pass | running 只有输入；launch 后才在下方出现 result |
| Workflow completed/failed/stopped | must-match | [`desktop-workflow-background-return.png`](evidence/desktop-workflow-background-return.png)、[`desktop-workflow-failed.png`](evidence/desktop-workflow-failed.png)、[`desktop-workflow-stopped-empty-message.png`](evidence/desktop-workflow-stopped-empty-message.png)、[`mobile-workflow-stopped-empty-message.png`](evidence/mobile-workflow-stopped-empty-message.png) | desktop/mobile；completed/failed/stopped/empty text | pass | failed 同时保留 raw result/error；stopped 空正文仍有过程项 |
| Agent background completed | must-match | [`desktop-workflow-and-agent-background-returns.png`](evidence/desktop-workflow-and-agent-background-returns.png)、[`mobile-workflow-background-return.png`](evidence/mobile-workflow-background-return.png) | desktop/mobile；completed | pass | 与 Workflow 同属第三类 process item，但各自显示 agent/run identity |
| permission pending/denied | must-match | [`desktop-collapsed.png`](evidence/desktop-collapsed.png)、[`desktop-workflow-denied.png`](evidence/desktop-workflow-denied.png)、[`mobile-workflow-permission.png`](evidence/mobile-workflow-permission.png) | desktop/mobile；pending/deny | pass | pending 只有既有 PermissionCard；deny 直接为 Not run，无 run/task/duration |

## Promotion Candidates

None.
