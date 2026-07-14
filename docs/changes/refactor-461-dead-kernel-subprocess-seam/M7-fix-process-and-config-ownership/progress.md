# refactor-461-M7 — Progress

## Baseline

- Context: unit integration head `14cd8af19` 上执行 post-acceptance fix round 6。Round 6 reviewer/verifier 正常旅程 verdict 均为 pass；full code review 的 8 个 candidates 均经独立 Phase 2 真实/受控复现确认为 `CONFIRMED`。
- Scope: `src/personal_assistant/{main.py,config/local_store.py}`、`scripts/{e2e-up.sh,e2e-down.sh,e2e-owned-processes.sh}` 与相关 config/public/e2e regression；不发送 P2P，不修改 reviewer/verifier 历史结论。
- Confirmed findings: stale whole-config save lost update；foreground shared-PGID collateral kill；public stop 遗留 detached tool；foreground bypass single-instance claim；freeze failure 遗留 STOP descendant；up 擦除 live internal owner；down missing IM evidence 半拆栈；IM numeric PID reuse误杀。
- Baseline gates: M6 affected `104 passed`；上一轮唯一 full `3598 passed, 1 skipped`。Round 6 verifier full 为 `6 failed, 3592 passed, 1 skipped`：1 个全仓负载 ticker 抖动，5 个 shell/e2e 固定 timeout/lock 持有失败单跑通过；同轮实际留下的 `Ts` descendants 已安全清理并成为 freeze finding 的额外证据。
- Plan: R1 narrow config mutation；R2 public instance/descendant ownership；R3 e2e IM/freeze failure ownership；R4 final gates。

## R1 — Narrow config mutations

- Status: DONE。
- C1 Red: `08f605669` 用真实 config 复现 Agent sync 已写入 `agent-b` 后 token getter 基于 stale snapshot 将其删除，以及 token refresh 已写入新 token 后旧 sync snapshot 将 token 回退。
- C2 Green: `e306935d4` 提供 `update_local_config()`：在 stable sidecar lock 内读取并复核最新磁盘 revision、对 typed config 执行窄 mutation、复用原 transaction backup/atomic commit；token getter 仅替换最新 `im_service` 的 token pair，IM sync 仅 upsert 最新 agents。首次尚无磁盘文件时仅允许显式 `initial` seed。
- Validation: 双向 ownership regression + token/runtime/config-sync `33 passed`；完整 local-store/migration transaction `73 passed`；affected Ruff、format、`git diff --check` 通过。
- Commit boundary: 未被 mutation 拥有的字段始终来自持锁后读取的最新 revision；输入 stale `LocalConfig` 不再拥有整文件覆盖权。异常继续沿用原 backup、pre-replace CAS、directory fsync 与 rollback 语义。
- Rollback: 可整体回退 R1 测试/实现；不改变 `save_local_config()` 的显式整文件替换契约，只把 runtime 的 token/Agent writer 切到窄 mutation。

## R2 — Public instance and descendant ownership

- Status: DONE。
- C1 Red: `b28f307b6` 锁定 shared PGID 必须 single-PID signal、public stop 必须以完整 owned set 的退出作为 commit、同 config lifetime claim 必须拒绝第二 holder；旧实现分别误用 `killpg`、只等 leader 与完全没有 runtime claim。
- C2 Green: `6d804e2dd` 增加独立于 start/stop generation lock 的 stable per-config instance claim，foreground/background child 均在构建 runtime 前 nonblocking 获取并持有到 evidence cleanup；background parent 继续持 generation lock等待 child publication，二者不嵌套同一 inode。owned set 记录 leader PGID 是否独占：独占组按 detached-first/leader-last group signal，共享 leader PGID 只对验证过 birth 的 owned PIDs逐个 signal；freeze 失败逐 PID `SIGCONT`。public stop 在 generation lock 内冻结完整 set、TERM+resume、必要时 KILL，并在全员 birth 消失后才 cleanup/返回。
- Validation: public ownership + PID/generation + launch/publication/legacy +真实 descendant（排除尚待 R3 修复的旧 e2e rollback case）`41 passed, 1 deselected`，另 R2 核心组合 `19 passed, 1 deselected`；真实 public stop 回收 same-group 与 detached child。affected Ruff、format、diff check通过，无测试进程残留。
- Commit boundary: runtime instance lock 是“同 config 只有一个 live Gateway”的 lifetime claim；generation lock 是 start/stop publication transaction。`STOPPED` 仅在 frozen original births 全部退出且 exact evidence 清理完成后成立。
- Rollback: 可整体回退 R2 测试/实现；external instance lock inode 与 generation lock 同样稳定保留，不在 runtime unlink。共享 PGID 永不获得 group signal 权。

## R3 — e2e IM and freeze failure ownership

- Status: DONE。
- C1 Red: `5fa8c9633` 固化五条独立缺口：shell freeze 必须委托完整 Python transaction；invalid/live internal Gateway evidence 不得被 up 擦除或触发第二 generation；有完整 stack 但 `.im.pid` 缺失时任何 Gateway/IM signal 都不得发生；IM numeric PID 的 birth 与 evidence 不一致时零信号并保留证据。
- C2 Green: `e2e_freeze_gateway_owned_processes()` 直接调用 R2 的 `freeze_gateway_owned_process_set()`，从而由同一原语负责三次 capture/STOP/confirm 与每次失败后的逐 PID `SIGCONT`。`e2e-up.sh` 将 internal Gateway evidence 与 IM PID+identity pair 视为启动拒绝条件；它不再从 start 路径删除 runtime-owned evidence。IM 启动后先 atomic publish `.im.identity.json`，再发布 `.im.pid`；identity schema 为 `schema_version/pid/process_start/cwd/argv`，argv 固定绑定 `-m uvicorn IM.app:app --host 127.0.0.1 --port <ephemeral>`。
- C2 Green (continued): `e2e-down.sh` 在任何 Gateway signal 前 snapshot IM PID 与 identity 的 regular-file revision/content hash，验证 schema 与 current OS birth；full-stack evidence 存在却缺 `.im.pid` 直接失败。Gateway freeze、TERM、IM TERM、IM KILL 与 cleanup 前均复核 immutable snapshot；任一 birth/revision drift fail closed。只有 Gateway 和 IM original births 都观测为 exited、两个 IM evidence 文件仍等于 snapshot 时，才删除 PID+identity 并继续删除 config/env。
- Validation: targeted red→green `5 passed, 2 warnings in 12.68s`；rollback/real-descendant critical path `3 passed, 2 warnings in 31.71s`；full e2e lifecycle suite `46 passed, 2 warnings in 313.13s`。`bash -n scripts/e2e-up.sh scripts/e2e-down.sh scripts/e2e-owned-processes.sh`、affected Ruff/format、`git diff --check` 通过。
- Commit boundary: start 从不获得 teardown deletion authority；durable IM identity 写在 PID marker 前。任何缺失、malformed、PID reuse、birth/revision drift 均保留完整 stack evidence，避免“未知 owner 被杀”或“live owner 被擦除”。
- Rollback: 可整体回退 R3 tests/scripts；不会改 public Gateway identity schema，e2e 仅新增 `.im.identity.json` sidecar，正常 down/rollback 均按 matching PID 清除。

## R4 — Final gates

- Status: TODO。
