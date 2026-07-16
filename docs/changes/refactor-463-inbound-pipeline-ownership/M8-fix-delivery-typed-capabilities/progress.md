# M8 Progress

## 2026-07-16 — Planning

- 基线：7 个相关测试文件共 `48 passed`。
- R1 根因：共享 stream helper 丢弃 terminal status，cron 因而无条件写 `completed` 与成功 awareness；helper 还维护了偏离 SDK 的本地 terminal literal。
- R2 根因：pipeline 已使用 typed-first identity，shadow adapter 却重新读取 raw metadata，导致 typed-only external message 被跳过。
- R3 根因：`_KernelClientShim` 未把 agent snapshot 的 skills 传给 unattended session，`None` 因而扩大为全量 skills。
- 范围澄清：本 milestone 不修改 `Kernel.create_session`、session binder 或 M7 语义；仅对非空受限 tuple 做精确透传，空 tuple 保持当前 `None` 兼容行为。
- 当前：R1 完成，进入 R2。

## 2026-07-16 — R1 completed

- C1 `1554f2ae2`：新增 canonical failed/cancelled、partial text、no-terminal 与 cron 非成功 awareness 回归；红测在 `StreamRunOutcome` 缺失处失败。
- C2 `9641c5ff0`：共享 helper 使用 SDK `TERMINAL_RUN_STATUSES` 并返回 `StreamRunOutcome`；cron 按真实 status 写 history，只有 completed 才写 awareness；heartbeat 适配 typed outcome。
- 聚焦验证：`17 passed`（stream + cron owner chain + heartbeat IM delivery）。
- Ruff：R1 相关源文件与测试全部通过。

## 2026-07-16 — R2 completed

- C1 `8534fd85f`：新增 typed-only external、typed IM-origin 与 legacy fallback 回归；旧实现分别暴露 skip 与 runtime dataclass JSON 序列化问题。
- C2 `25dce7f1a`：adapter 复用 `external_identity_from_message`，自身执行 IM-origin guard，并在 HTTP persistence 前剥离 typed runtime metadata；标题消费 typed conversation type。
- 聚焦验证：`15 passed`（shadow adapter + inbound identity guard + gateway relay）。
- Ruff：R2 相关源文件与测试全部通过。
