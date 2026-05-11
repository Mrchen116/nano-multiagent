# feat-340-M9 — feature-notifications

## 目标

实现浏览器桌面通知(Notification API)体验:Agent 回复完成时,若标签页/窗口不在前台,弹出系统通知;点击通知聚焦窗口并跳到对应会话;用户可通过 Account/Me 页 toggle 开关。

## 退出标准(来自 design.md M9 行)

- 标签未激活时 agent 完成回复 → 系统通知弹出
- 点击 → 窗口聚焦 + 跳到对应会话
- toggle 关闭后不再弹

## 范围

- `src/IM/frontend/src/features/notifications/`:
  - `notification-api.ts`(新) — Notification API 封装(权限/弹出/点击 handler)
  - `document-visibility.ts`(新) — `visibilitychange` 订阅 + `isDocumentHidden()` 谓词
  - `agent-completion-notifier.tsx`(新) — 订阅 WS 流,过滤 `message.completed` 触发通知
  - 测试若干
- `src/IM/frontend/src/app/App.tsx`(微改) — 挂载 notifier
- `src/IM/frontend/src/features/me/me-page.tsx`(微改) — 增加通知 toggle(spec 要求 Me 页可开关)

## 测试策略

- **R1** — `notification-api.test.ts`:mock `globalThis.Notification`,断言权限请求/show/点击 handler 调用。
- **R2** — `document-visibility.test.ts`:模拟 `document.visibilityState` 变化,验证订阅。
- **R3** — `agent-completion-notifier.test.tsx`:挂载 hook,模拟 WS event 事件 + 隐藏标签 + 开关开 → 触发通知 mock;再覆盖各 gating 条件(开关关、tab 前台、权限非 granted、自己发的 user 消息 — 不弹)。
- **R4** — Me 页 toggle 测试:勾上 → preference 持久化;同时验证 Account 页已有 toggle 行为不破。

入口测试:agent-completion-notifier 集成测试用真实 reducer / 真实 preference 模块 + 假 WS event,断言用户真能收到通知。

## Roadpoints

| ID | 标题 | 状态 |
|---|---|---|
| R1 | notification-api 封装(权限/show/click) | DONE |
| R2 | document-visibility 订阅 + 谓词 | DONE |
| R3 | agent-completion-notifier(订 WS + 综合 gating + 点击聚焦/跳转) | DONE |
| R4 | App.tsx 挂载 + Me 页 toggle | DONE |
| R5 | progress.md 收尾 + e2e build 验证 | TODO |
