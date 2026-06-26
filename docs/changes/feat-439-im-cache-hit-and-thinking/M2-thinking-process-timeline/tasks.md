# feat-439-M2: thinking 过程时间线 — Tasks

> 对齐: ../design.md（决策 4 + §1 架构事实 A/B）

## 目标

带 thinking 的模型回复，内部 Web IM 气泡里出现可折叠「过程」盘：整轮多段思考 + 工具调用按真实时序混排（思考①→工具…→思考②→…），每段思考默认收起为一行 💭、可逐段展开读完整内容、刷新历史仍可展开；本轮无思考则过程盘不出现 💭 行；外部 channel 只见正文。

## 退出标准

- [ ] 内核 message_end / realtime_stream assistant_message 事件带 `reasoning_content`
- [ ] gateway observer：空正文但有 reasoning 的回合不再丢弃，作为「过程项」转发到当前气泡（不 roll 新气泡、不产生空气泡）；空正文且无 reasoning 仍丢
- [ ] thinking 段持久化（messages 表新增列），刷新历史可还原 + 可展开
- [ ] event payload（WS thinking.segment + message.created）与 REST 带思考段
- [ ] 前端过程盘按 seq merge 思考段+工具渲染（多段交错 / 无思考空态 / 展开收起）
- [ ] CLI 侧忽略 reasoning 字段无回归
- [ ] 真浏览器验收：带 thinking 模型真栈跑一轮多工具对话，过程盘时序混排 + 逐段展开 + 刷新可展开 + 无思考无 💭

## 测试策略

- 被测行为：
  - 内核：message_end / assistant_message 事件 payload 带 reasoning_content（单测，扩展现有 loop/realtime_stream 测试）
  - gateway：observer 对「空正文+有 reasoning」转发 thinking_segment 到当前气泡、不 roll、不发空 delta；「空正文+无 reasoning」仍 return None（单测，扩展 personal_assistant observer 测试）
  - IM：append_thinking_segment 持久化往返 + seq=插入索引（= 当前 tool_calls 数）；gateway_handler kind=thinking_segment 分发；event_types/REST 序列化带思考段（单测，扩展 IM repositories / event_bridge / gateway_handler / event_types 测试）
  - 前端：reducer thinking.segment 追加 + message.created 还原；过程盘 merge 渲染（多段交错 / 无思考 / 展开收起）（vitest，扩展 chat-stream-reducer.test / tool-calls-panel.test）
- 已有测试在：内核 `tests/unit/test_hook_event_coverage.py` / `test_streaming_tool_executor.py`（扩展）；gateway `tests/unit/personal_assistant/`（扩展 observer 测试）；IM `tests/im_service/unit/`（扩展 repositories/event_bridge/gateway_handler）；前端 `chat-stream-reducer.test.tsx` / `tool-calls-panel.test.tsx`（扩展）
- 落层/目录/marker：tests/unit、tests/im_service/unit、frontend vitest；marker：无（live 验收为一次性证据）
- 可选依赖 importorskip：无
- 一次性验收证据（收尾删除，不进套件）：R5 真栈浏览器截图（过程盘混排 / 展开 / 刷新 / 无思考空态）

## Roadpoints

| ID | 标题 | 状态 |
|---|---|---|
| R1 | 内核事件带 reasoning_content（loop.py + realtime_stream.py） | DONE |
| R2 | gateway observer 转发 thinking 过程项（不丢空正文+reasoning、不 roll 空气泡） | TODO |
| R3 | IM 持久化 + 序列化链（db/domain/repositories/event_bridge/event_types/gateway_handler/REST） | TODO |
| R4 | 前端过程时间线（types/reducer/过程盘/message-pane/css） | TODO |
| R5 | 真栈浏览器验收 + CLI 回归 | TODO |

## 前端 UI（R4）

用户路径分类：normal-ui（思考过程展示，非核心交易路径；但历史回看属重要回归 → 落库 reducer + 组件回归 + 浏览器验收）

UI 状态矩阵：

| 状态 | 覆盖计划 |
|---|---|
| default | 多段思考 + 多工具混排，过程盘默认折叠 |
| loading | 工具 running 态脉冲（沿用现状） |
| empty | 本轮无思考 → 过程盘只有工具、无 💭；无工具无思考 → 不渲染过程盘 |
| error | 工具失败行（沿用现状） |
| disabled | N/A |
| submitting | N/A |
| permission denied | 沿用现状（gate 区） |
| long content | 长思考文本展开滚动 |
| missing/nullable data | 旧消息无 thinking 字段 → 不渲染思考行（兼容） |
| mobile viewport | 过程盘 375px 不溢出 |
| desktop viewport | 1440px 主验收 |
| dark mode | 沿用现有主题变量 |

测试与验收映射：

| 风险点 | 验收方式 | 是否落库 |
|---|---|---|
| 思考段+工具按 seq 混排渲染 | vitest 组件测试 + 浏览器验收 | 是 |
| reducer thinking.segment 追加 / message.created 还原 | vitest reducer 测试 | 是 |
| 历史刷新仍可展开思考 | 浏览器验收（REST 回放） | 截图证据 |
| 无思考不留空壳 | vitest + 浏览器截图 | 是 |
| 💭 行视觉（靛紫调） | 浏览器截图对照 prototype | 否 |
