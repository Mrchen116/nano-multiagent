# feat-340-M9 — progress

## Context

M7 已落地 `notification-preference.ts`(localStorage + `useSyncExternalStore` hook)和 Account 页 toggle。M9 接上后端事件(`message.completed`)、补 Notification API 调用、visibility 判断、点击聚焦/跳转,以及 Me 页 toggle。

## Roadpoints

<!-- 每个 R 完成后追加 -->

### R1 — notification-api 封装

- Context: 需要一处稳定的边界封装 `Notification` 全局,以便其余代码不到处 `typeof Notification` + 让单测注入 fake。
- Decision: `notification-api.ts` 暴露 `isNotificationSupported / ensureNotificationPermission / showAgentNotification`;`ensureNotificationPermission` 已 denied 不再追问。
- Rationale: 把"浏览器是否支持""权限态机""点击 handler 绑定"三件易出错的事集中收口。
- Evidence:
  - Tests: `vitest run src/features/notifications/notification-api.test.ts` — 9 通过。
- Rollback: revert C2(93741624) → C1(347164f0)。
- Commits: C1=347164f0, C2=93741624, C3=<本提交>
- Next: R2 visibility 谓词。

### R2 — document-visibility 谓词 + 订阅

- Context: Notification 触发条件之一是"标签未激活",需要稳定可测的边界。
- Decision: `document-visibility.ts` 暴露 `isDocumentHidden()` 和 `subscribeDocumentVisibility(cb)`,SSR/无 document 时退化为永远可见 + 空订阅。
- Rationale: 抽边界使 notifier 调用方无需自己 polyfill;订阅 unsubscribe 在卸载时归零监听。
- Evidence:
  - Tests: `vitest run src/features/notifications/document-visibility.test.ts` — 2 通过。
- Rollback: revert 7eaa3d9b → d6bc801e。
- Commits: C1=d6bc801e, C2=7eaa3d9b, C3=<本提交>
- Next: R3 agent-completion-notifier。

### R3 — agent-completion-notifier(WS 订阅 + gating + 点击跳转)

- Context: 主体功能。需要订 WS、过滤 agent 消息、综合 visibility/preference/permission gating、点击聚焦 + 跳会话。
- Decision:
  - 纯归约 `reduceNotifierEvent` + 纯 spec `buildNotificationSpec(priorState, event, ctx)`,二者完全可单测。
  - React `AgentCompletionNotifier`(空 DOM)挂在 App 内部:开自己的 `openChatStream` + visibilityRef + preferenceRef,onEvent 时先按 prior state 决策,再 reduce。
  - 单独开 WS(不寄生 chat workspace)使得在 /me 等非 chat 路由上也持续工作(场景 D)。
- Rationale: 集成测试覆盖"开关关 / tab 前台 / 用户消息回声 / 完整链路"四档,prior state 模式避免"completed 清掉了再查"的 off-by-one。
- Evidence:
  - Tests: `vitest run src/features/notifications/agent-completion-notifier.test.tsx` — 14 通过(7 单元 + 4 集成 + 3 reducer);完整 `vitest run` — 206/206 通过。
  - Entry: 集成测试以真实 reducer/真实 preference/真实 Notification 边界(注入 fake)断言"标签隐藏 → 弹通知 → 点击聚焦 + 路由跳到 /chat/<conv-id>"。
- Rollback: revert 0cbb6c1c → 1d0ceb53。
- Commits: C1=1d0ceb53, C2=0cbb6c1c, C3=<本提交>
- Next: R4 App.tsx 挂载 + Me 页 toggle。
