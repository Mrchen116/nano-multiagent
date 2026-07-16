# M9 Progress

## 2026-07-16 — Planning

- Round 4 issue fingerprint `steer-identity-switch` 首次出现：SDK 先缓存 A，再按 session 二次查 active 并可能注入 B，最终却返回 A。
- Round 4 issue fingerprint `binder-reuse-ohistory` 首次出现：M7 已把扫描移出锁与 event loop，但稳定 reuse 仍每轮重放完整 JSONL。
- 正确修复边界：steer 原子性在 registry/SDK 源头闭合；binder 以 process-local provenance 缓存完成首次权威接管，不修改持久化 schema。
