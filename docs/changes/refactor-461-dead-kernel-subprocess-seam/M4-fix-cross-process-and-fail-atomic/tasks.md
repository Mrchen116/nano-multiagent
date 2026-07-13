# refactor-461-M4: Cross-process and fail-atomic lifecycle hardening — Tasks

> 对齐: ../design.md v1.3；验收后修复 round 3

## 目标

把 round 3 的十一个 symptom 收敛成三个可复用机制：config save 由稳定 sidecar lock 跨进程串行，并在同一事务内守护 source revision、backup identity 与失败回滚；Gateway 由公共、持久化的 process-instance identity 证明 signal ownership；e2e up/down 复用同一身份 schema，把 evidence、ownership、rollback 和 teardown 组成 fail-closed 状态机。

## 诚实并发边界

- 本系统所有 `save_local_config` 写者都通过稳定、不删除的 sidecar inode 取得 advisory lock，因此在 snapshot → backup → replace → directory durability 全区间跨进程串行。
- 不持有该 advisory lock 的外部写者不属于协作写者。系统会在 commit gate 检测 source identity/content/mode 漂移，但不声称消除“最后一次 CAS 返回”到 `os.replace` 系统调用之间不可避免的 POSIX 窗口，也不防御可任意改写父目录的恶意主体。

## 退出标准

- [x] 两个独立进程的 public config saves 在稳定 sidecar lock 上串行；backup fd/identity 一直守到 commit gate，mode drift 也拒绝覆盖。
- [x] replace 后 directory fsync 失败时 best-effort 恢复原 source 并再次持久化；恢复失败返回明确、不可误判为普通 CAS 的 outcome。
- [x] foreground Gateway 持久化 PID、OS start identity、resolved config、entry/argv；state 与 PID-only stop 都先只读验证 identity，mismatch 零信号且保留证据；matching legacy state 可无信号安全升级以维持 forward-read stop。
- [x] stop 的 TERM/KILL 两阶段都以 `min(poll_interval, remaining)` bounded sleep，长 poll 不越过 grace deadline。
- [ ] e2e-down 对 missing/non-regular external PID + 任一内部 evidence fail closed，零 Gateway/IM signal；只有 Gateway evidence 全无才可继续停 IM。
- [ ] e2e-up 无 live external owner 时只无信号清理 stale internal evidence；spawn 后 identity/readiness 失败回滚本次精确 PID，确认退出，只清匹配 lifecycle 文件并保留日志。
- [ ] e2e identity wait 使用 config startup timeout/full-stack budget；default symlink cwd 在参数解析后统一物理 canonicalize；脚本与 public runtime 共享 identity schema/clear primitive。
- [ ] affected、ruff、format、bash syntax、唯一 full non-e2e、真实 cold e2e 正常与 timeout rollback、default start/stop/restart 全部通过。

## 测试策略

- 被测行为：public save 的跨进程串行、backup path swap、chmod drift、post-replace fsync rollback；public foreground/start/stop 的 instance identity 与 bounded timing；e2e up/down 的 evidence matrix、delayed identity、timeout rollback 与 symlink cwd。
- 扩展已有测试：`tests/unit/personal_assistant/test_config_migration_transaction.py`、`tests/unit/personal_assistant/test_gateway_forced_stop.py`、`tests/integration/test_e2e_down_script.py`。
- 新建 `tests/unit/personal_assistant/test_gateway_process_identity.py`：既有 PID lifecycle 文件已超过 400 行软上限；新文件聚焦持久 identity schema 与 state/PID-only 的公共 stop ownership 门禁。
- 新建 `tests/integration/test_e2e_up_script.py`：down 集成文件已有独立职责；新文件用隔离 fake runtime 驱动真实 shell 入口，覆盖 delayed child 与 rollback，不把长驻真实服务加入非 e2e suite。
- 落层/marker：纯函数和 public Python lifecycle 在 `tests/unit/`；跨 OS 进程/真实 shell 入口在 `tests/integration/`；marker 无。两个独立 Python 进程测试 public `save_local_config`，不直接验 private lock helper。
- 一次性验收：tmux 中真实 cold `e2e-up.sh`/`e2e-down.sh`、identity mismatch/missing evidence/timeout rollback，以及临时 HOME 下 default start/stop/restart；只把结论写入 `progress.md`。

## Roadpoints

### R1 — 跨进程 config transaction 与失败回滚

- [x] C1 Red：补两个独立 public save、existing/new backup path-swap barrier、chmod drift、post-replace directory fsync failure 与 rollback-failure regression。
- [x] C2 Green：引入稳定 sidecar advisory lock；将 backup verified fd 守到 commit gate；CAS 纳入 mode；为 replace 后 durability failure 实施精确 best-effort rollback 和 typed failure outcome。
- [x] C3 Docs：记录协作/非协作 writer 边界、failure outcome、证据与回退点。

### R2 — 公共 Gateway process-instance identity

- [x] C1 Red：补 foreground identity persistence、state/PID-only mismatch 零信号、PID-only identity absent 证据保留、legacy state safe upgrade 和 fake-clock grace1/poll10 两阶段 deadline 回归。
- [x] C2 Green：新增单一 identity schema/read/write/verify/conditional-clear primitive；launch/stop 统一使用，所有 direct/group signal 前完成只读 ownership 验证。
- [x] C3 Docs：记录 identity 字段、fail-closed 判据、时间上界和兼容边界。

### R3 — e2e evidence state machine 与 spawn rollback

- C1 Red：补 external PID missing/nonregular + internal evidence、all-absent、stale preflight、delayed identity、timeout rollback、default symlink cwd 的 shell integration。
- C2 Green：up/down 共享 public identity schema；up preflight 无信号清 stale，spawn 后 trap 回滚精确 PID；down 对 incomplete evidence fail closed；identity wait 使用 startup/full-stack budget。
- C3 Docs：记录 evidence matrix、rollback ownership、真实 cold-stack 证据与回退点。

### R4 — 全链路验收收口

- 执行 selective affected、`ruff check .`、`ruff format --check .`、`bash -n`；共享 runner 空闲后只跑一次完整 `pytest -m "not e2e"`。
- 真实入口覆盖 cold e2e 正常起停、negative mismatch/missing evidence/timeout rollback 和 default start/stop/restart；不改 canonical spec/acceptance/verification。
