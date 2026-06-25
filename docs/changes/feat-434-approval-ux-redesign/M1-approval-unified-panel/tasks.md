# feat-434-M1: approval-unified-panel — Tasks

> 对齐: ../design.md v1

## 目标

工具调用与审批呈现合一到同一个 agent 气泡内（气泡外不再有独立审批卡）；新增 `ToolCall.approval` 标识从内核 gate 一路贯穿到前端：allow 成功的工具行内显「已授权」、deny 显「已拒绝」+「未执行」，收起态后缀分项计数「N 次授权 · X 允许 · Y 拒绝」；行内「闸门区（是否授权）」与「结果区（执行结果）」分区，覆盖「授权后失败」边界；failTag 接 i18n，失败文案随界面语言。逐项对齐 `../prototype.html`。

## 退出标准

- [ ] [worker] allow 成功工具的 `approval=user_allow` 端到端到达前端（覆盖决策2 五步链；内核单测）
- [ ] [worker] `approval` 贯穿 内核→Gateway→IM→前端，IM REST 历史与 WS 均携带（IM encode/decode round-trip、Gateway 透传单测）
- [ ] [worker] 前端单测覆盖 ToolCallRow 闸门/结果分区 + denied 去重 + 已决并入
- [ ] [worker] `failTag` 经 i18n，zh/en 各出对应文案
- [ ] [worker] `npm run test` + `pytest -m "not e2e"` 全绿
- [ ] [worker] 真端到端跑通：live 栈（内核→Gateway→IM→前端）下 allow 成功工具前端真显「已授权」

## 测试策略

- 被测行为（来自退出标准）：
  1. gate allow 分支返回 `{"block":False,"approval":"user_allow"}`；deny 分支 approval=user_deny（内核单测）
  2. runner block=False 合并保留 approval（内核单测）
  3. registry 成功路径 lift approval → tool_executor 填 `ToolResult.approval`；deny 经 ToolError.details lift（内核单测）
  4. realtime_stream tool_end 携带 approval（内核单测）
  5. Gateway tool_end 把 approval 拼进 tool_call payload（PA 单测）
  6. IM ToolCall encode/decode round-trip 含 approval；WS/REST 序列化携带（IM 单测）
  7. 前端 ToolCallRow：approval=user_allow→闸门「已授权」、user_deny→闸门「已拒绝」+ 结果区「未执行」、授权后失败两区并存、denied 去重（vitest）
  8. failTag i18n：zh「退出码 N」/「失败」，en「exit N」/「failed」（vitest）
  9. 收起态后缀分项计数（vitest）
  10. 合一气泡：pending 卡在气泡内、气泡外无审批卡（vitest message-pane）
- 已有测试在：内核 `tests/unit/agent/`（test_auto_mode_gate / test_tool_executor / registry / realtime_stream）扩展；IM `tests/im_service/unit/`（repositories / event_types / gateway_handler）扩展；PA `tests/unit/personal_assistant/` 扩展；前端 component 测试同目录 `*.test.tsx` 扩展。优先扩展现有文件。
- 落层/目录/marker：tests/unit/ + tests/im_service/unit/（无 e2e marker，单测）；live 端到端为一次性验收证据（不进套件）
- 可选依赖 importorskip：无
- 本 milestone 产生的一次性验收证据（收尾删除，不进套件）：live 栈端到端 + 浏览器截图（记 progress.md，不落库）

### 前端 UI

用户路径分类：
- 合一气泡 / pending 卡入气泡 / 已决并入工具行 = `critical-path`（组件 regression + 浏览器验收）
- 行内闸门-结果分区 / 收起态分项计数 / failTag i18n = `normal-ui`（组件测试 + 浏览器对照原型）
- 深色待决卡视觉 = `visual-only`（浏览器截图对照原型）

UI 状态矩阵：
| 状态 | 覆盖计划 |
|---|---|
| default | 工具行无 approval → 闸门区不显（组件测试 + 浏览器） |
| loading | running 工具行（已有，不回归破坏） |
| empty | 无审批消息：无授权后缀、无审批呈现（组件测试 spec 空态场景） |
| error | 授权后失败：闸门「已授权」+ 结果区失败报错并存（组件测试 + 浏览器行变体 3） |
| disabled | pending 卡 submitting 时按钮禁用（已有 PermissionCard，不破坏） |
| submitting | 同上 |
| permission denied | approval=user_deny → 闸门「已拒绝」+ 结果区「未执行」+ denied 去重（组件测试） |
| long content | 长命令摘要省略（沿用现有 .chat-tool-call-summary ellipsis，浏览器抽查） |
| missing/nullable data | 历史行无 approval → undefined 不显；历史 denied 行回退读 reason==="denied"（组件测试） |
| mobile viewport | 浏览器 375 抽查气泡布局 |
| desktop viewport | 浏览器 1440 对照原型 |
| dark mode | N/A（工具面板/待决卡本就深色，IM 无整体 dark mode 切换） |

测试与验收映射：
| 风险点 | 验收方式 | 是否落库 |
|---|---|---|
| 合一气泡 / 气泡外无审批卡 | message-pane 组件测试 + 浏览器 | 是 |
| 闸门区 / 结果区分区 + 授权后失败 | ToolCallRow 组件测试 + 浏览器行变体 | 是 |
| denied 去重 | ToolCallRow 组件测试 | 是 |
| 收起态分项计数 | ToolCallsPanel 组件测试 | 是 |
| failTag i18n | tool-presentation 组件/单元测试 | 是 |
| 深色待决卡视觉 / 整体对照原型 | 浏览器截图 | 否 |

## Roadpoints

| R | 描述 | 状态 |
|---|---|---|
| R1 | 内核 approval 产出链：types.ToolResult.approval + auto_mode_gate(allow/deny 信号) + runner(block=False 保留) + registry(lift 成功路径) + tool_executor(填充) + realtime_stream(tool_end 携带) | TODO |
| R2 | Gateway→IM 透传链：main.py tool_end 透传 + IM domain/payload/repositories(encode/decode)/event_types/gateway_handler 五点 | TODO |
| R3 | 前端数据+行内呈现：chat-types.approval + tool-presentation(failTag i18n + isGateDenied 回退) + ToolCallRow(闸门/结果分区 + denied 去重) + ToolCallsPanel(分项计数) + i18n 键 | TODO |
| R4 | 前端合一气泡：message-pane(pending 入气泡、删气泡外卡) + permission-card(删 resolved 分支) + global.css 闸门/待决样式对齐原型 | TODO |
| R5 | 端到端 live 验收：整栈重启，真走 ask→allow→「已授权」、ask→deny→「已拒绝/未执行」、授权后失败两区并存；浏览器逐项对照原型截图 | TODO |
