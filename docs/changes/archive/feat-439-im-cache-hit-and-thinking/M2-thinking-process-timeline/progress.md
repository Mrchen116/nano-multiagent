# feat-439-M2 — Progress

> 设计：design.md 决策 4 + §1 架构事实 A/B。
> seq 设计：思考段 seq = 到达时所属气泡已有 tool_calls 数（= 插入索引），由 IM 持久化边界统一赋予。

## R1 — 内核事件带 reasoning_content

- Context: gateway observer 要把整轮每回合的思考作为过程项转发，但内核 message_end / assistant_message 事件现状只带 content，不带 reasoning。
- Decision: loop.py message_end payload 加 `reasoning_content=msg.reasoning_content`；realtime_stream on_message_end assistant_message payload 加 `reasoning_content=event.get("reasoning_content") or ""`。
- Rationale: msg.reasoning_content 已落在 Message 上（loop.py:402/410），只是没暴露进事件；纯 additive，CLI 消费者忽略未知字段。
- Evidence:
  - Tests: `tests/unit/test_agent_loop.py::test_message_end_observe_event_carries_reasoning_content` + `test_realtime_stream_events.py::test_message_end_assistant_message_carries_reasoning_content` 红→绿；全 tests/unit + contract 2541 passed。
  - Entry: 内核事件层，真实入口验证在 R5 真栈。
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: tests/unit + tests/contract 全绿（含 CLI contract 边界，确认忽略新字段无回归）。
  - Visual/Interaction: N/A
- Rollback: revert R1 C2（字段带默认值，回滚无影响）。
- Commits: C1=红测, C2=feat
- Next: R2 gateway observer 转发 thinking 过程项。

## R2 — gateway observer 转发 thinking 过程项

- Context: observer 现状 `if not content: return None`（main.py:3406）整段丢弃空正文回合，绝大多数「思考+调工具不输出正文」的回合 reasoning 到不了 IM。
- Decision: assistant_message 分支改为：① 提取 `reasoning`，`not content and not reasoning` 才丢；② 多气泡 roll 仅由 `content` 触发（纯思考回合不 roll、不冒空气泡）；③ `if message_id` 分支思考过程项（kind=`thinking_segment` {message_id,text,run_id}）先于正文 delta 转发，纯思考回合只发 thinking、不动 kernel_message_id（保留 roll 判定基准）；④ roll 路径 / turn_start_then_delta 路径把本回合 reasoning 随新气泡一起发；⑤ heartbeat lazy 路径仅正文驱动，纯思考跳过。gateway 不算 seq（IM 持久化边界统一赋予）。
- Rationale: 思考事件必早于本回合工具事件到达 → 转发到当前气泡即正确时序锚点；不碰 tool_call 合并路径；多气泡场景思考随产出正文的那一回合的新气泡走，归属正确。
- Evidence:
  - Tests: `TestObserverForwardsThinkingSegment` 3 例红→绿（空正文+reasoning 转发不 roll/不发 delta、空正文+无 reasoning 丢、内容+思考双发）；observer 既有测试 25 例全绿。
  - Entry: gateway 中继层，真实入口验证在 R5 真栈。
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: tests/unit/personal_assistant + streaming 658 passed；ruff 通过。
  - Visual/Interaction: N/A
- Rollback: revert R2 C2。
- Commits: C1=红测, C2=feat
- Next: R3 IM 持久化 + 序列化链。

## R3 — IM 持久化 + 序列化链

- Context: IM 无承载思考的结构。需 messages 加列 + domain/repo/event_bridge/event_types/gateway_handler/REST 全链路带思考段，且 seq 统一在持久化边界赋予。
- Decision: ① domain 加 `ThinkingSegment{seq,text}` + `Message.thinking`；② db.py messages 加 `thinking_json` 列 + 迁移；③ repositories `_encode/_decode_thinking` + `append_thinking_segment`（seq=当前 tool_calls 数=插入索引）+ `_message_from_row`/两处 SELECT 带 thinking_json；④ event_bridge `on_thinking_segment` 持久化+发 `thinking.segment`；⑤ event_types `EVENT_THINKING_SEGMENT` + `thinking_segment_to_dict` + `build_thinking_segment_payload` + message_created 带 thinking；⑥ gateway_handler `kind=thinking_segment` 分发；⑦ REST `ThinkingSegmentPayload` + MessageResponse.thinking。
- Rationale: seq 在 IM（持有 tool_calls 列表、思考事件早于本回合工具事件到达）算一次，live/历史回放同读持久化值，口径一致；列加法变更，旧行 NULL→thinking=None 天然兼容（不留空壳）。
- Evidence:
  - Tests: repo 往返/默认 None、event_bridge 持久化+发事件、gateway_handler 分发、event_types 两 builder、REST 序列化 共 7 例红→绿；tests/im_service 354 passed。
  - Entry: WS thinking.segment + REST thinking 字段（真栈在 R5）。
  - Frontend State Matrix: N/A（R4）
  - Browser QA: N/A（R4/R5）
  - E2E/Regression: tests/im_service 全绿（含 schema/db_init/golden 序列化）；ruff 通过。
  - Visual/Interaction: N/A
- Rollback: revert R3 C2（列为加法，回滚保留空列无数据迁移风险）。
- Commits: C1=红测, C2=feat
- Next: R4 前端过程时间线。

## R4 — 前端过程时间线

- Context: 前端无承载思考的结构，工具折叠盘需升级为「过程」时间线，思考段+工具按 seq merge。
- Decision: ① chat-types 加 `ThinkingSegment` + `Message.thinking` + WsEvent `thinking.segment`/message.created thinking；② chat-stream KNOWN_TYPES 加 thinking.segment；③ reducer thinking.segment 追加 + message.created 还原；④ tool-calls-panel 升级为过程盘：`buildTimeline` 按 seq 插入索引 merge（seq=k 思考排 tool[k] 前，溢出排末尾），`ThinkingRow` 💭+首行摘要+展开全文（靛紫调），toggle 显「过程 · N 工具 · M 段思考」；⑤ message-pane 在有工具 OR 有思考时渲染过程盘；⑥ global.css 加思考行样式；⑦ i18n process/thinking/count keys。
- Rationale: seq 来自后端持久化值，前端纯按 seq 排，不重算；空态自然（无思考无 💭、无工具无思考不渲染盘）；复用既有折叠盘形态，不另造交互。
- Evidence:
  - Tests: reducer 2 例（追加/还原）+ 过程盘 5 例（merge 顺序/展开全文/无思考无💭/仅思考/全空）红→绿；全前端 vitest 474 passed；tsc+vite build 通过。
  - Entry: 组件层；真实浏览器验收在 R5（带 thinking 模型真栈）。
  - Frontend State Matrix: default(混排)/loading(running 脉冲)/empty(无思考无💭、全空不渲染)/long-content(多行思考首行摘要+展开全文)/missing(旧消息无 thinking 字段不渲染) 已 vitest 覆盖；mobile/desktop/视觉 在 R5 截图。
  - Browser QA: 见 R5（真栈）。
  - E2E/Regression: 前端 474 passed（含既有 tool 面板 65 例，toggle 标签变更同步更新 feat-414 W3 时长守卫正则）。
  - Visual/Interaction: 见 R5 截图对照 prototype。
- Rollback: revert R4 C2。
- Commits: C1=红测, C2=feat
- Next: R5 真栈浏览器验收 + CLI 回归。

## [Design 修订] R5: 思考段 seq 由「插入索引」改为「思考+工具共享的全局单调 seq」

- 现状方案: design 决策 4 文中我先按「seq = 到达时已有 tool_calls 数（插入索引）」实现（R3/R4）。
- 新方案: IM 持久化边界给思考段与工具调用**共享一个 per-message 单调递增 seq**（真实到达序、全局唯一）；前端按 seq merge、并按 seq 幂等去重。ToolCall 新增可选 `seq` 字段。
- 原因: 插入索引非唯一键（两段紧邻的纯思考回合会同 seq），无法支撑 reducer 契约要求的「事件重放/双投递幂等」——live 真栈实测 thinking 段被重复渲染（持久化 4、live 显示 8）。design 决策 4 原文即写「每个过程项带一个**时序序号**…单调递增」，全局单调 seq 才是其字面意图；插入索引是我引入的近似偏差。
- 影响范围: 仅本 milestone（M2）。ToolCall 多一个可选 seq 字段（additive，沿 emoji/approval 模式），reviewer 需知。
- design.md 是否同步改: 是（决策 4 的「时序序号」语义以本段为准；未改 design 正文措辞，因其原文已是「单调递增序号」，本段记录实现纠偏）。

## R5 — 真栈浏览器验收 + CLI 回归（含上面 seq 修订的实现）

- Context: R4 完成后真栈 live 验收，暴露两个我引入的 live-only bug（见上 Design 修订）：① thinking WS 事件无幂等去重被重复渲染；② event_bridge 发的是入参 tool_call（无 seq）而非持久化后的（有 seq），导致 live 工具排到所有思考之后。
- Decision: ① domain ToolCall +seq；repositories `_next_process_seq`（思考+工具共享计数器）+ append_thinking_segment/update_runtime_state 赋 seq + encode/decode；event_types/REST 带 seq；② event_bridge tool_call.* 改发持久化后的 tool_call（`_persisted_tool_call`）；③ 前端 ToolCall.seq + buildTimeline 按 seq 升序 merge + reducer thinking.segment 按 seq 幂等去重。gateway 不变（IM 赋值）。
- Rationale: 单一计数器 = 单调唯一序，既给正确混排序又给幂等键；live/历史回放同读持久化 seq，口径一致。
- Evidence:
  - Tests: IM seq 往返/共享计数/工具 seq 保留、event_bridge 发带 seq tool_call、reducer 幂等、过程盘按 seq merge —— 红→绿；Python 全树 2994 passed；前端 vitest 475 passed；ruff check+format 全通过。
  - Entry / Browser QA: 真栈 K2.6 default-agent，真 Gateway 进程。发「bash 列目录→读 README→bash 数行→总结」一轮多工具对话：
    - live 过程盘「Process · 3 tools · 4 thinking」，时序混排 **think→bash→think→read→think→bash→think**（截图 /tmp/feat439-evidence/r5-final-live-interleaved.png）；逐段 💭 可展开看全文。
    - **修复验证**：修前 live 显示 8 thinking（持久化 4）= 重复；修后 live thinking 数==持久化数(4)，all_seqs=[0,1,2,3,4,5,6] 连续唯一；工具不再排到思考之后。
    - 刷新页面（REST 历史回放）过程盘与思考段仍在、顺序一致、仍可展开。
    - 无思考回合：过程盘只有工具、无 💭（vitest 覆盖 + 第二气泡「1 thinking / 0 tools」纯思考态正常渲染）。
  - E2E/Regression: CLI 侧 contract/单测无回归（reasoning/seq 为忽略的可选字段）；Python 全树 + 前端全测全绿。
  - Visual/Interaction: 截图 /tmp/feat439-evidence/r5-final-live-interleaved.png、r5-thinking-expanded.png（对照 prototype「过程时间线」一致：💭 靛紫思考行 + 工具行按时序混排、逐段展开）。
- Rollback: revert R5 三个 fix commit（字段均可选带默认，回滚后旧前端忽略 seq）。
- Commits: C1=红测(seq+幂等), C2=fix(共享 seq), C2'=fix(event_bridge 发持久化 tool_call)
- Next: 本 milestone 完成，集成到 unit/feat-439。

<!-- 每个 roadpoint 完成后追加一段。 -->
