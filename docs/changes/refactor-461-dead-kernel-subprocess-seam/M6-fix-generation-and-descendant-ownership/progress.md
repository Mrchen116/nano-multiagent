# refactor-461-M6 — Progress

## Baseline

- Context: unit integration head `a084ce907` 上执行 post-acceptance fix round 5；七个 finder candidates 与 verifier W13 已由独立验证确认。
- Scope: `src/personal_assistant/{main.py,config/local_store.py}`、`scripts/{e2e-up.sh,e2e-down.sh}` 与相关 launch/config/e2e regression；不修改 canonical/acceptance/verification，不发送 P2P。
- Evidence: affected config/start/identity/e2e suites → `81 passed, 2 warnings in 81.33s`。Round-5 verifier 的唯一 full failure W13 已有 PDB 证据：产品 stop 成功后 retained `Popen` 成为 Darwin zombie，测试 finally 裸 `killpg` 触发 `EPERM`；最终 full 留到全部实现完成后单次执行。
- Plan: R1 config/start final gates；R2 public lifecycle generation；R3 e2e generation + IM preflight；R4 owned descendant set + final signoff。

## R1 — Config/start publication final gates

- Status: DONE。
- C1 Red: `1dc69c221` 增加 backup held-fd content/mode drift、durable state 后 child/identity 漂移、group-only rollback 与 quoted-path owned `Popen` 回归。
- C2 Green: `dd7d881ec` 让 existing/new backup 都通过 held fd 重读 content 并复核 mode/inode/link revision；background launch 在 durable state 后重验 poll、PID、identity PID+birth；rollback 每阶段仅向 owned process group 发一次信号，并由测试持有/回收真实 `Popen`。
- Validation: 三个 affected 文件 `15 passed, 2 warnings`；affected Ruff、format 与 `git diff --check` 全通过。
- Commit boundary: migration source replacement 仅在 backup held inode 的 content、mode 与 revision 仍等于 pre-commit snapshot 时发生；background start 仅在 state、PID、identity 与 child birth 同时稳定后返回成功。
- Rollback: 可整体回退 R1 两个提交；失败路径保留 startup failure 与 cleanup failure 双 cause，无法确认退出时保留 lifecycle evidence。

## R2 — Public lifecycle generation

- Status: TODO。

## R3 — e2e generation and IM preflight

- Status: TODO。

## R4 — Owned descendant process set and final signoff

- Status: TODO。
