# bugfix-417-M1: lock-force-cancel — Tasks

> 对齐: ../design.md（决策 1 / 接口与数据流 A）

## 目标

`kernel.cancel(run_id)` / `registry.cancel(run_id)` 能**强制终止**承载该 run 的 asyncio Task（不再只翻协作标志），让 parked 在 `async with lock` 内的 `_run_locked` 经 `CancelledError` 异常路径退出，释放 per-session 串行锁；同时 `kernel.cancel` 连带 `permission_broker.cancel_all_pending(run_id=run_id)` 取消该 run 待决的权限请求。外部观察：取消一条 parked run 后，同 session 下一条 submit 不再被永久阻塞。

## 退出标准

- [ ] `registry.cancel(run_id)` 复用 `_owned_tasks`，经 `_async_loop.call_soon_threadsafe(task.cancel)` 强制取消承载 Task，使 `_run_locked` 的 `async with lock` 经 CancelledError 退出释放锁
- [ ] `kernel.cancel(run_id)` 在 `runs_registry.cancel` 后调 `permission_broker.cancel_all_pending(run_id=run_id)`
- [ ] 幂等：已终态 / 无 Task 的 run cancel 不抛错、不重复取消
- [ ] 取消一条 parked run 后同 session 可继续 submit（锁已释放）— 真实入口（进程内 kernel）证明
- [ ] `<test_command>` 全绿，既有 cancel 测试不回归

## 测试策略

> 规范见 docs/TESTING_GUIDE.md。

- 被测行为（来自退出标准）：
  1. cancel 强制取消承载 Task → parked run 经 CancelledError 退出、session 锁释放、同 session 下一条 run 能开始（这是 P0 不变量的可观察投影，**最重要**）
  2. kernel.cancel 连带 cancel_all_pending(run_id) → 该 run 的待决 permission future resolve 为 deny
  3. 幂等：已终态 / 无 Task cancel 安全无害
- 已有测试在：`tests/unit/test_run_cancel.py`（registry 层 cancel 行为，扩展）+ 新建 kernel 层 cancel-broker 测试（现有 test_run_cancel 是纯 registry 单测，不持 broker；kernel.cancel 连带取消 broker 需在 sdk 层测，现有无合适文件）
- 落层/目录/marker：tests/unit/（进程内，无 e2e 依赖），marker：无
- 可选依赖 importorskip：无
- 本 milestone 产生的一次性验收证据：无（全部沉淀为回归单测）
- 真实入口：进程内 kernel（`agent.sdk`）/ registry 直跑——核心断言「parked run cancel 后锁释放、同 session 新 run 能跑到终态」是 P0 不变量的真实投影，非 mock。非前端 → Frontend State Matrix / Browser QA = N/A。

## Roadpoints

### R1 — registry.cancel 强制取消承载 Task，释放 session 锁

- 步骤:
  - C1（红）：在 test_run_cancel.py 加测试——一个 runtime parked 在 `asyncio.Event().wait()`（模拟卡死/parked），用真实 SessionManager（持真 per-session 锁，`_run_locked` 路径），cancel 后断言:
    (a) 承载 Task 被取消到终态;(b) 同 session 下一条 submit 能开始执行并到达终态（证明锁已释放）。当前代码下 (b) 会因锁不释放而卡住超时 → 红。
  - C2（绿）：`registry.cancel` 加：若 `_owned_tasks` 有该 run 未完成 Task，经 `self._async_loop.call_soon_threadsafe(task.cancel)` 强制取消。幂等（已终态 / 无 Task 跳过）。
- 验证: `<test_command>` 全绿;新红测试转绿;既有 cancel/interrupt 测试不回归。

### R2 — kernel.cancel 连带取消 permission broker pending

- 步骤:
  - C1（红）：新建 sdk 层测试——build_kernel + create_session，run parked 在等权限决策（broker 有该 run pending future），`kernel.cancel(run_id)` 后断言该 run 的 pending future 被 resolve 为 deny、broker 无残留 pending。当前 `kernel.cancel` 不碰 broker → 红。
  - C2（绿）：`Kernel.cancel` 在 `runs_registry.cancel` 后，调 `self._c.permission_broker.cancel_all_pending(run_id=run_id)`。
- 验证: `<test_command>` 全绿;新红测试转绿。
