# M8 Progress

## 2026-07-16 — Planning

- 基线：7 个相关测试文件共 `48 passed`。
- R1 根因：共享 stream helper 丢弃 terminal status，cron 因而无条件写 `completed` 与成功 awareness；helper 还维护了偏离 SDK 的本地 terminal literal。
- R2 根因：pipeline 已使用 typed-first identity，shadow adapter 却重新读取 raw metadata，导致 typed-only external message 被跳过。
- R3 根因：`_KernelClientShim` 未把 agent snapshot 的 skills 传给 unattended session，`None` 因而扩大为全量 skills。
- 范围澄清：本 milestone 不修改 `Kernel.create_session`、session binder 或 M7 语义；仅对非空受限 tuple 做精确透传，空 tuple 保持当前 `None` 兼容行为。
- 当前：R1 C1 红测准备中。

