# Design 评审: bugfix-441-running-tool-row-summary-input

**结论**: Issues Found

**核实台账**(逐条核过的承重原子;结论附证据,不是打勾):

| 原子 | 核实动作 | 结论 + 证据 |
|---|---|---|
| 现状: tool_start 已调用 presenter.format_start | 从 hook wiring 追 tool_call 事件 | ✓ `realtime_stream.on_tool_call` 经 `_resolve_presenter` 调 `format_start(event.get("arguments") or {})`,并发布 `tool_start` payload(`src/agent/platform/hooks/builtins/realtime_stream.py:62-79`) |
| 现状: _presentation_dict 已序列化 summary/detail/emoji | 查序列化函数 | ✓ `_presentation_dict` 输出 `summary`、`detail`、`emoji` 字段(`src/agent/platform/hooks/builtins/realtime_stream.py:211-230`) |
| 现状: Gateway tool_start 只转 emoji,不转 output/detail | 从 Gateway session event handler 追 IM delta | ✓ `tool_start` 分支仅读 `start_pres["emoji"]`,构造 `start_tool_call` 只含 id/name/status/input/emoji(`src/personal_assistant/main.py:3675-3715`) |
| 现状: Gateway tool_end 转 output/detail/emoji | 对照 tool_end 分支 | ✓ `tool_end` 从 `presentation` 取 `summary`→`output`、`detail`、`emoji`,并下发 `tool_call_completed`(`src/personal_assistant/main.py:3749-3799`) |
| 现状: IM 对 tool_call_upserted/completed 字段无关透传 | 追 Gateway WS handler/EventBridge/序列化 | ✓ 两类 kind 均走 `_parse_tool_call`;该函数读 `output/detail/emoji`(`src/IM/ws/gateway_handler.py:1204-1219`,`src/IM/ws/gateway_handler.py:2519-2546`);WS 与落库序列化条件输出同字段(`src/IM/api/ws/event_types.py:50-70`,`src/IM/infra/repositories.py:2796-2814`) |
| 现状: 前端折叠摘要只读 call.output | 查折叠呈现 | ✓ `collapsedSummary` 返回 `call.output` 字符串,无 output 则空(`src/IM/frontend/src/features/chat/v2/components/tool-presentation.ts:48-55`) |
| 现状: 前端展开卡不读 call.input,有 detail 才走 bespoke/generic | 查 ToolDetailBody | ✓ `ToolDetailBody` 有 detail 时按工具名渲染,无 detail 仅 fallback 到 `call.output`,不读取 `call.input`(`src/IM/frontend/src/features/chat/v2/components/tool-detail-renderers.tsx:498-514`) |
| 现状: 部分卡 running 时会伪完成 | 查各卡 JSX | ✓ `WebSearchCard` 空 results 显"无结果"(`tool-detail-renderers.tsx:258-270`);`AgentCard` 无条件显 `✓ completed` 区(`tool-detail-renderers.tsx:292-320`);`MemoryCard`/`SkillCard`/`TaskStopCard` 无条件显 ✓ 头(`tool-detail-renderers.tsx:375-440`) |
| 现状: reducer 会保留非空 input/output,detail 整体覆盖 | 查 mergeToolCall | ✓ `input/output` 空值不 clobber,`detail` 走 `{...prev,...next}` 后整体使用 next(`src/IM/frontend/src/features/chat/v2/chat-stream-reducer.ts:67-75`) |
| 现状: PA 产品工具注册集为 cron/send_message/web_search | 从 PA kernel factory 追工具装配 | ✓ `build_pa_kernel` 注入 `make_cron_tool(...)`,`SendMessageTool()`,`WebSearchTool()`(`src/personal_assistant/product.py:378-421`) |
| 现状: send_message/cron 当前无 presenter | 查工具类 | ✓ `SendMessageTool` 只有 name/description/input_schema/run/get_tool,无 `presenter`(`src/personal_assistant/tools/send_message.py:18-138`);`CronTool` 只有 name/description/input_schema/run,无 `presenter`(`src/personal_assistant/tools/cron.py:278-510`) |
| 现状: 默认 presenter start 只产截断 args summary,不产 detail | 查默认 presenter | ✓ `_DefaultPresenter.format_start` 返回 summary=`_truncate(json.dumps(args),80)`,无 detail(`src/agent/platform/tools/presentation.py:54-62`) |
| 现状: detail cap 不是 ToolPresentationEvent 自动行为 | 查协议与 cap helper | ✓ `ToolPresentationEvent.detail` 是裸 Mapping(`src/agent/core/tools/presentation.py:9-20`);cap 只在 presenter 显式调用 `_enforce_cap` 时发生,且仅截 `stdout/stderr/diff/content`(`src/agent/platform/tools/presentation.py:97-118`) |
| 决策 1: format_start 补参数片 detail + gateway 镜像转发 + 前端运行态 gate,结束路径不动 | 拍死?自洽?落在现状约束内? | ✓ 三个改点清楚,且落在真实路径: presenter start(`realtime_stream.py:62-79`)、Gateway start(`main.py:3675-3715`)、前端 ToolDetailBody/卡片(`tool-detail-renderers.tsx:498-514`) |
| 决策 2: 切分是 presenter 作者规范,现有全部工具落实,逐分支对齐 format_end | 覆盖范围与歧义检查 | ⚠ 方向成立,但 M1 范围写“`src/personal_assistant/tools/*.py` 各工具 `format_start` 补参数片”与 send_message/cron 无 presenter 的现状冲突;worker 可能误给 send_message/cron 新造 presenter,改变完成态旧行为(`src/personal_assistant/tools/send_message.py:18-138`,`src/personal_assistant/tools/cron.py:278-510`) |
| 决策 3: summary 纯转发,不涉及拆分 | 覆盖 reducer 风险 | ✓ tool_start 写 output 后,tool_end 非空 output 可覆盖;reducer 只阻止空 output clobber 非空 output(`chat-stream-reducer.ts:67-75`) |
| incident 约束: 参数在开始展示,结果在结束展示 | 对照 design 落点 | ✓ 决策 1/2 + IM delta 覆盖;前端 gate 明确禁止 running 显结果/完成标记 |
| incident 不变量: 完成态展示与旧代码逐项一致 | 对照 design 落点 | ✓ design 明确不动 `format_end`/`tool_end`/完成态 reducer,并要求 completed/failed 渲染与变更前逐字一致 |
| incident 不变量: running 脉冲保留、完成后转完成态 | 对照 design 落点 | ✓ M1 reviewer 标准要求 running 折叠仍有脉冲,且 running 展开无伪完成态 |
| incident 不变量: emoji 执行中正确显示 | 对照 design 落点 | ✓ Gateway start 继续保留 emoji 透传;现状代码已有 `start_emoji` 逻辑(`src/personal_assistant/main.py:3688-3703`) |
| incident 非目标: 内核 error 原文直透气泡排除 | 越界检查 | ✓ design 未纳入错误气泡文案重做 |
| kernel delta: 修改“工具展示由工具自带 presenter 决定” | 锚 canonical/用法/THEN 可观察 | ✓ 锚到 canonical 同名 requirement(`docs/specs/kernel/spec.md:366-416`),用 MODIFIED 合理;Scenario 从 SDK 消费者可观察的 `tool_start/tool_end` presentation 描述 |
| im delta: 修改“工具调用折叠态摘要有信息量且用真实工具名” | 锚 canonical/用法/THEN 可观察 | ✓ 锚到 canonical 同名 requirement(`docs/specs/im/spec.md:437-465`),Scenario 以用户可见折叠/展开行为描述 |
| gateway delta: design 声称 no spec delta | 覆盖有对外行为变化的包 | ✗ 本 unit 明确改变 Gateway→IM 的 `tool_call_upserted` payload,从只含 input/emoji 变成含 output/detail;Gateway canonical 目前没有 tool_start 参数侧透传 Scenario,只有授权条目顺带提到既有 presentation detail(`docs/specs/gateway/spec.md:535-538`) |
| cli delta: no spec delta | 覆盖对外行为变化 | ✓ CLI 渲染不在本 unit;kernel 事件契约变化已由 kernel delta 承载 |
| M1: split-param-display | 垂直/范围/退出标准 | ✓ 单 M1 是垂直链(presenter+gateway+frontend+测试),未做横切拆分;退出标准含 reviewer 用户可见旅程与 worker 单测/vitest/build |
| M1 退出标准: 全部 PA 可调用工具逐个落实参数片 | 可验性与歧义检查 | ⚠ “全部 PA 可调用工具”可验,但与 send_message/cron 无 presenter 现状结合时边界不够精确:它们应保持默认 presenter还是新建 presenter,Milestone 行与决策 2 表述不完全一致 |
| 整体: 上层综述与图 | 人读方向检查 | ✓ 架构总览把三个改点、结束路径不动和数据流串起来,能快速理解 |
| 整体: 接口与数据流闭合 | 来源/出口/调用方检查 | ✓ start detail 从 presenter→realtime hook→gateway→IM→前端 ToolDetailBody 闭合;end detail 仍走旧路径 |
| 整体: runbook | 常驻服务重启/健康检查 | ✓ IM/Gateway/前端启动与检查命令已列出 |

**架构进攻**(四角度逐个走,每条发现带具体长远代价;某角度无发现也写“走完无存活发现”):

| 角度 | 攻的对象 | 发现 + 长远代价 |
|---|---|---|
| 归属 | 参数片 detail 放 presenter、Gateway 纯透传、前端只做运行态 gate | ✓ 归属顺:数据语义仍在 presenter,Gateway 不按工具解释,前端只管展示状态;未引入 core→product 或 product→IM import 反向依赖 |
| 该不该存在 | 新增运行态 gate | ✓ gate 不是多余抽象:现有卡确实有无条件结果区(`tool-detail-renderers.tsx:258-320`,`375-440`),没有 gate 会把 running 行渲成完成态 |
| 该不该存在 | send_message/cron 是否需要新增 presenter | ⚠ 删除测试:若保持默认 presenter,本需求仍满足“running 折叠显入参摘要、展开 fallback 入参串”;若为这两个工具新增 presenter,复杂度增加且完成态从默认输出摘要变成新结构化卡的风险上升。长远代价是 PA 工具每增一个无 presenter 工具都被误认为必须补 bespoke presenter,扩大展示维护面 |
| 深还是浅 | format_start detail 复用 format_end 字段 | ⚠ 方向是深接口(复用现有 detail 渲染),但 start detail cap 未被设计拍死。`ToolPresentationEvent` 不自动 cap,write/memory 等参数可含 `content`;若 worker 直接塞原文,会让 running 事件和 `tool_calls_json` 承载超大输入,复发“展示字段撑爆链路”的债 |
| 治本还是补丁 | gateway tool_start summary/detail 转发 | ✓ 是补全既有透传链,不是按 bash 特判;能覆盖自带 presenter 与 DIY presenter |

**Issues**(从台账 ✗ 与架构进攻发现升级而来,按 CRITICAL > WARNING 排序):

- [CRITICAL] [delta-spec / gateway]:design 写 `gateway: no spec delta`,但本 unit 实际改变 Gateway 对 IM 的 `tool_call_upserted` 对外 payload:running 工具调用将新增 `output` 和 `detail`。Gateway canonical 目前没有“tool_start 透传 presenter summary/detail”的可归并条目,只有授权 requirement 顺带提“既有 presentation detail”(`docs/specs/gateway/spec.md:535-538`)。不补 gateway delta,收尾时 Gateway 契约层不会记录这个边界行为,后续只改 Gateway 中继时可以再次丢掉 start summary/detail 而 contract 不报警。建议新增 `docs/changes/.../specs/gateway/spec.md`,MODIFIED/ADDED 一个 Gateway→IM 工具调用中继场景:tool_start/upserted 携带 presenter summary→output 与参数片 detail,tool_end/completed 携带完整 detail。

- [WARNING] [决策 2 / Milestone M1]:send_message 与 cron 生产工具当前没有 presenter,会走默认 presenter(`src/personal_assistant/tools/send_message.py:18-138`,`src/personal_assistant/tools/cron.py:278-510`,`src/agent/platform/tools/presentation.py:54-62`),但 M1 范围写 `src/personal_assistant/tools/*.py`“各工具 format_start 补参数片”。worker 按字面可能给 send_message/cron 新增 presenter,从而改变完成态展示,撞 incident “完成态与旧代码逐项一致”。建议把 M1 范围改成:已有自带 presenter 的工具补 start detail;send_message/cron 明确保持默认 presenter,只加测试确认 default start summary + fallback 展开行为,除非 design 另行拍板给它们新增 presenter 且证明完成态不变。

- [WARNING] [决策 1/2 / kernel delta]:start detail 的大小上限没有拍死。现有 cap 只在 presenter 显式调用 `_enforce_cap` 时发生(`src/agent/platform/tools/presentation.py:97-118`),`ToolPresentationEvent.detail` 本身不自动截断(`src/agent/core/tools/presentation.py:9-20`)；design 表中 `write`/`memory` start detail 会包含 `content`。不明确要求 `format_start` 参数片也复用 `_enforce_cap`/同等 cap,worker 很容易把大 content 原样塞进 running 事件、WS 和 `tool_calls_json`,造成长输入工具在执行刚开始就撑大消息链路。建议在决策 2 与 kernel delta 补一句:start detail 与 end detail 共享同一 detail hard cap/`truncated` 语义,所有含 `content`/大字段的参数片必须先 cap。

**Recommendations**(不阻断门禁,作者自行取舍):

- 把 M1 的测试矩阵里加一个“大 content write/memory running detail 被截断且完成态仍与旧码一致”的单测,避免 start detail 新路径绕过既有 cap。
- Gateway delta 可以很小,只锚“向 IM 中继工具调用”这一行为,不要把 IM UI 细节写进 Gateway spec。
