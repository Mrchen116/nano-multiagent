# M8: fix preview tool_ids

## 目标

修复 agent detail 页 Preview 面板切换 Memory Curation 开关后内容不变的问题。
根因：IM `GET /config?source=mirror` 返回的 `tool_allowlist` 可能为空（Gateway 首次 `node.register`
只发 agent_id，不携带 tool_allowlist，IM 用空值创建 profile），导致 `draft.tool_allowlist = []`，
进而 preview 请求 `tool_ids: []`，memory_curation 的 `requires_tool="memory"` 门控永远失败。

agent-create 页（`CreateBehaviorCard`）同样未传 `tool_ids`，也需要修复。

## 退出标准

1. 打开已配置 memory 工具的 agent detail 页，preview 中 memory guidance 段出现（on）/消失（off），
   len 差约 +583 bytes（M7 live chain 证据）。
2. 浏览器 Network 拦截 preview 请求 body：`tool_ids` 非空且含 "memory"。
3. `npm run test`（vitest）全绿；`npm run build` 无错误。
4. diff main：0 新增失败。

## 测试策略

类型：前端历史 bug 修复（bug-regression）。

现有测试文件：`agent-detail-page.test.tsx`

补 regression：在现有测试文件中补一个 case，验证 fetchPreview 发出的 tool_ids
包含从 capabilityFeatures 推断出的工具（即 feat.available && feat.requires_tool 的 requires_tool）。

UI 状态矩阵：
- detail 页 Memory Curation on：preview 请求 tool_ids 含 "memory"  → 适用
- detail 页 Memory Curation off：同样触发 preview，tool_ids 含 "memory"（因工具仍在 allowlist）→ 适用
- detail 页无 memory 工具（disabled 态）：tool_ids 不含 "memory"，memory guidance 段不出现 → 适用
- create 页：tool_ids 来自 draft.tool_allowlist（PillSelector 已选） → 适用
- loading 态：draft 为 null，BehaviorCard 不渲染 → N/A
- error 态：preview fetch 失败显示 error → N/A（已有覆盖）

| 风险点 | 验收方式 | 是否落库 |
|---|---|---|
| detail 页 preview tool_ids 含 capabilities 推断工具 | vitest regression + 浏览器验收 | 是 |
| create 页 preview tool_ids 传入 | vitest regression + 浏览器验收（次要） | 是 |
| 切换 features 后 preview 重新触发 | 浏览器验收（已通过 round 4） | 否 |

## Roadpoints

| ID | 标题 | 状态 |
|---|---|---|
| R1 | 分析根因 + 写 regression 验收 case（红）| DONE |
| R2 | 实现修复（绿）| TODO |
| R3 | 浏览器验收 + 文档 | TODO |

## 修复方案

**detail 页**：在 `BehaviorCard` 里新增 `effectiveToolIds` useMemo，
从 `capabilityFeatures` 里提取 `feat.available && feat.requires_tool` 的工具名，
与 `draft.tool_allowlist` union。这样即使 IM mirror 的 `tool_allowlist` 因首次 register
未同步而为空，也能通过 capabilities（Gateway 用本地 config 计算 available）正确传入工具。

**create 页**：`CreateBehaviorCard` 的 `fetchPreview` 加上 `tool_ids: draft.tool_allowlist ?? []`，
同时也加 capabilityFeatures 推断逻辑（create 时 all features available=true，所有 requires_tool 均在）。
