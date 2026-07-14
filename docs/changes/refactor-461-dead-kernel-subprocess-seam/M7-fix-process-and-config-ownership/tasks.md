# refactor-461-M7: Process and config ownership closure — Tasks

> 对齐: ../design.md；post-acceptance fix round 6

## 目标

关闭 Round 6 full code review 独立确认的 8 个 ownership 缺陷：任何配置写入只修改调用者拥有的字段；public foreground/background 与 e2e full stack 都必须以同一 process instance、完整 descendant set 和 durable evidence 为信号/清理授权，失败路径不得误杀、遗留暂停进程、擦除 live owner 或拆成无证据半栈。

## 退出标准

- [x] token refresh 与 IM Agent sync 使用锁内 read-modify-write 窄 mutation，双向顺序均保留对方最新字段。
- [x] foreground 与 background child 共享原子 per-config single-instance claim，不死锁、不覆盖 live owner；foreground 非独占 PGID 时 public stop 只 signal 已验证 PID。
- [x] public stop 冻结 PID/PPID/PGID/birth descendant set，逐组 TERM/KILL 并确认全员退出后才返回 `STOPPED`、清 evidence、释放 generation lock。
- [x] e2e freeze 任一失败出口恢复每个已 STOP 的 owned group；失败后 leader 与 detached descendant 均可继续运行或被后续安全回收。
- [x] e2e-up 遇到任意 internal Gateway/IM lifecycle evidence 都 fail closed；只有 e2e-down 在验证 original birth 已退出且 evidence revision 未变后清理，malformed/incomplete evidence 不启新 generation。
- [x] e2e-down 在有 full-stack evidence 时将 missing IM PID 视为 incomplete ownership；IM PID identity 绑定 birth + argv/cwd/port，TERM/KILL 前重验，PID reuse 零信号。
- [ ] affected、Ruff、format、bash syntax、diff check、test naming/size、最终 full non-e2e 与真实 public/e2e entry 全通过，无 process/file/lock residue。

## 测试策略

- 被测行为：token→agent 与 agent→token 双向保留；foreground+foreground/background 竞争；shared-PGID stop；public detached ShellRunner forced stop；freeze instability cleanup；live internal evidence up preflight；missing IM evidence；IM PID reuse before TERM/before KILL。
- 已有测试落点：`tests/unit/personal_assistant/test_gateway_build_runtime.py`、`test_gateway_pid_lifecycle.py`、`test_gateway_lifecycle_generation.py`；`tests/integration/test_gateway_owned_process_set.py`、`test_e2e_up_script.py`、`test_e2e_down_script.py`、`test_e2e_lifecycle_generation.py`。若单文件超过测试规范软上限，按行为新建小文件。
- marker：无。永久回归使用 tmp config、可控 fake runtime 或短生命周期真实子进程；所有子进程必须由测试持有并在 `finally` 按 PID/birth/PGID ownership 回收。
- 最终 full 使用项目固定命令并记录 duration；脚本测试等待时间必须从生命周期配置/可观测状态派生，不依赖 15/20/30 秒固定锁持有。
- 一次性验收：隔离 worktree 中的真实 foreground shared-PGID、public detached tool、live-internal up、IM identity down 与 cold up/down；证据写入 `progress.md`，临时文件/进程不入库。

## Roadpoints

### R1 — Narrow config mutations

- 状态：DONE
- C1 Red：复现 Agent sync 后 token refresh 删除 Agent，以及 token refresh 后旧 Agent sync 覆盖 token。
- C2 Green：提供 stable config lock 内的最新磁盘 read-modify-write API；token 与 Agent writer 只 patch owned field。
- C3 Docs：记录 mutation ownership、commit point、failure/rollback 与验证结果。

### R2 — Public instance and descendant ownership

- 状态：DONE
- C1 Red：复现 foreground 双实例覆盖、shared-PGID collateral signal、public forced stop 遗留 detached ShellRunner。
- C2 Green：统一 single-instance claim；按 exclusive/nonexclusive PGID 选择 group/PID signal；public stop 使用完整 frozen owned set并全员确认。
- C3 Docs：记录 claim handoff、signal authority、STOPPED commit point 与回退点。

### R3 — e2e IM and freeze failure ownership

- 状态：DONE
- C1 Red：复现 freeze失败残留 `Ts`、live internal evidence 被擦除、missing IM 半拆栈、IM PID reuse误杀。
- C2 Green：失败恢复全部 frozen groups；up 验证 internal owner；持久化并复核 IM process identity；缺失/漂移 fail closed。
- C3 Docs：记录 full-stack evidence matrix、IM identity schema、失败清理边界与回退点。

### R4 — Final gates

- 状态：TODO
- C1/C2：修复 xdist 暴露的脚本固定 timeout/cleanup 不稳定，只做由本轮 ownership 行为引起的最小调整。
- C3 Docs：完成 affected/static/唯一 full/真实入口/residue 证据，交回独立 reviewer/verifier/code review。
