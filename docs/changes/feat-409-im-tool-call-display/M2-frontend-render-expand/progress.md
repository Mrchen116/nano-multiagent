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

- Context: R2 后大字段(bash stdout、write content、web content、edit diff)全量渲染，长输出会撑乱聊天流滚动(spec 反例)。需前端两级展开 + 限高滚动 + 源头截断标注。
- Decision:
  - `LongOutput` 组件:行数阈值(`LONG_OUTPUT_LINE_THRESHOLD=50`)截断预览 + "展开全部" → `max-height:320px; overflow:auto` 内部滚动 + "收起";`truncatedAtSource`(detail.truncated) 渲染"输出过长，已在源头截断"标注(i18n)。`render` prop 让调用方决定内层元素(终端 `<pre>`/diff 行/web 摘录)，共享截断/滚动/标注 chrome。
  - bash stdout/stderr、write content、web content、edit diff body 统一走 LongOutput。DiffCard 抽 `diffLineClass`，body 行经 LongOutput 截断再着色。
  - 决策 5:前端阈值与内核 256KB cap 是两级独立关卡(前端管视觉、内核管体量)。
- Rationale: 限高滚动让"展开全部"不撑乱消息列表滚动位置(spec)；源头截断标注让用户知道完整输出已在内核侧截断、前端拿不到更多。
- Evidence:
  - Tests: `tool-calls-panel.test.tsx` 24 passed(R3 新增 5:截断+toggle/展开显全+collapse/收起回截断/短输出无 toggle/源头截断标注)；全量 vitest 59 files / 398 passed;`tsc --noEmit` 绿;`npm run build` 绿。
  - Entry: 真实浏览器(gstack Chromium)打开真实 ToolCallsPanel 组件 + 真实 presenter detail schema 样本(临时验收入口 acceptance-tool-calls.html，验收后删除，未提交)。
  - Frontend State Matrix: default/error(失败标红+终端 exit 1)/long-content(220 行 stdout 截断→展开→限高滚动→收起)/missing-data(read 行无 detail 降级)/mobile(375)/desktop(1440)/dark(默认暗色) 全覆盖。
  - Browser QA: 打开 http://localhost:62666/acceptance-tool-calls.html;无 console error、无 network failure(仅 google fonts 200);点击展开/收起 toggle 工作;限高验证 expanded 容器 clientHeight=320 < scrollHeight=4101(内部滚动不撑爆)。
  - E2E/Regression: component test 落库(vitest)，项目无浏览器 E2E 体系，不强行引入。
  - Visual/Interaction(与 prototype 对照): 截图存主仓 `ACCEPTANCE/feat-409-M2/`：
    - r3-desktop-1440.png:整体两条消息 5+5 工具，与 prototype 右侧布局一致。
    - r3-bash-term.png:bash 失败终端块($命令 + stdout 截断 + "Output too long — truncated at source" + "Expand all" + exit 1) —— 对照 prototype 终端块。
    - r3-edit-diff.png:diff 删除行红/新增行绿着色 —— 对照 prototype diff 视图。
    - r3-agent.png:DISPATCH PROMPT 完整 prompt 在结果(✓ sub-agent completed)**之前** —— 对照 prototype agent 卡片 + spec 关键要求。
    - r3-generic.png:未知工具 deploy_infra 按 key/value 行渲染(region/instances/dry_run/stack) —— 决策 4 通用卡片。
    - r3-mobile-375.png:窄屏不溢出。
  - 结论:渲染与定稿 prototype 一致;agent 完整 prompt 在结果前、长输出展开不撑乱滚动、失败标红、未知工具通用卡片均符合 spec/design。
- Rollback: `git revert` R3 C2;LongOutput 是可选包装，回退即全量渲染(不破坏数据)。
- Commits: C1=test R3 长输出红测, C2=feat R3 实现, C3=本文档

---

### failalign — 失败态对齐原型(PR #101 用户实测 fix,reviewer 反馈循环小修)

走 §FL 轻量化:② 不复制独立 milestone 目录(轻量 fix,记本 progress 续段);③ 架构治本不放松。
红测不豁免(行为/契约 fix):先写红测(C1=e5bee2ec)再实现(C2=5fcec454)。

- Context: 用户实测 PR #101,read 读不存在路径折叠行显 `file does not exist | <path>: file does not exist`(error 两次)、展开再一次共三次;bash 失败同类 `failed: <error>` 被 Gateway 再前缀。此前实现只对齐了成功态/展开卡,失败态跑偏。
- 根因(两处叠加):
  1. Gateway `main.py` tool_end `output = " | ".join(output_parts)`,output_parts = [原始 error, presenter summary] —— 原始 error 前缀进折叠摘要。
  2. 各 presenter 失败分支把 error 塞进 summary(read=`<path>: <error>`、bash=`failed: <error>`、memory/skill=`failed: <error>` 等)—— 与 ① 叠加。
  前端 `collapsedSummary(call)` 直接渲染 `call.output`,于是 error 反复出现。
- Decision:
  - 内核 presenter(presentation.py)所有工具 format_end 失败分支:summary 改为干净主参数(同成功态),不再拼 error;error 进 detail 供展开卡渲染一次。逐个核:read→path / bash→description(命令首段降级) / edit·write→path / web→url / agent→description / memory→`action target` / skill→`action name` / task_stop→task_id / default→裸 "failed"。
  - Gateway main.py tool_end:`output` 只放 presenter summary(去掉 `output_parts` 与 error 前缀;`|` 拼接逻辑删除)。reason 字段独立未动;running 的 tool_call_upserted 路径未动。
  - 前端 tool-presentation.ts:`failTag` 在有 reason 徽标命中(REASON_BADGE_NAMES)时返回 null,抑制「已拒绝」+「failed」双标识(cr4-frontend)。
  - 前端展开卡 error 只渲染一次:BashCard out-of-band 失败(无 stderr 但有 error)在 stderr 槽渲染 error;edit/write/web/task_stop out-of-band 失败 detail 只放 `{error}` → 走 ErrorCard;read 失败走 ReadCard 失败分支(✕ path + error);memory/skill success=False 走各自卡片失败分支(✕ + message)。
  - cr4 read minor:file_unchanged 删无效 `output.file.filePath` 兜底;total_lines 缺失时 presenter 不伪造 0(detail.total_lines=None、summary 退化只显路径)、前端 ReadCard 缺失时省略行计数(不显 "0 lines")。`_with_path` 处理 suffix 为空只显路径。
- Rationale: summary 永远是干净人话主参数(成功失败同构),失败由 ✕ 图标 + 简洁 fail-tag(bash 有结构化 exit code 显 `exit N`,否则 `failed`)表达,error 文本只在展开卡/终端块出现一次 —— 对照 prototype.html bash 失败行(L326-373)+ read 行(L375)+ 提案改动点说明(L568)。
- Evidence:
  - Tests(python): `test_presentation.py` 各 presenter 失败分支断言 summary = 干净主参数(`not in` error 文本)+ detail 含 error;`test_presentation_golden.py` bash 失败 golden 更新;`test_tool_end_detail_passthrough.py` 新增 `test_tool_end_failed_output_is_clean_summary`(断言 output 不含原始 error 前缀)。`pytest -m "not e2e"` 全绿:2629 passed, 1 skipped。ruff check + ruff format --check 绿。
  - Tests(frontend): `tool-calls-panel.test.tsx` 失败行测试改为断言折叠行无 error 文本 + summary 为干净 description + fail-tag="exit 1";新增 "suppresses the fail tag when a reason badge is shown"。全量 vitest 59 files / 413 passed;`npm run build` 绿。
  - Entry(真实浏览器,gstack Chromium + 真实 IM + Gateway + Vite,e2e-up.sh 起):登录 nano,与 default-agent 直聊,真实让 agent 执行 read 不存在路径 / bash ls 不存在目录 / read 成功 / bash echo(成功) / bash reboot(硬拦截 denied)。
  - Frontend State Matrix: read 失败/成功、bash 失败/成功、denied(硬拦截)全真实触发覆盖。
  - Browser QA: 无 console error;逐状态对照 prototype:
    - failalign-collapsed-all.png:折叠态四行 —— read 失败 `✕ 📖 read <path> [failed]`(对照 prototype L375,**summary 干净 path 无重复 error**,一致);bash 失败 `✕ 💻 bash 列出不存在的目录 [failed]`(对照 L326-333,summary=description,一致);bash 成功 `● 💻 bash 打个招呼`(对照 L427-433,一致)。**核心 bug 根治:折叠行 0 次 error**。
    - failalign-read-expanded.png:read 失败展开 `✕ <path>` + `file does not exist`(对照 prototype ReadCard 失败态,**error 仅一次**,与 bug 现象「三次」对比已根治)。
    - failalign-bash-card-full.png:bash 失败展开终端块 `$ ls ...` + stderr + `Command exited with code 1`(error 仅一次,对照 L336-371 终端块)。
    - failalign-denied.png:denied 折叠行 `✕ 💻 bash 测试重启拦截 [Denied]`(**Denied 红徽标 + 无 fail-tag 双标识**,cr4-frontend 抑制逻辑真实生效)+ 展开 `$ reboot` + `tool blocked by hook`。
  - 未真实浏览器逐一触发的工具(edit/write/web/agent/memory/skill/task_stop 失败态):渲染路径与已验证的 read/bash 同构(干净主参数 summary + error 进 detail 渲染一次),由 presenter 单测 + vitest 严格覆盖;真实触发需构造特定失败场景且依赖 LLM 配合,成本高、收益边际,以单测覆盖为准。
  - Visual/Interaction: 截图存主仓 `ACCEPTANCE/feat-409-M2/failalign-*.png`(collapsed-all / read-expanded / bash-expanded / bash-card-full / denied)。
- Rollback: `git revert 5fcec454`(C2)回到上一稳定态(失败态行为退回原样,数据无损);C1 红测可单独保留或同 revert。
- Commits: C1=e5bee2ec(红测), C2=5fcec454(实现 presenter+gateway+frontend), C3=本文档段。
