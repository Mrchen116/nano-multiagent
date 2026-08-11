# M2: Assistant Workflow Surfaces — Tasks

> 对齐: ../design.md（2026-08-10 approved）；同一 milestone 同时覆盖 Gateway、IM backend 与 Web frontend。

## Backend 退出标准

- [x] Gateway/IM 以 message-owned `background_returns` sidecar 持久化、实时投递和重连恢复 Workflow/Agent 原始后台返回，按 `task_id` 幂等。
- [x] Workflow child permission 以 run/call/request 精确 binding 回到原会话，覆盖 request/terminal 早于 anchor 与同 session 多 launch。
- [x] Agent capability 的 `commands` 只从 active `Workflow` allowlist + SDK saved/bundled/plugin discovery 生成；IM 只校验转发。
- [x] `/workflows` query/control/save、named invocation、`/config workflowSizeGuideline` 与按当前有效模型 capability 派生的完整 `/effort <level>` 共用 Web/外部 IM inbound seam；普通 level 在 Workflow disabled 时仍可用，`ultracode` 只在 Workflow+xhigh 时可用；群聊 `/effort` 始终要求精确 mention/reply target，不受 `ALWAYS` peer 影响。
- [x] PA 持久化 guideline，并在 IM config sync 后保留；只在 active Workflow runtime 中影响下一轮 tool description。
- [x] Gateway/IM focused contract、routing、replay、permission 与 command tests 通过。

## 前端目标

Web IM 只在既有消息气泡、过程时间线、工具详情和 slash picker 中消费 Workflow 数据：Workflow launch 详情输入在前、结果在后；后台 Workflow 与后台 Agent 的原始返回作为第三类 process item 显示；动态 Workflow 命令沿用已有 slash candidate 行。

## 前端退出标准

- [x] `Message` / canonical event / reducer / history merge typed 支持 `background_returns`，按 `task_id` 幂等合并。
- [x] `ToolCallsPanel` 按共享 `seq` 混排 thinking、tool 与 background-return；后台返回单独计数且不进入 tool/running/approval 统计。
- [x] `BackgroundReturnRow` 可展开显示既定来源、result/error、usage、duration、identity 与 artifact 字段；空正文消息仍可见。
- [x] `WorkflowCard` 仅使用 presenter 公开字段，固定 input-first/result-second；pending 无空结果区；deny 显示未执行且不伪造 run/task/duration。
- [x] slash picker 接受上游动态 command candidates，复用现有候选形态、过滤与插入语义；不同 Agent 的 `/effort` 保留各自 levels/source，群聊选择复用已有 mention 精确路由，前端不推导 Workflow enablement。
- [x] PA 随包 `nanoassistant-docs` 将 Agent 默认推理强度、会话 `/effort`、模型切换、群聊精确目标和 `ultracode` 的条件写成用户可操作说明。
- [x] PA 随包 `nanoassistant-docs` 将 Workflow 的显式/单次 opt-in、启动/权限、后台查询控制、终态、保存复用、Web/外部投递差异和 `ultracode` 成本边界作为独立按需手册页；同时在概览、聊天过程和故障排查补充最少必要入口。
- [x] 相关 Vitest、TypeScript/Vite build、diff-check 与真实浏览器 desktop/mobile 对照通过。

## 测试策略

- 被测行为：typed sidecar restore/reconcile/history merge；process 排序/计数/展开；Workflow running/completed/failed/denied 详情；空正文可见；动态 slash candidate。
- 已有测试在：`src/IM/frontend/src/features/chat/chat-stream-reducer.test.ts`、`components/tool-calls-panel.test.tsx`、`components/message-pane.test.tsx`、`components/slash-picker.test.tsx`（扩展同一 owner）。
- 落层/目录/marker：frontend Vitest unit/component，无 marker。
- 可选依赖 importorskip：无。
- 一次性验收证据：不为 `prototype.html` 或 slash picker 新增、提交截图资产；交互契约由永久 frontend/Gateway tests 覆盖。

### 受影响的既有测试处置

| 风险 / 行为 | 既有测试 | 处置 | 理由与保护 | 验证 |
|---|---|---|---|---|
| process timeline 既有 thinking/tool 顺序和统计 | `components/tool-calls-panel.test.tsx` | keep | 第三类 item 不改变前两类语义 | focused Vitest |
| AgentCard 输入先于结果 | `components/tool-calls-panel.test.tsx::renders agent with the full prompt BEFORE the result` | keep | Workflow 仿照而不改 Agent | focused Vitest |
| 空消息与 process 可见性 | `components/message-pane.test.tsx` | rewrite-merge | 把后台返回加入既有 process visibility 判据 | focused Vitest |
| slash built-ins / skills filtering and insertion | `components/slash-picker.test.tsx` | keep | 动态 command 使用同一 command candidate | focused Vitest |

### UI 状态矩阵

| 状态 | 覆盖计划 |
|---|---|
| default | Workflow launched；Workflow/Agent completed background return |
| loading | Workflow running，仅输入区，无结果区 |
| empty | 无 process 不显示；空正文 + background return 仍显示 |
| error | Workflow launch failed；background failed error 原样展示 |
| disabled | 本切片只消费上游 candidates；空动态列表保持既有命令/skill |
| submitting | N/A（复用现有 PermissionCard，不改批准提交） |
| permission denied | denied tool end 直接显示已拒绝 / 未执行，无 run/task/duration |
| long content | 复用现有详情滚动/换行；长 result/error 不撑破气泡 |
| missing/nullable data | 可选 identity/usage/artifact 缺省时只省略对应行 |
| mobile viewport | direct-agent message bubble 与 process 展开 |
| desktop viewport | direct-agent message bubble 与 process 展开 |
| dark mode | 项目无独立 dark-mode 契约；沿用既有深色 process detail |

### Prototype / Reference Contract

| Reference | Required contract | Evidence plan | Owner |
|---|---|---|---|
| `prototype.html` 等待确认 / denied | must-match | 永久 component test 核对没有预造 tool row；denied 无 running/duration/run | worker |
| 工具调用中 / 后台已启动 | must-match | 永久 component test 核对输入先于结果且 pending 隐藏结果 | worker |
| Workflow completed/failed/stopped | must-match | 永久 component test 核对后续普通消息中的 background-return 展开 | worker |
| Agent 后台完成 | must-match | 永久 component test 核对同一 BackgroundReturnRow | worker |
| presenter 文案与真实 id/path | may-adapt | 仅核字段集合和层级 | worker |

## 前端 Roadpoints

### F1 — typed sidecar 与 reducer/history merge

- 步骤：先补 canonical/message/reconcile/history 的 Red；再加入类型、校验、reducer 与 `task_id` merge。
- 验证：`chat-stream-reducer.test.ts` 及最小 history integration。

### F2 — Workflow detail 与 background process item

- 步骤：先补 renderer/timeline/message visibility Red；再实现 WorkflowCard、BackgroundReturnRow、i18n/CSS。
- 验证：`tool-calls-panel.test.tsx`、`message-pane.test.tsx`。

### F3 — dynamic slash candidate UI seam

- 步骤：先补动态 command 显示/过滤/选择 Red；再把上游 candidates 接入现有 SlashPicker。
- 验证：`slash-picker.test.tsx` 与 type/build。

### F4 — 浏览器对照与交付门禁

- 步骤：以永久 frontend/Gateway tests 核对 prototype 的行为契约；不保存或提交 prototype 截图。
- 验证：focused/all relevant Vitest、`npm run build`、`git diff --check`。

## Backend Roadpoints

### B1 — message sidecar 与终态投递

- 步骤：扩展 IM domain/DB/API/WS 和 Gateway active/idle/stranded notification carrier；保持外部 channel 不生成空文本。
- 验证：IM persistence/realtime/history、Gateway active/idle/replay focused tests。

### B2 — child permission 精确路由

- 步骤：以 parent tool call、Workflow run、Agent call、request id 建立窄 binding，支持乱序 buffer/tombstone 与 terminal cleanup。
- 验证：同会话双 launch、request-before-anchor、resolved/terminal-before-anchor、deny audit tests。

### B3 — capability 与命令

- 步骤：Gateway 从 active allowlist 和 SDK discovery 输出 `commands`；共享 inbound parser 执行 query/control/save/config/effort，named command 进入正常 Workflow tool 审批链。
- 验证：enabled/disabled A/B、IM wire forwarding、SDK truth、config persistence/sync tests。

### B4 — 集成门禁

- 步骤：合并 frontend slice 后运行 Gateway/IM focused regression、真实 Luna minimal lifecycle 与 Web/Feishu product journey。
- 验证：记录到 `progress.md`，最终由 verifier/reviewer 独立验收。
