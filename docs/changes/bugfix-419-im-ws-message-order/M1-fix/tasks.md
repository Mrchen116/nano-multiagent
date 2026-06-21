# M1-fix: 消息列表按 created_at 有序渲染

## 目标

修复 Chat v2 实时路径中消息列表渲染顺序不按 `created_at` 排序的 bug，使实时路径与刷新后一致。

## 退出标准

- WS `message.created` 事件到达顺序与 `created_at` 不一致时，渲染顺序仍按 `created_at` 升序。
- 乐观插入用户消息后，agent 回复的 `message.created` 事件到来时，顺序按 `created_at`。
- 保留已有去重逻辑（`:relay:` 过滤、message_id dedupe）。
- 其余 WS 事件（delta/completed/tool/permission 等 patchMessage 路径）行为不变。
- `chat-stream-reducer.test.ts` 新增回归 case，测试全绿。

## 测试策略

- 类型：`bug-regression`（历史 bug 修复）
- 落点：扩展 `src/features/chat/v2/chat-stream-reducer.test.ts`（已有对应测试文件，直接扩展）
- 新增两个 case：
  1. WS `message.created` 到达顺序与 `created_at` 相反时，渲染顺序仍按 `created_at` 升序
  2. 乐观插入用户消息后 agent 回复先到，顺序仍按 `created_at`
- 修复位置：`streamReducer`（`chat-workspace-page.tsx`）的 `reset` / `append_optimistic` / `event` 分支统一做 `sortByCreatedAt`，或在 `applyWsEvent` 的 `message.created` 路径做有序插入。
  - 优选：在 `streamReducer` 的 `ConversationState` 输出处统一排序（单点，覆盖三条路径）。
- 浏览器验收：通过 fix.md「验证」段记录，不引入新 E2E 基础设施。

## UI 状态矩阵

N/A（纯状态排序逻辑，无 UI 状态变化）

## 用户路径分类

`bug-regression`

## Roadpoints

| ID | 标题 | 状态 |
|---|---|---|
| R1 | C1 红测：两个回归 case 失败 | TODO |
| R2 | C2 实现：streamReducer 排序，红测转绿 | TODO |
| R3 | C3 文档：回填 fix.md 修复/验证段 | TODO |
