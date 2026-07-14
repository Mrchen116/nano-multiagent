# refactor-461-M11: Stabilize lifecycle validation — Tasks

> 对齐：`../design.md` 的 fail-atomic lifecycle 约束，以及归档单元完成后的 CI 回归。

## 目标

让 `e2e-up.sh` 启动失败后的回滚，以真实子进程退出作为清理条件；让相关测试不再以固定时间窗口
误判或掩盖 `e2e-down.sh` 的失败关闭原因。

## 退出标准

- [x] 已退出的、由 `e2e-up.sh` 直接启动的 IM 子进程在删除 PID/identity 证据前被精确回收；SIGKILL
  后仍以有界观察失败关闭，不会无期限等待。
- [x] SIGKILL-only IM、identity timeout 与 readiness failure 都覆盖回滚后的证据清理。
- [x] 锁持有测试以显式 release 条件维持锁；fixture 不压缩 teardown 的真实等待间隔。
- [x] `e2e-down.sh` 进程树测试先报告脚本失败关闭原因，再等待 fixture leader。
- [x] 目标 xdist 测试、测试命名/尺寸契约、静态检查和 CI 同款 non-e2e xdist 回归通过。

## R2 — Remote CI timing follow-up

- [x] 用不会自然到期的 fixture child 替代 30 秒 sleep，并移除 lifecycle-lock test 的 5 秒外部
  `communicate()` deadline。
- [x] fixture teardown 保留短暂的真实调度让步，而不是把生产 50ms polling 原样带入 CI。
- [x] CI 失败涉及的 lifecycle target xdist bundle、静态检查和测试命名/尺寸契约通过。
- [x] 无限 fixture child 在全部 setup 路径下立即受 `try/finally` 保护；lock-release watchdog 在报告
  hang 前先杀死并回收 subprocess。
- [ ] 远端完整 non-e2e CI rerun 通过。

## 测试策略

- 用假 IM 忽略 TERM，守护 SIGKILL 后 `wait` 的精确回收和证据删除。
- 用 stdin 控制的 `flock` holder 代替固定 30 秒睡眠，使锁在测试结束条件前不会自行释放。
- 真实进程树覆盖同组与 detached descendant；若 `e2e-down.sh` fail-closed，优先输出其 stderr。
