# feat-409-M2 — Progress

## R1 — 类型 detail + 折叠态通用渲染

- Context: M1 已把 presenter 的 `detail`/`output`(人话 summary) 透传到 IM WS payload，但前端 `chat-types.ts` ToolCall 尚无 detail，折叠行只显示 name+duration、output 仅在展开 body 裸 `<pre>` 出现，且 failed 标红的 CSS modifier 是死的(`--error` 永不匹配 status="failed")。
- Decision:
  - `chat-types.ts` 加 `ToolDetail`(开放 `Record<string,unknown>` + `truncated`/`error`)、ToolCall.detail。开放类型是因为各内置工具 detail schema 不同 + DIY/MCP 工具 shape 未知(决策 4)，字段访问在 renderer 层 guard。
  - 新建 `tool-presentation.ts`:`toolEmoji`(name→emoji 查表 + 未知工具 🔧 兜底)、`collapsedSummary`(取 output，老消息无则 "")、`failTag`(failed 时 bash 取 exit code 否则 "failed")。
  - 折叠行渲染 emoji(aria-hidden) + 真实 name + presenter summary(ellipsis) + fail-tag；修 `--error`→`--failed` 让标红真正生效。
- Rationale: 决策 4——折叠文案是 presenter 产的 `output`，前端**不按 name 派生**；唯一 name-keyed 的是 emoji(纯视觉，generic 兜底)，所以加新工具/DIY/MCP 工具零改 IM。emoji 用查表而非 switch，保持「加工具不碰 IM 行为」。
- Evidence:
  - Tests: `tool-calls-panel.test.tsx` 8 passed(新增 5 个折叠态分支)；全量 vitest 59 files / 382 passed；`tsc --noEmit` 绿。
  - Entry: 折叠行浏览器视觉验收留到 R3 统一做(避免重复起服务)。
  - Frontend State Matrix: default/error(failed 标红)/missing-data(老消息无 output→summary "")已 component 覆盖；long-content/mobile/desktop 留 R3。
  - Browser QA: 留 R3。
  - E2E/Regression: component test 落库(vitest)，项目无浏览器 E2E 体系。
  - Visual/Interaction: 留 R3。
- Rollback: `git revert` C2 即回到 R1 前；detail 是增量字段，回退不破坏数据链。
- Commits: C1=test 折叠态红测, C2=feat R1 实现, C3=本文档

## R2 — 展开态分工具精渲染 + 未知/DIY 通用卡片

## R3 — 长输出两级展开 + 浏览器验收
