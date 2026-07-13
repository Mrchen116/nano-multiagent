# refactor-461-M4 — Progress

## Baseline

- Context: unit integration head `4f36f071` 上执行 post-acceptance fix round 3。
- Evidence: `/Users/czj/Repos/nano-multiagent/.venv/bin/pytest -m "not e2e" -q` → `3533 passed, 1 skipped, 23 deselected, 16 warnings in 117.11s`，exit 0。
- Boundary: 协作 writer 通过稳定 sidecar inode 串行整个事务；对不持锁外部 writer 只承诺 pre-commit identity/content/mode drift 检测，不声称消除 CAS-return → replace 的 POSIX 窗口。

## R1 — 跨进程 config transaction 与失败回滚

- Status: in progress。

## R2 — 公共 Gateway process-instance identity

- Status: pending。

## R3 — e2e evidence state machine 与 spawn rollback

- Status: pending。

## R4 — 全链路验收收口

- Status: pending。
