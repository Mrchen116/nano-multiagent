# bugfix-525-M3 — Progress

## Readback 与基线

- Baseline: `68707b70363282feb2a238aacbe0ed48c18b18cb`，`milestone/bugfix-525-M3` 从 synced `origin/unit/bugfix-525` 创建；worktree 初始 clean。
- Readback: 完整读取 current `incident.md`、`design.md`、全部 M3 delta-spec、canonical Kernel/Gateway/CLI specs、`AGENTS.md`、coding/testing/evidence/worktree runtime 规范，以及 design 范围内生产实现和既有测试。
- Scope: true update receipt、opaque trace propagation、manager per-run route、existing external sender 双投、CLI projection、专用 Feishu 验收；不重开 M1 raw event policy/Skill owner，不改 IM schema/UI 或普通 background Agent 输出。
- Baseline gate: `PYTHONPATH=src /Users/czj/Repos/nano-multiagent/.venv/bin/python -m pytest -m 'not e2e' -n 4 --dist worksteal --durations=20 --durations-min=0.5` → `3203 passed, 28 warnings in 235.59s`。

## R1 — 真实更新回执与 Kernel trace

- Status: TODO
- Next: 写 outcome + trace propagation 红测。

## R2 — 精确 per-run route 生命周期

- Status: TODO

## R3 — structured notice 双出口与 composition

- Status: TODO

## R4 — CLI、跨层与真栈 fixture

- Status: TODO

## R5 — 专用 Feishu 验收与收尾门禁

- Status: TODO

## Promotion Candidates

None.
