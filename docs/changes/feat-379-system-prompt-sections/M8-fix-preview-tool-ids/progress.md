# M8 Progress

## R1 — 根因分析 + regression case

- Context: round 4 reviewer 拦截到 preview 请求 `tool_ids: []`，即使 agent 配置了 `["memory", "web_search"]`。
- Decision:
  - 根因在于 Gateway `node.register` 只发 `agent_ids`，IM 首次创建 profile 时 `tool_allowlist: []`。
    前端 `draft.tool_allowlist` 来自 `GET /config?source=mirror`，值为 `[]`，进而 preview `tool_ids: []`。
  - `GET /capabilities` 返回的 `features[*].available` 是 Gateway 基于本地 config 计算的（ground truth）。
    `feat.available=true && feat.requires_tool="memory"` 说明 memory 在 tool_allowlist 里。
  - 修复：在 `BehaviorCard` 里 useMemo 推断 `effectiveToolIds`，union `capabilityFeatures` 推断 + `draft.tool_allowlist`。
  - Create 页 `CreateBehaviorCard` 完全缺少 `tool_ids`，也需要补上。
- Rationale: 从 capabilities 推断比从 draft 更可靠——capabilities 是 Gateway 实时计算的，draft 依赖 IM mirror 的准确性。
- Evidence:
  - Tests: 待 R2 后跑
  - Entry: N/A（纯前端）
  - Frontend State Matrix: 见 tasks.md
  - Browser QA: 待 R3
  - E2E/Regression: agent-detail-page.test.tsx 新增 case — 待 R2
  - Visual/Interaction: 待 R3
- Rollback: aabe99f5（unit HEAD）
- Commits: C1=pending, C2=pending, C3=pending
- Next: 写 regression case（红），然后实现修复
