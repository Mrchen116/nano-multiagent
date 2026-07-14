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

- Status: DONE。
- C1 Red: `cb2f0cba2` 用两个同 config 的真实线程化 public 调用稳定复现 old stop 尚未 cleanup 时 replacement start 穿越 generation，以及旧 cleanup 无条件删除 replacement state revision。
- C2 Green: `6e9f43aea` 为 resolved config identity 引入 `~/.cache/nano-multiagent/gateway-lifecycle-locks/<sha256>.lock`；lock inode 持久存在、目录/文件收紧为 `0700/0600`，start 从 config load 到 state/identity commit、stop 从 snapshot 到 signal/expected cleanup 全程独占。state、PID 与 identity cleanup 均以本调用 snapshot 为 expected owner，launch rollback 不再采信 cleanup 时才出现的 identity。
- Validation: lifecycle generation + launch/PID/identity/forced-stop/legacy-upgrade affected suites `46 passed, 2 warnings`；affected Ruff、format 与 `git diff --check` 全通过。
- Commit boundary: public start 返回前拥有同 config generation lock 并完成 child/state/PID/identity 双侧复核；public stop 仅删除 snapshot 中的 exact state/PID/identity revision，随后才释放 lock 给 replacement start。
- Rollback: 可整体回退 R2 三个提交；external cache lock 可安全保留，代码从不 unlink stable lock inode，避免 waiter 与新 holder 落到不同 inode。

## R3 — e2e generation and IM preflight

- Status: DONE。
- C1 Red: `c8b16cc43` 增加 up/down 外部 lock barrier、dangling/nonregular/malformed IM evidence 零信号，以及 Gateway exit 期间 IM inode drift 零 IM signal 回归；旧实现稳定暴露 5 个 failure。
- C2 Green: `d70eaa79d` 增加共享 `scripts/e2e-lifecycle-lock.sh`，以 physical worktree hash 派生 `/tmp/nano-multiagent-e2e-lifecycle-locks-<uid>/` 下的 stable inode；up/down 从首项 lifecycle preflight 到 rollback/cleanup exit 持有 FD 9 flock，两个长驻子进程显式关闭该 fd。down 在任何 Gateway signal 前通过 held fd snapshot IM PID file 的 type/inode/mode/size/mtime/content，SIGTERM 前与 Step2 再验同一 revision，漂移时保留剩余 stack。
- Validation: 原有 up/down + 新 generation/preflight integration 全量 `35 passed in 143.54s`；强化后的新文件 `7 passed`；bash syntax、Ruff、format 与 `git diff --check` 全通过。
- Commit boundary: 同 worktree 的 up/down 永不跨 generation 执行；lock 永不写入用户 worktree，也不在脚本内 unlink。IM evidence invalid 时 Gateway/IM 零信号；Gateway shutdown 期间漂移时 IM 零信号且 remaining evidence 保留。
- Rollback: 可整体回退 R3 三个提交；外部空 lock inode 可安全保留，测试 override 同样拒绝落入 target worktree。

## R4 — Owned descendant process set and final signoff

- Status: TODO。
