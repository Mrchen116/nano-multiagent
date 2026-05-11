# feat-340-M7: frontend-account-rewrite — Tasks

> 对齐: ../design.md v1

## 目标

Account 页(`/settings/account`)按原型重写,所有字段(display_name / default_entry_node / locale / 通知开关)真实存盘,
EN/中 双语,移动端 Me 页也可触达。Account 提供的 locale 切换与 M3 顶栏/Me 页一致。

## 退出标准

- [x] Account 页桌面布局对齐原型(Identity / Defaults / Preferences 三块卡片)
- [x] display_name / default_entry_node_id 走 PATCH /im/v1/me 真存盘,dirty 检测正确
- [x] locale 选项可改且 PATCH 到后端,刷新页面后保持
- [x] 通知开关持久化到 localStorage 并暴露给 features/notifications 消费的 hook
- [x] 文案走 i18n,EN/中 全覆盖
- [x] vitest 全绿

## 测试策略

- **入口测试**:Account 页通过 router 渲染,模拟 fetch:加载 → 改 display_name + 切换 default_entry_node → Save → PATCH 命中 `/im/v1/me`,Save 按钮变灰(dirty 清除)
- **locale**:切换 locale 选项,Save 后 PATCH body 含 `locale`,且 i18n 切换 + localStorage 更新
- **notifications**:勾选通知开关,localStorage `im_notifications_enabled` = "1";`useNotificationPreference` hook 返回新值
- 行为测试为主,无 snapshot;现有 account-page.test.tsx 改写为新 UI 的入口测试

## Roadpoints

### R1 — 重写 Account 页面 UI + dirty/Save/Discard

- 步骤:
  - 重写 `account-page.tsx`,改为按原型布局的三组卡片
  - dirty 检测(任一字段改 → Save 高亮),Discard 回滚,Save 调 PATCH
  - 重写 `account-page.test.tsx` 覆盖新交互
  - i18n key 追加(`settings.account.*`)
- 验证: vitest account-page.test.tsx 通过;手测桌面布局

### R2 — Locale 切换打通 + 同步到后端 + auth-store

- 步骤:
  - 扩展 `updateAccount` API + 后端 `UpdateMeRequest` 支持 `locale`
  - Account 页加 locale 选择 segment;Save 时 PATCH `locale` 一并提交
  - 成功后调用 i18n `setLanguage(next)` 并同步 auth-store user.locale
  - 后端单测覆盖 locale 字段更新
- 验证: vitest + pytest 通过;手测切换语言后刷新仍为新语言

### R3 — Notifications 偏好 hook + Account 页开关

- 步骤:
  - 新增 `features/notifications/notification-preference.ts`(`useNotificationPreference` + `setNotificationPreference`,localStorage 持久化)
  - Account 页加通知开关,勾选 → 持久化 + 触发 `Notification.requestPermission()` 提示
  - 单元测试:开关切换写 localStorage;Account 集成测试断言 toggle 可见且响应点击
- 验证: vitest 全绿
