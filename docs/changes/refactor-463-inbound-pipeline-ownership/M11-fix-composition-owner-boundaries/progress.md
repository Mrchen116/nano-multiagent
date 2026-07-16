# M11 Progress

## 2026-07-16 — Planning

- Round 4 issue fingerprint `session-capability-double-projection` 首次出现；M8 的 unattended skills 漏传已证明该重复会产生真实行为漂移。
- Round 4 issue fingerprint `im-http-private-owner` 首次出现：shadow/main 跨 owner 依赖 config-sync underscore helper，删除 config-sync 会无理由破坏其他 owner。
- Round 4 release fingerprint `eof-whitespace` 首次出现：baseline diff 有三处 new blank line at EOF。
- 正确修复边界：共享 typed projection 只统一 capability 规则，不合并不同 lifecycle owner；IM HTTP 归一化迁入中立 transport module，不让 shadow 反向依赖 config sync。
