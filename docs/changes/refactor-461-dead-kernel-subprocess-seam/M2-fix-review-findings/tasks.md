# refactor-461-M2: Post-acceptance fixes — Tasks

> 对齐: ../design.md v1.1；验收后修复 round 1

## 目标

关闭验收确认的生命周期、配置迁移、M170 真实入口和 e2e 清理缺口：后台启动只承诺 PID/子进程存活，停止能强制回收所属进程组并清理状态；legacy `kernel` 配置只有在安全、持久的独立备份完成后才会被覆盖；M170 helper 通过真实认证和自动绑定观测节点；e2e-down 只清理本 worktree 所管 Gateway 的残留。

## 退出标准

- [ ] README 与 operator runbook 使用真实 `Gateway started (pid=...)` / `Log:` / `IM service:` 输出，并明确启动确认不等于 runtime/channel ready。
- [ ] 公共 `launch_gateway_in_background` 默认 waiter 对 child early exit、PID 缺失超时、PID 成功都有耐久回归；公共 `stop_gateway` 对强制 SIGKILL、进程组回收、`forced=true` 与 PID/state 清理有回归。
- [ ] legacy config 迁移备份在 open/write/fsync/目录 fsync 失败时不覆盖原配置，只删除自己创建的半成品；并发 loser 不删 winner；拒绝 symlink/hardlink alias；匹配备份权限不宽于 source；`nan`/`inf` 生命周期数值被拒绝。
- [ ] M170 helper 从真实入口注册/登录测试用户、配置 credentials、以 `--auto-bind` 启 Gateway，并用 Bearer token 查询 `/im/v1/nodes`；fresh rebuild + live start 可观测 `m170-node=online`。
- [ ] `scripts/e2e-down.sh` 在确认 Gateway 已退出后清理 `$WT_ROOT/gateway.pid` 与 `.gateway-state.json`，不杀无关进程，并有集成回归。
- [ ] 相关窄测、受影响测试集、ruff、完整 `pytest -m "not e2e"` 与真实入口验收通过。

## 测试策略

- 被测行为（来自退出标准）：公共后台启动三态；公共 stop 优雅/强制回收与状态清理；legacy migration backup 的 I/O、并发、alias、mode、目录 durable boundary；有限正数解析；M170 auth/auto-bind/Bearer 节点观测；e2e-down owned-residue 清理；README/runbook 输出契约。
- 已有测试在：`tests/unit/personal_assistant/test_gateway_launch.py`、`tests/unit/personal_assistant/test_gateway_pid_lifecycle.py`、`tests/unit/personal_assistant/test_local_store.py`、`tests/unit/test_runtime_helpers.py`、`tests/integration/test_e2e_down_script.py`（全部扩展）；文档输出契约扩展已有 `tests/contract/test_no_dead_kernel_subprocess_seam.py`，不新建 milestone 命名测试文件。
- 落层/目录/marker：`tests/unit/`、`tests/integration/`、`tests/contract/`，marker：无；真实长驻进程仅作一次性验收证据，不落入非 e2e 套件。
- 可选依赖 importorskip：无。
- 本 milestone 产生的一次性验收证据（收尾删除，不进套件）：`scripts/acceptance/m170_runtime.py rebuild/start/status/stop` 的 fresh DB + authenticated auto-bind live 输出；`scripts/e2e-up.sh` / `scripts/e2e-down.sh` 实际起停与残留检查，结论写入 `progress.md`。

## Roadpoints

### R1 — 公共 Gateway 生命周期与操作输出

- 步骤：先从公共 API 补 default waiter 三态、强制 stop 进程组/状态清理和文档输出契约红测；再修正生命周期实现及 README/runbook；记录入口语义。
- 验证：相关 unit/contract 窄测；公共 API 不直接测试私有 waiter/kill helper。

### R2 — legacy migration backup 事务边界

- 步骤：先补 I/O failure、并发 winner、symlink/hardlink alias、mode、directory fsync、finite number 红测；再把 backup 实现收敛为独占创建、身份校验、权限收紧和目录 durability gate。
- 验证：`test_local_store.py` 窄测及全部 local-store 受影响用例。

### R3 — M170 authenticated auto-bind 真实入口

- 步骤：先扩 helper 回归证明 fresh config 含 credentials、启动携带 `--auto-bind`、节点查询带 Bearer；再在真实 helper 入口完成 register/login/token 传递；运行 fresh live start/status/stop。
- 验证：`test_runtime_helpers.py` 窄测；真实 M170 runtime 观测 node online。

### R4 — e2e-down owned Gateway residue cleanup

- 步骤：先补脚本集成红测，覆盖确认退出后清理内部 PID/state 且不向无关 PID 发信号；再修正 shutdown 清理顺序。
- 验证：`test_e2e_down_script.py`；真实 `e2e-up.sh` / `e2e-down.sh` 起停与残留检查。
