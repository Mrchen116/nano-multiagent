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

---

### R2 — 前端：删硬编码兜底 + HEARTBEAT.md 只读预览

- Context: `agent-detail-page.tsx` HeartbeatCard 有 `?? { every: "30m" }` 和 `?? "30m"` 硬编码兜底，导致 cadence 输入展示 UI 值而非 backend 真值；缺少 HEARTBEAT.md 只读预览 panel。
- Decision:
  - 删两处 hardcoded fallback，cadence 输入直接绑 `draft.heartbeat?.every ?? ""`（empty 时展示 placeholder "30m"）。
  - HeartbeatCard 新增 `agentId` prop，加可折叠 HEARTBEAT.md 只读预览 button（data-testid="heartbeat-md-preview-toggle"，仿 promptPreview pattern）。
  - IM 端 `GET /im/v1/agents/{id}/heartbeat-md` 新端点直读 workspace HEARTBEAT.md（与 cron jobs 读文件模式一致，不走 Gateway WS）。
  - 前端 `getAgentHeartbeatMd()` API 函数调对应端点。
- Rationale: HEARTBEAT.md 由 agent 写入，UI 只需只读预览；cadence 绑 config 值为 decision E 核心要求。
- Evidence:
  - Tests: 3 个 M11 vitest 新测全绿（370 passed，基线 367）；2 个 M11 C1 红测（cadence + md preview）变绿
  - tsc -b: 通过
  - E2E/Regression: 全树 `pytest -m "not e2e"` 2567 passed（+8，排除 macOS /private/tmp 预存失败 2 个）
- Commits: C1=test(红测), C2=fix(实现)
- Status: DONE
