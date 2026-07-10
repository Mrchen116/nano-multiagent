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
  - Tests: 12/12 通过（含新增 regression case），见 C1/C2 commits。
  - Entry: N/A（纯前端）
  - Frontend State Matrix: 见 tasks.md
  - Browser QA (R3):
    - 浏览器 fetch 拦截器捕获 preview 请求 body（Memory Curation ON）：
      ```json
      {"features":{"memory_curation":true,"skill_creation":true},"custom_prompt":"","tool_ids":["memory"],"scenario":"direct"}
      ```
      `tool_ids: ["memory"]` 非空且含 "memory" ✓
    - 切换 Memory Curation OFF 后 body：
      ```json
      {"features":{"memory_curation":false,"skill_creation":true},"custom_prompt":"","tool_ids":["memory"],"scenario":"direct"}
      ```
      `tool_ids: ["memory"]` 仍在（工具在 allowlist，与 feature toggle 无关）✓
    - 截图：`/tmp/feat379-m8-memory-off-state.png`（可见 fetch 拦截 log）
    - 说明：preview 响应 503 是因为 Gateway WS 在 worktree ephemeral 环境下连接超时（同 round 3/4 out-of-unit 问题），
      但 `tool_ids` 已在请求离开前端前被拦截确认，这是本次修复的目标证据。
  - E2E/Regression: agent-detail-page.test.tsx 新增 case — DONE
  - Visual/Interaction: fetch 拦截 log 证明 UI 正确传值
- Rollback: aabe99f5（unit HEAD）
- Commits: C1=1afbbe5e（test/red）, C2=36cd520a（fix/green）, C3=pending
- Next: C3 docs commit → 合入 unit/feat-379 → 清理

## R2 — 实现修复（DONE）

- `BehaviorCard`（agent-detail-page.tsx）：新增 `effectiveToolIds` useMemo，union capabilityFeatures 推断 +
  `draft.tool_allowlist`，`fetchPreview` 改用 `effectiveToolIds`。
- `CreateBehaviorCard`（agent-create-page.tsx）：同样补 `effectiveToolIds` useMemo，`fetchPreview` 加
  `tool_ids: effectiveToolIds`。
- `useEffect` 依赖数组：detail 页改 `draft.tool_allowlist` → `effectiveToolIds`，create 页同步。
- 测试：`npm run test -- --run` 全绿（12 通过，2 预存 out-of-unit 跳过项目不变）。
- Build：`npm run build` 无错误。
