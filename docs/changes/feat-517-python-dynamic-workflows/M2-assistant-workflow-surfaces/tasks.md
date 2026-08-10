# M2: Assistant Workflow Surfaces — Tasks

> 对齐: ../design.md（2026-08-10 approved）；本页当前只记录前端切片，Gateway / IM backend / 飞书由同 milestone 的其他实施者补充。

## 前端目标

Web IM 只在既有消息气泡、过程时间线、工具详情和 slash picker 中消费 Workflow 数据：Workflow launch 详情输入在前、结果在后；后台 Workflow 与后台 Agent 的原始返回作为第三类 process item 显示；动态 Workflow 命令沿用已有 slash candidate 行。

## 前端退出标准

- [x] `Message` / canonical event / reducer / history merge typed 支持 `background_returns`，按 `task_id` 幂等合并。
- [x] `ToolCallsPanel` 按共享 `seq` 混排 thinking、tool 与 background-return；后台返回单独计数且不进入 tool/running/approval 统计。
- [x] `BackgroundReturnRow` 可展开显示既定来源、result/error、usage、duration、identity 与 artifact 字段；空正文消息仍可见。
- [x] `WorkflowCard` 仅使用 presenter 公开字段，固定 input-first/result-second；pending 无空结果区；deny 显示未执行且不伪造 run/task/duration。
- [x] slash picker 接受上游动态 command candidates，复用现有候选形态、过滤与插入语义；前端不推导 Workflow enablement。
- [x] 相关 Vitest、TypeScript/Vite build、diff-check 与真实浏览器 desktop/mobile 对照通过。

## 测试策略

- 被测行为：typed sidecar restore/reconcile/history merge；process 排序/计数/展开；Workflow running/completed/failed/denied 详情；空正文可见；动态 slash candidate。
- 已有测试在：`src/IM/frontend/src/features/chat/chat-stream-reducer.test.ts`、`components/tool-calls-panel.test.tsx`、`components/message-pane.test.tsx`、`components/slash-picker.test.tsx`（扩展同一 owner）。
- 落层/目录/marker：frontend Vitest unit/component，无 marker。
- 可选依赖 importorskip：无。
- 一次性验收证据：`evidence/` 下 desktop/mobile 截图与 prototype 对照；不进入自动化套件。

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
| `prototype.html` 等待确认 / denied | must-match | 真浏览器核对没有预造 tool row；denied 无 running/duration/run | worker |
| 工具调用中 / 后台已启动 | must-match | desktop/mobile 截图，输入先于结果且 pending 隐藏结果 | worker |
| Workflow completed/failed/stopped | must-match | 后续普通消息内 background-return 展开截图 | worker |
| Agent 后台完成 | must-match | 同一 BackgroundReturnRow 展开截图 | worker |
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

- 步骤：隔离真栈按 prototype desktop/mobile 状态核对，检查 console/network，保存 evidence。
- 验证：focused/all relevant Vitest、`npm run build`、`git diff --check`。
