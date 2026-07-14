# refactor-461-M11 — Progress

## Baseline

归档后的 CI 同款 xdist 回归偶发暴露 lifecycle 测试时序问题：一个 rollback 场景可在已终止 IM
仍是 shell 子进程时清除证据；另一个进程树测试会先等待 fixture leader，从而掩盖
`e2e-down.sh` 的 fail-closed stderr。

## Implementation

- `48e2e8328`：将 busy sidecar holder 改为显式 stdin release；fixture 只加速 startup polling，保留
  teardown 的真实间隔。
- `d64c3928c`：`e2e-up.sh` 对自身 `$!` 启动的 IM，在确认退出后执行精确 `wait` 再清理证据；增加
  TERM-ignored IM 回归，并把 rollback 集合拆分以满足测试文件尺寸契约。
- 当前提交：`e2e-down.sh` 进程树测试先断言脚本成功，避免 retained leader 把真正的 fail-closed
  原因覆盖成无诊断的 timeout。

## Evidence

- rollback / e2e-down / Gateway-owned cluster：`36 passed`。
- `test_e2e_down_reaps_same_group_and_detached_descendants` 的 xdist 聚焦复跑通过。
- Ruff check、Ruff format、`git diff --check` 与测试命名/尺寸契约通过。
- CI 同款 `pytest -q -m "not e2e" -n 4 --dist worksteal` 完成后 pytest failure cache 为空，且该轮
  临时子进程无残留。

## Status

实现与本地回归完成；等待 delta reviewer、verifier 和 final code review。
