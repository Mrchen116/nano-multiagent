# refactor-521-M1 — Progress

## Baseline

- Claim: unit 基线在 typed ingress 改动前全绿。
- Baseline: `milestone/refactor-521-M1` at `a18b88fab666af1862cb6553e38af89c3000b2be`。
- Method: `/Users/czj/Repos/nano-multiagent/.venv/bin/python -m pytest -m 'not e2e' -n 4 --dist worksteal --durations=20 --durations-min=0.5`。
- Result: PASS，`3181 passed, 28 warnings in 238.51s`。
- Locator: 本机 milestone worktree pytest output；warnings 为既有 dependency/deprecation warning。
- Limit: baseline 未运行 e2e/真实 Feishu。

## R1 — 建立 typed carrier 与 producer matrix

- Status: TODO

## R2 — 切换 RoutedInbound 与 shadow/session owners

- Status: TODO

## R3 — 投影 runtime delivery 并删除 legacy authority

- Status: TODO

## Promotion Candidates

None.
