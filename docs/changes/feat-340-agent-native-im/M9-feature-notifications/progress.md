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
