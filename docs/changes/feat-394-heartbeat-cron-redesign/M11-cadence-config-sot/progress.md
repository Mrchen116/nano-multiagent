# feat-394-M11 cadence-config-sot — Progress

## 启动说明

- unit/feat-394 HEAD: 1f744496 (决策 E+F + M11/M12 空目录)
- 基线：macOS 预存 2 个失败（/private/tmp vs /tmp 路径差异），Linux CI 绿，非本 unit 引入
- worktree: /Users/czj/Repos/nano-multiagent/.worktrees/feat-394-M11

---

### R1 — 后端：scheduler 顶层节律改读 config.heartbeat_every，退役 md every:

- Context: scheduler 的 `_load_heartbeat_spec` 将 md 的 `every:/interval:` 行收入 schedule_entries，`tick()` 用 spec.schedule 作节律；`agent.heartbeat_every` 从未被消费，导致 UI 显示 config 值与实际调度割裂。
- Decision: 在 `_load_heartbeat_spec` 中，`every:/interval:` 行静默忽略（不入 schedule_entries）；`_HeartbeatSpec.schedule` 改为 Optional（None 表示由 config 决定节律）；`tick()` 的 legacy 路径从 `agent.heartbeat_every`（None 时默认 30m）构建 `_IntervalSchedule`；at:/cron: 仍读 md。增加常量 `_DEFAULT_HEARTBEAT_EVERY = "30m"`（对齐 openclaw）。
- Rationale: 最小改动实现决策 E；不破坏 at:/cron: 路径；既有 tasks: 多子节律不受影响。
- Evidence:
  - Tests: 25 个 heartbeat_scheduler 单测全绿（含 4 个新测 config SoT + 4 个旧测更新为用 config cadence）
  - Entry: N/A（纯后端调度逻辑，入口测试在 R2 前端验收时覆盖）
  - Frontend State Matrix: N/A（后端改动）
  - Browser QA: N/A（后端）
  - E2E/Regression: 全树 `pytest -m "not e2e"` 2559 passed（排除 macOS /private/tmp 预存失败，非本 unit 引入）
  - Visual/Interaction: N/A
- Rollback: `fix(feat-394/M11/R1)` commit
- Commits: C1=test(红测), C2=fix(实现), C3=docs(本记录)
- Next: R2 — 前端删硬编码兜底 + HEARTBEAT.md 只读预览
