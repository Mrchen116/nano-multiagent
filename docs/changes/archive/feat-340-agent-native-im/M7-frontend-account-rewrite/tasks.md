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

### R1 — Account 页重写 + locale 真存盘 + 通知偏好 hook  [DONE]

实际执行合并了原 R1/R2/R3(理由见 progress.md "Roadpoint 合并说明")。一次性交付:

- 后端 `UpdateMeRequest.locale` + `MeResponse.locale` + `bind_service.update_me(locale)` 透传
- 前端 `account-page.tsx` 重写(Identity / Defaults / Preferences 三组卡片 + dirty/Save/Discard)
- 新增 `features/notifications/notification-preference.ts`(localStorage + `useSyncExternalStore` hook)
- i18n `settings.account.*` EN/中 追加;`me.language.*` 复用
- 入口测试 `account-page.test.tsx` + 单测 `notification-preference.test.tsx` + 后端
  `test_patch_me_persists_locale` 全部通过

验证: 前端 178 vitest 全绿,后端 IM 175 pytest 全绿(15 个 deselect 为 base 分支预存在的 M2 fake-kernel 问题)。
