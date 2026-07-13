# refactor-461-M6: Generation and descendant ownership — Tasks

> 对齐: ../design.md；post-acceptance fix round 5

## 目标

让 config migration、public Gateway lifecycle 与 e2e full-stack lifecycle 都以稳定 generation lock 为提交边界，并把 Gateway 关闭所有权扩展为 PID/birth 验证的完整 descendant process set。任何旧 generation、证据漂移、IM preflight 异常或 descendant identity drift 都必须在发信号/删证据/停 IM 前 fail closed。

## 退出标准

- [ ] migration backup commit gate 从 held fd 读取并复核完整 content + mode，existing/new backup 原地漂移均不覆盖 source。
- [ ] background state durable publish 后 return 前重验 child poll、PID、identity PID+birth；失败进入同一 rollback，startup rollback 每阶段只 group signal 一次。
- [ ] quoted-path 真实进程测试保留并 reap owned `Popen`，完整 non-e2e 无 Darwin zombie teardown failure。
- [ ] public start/stop 全程持有同一 per-config stable generation lock；所有 cleanup 都携带 expected state/identity，old stop 不删除 new start state。
- [ ] e2e-up/down 从第一项 preflight 到 rollback/exit 持有同一 worktree generation lock，lock 不落用户 worktree residue；并发 up/down 不跨 generation 操作。
- [ ] down 在任何 Gateway signal 前完整 snapshot IM PID evidence，dangling/nonregular/malformed IM 产生零 Gateway/IM signal、全栈保留；Step2 复核相同 revision。
- [ ] e2e Gateway 为 PID==PGID 的独占 session leader；down/rollback 冻结 leader、same-group 与 detached descendant 的 PID/PPID/PGID/birth ownership set，逐组 TERM/KILL 并确认全员退出后才 cleanup/stop IM。
- [ ] affected、ruff、format、bash syntax、diff check、最终唯一 full non-e2e 与真实 operator/e2e/descendant entry 全通过，无本轮 process/file/lock residue。

## 测试策略

- 被测行为（来自退出标准）：backup content/mode guard；post-state child exit；group-only rollback；owned Popen reap；public old-stop/new-start barrier；e2e up/down generation barrier；IM evidence preflight；same-group/detached descendant cleanup 与 birth-drift fail-closed。
- 已有测试在：`tests/unit/personal_assistant/test_config_migration_transaction.py`、`test_gateway_startup_publication.py`、`test_gateway_launch.py`（扩展）；`tests/integration/test_gateway_legacy_state_upgrade.py`、`test_e2e_up_script.py`、`test_e2e_down_script.py`（扩展）。owned process set 若现有 e2e shell 文件超过软上限，按行为新建 `tests/integration/test_gateway_owned_process_set.py`，避免继续堆叠。
- 落层/目录/marker：`tests/unit/` 与 `tests/integration/`，marker：无；永久回归使用短生命周期真实子进程/受控 shell entry，不依赖外部服务。真实 full-stack 仅作一次性验收。
- 可选依赖 importorskip：无。
- 本 milestone 产生的一次性验收证据（收尾删除，不进套件）：隔离临时目录中的真实 quoted start/restart/legacy stop、cold up/down、concurrent up/down、malformed IM、leader + same-group + detached descendant 与 PID/birth drift logs；结论写入 `progress.md`。

## Roadpoints

### R1 — Config/start publication final gates

- 状态：TODO
- C1 Red：扩展 backup held-fd content/mode drift、post-state child exit/self-clean、group-only signal sequence与 owned Popen reap regression。
- C2 Green：补 migration fd read gate、return 前 liveness/identity gate、single group signal与 test ownership cleanup。
- C3 Docs：记录 pre-commit 边界、startup commit point、Darwin reap 与回退点。

### R2 — Public lifecycle generation

- 状态：TODO
- C1 Red：以两个真实/受控 public lifecycle 调用构造 old stop/new start barrier，证明旧 teardown 当前可删新 state。
- C2 Green：引入 stable per-config generation lock，覆盖 start publication、stop snapshot/signals/cleanup；所有 cleanup 显式携带 expected runtime state/identity。
- C3 Docs：记录 generation lock location、持锁区间、state ownership 与回退点。

### R3 — e2e generation and IM preflight

- 状态：TODO
- C1 Red：补 concurrent up/down barrier，以及 dangling/nonregular/malformed/drift IM evidence 的零信号 regression。
- C2 Green：up/down 从 preflight 起获取 worktree-external stable lock；down 先 snapshot IM evidence，Step2 重验同 revision后才 stop。
- C3 Docs：记录 full-stack generation 状态矩阵、IM fail-closed boundary 与回退点。

### R4 — Owned descendant process set and final signoff

- 状态：TODO
- C1 Red：补 PID==PGID、same-group child、detached descendant、startup rollback、PID reuse/birth mismatch regression。
- C2 Green：提供共享 structured process-tree snapshot；up 用 `os.setsid+exec` 建 leader，down/rollback按 frozen owned groups signal并确认全 set退出；完成 affected/static/single full与真实入口。
- C3 Docs：记录 owned set 算法、安全排除边界、真实/自动证据、最终 residue 与回退点。
