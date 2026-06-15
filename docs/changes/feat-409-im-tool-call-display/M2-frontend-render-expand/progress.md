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

- Context: R1 后展开 body 仍是裸 input/output `<pre>`。M2 要求按 name 精渲染 8 个内置工具，未知/DIY 工具忠实结构化呈现 detail（非裸 JSON），agent 完整 prompt 排在结果前，历史无 detail 降级。
- Decision:
  - 新建 `tool-detail-renderers.tsx`，`ToolDetailBody` 按 `call.name` 分发：bash 终端块($命令 + stdout/stderr + exit)、edit unified diff 着色(按 +/-/@@ 行首)、write 内容、web_fetch 标题+url+正文卡片、agent(prompt Section 在前 + 结果在后)、memory/skill/task_stop 紧凑 info 卡片；未知 name 但有 detail → `GenericCard` 按 Object.entries 渲染 key/value 行；无 detail → 降级 `<pre>output</pre>`；`detail.error` 存在 → 统一 ErrorCard(任意工具)。
  - 字段名严格镜像 presenter schema(bash `command/stdout/exit_code`、edit `diff/firstChangedLine`、agent `prompt/content/output_file`...)，访问用 `str()` guard（detail 是开放记录）。
  - agent prompt-before-result 用 `compareDocumentPosition` 测试保证文档顺序（spec 关键要求）。
- Rationale: 决策 4——detail 是 presenter(工具)产的数据；前端对已知工具做视觉精修(diff 着色/prompt 在前)，对 DIY/MCP 工具用通用卡片忠实按 key 呈现，差别仅在拿不到 bespoke 视觉。加新工具/DIY 工具零改 IM 行为(分发表缺失即落 GenericCard)。
  - **i18n**：发现项目严格双语(en/zh + i18n parity 测试)。卡片的结构性标签(派发指令/子 agent/输出文件/已写入记忆)走 `chat.messagePane.toolDetail.*` i18n key；presenter 产出的数据(command/stdout/content/message/path)原样渲染不翻译。
- Evidence:
  - Tests: `tool-calls-panel.test.tsx` 19 passed(R2 新增 11 个分支:bash/edit/write/web/agent-prompt-before-result/memory/skill/task_stop/未知通用卡片/失败 error 卡片/detail 缺失降级)；i18n parity 测试通过；全量 vitest 59 files / 393 passed；`tsc --noEmit` 绿。
  - Entry: 浏览器视觉验收留 R3 统一做。
  - Frontend State Matrix: default(各工具精渲染)/error(ErrorCard)/missing-data(降级 output)已 component 覆盖；long-content/mobile/desktop 留 R3。
  - Browser QA: 留 R3。
  - E2E/Regression: component test 落库(vitest)。
  - Visual/Interaction: 留 R3。
- Rollback: `git revert` C2；panel body 可整体回退裸 `<pre>`，detail 增量字段不破坏数据链。
- Commits: C1=test R2 展开态红测, C2=feat R2 实现, C3=本文档

## R3 — 长输出两级展开 + 浏览器验收
