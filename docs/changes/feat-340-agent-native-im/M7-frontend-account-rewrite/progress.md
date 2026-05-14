# feat-340-M7 — Progress

## R1 — Account 页重写 + locale/通知偏好真存盘(R1+R2+R3 合并)

- Context: M7 范围(display_name / default_entry_node / locale / 通知开关)三个字段集中,
  分三个 roadpoint 拆得过细(每个只有 1-2 个组件改动),按 §9 反 anti-pattern 合并为一个 R1。
- Decision:
  - 后端:`UpdateMeRequest` 增可选 `locale` 字段,`MeResponse` 暴露 `locale`(repo `update_user` 已支持)。
    `bind_service.update_me` 透传 `locale`。
  - 前端:`account-page.tsx` 重写为 Identity / Defaults / Preferences 三组卡片,统一的 dirty/Save/Discard,
    成功后同步 i18n + auth-store user.locale + display_name,刷新页面后状态保持。
  - 新增 `features/notifications/notification-preference.ts`(localStorage `im_notifications_enabled` 持久化 +
    `useSyncExternalStore` hook),为 M9 通知功能提供统一的偏好开关,无 mock 依赖。
  - i18n EN/中 在 `settings.account.*` 下统一追加,不重写既有 key,与 M3-M6 范围零交集。
- Rationale:
  - 设计 §6 已确定保留 `im-card / im-input / im-btn / im-section-card` 等 utility 类,沿用即可获得对齐视觉。
  - i18next 切换 + localStorage 与 M3 的 `setLanguage` 完全一致,避免双轨。
  - `useSyncExternalStore` 让其它组件(M9 的通知监听器)与 Account 页共享真值无 race。
  - 通知首开触发 `Notification.requestPermission()`,只在 `permission === "default"` 时调用,避免重复弹窗。
- Evidence:
  - Tests:
    - 前端 vitest 全套 32 文件 / 178 测试通过(原 177 + R1 新增 1 个 account 入口测试,加 2 个偏好 hook 单测合并到 2 个文件)。
    - 后端 `tests/im_service/` 175 通过 / 15 deselect(15 项 deselect 为 M2 引入的 `_FakeKernelClient`
      未实现 `submit_message` 的预存在失败,已在 base 分支验证同样失败,与本 milestone 无关)。
  - Entry: `PATCH /im/v1/me {locale: "zh"}` 后 `GET /im/v1/me` 返回 `locale=zh`,刷新前端语言保持中文。
- Rollback: `git revert 0ed268d8 56a4ab1b 51e6532b`。
- Commits: C1=56a4ab1b, C2=0ed268d8, C3=本次。
- Next: M7 完成,准备 rebase + merge 到 `unit/feat-340-agent-native-im`。

### Roadpoint 合并说明

`tasks.md` 计划的 R1/R2/R3 实际合并执行,理由:每个原 R 单独不足以拆出 C1+C2+C3 三档而不强凑
(R2 只有 5 行后端 + 1 行前端;R3 只有 1 个 35 行新 hook + 1 行 import)。三者作为一个原子 commit
对 reviewer 更易理解:`feat(R1): account 页重写 + locale/通知偏好真存盘`。
