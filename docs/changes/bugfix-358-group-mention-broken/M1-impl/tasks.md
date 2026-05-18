# bugfix-358-M1: impl — Tasks

## 目标

修复群聊 @-mention 处理链路：wire ID (agent_id / user_id) 与 display 层分离；mention 文本承载改为 inline `<mention type="..." target_id="..."/>` 标签；IM 不改写只存原文；agent 和 user 两条产出路径源头一致。

## 退出标准

来自 design.md Milestones 表：

- `[worker]` `pytest -xvs tests/unit/IM/test_relay_service.py` 全绿；新增测试覆盖：agent 项 payload 含 `agent_id` 且不含 synth user UUID；mention 解析只认 `<mention/>` 标签；display_name fallback 分支已删除
- `[worker]` `pytest -xvs tests/integration/test_group_mention_routing.py`（新增）覆盖 agent→agent / user→agent / agent→user 三向 mention 路由 + 同名 agent 消歧路由
- `[worker]` `cd src/IM/frontend && npm run test` 全绿（含新增测试）；覆盖：`handleMentionSelect` 写入 `<mention/>` 标签；composer mirror + MessageBubble 共用 `parseMentions` 解析；chip 按 `conversation.participants` 查当前 display_name；picker handle 列条件显示
- `[worker]` `cd src/IM/frontend && npm run build` 通过
- `[worker]` `pytest -m "not e2e"` 全绿（全局无新增失败）

## 测试策略

### 后端
- 修改 `tests/unit/IM/test_relay_service_broadcast.py` — 补充 participants payload schema 验证 + mention tag 解析验证
- 新增 `tests/integration/test_group_mention_routing.py` — HTTP 入口真实请求，覆盖三向 mention 路由
- 删除 `_extract_mentioned_agent_ids` / `_normalize_mentioned_agent_id` 后相关测试同步更新

### 前端
核心业务路径分类：`critical-path` (mention 路由) + `normal-ui` (chip 渲染)

UI 状态矩阵：
- default: mention chip 正常显示 display_name ✓
- empty/no mention: 无标签时字面渲染 ✓
- unknown target_id: 灰色 @unknown 降级 ✓
- long display_name: 待验证 (browser)
- composer mirror: `<mention/>` 被遮盖成 chip ✓
- duplicate display_name: picker handle 列条件显示 ✓
- mobile viewport: N/A (不影响路由逻辑)

| 风险点 | 验收方式 | 是否落库 |
|---|---|---|
| handleMentionSelect 写入标签 | 组件测试 | 是 |
| parseMentions 解析标签 | 单元测试 | 是 |
| MessageBubble chip 渲染 | 组件测试 | 是 |
| picker handle 列重名消歧 | 组件测试 | 是 |
| composer mirror 覆盖 | 浏览器验收截图 | 否 |
| 完整 user→agent 旅程 | 浏览器验收 | 否 |

## Roadpoints

| ID | 标题 | 状态 | 范围 |
|---|---|---|---|
| R1 | IM relay payload schema 修正 + 测试 | TODO | relay_service.py: _resolve_all_participants, _resolve_sender_info |
| R2 | IM mention 解析改为 inline tag | TODO | relay_service.py: _resolve_mention_to_agent_ids, _extract_mentioned_agent_ids |
| R3 | Agent prompt + hook 更新 | TODO | prompts.py, communication_context.py |
| R4 | 前端 parseMentions 工具函数 + 单测 | TODO | chat-types.ts or 新 mention-parser.ts, message-pane.tsx |
| R5 | 前端 picker 写入标签 + handle 条件显示 | TODO | message-pane.tsx handleMentionSelect, mention-picker.tsx |
| R6 | 前端 MessageBubble MentionChip 渲染 | TODO | message-pane.tsx MessageBubble/MarkdownContent |
| R7 | 集成测试 + 全局验证 | TODO | tests/integration/test_group_mention_routing.py, npm run build |
