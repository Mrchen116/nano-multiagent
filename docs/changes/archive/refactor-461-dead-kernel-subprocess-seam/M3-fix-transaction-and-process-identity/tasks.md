# refactor-461-M3: Transaction and process identity hardening — Tasks

> 对齐: ../design.md v1.2；验收后修复 round 2

## 目标

把验收发现的七个 symptom 收敛成两个机制：配置写入是一条由 source snapshot、durable legacy backup、pre-commit CAS 与原子 replace 组成的连续事务；Gateway 生命周期是一套以 spawned PID、内部 PID、进程存活和启动身份共同判定 ownership/exit 的状态机。所有失败路径均保留原配置或生命周期证据，不把“发过信号”误报成“已经退出”。

## 退出标准

- [x] legacy backup 对 FIFO/非 regular file fail-fast，existing/new backup 都要求单链接独立文件；子进程硬超时回归证明不会阻塞。
- [x] `save_local_config` 对同路径串行协调，基于事务起点 snapshot 完成 durable backup，并在原子提交前执行 identity/content CAS；外部写入漂移时拒绝覆盖，保留第三方内容和原始备份。
- [x] 默认后台启动只在 PID 文件可解析、等于 spawned PID 且 child 存活时成功；malformed/mismatch/dead child 均不写成功状态。
- [x] state 与 PID-only 两条 stop 路径共享强制退出语义：SIGKILL ESRCH 视为已退出，成功发 KILL 后仍要 bounded confirm；未确认退出时保留状态并明确失败。
- [x] e2e-up 持久化 Gateway ownership identity；e2e-down 在发任何信号前验证内部 PID、精确 config/foreground argv 与启动身份，mismatch 或未确认退出均非零退出且保留整栈证据。
- [x] `test_runtime_helpers.py` 格式化，`ruff check .`、`ruff format --check .`、受影响套件与完整非 e2e 套件通过；真实默认 start/stop/restart、配置迁移/drift、e2e 正负路径验收通过。

## 测试策略

- 被测行为（来自退出标准）：public config save 的 FIFO/hardlink/drift/mode/failure 原子性；public launch 的 PID identity；public stop 的 ESRCH/仍存活确认；真实 e2e shell 入口的 ownership mismatch 与 unexited fail-atomic；全仓 formatter gate。
- 已有测试扩展：`tests/unit/personal_assistant/test_gateway_launch.py`、`tests/integration/test_e2e_down_script.py`、`tests/unit/test_runtime_helpers.py`。
- 新建 `tests/unit/personal_assistant/test_config_migration_transaction.py`：现有 `test_local_store.py` 已超过 400 行软上限，新文件聚焦跨进程/并发事务行为，只通过 `save_local_config` 公共入口验收。
- 新建 `tests/unit/personal_assistant/test_gateway_forced_stop.py`：现有 `test_gateway_pid_lifecycle.py` 已接近 400 行软上限，新文件聚焦 state/PID-only 两种公共 stop 的共享 force-confirm 语义。
- 落层/目录/marker：`tests/unit/` 与 `tests/integration/`，marker：无；真实常驻服务仅作一次性验收证据，不落入非 e2e 套件。
- 本 milestone 产生的一次性验收证据（收尾删除，不进套件）：临时 HOME/config 的默认 start/stop/restart、config drift barrier 探针、`scripts/e2e-up.sh` / `e2e-down.sh` 正常与 identity/unexited 负路径，结论写入 `progress.md`。

## Roadpoints

### R1 — 连续 config migration transaction

- 步骤：先从 `save_local_config` 公共入口补 FIFO 子进程硬超时、existing/new backup 单链接、外部 writer barrier、mode 与失败不覆盖红测；再实现同路径协调、单次 source snapshot、durable backup、pre-commit CAS 和 same-directory atomic replace。
- 验证：新事务测试文件 + 既有 local-store 套件；不把 private helper 当行为契约。

### R2 — 统一 Gateway PID/exit 确认状态机

- 步骤：先补 public launch 的 malformed/mismatch/dead-child 与 public stop 两种来源的 ESRCH/post-KILL-alive 红测；再让启动、强制退出共享严格 PID/liveness 判据和 bounded confirmation。
- 验证：launch + forced-stop + 既有 PID lifecycle 单测；明确断言失败时不清状态。

### R3 — e2e Gateway ownership identity 与 fail-atomic teardown

- 步骤：先扩 shell 集成红测覆盖 identity mismatch、argv mismatch、KILL 后仍存活；再由 e2e-up 持久化 ownership identity，e2e-down 先验证 identity、后发信号、确认退出后才继续 teardown。
- 验证：`test_e2e_down_script.py`；真实 e2e 正常起停与隔离负路径。

### R4 — 格式与全链路收口

- 步骤：记录既有 formatter 红门禁，格式化 `test_runtime_helpers.py`；执行 affected/full/ruff，并从真实入口复验两个统一机制。
- 验证：`ruff check .`、`ruff format --check .`、完整 `pytest -m "not e2e"` 与真实入口验收。
