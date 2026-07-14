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
- `bc5091189`：`e2e-down.sh` 进程树测试先断言脚本成功，避免 retained leader 把真正的 fail-closed
  原因覆盖成无诊断的 timeout。
- `cc277d1ce`：code review 发现 SIGKILL 后直接 `wait` 可能无界阻塞；改为有界退出观察，并只在已经
  观察到退出时回收精确 child。新增 IM TERM/KILL 均未生效时保留 IM evidence 的回归。

## Evidence

- rollback / e2e-down / Gateway-owned cluster：`36 passed`。
- `test_e2e_down_reaps_same_group_and_detached_descendants` 的 xdist 聚焦复跑通过。
- 新增 IM survivor regression：`1 passed in 16.69s`。
- Ruff check、Ruff format、`git diff --check` 与测试命名/尺寸契约通过。
- CI 同款 `pytest -q -m "not e2e" -n 4 --dist worksteal` 完成后 pytest failure cache 为空，且该轮
  临时子进程无残留。

## Final gates

- Independent product re-review: PASS for `8c315ae27..cc277d1ce`; the reviewer ran the 37-case lifecycle
  integration group and a real isolated tmux `e2e-up` / `e2e-down` journey, then confirmed all lifecycle
  artifacts were gone.
- Final code review: initial finding of an unbounded post-SIGKILL `wait` was fixed by `cc277d1ce`; follow-up
  review returned `[]`.
- Delta verification: M11 tasks, source, and regression evidence agree; no kernel seam, public runtime behavior,
  or canonical contract changed.

## R2 — Remote CI timing follow-up

- Remote run `29347706827` failed after Python static checks had passed. Four lifecycle failures exposed
  test-harness timing assumptions: the ownership fixture's 30-second children expired before capture under xdist
  load, two lifecycle-lock tests imposed a 5-second external `communicate()` deadline on a deliberately blocked
  script, and accelerated teardown polling gave a just-signalled child too little scheduling time before evidence
  cleanup. The same run also had one unrelated IM dispatch concurrency assertion; its focused retry passed.
- `ba1689df8` replaces the finite children with explicitly killed infinite children, removes the two external
  deadlines, and changes the e2e-up harness to give signal-driven teardown a short scheduling yield rather than
  preserving production wall-clock intervals.
- A four-file xdist target bundle covering the three lifecycle areas plus the IM concurrency regression completed
  with no pytest `lastfailed` entries; Ruff, shell syntax, and test naming/size checks passed.

## Status

R2 is ready for remote CI rerun.
