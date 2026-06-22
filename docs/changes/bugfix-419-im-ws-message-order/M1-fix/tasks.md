# M1-fix: 消息列表按 created_at 有序渲染

## 目标

修复 Chat v2 实时路径中消息列表渲染顺序不按 `created_at` 排序的 bug，使实时路径与刷新后一致。

## 退出标准

- WS `message.created` 事件到达顺序与 `created_at` 不一致时，渲染顺序仍按 `created_at` 升序。✅
- 乐观插入用户消息后，agent 回复的 `message.created` 事件到来时，顺序按 `created_at`。✅
- 保留已有去重逻辑（`:relay:` 过滤、message_id dedupe）。✅
- 其余 WS 事件（delta/completed/tool/permission 等 patchMessage 路径）行为不变。✅
- `chat-stream-reducer.test.ts` 新增回归 case，测试全绿。✅

## 测试策略

- 类型：`bug-regression`
- 落点：扩展 `src/features/chat/v2/chat-stream-reducer.test.ts` + `chat-workspace.integration.test.tsx`
- 新增三个 case，覆盖三条插入路径的排序行为

## UI 状态矩阵

N/A（纯状态排序逻辑，无 UI 状态变化）

## 用户路径分类

`bug-regression`

## Roadpoints

| ID | 标题 | 状态 |
|---|---|---|
| R1 | C1 红测：三个回归 case 失败 | DONE |
| R2 | C2 实现：compareMessages + 三处排序，全绿 | DONE |
| R3 | C3 文档：fix.md 回填 + progress.md 补齐 | DONE |
