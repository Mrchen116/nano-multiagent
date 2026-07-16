# M8 Progress

## 2026-07-16 — Planning

- 基线：7 个相关测试文件共 `48 passed`。
- R1 根因：共享 stream helper 丢弃 terminal status，cron 因而无条件写 `completed` 与成功 awareness；helper 还维护了偏离 SDK 的本地 terminal literal。
- R2 根因：pipeline 已使用 typed-first identity，shadow adapter 却重新读取 raw metadata，导致 typed-only external message 被跳过。
- R3 根因：`_KernelClientShim` 未把 agent snapshot 的 skills 传给 unattended session，`None` 因而扩大为全量 skills。
- 范围澄清：本 milestone 不修改 `Kernel.create_session`、session binder 或 M7 语义；仅对非空受限 tuple 做精确透传，空 tuple 保持当前 `None` 兼容行为。
- 当前：R1 完成，进入 R2。

## 2026-07-16 — R1 completed

- C1 `cb82bd220`：新增 canonical failed/cancelled、partial text、no-terminal 与 cron 非成功 awareness 回归；红测在 `StreamRunOutcome` 缺失处失败。
- C2 `549ac842a`：共享 helper 使用 SDK `TERMINAL_RUN_STATUSES` 并返回 `StreamRunOutcome`；cron 按真实 status 写 history，只有 completed 才写 awareness；heartbeat 适配 typed outcome。
- 聚焦验证：`17 passed`（stream + cron owner chain + heartbeat IM delivery）。
- Ruff：R1 相关源文件与测试全部通过。

## 2026-07-16 — R2 completed

- C1 `f0d81bd94`：新增 typed-only external、typed IM-origin 与 legacy fallback 回归；旧实现分别暴露 skip 与 runtime dataclass JSON 序列化问题。
- C2 `922553f90`：adapter 复用 `external_identity_from_message`，自身执行 IM-origin guard，并在 HTTP persistence 前剥离 typed runtime metadata；标题消费 typed conversation type。
- 聚焦验证：`15 passed`（shadow adapter + inbound identity guard + gateway relay）。
- Ruff：R2 相关源文件与测试全部通过。

## 2026-07-16 — R3 completed

- C1 `a030ddea4`：新增 cron catalog lookup 与 heartbeat captured snapshot 两条 unattended 装配路径回归；restricted 与 empty/`None` 四个 case 均在缺失 `skills` kwarg 处失败。
- C2 `8293faa77`：`_KernelClientShim` 仅对非空 `agent.skills` 透传精确列表；空 tuple 明确传 `None`，不改 SDK/binder 语义。
- 聚焦验证：`24 passed`（unattended skills + heartbeat gate + cron runner + foreground binder compatibility）。
- Ruff：R3 相关源文件与测试全部通过。
- 当前：进入 milestone 全量验证与 unit 集成。

## 2026-07-16 — Milestone verification

- 已 rebase 到当时最新 `origin/unit/refactor-463`（含 M7），无冲突；M6 当时仍为独立 pending milestone，本段测试不声称覆盖 M6 组合 delta，待 M6 合入后由 M6/最终复验覆盖组合状态。
- M8 聚焦回归：`58 passed`。
- 全仓 Ruff：`All checks passed!`。
- 全量非 e2e：`3410 passed, 1 skipped, 20 deselected`，耗时 111.12 秒。

## 2026-07-16 — Integrated

- milestone 分支以 `--no-ff` 合入 `unit/refactor-463`；unit push 与临时 worktree/branch 清理按 worker 集成流程完成。

## 2026-07-16 — Strict live sign-off supplement

- 基于 unit `efd9d2d19` 建立临时 evidence worktree；当时 unit 含 M7+M8，M6 仍独立 pending。
- 真 IM `49277` + 真 Gateway/进程内 Kernel + fixture `65446` 的隔离栈触发 scheduled cron；公开 `CronTool runs` 从 running 收敛到 `failed`，保留真实 error、failure summary 与 Kernel run ID。
- owner direct conversation 的公开 messages API 只出现 `delivery_status=failed` 的 cron failure bubble，没有 completed/sent 成功 bubble 或成功 awareness；conversation 最终回到 idle。
- public cron-jobs API 删除 evidence job 后剩余匹配数为 0；Gateway、IM、fixture PID 均停止，两个端口关闭，生成状态已清理。
- typed shadow + IM-origin guard + unattended skills 的可控回归刷新为 `8 passed`。
- 完整命令、公开输出与清理证据见 `evidence/live-cron-failure.md`。
