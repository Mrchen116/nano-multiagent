# Verification Report: feat-447

## Summary

| 维度 | 结果 |
|---|---|
| Completeness | 26/27 tasks complete (M1 exit criteria unchecked) |
| Correctness | 16/18 requirements/scenarios covered |
| Coherence | 5/6 design decisions followed |

1 critical issue(s) found. Fix before PR.

## Completeness

### §2.1 Task 完成检查

| Milestone | 状态 | 备注 |
|---|---|---|
| M1-feishu-messaging | 4/4 roadpoints DONE, 0/5 exit criteria checked | 退出标准框未标 `[x]`，但 checkpoint 确认 DONE |
| M2-feishu-cli-integration | 8/8 exit criteria checked, 1/1 roadpoint DONE | 完成 |
| M3-error-handling | 8/8 exit criteria checked, 3/3 roadpoints DONE | 完成 |

**Tasks: 26/27 complete** — M1 tasks.md 退出标准全部 `- [ ]`，与 checkpoint 的 DONE 状态不一致。代码和测试均已交付，属于文档标记遗漏。

### §2.2 Spec 覆盖检查

| Spec Requirement | 实现 | 状态 |
|---|---|---|
| 飞书 1:1 私聊对话 | feishu_adapter.py:155-174 | 有实现 |
| 飞书群聊 @Bot 触发 | feishu_adapter.py:176-208 | 有实现 |
| 多 Agent 路由 | main.py:2902-2910 + config | 有实现 |
| 飞书对话同步到内部 IM | InboundMessage.agent_id 设置 + kernel event observer（design 决策 6） | 有实现（MVP 半边对话） |
| 飞书云文档操作（用户身份） | skills/feishu-doc.md（feishu-cli） | 有实现（skill 文件） |

Spec 5 个 Requirement 全部有实现覆盖。

## Correctness

### §3.1 / §3.2 Requirement 实现映射

| Requirement / Scenario | 实现位置（file:line） | 测试覆盖 | 状态 |
|---|---|---|---|
| 用户在 1:1 私聊中发消息 | feishu_adapter.py:155-174 `_deliver_dm` | test_feishu_adapter.py:54-75 | covered |
| 私聊无需 @ 触发 | feishu_adapter.py:146-148 `_handle_message` DM branch | test_feishu_adapter.py:77-93 | covered |
| 私聊 session 隔离 | feishu_adapter.py:161 `external_chat_id` 含 sender_open_id | test_feishu_adapter.py:75 | covered |
| 群聊中 @Bot 触发回复 | feishu_adapter.py:176-208 `_deliver_group_with_context` | test_feishu_adapter.py:99-127 | covered |
| 群聊中未 @Bot 不触发 | feishu_adapter.py:210-216 `_buffer_group_message` | test_feishu_adapter.py:129-155 | covered |
| 未 @ 消息作为上下文 | feishu_adapter.py:179-189 drain + prepend | test_feishu_adapter.py:157-189 | covered |
| @所有人 不算 @Bot | feishu_adapter.py:232-237 `_is_bot_mentioned` open_id=="all" | test_feishu_adapter.py:191-216 | covered |
| 不同 Bot 对应不同 Agent | main.py:2902-2910 config agentId 绑定 | test_feishu_integration.py:41-77 | covered |
| 飞书消息出现在内部 IM | feishu_adapter.py:163,198 `agent_id=self._agent_id` | 无直接测试 | covered（依赖 kernel event observer，InboundMessage.agent_id 正确即自动同步） |
| 飞书群聊消息出现在内部 IM | 同上 | 同上 | covered |
| 以用户身份创建文档 | skills/feishu-doc.md:24-26 `doc create` | 纯文档，无代码测试 | covered |
| 以用户身份编辑文档 | skills/feishu-doc.md:39-40 `doc import` | 纯文档 | covered（通过 import 覆盖） |
| 未授权时提示授权 | skills/feishu-doc.md:13-17 `auth login` | 纯文档 | covered |
| 以用户身份读取文档内容 | skills/feishu-doc.md:31-33 `doc read` | 纯文档 | covered |
| 以用户身份创建文件夹 | skills/feishu-doc.md 未显式覆盖 mkdir | 无 | 偏离 — feishu-cli skill 缺少文件夹创建命令 |
| 以用户身份移动文件 | skills/feishu-doc.md 未覆盖移动 | 无 | 偏离 — feishu-cli skill 缺少文件移动命令 |
| 云文档 API 调用失败 | feishu_adapter.py:104-125 FeishuAuthError/FeishuAPIError | test_feishu_adapter.py:292-349 | covered（消息发送路径；文档操作路径由 feishu-cli 自身处理） |
| config.yaml 飞书 accounts 解析 | local_store.py:910-966 `_parse_feishu_accounts` | test_feishu_config.py:15-213 (11 tests) | covered |

### 测试覆盖统计

| 测试文件 | 测试数 | 覆盖范围 |
|---|---|---|
| test_feishu_config.py | 11 | config 飞书 accounts 解析（正常/异常/禁用/共存） |
| test_feishu_adapter.py | 14 | DM/群聊@/未@/上下文/多Bot/send/错误处理 |
| test_feishu_client.py | 17 | 生命周期/事件解析/消息发送/错误分类重试 |
| test_feishu_integration.py | 4 | main.py channel 注册/多Bot/禁用/共存 |
| **合计** | **46** | |

## Coherence

### §4.1 Design 决策遵守

| design 决策 | 遵守? | 代码证据（file:line） |
|---|---|---|
| 决策 1: WebSocket 长连接模式 | 是 | feishu_client.py:138-144 `WSClient(auto_reconnect=True)` |
| 决策 2: config.yaml accounts 列表 + agentId 绑定 | 是 | local_store.py:910-966 `_parse_feishu_accounts` |
| 决策 3: feishu-cli 不自建 doc tools | 是 | skills/feishu-doc.md 为 skill 文件，无自建 Python doc tools |
| 决策 4: Session key 含 agent_id | 是 | feishu_adapter.py:161,195 `external_chat_id` 格式 `feishu:<app_id>:dm/group:<id>`，agent_id 由 build_session_key 自动拼接 |
| 决策 5: 复用 GroupContextStore | 是 | feishu_adapter.py:26 `from ...group_context_store import GroupContextStore`，feishu_adapter.py:179,213 使用 drain/append |
| 决策 6: kernel event observer 自动同步 IM | 是 | InboundMessage.agent_id 正确设置（feishu_adapter.py:163,198），design 明确记录 MVP 半边对话 gap |

### §4.2 代码模式一致性

- **ChannelAdapter Protocol 实现**: FeishuAdapter 实现了 start/send/stop 三方法（feishu_adapter.py:68,79,127），符合 base.py Protocol
- **Docstring 风格**: Google 风格 docstring（feishu_adapter.py:32-43, feishu_client.py:99-106），符合 COMMENTING_GUIDE.md
- **模块边界**: channels/ 内只 import base.py + gateway/group_context_store.py，未反向 import 内核内部
- **import 边界**: main.py:36 `from personal_assistant.channels.feishu_adapter import FeishuAdapter`，未 import agent.core/platform

### §4.3 架构自洽性

- **依赖方向**: channels/ → gateway/ (GroupContextStore) + base.py，main.py → channels/，无反向依赖。遵守。
- **跨机边界**: FeishuClient 通过 WebSocket 连飞书服务器（进程外），adapter 进程本地。无跨机假设。遵守。
- **复用 vs 平行**: 复用 ChannelAdapter Protocol、GroupContextStore、ChannelRegistry。未另造平行机制。遵守。
- **外部依赖**: lark-oapi 声明在 pyproject.toml:29 `"lark-oapi>=1.4,<2.0"`。遵守。

## Issues

### CRITICAL（提 PR 前必须修）

1. **main.py 创建 FeishuAdapter 缺少必需参数 `group_context_store`**
   - `main.py:2904-2910` — FeishuAdapter 构造函数要求 keyword-only 参数 `group_context_store`（feishu_adapter.py:52），但 `_build_channel_registry` 未传入。运行时 Gateway 启动会抛 `TypeError: missing keyword-only argument: 'group_context_store'`，飞书 channel 功能完全不可用。
   - **根因**: 集成测试 test_feishu_integration.py 全部 mock 了 FeishuAdapter（`@patch("personal_assistant.main.FeishuAdapter")`），mock 不检查构造参数，掩盖了缺参 bug。
   - **修复**: 在 `_build_channel_registry`（main.py:2886）中创建 `GroupContextStore` 实例并传入 FeishuAdapter 构造。同时考虑传入 `bot_open_id`（从 settings 可选读取，用于精确 @mention 检测）。补一个不 mock FeishuAdapter 的集成测试验证构造参数完整性。

### WARNING（应该修）

2. **feishu-cli skill 缺少 spec 要求的文件夹创建和文件移动命令**
   - `skills/feishu-doc.md` 覆盖了 doc/wiki/sheet/chat 操作，但 spec 的 Scenario「以用户身份创建文件夹」和「以用户身份移动文件」在 skill 中无对应命令。
   - **建议**: 在 feishu-doc.md 的文档操作章节补充 `feishu-cli doc mkdir`（或等效命令）和 `feishu-cli doc move`（或等效命令）。若 feishu-cli 不支持这些操作，在 skill 中注明并指引用户手动操作。

### SUGGESTION（可以修）

1. **M1 tasks.md 退出标准未勾选**
   - `M1-feishu-messaging/tasks.md:11-15` — 5 个退出标准全部 `- [ ]`，但 checkpoint 确认 M1 DONE。所有 roadpoint 已标 DONE。
   - **建议**: 将 `- [ ]` 改为 `- [x]`，与 checkpoint 状态对齐。

2. **typing.Any 在 feishu_adapter.py 中未使用**
   - `feishu_adapter.py:12` — `from typing import Any` 导入但文件中无使用。
   - **建议**: 移除未使用的导入。

3. **M2 skill 超出 spec 范围（wiki/sheet/chat）**
   - `skills/feishu-doc.md:44-77` — 包含 wiki、sheet、chat 操作，但 spec 范围明确排除 wiki 和 bitable，且 Q5 排除文档评论。超范围部分不影响功能（skill 只是文档），但可能误导 agent 使用非目标能力。
   - **建议**: 在 skill 文件中加注 "以下操作超出当前 MVP 范围" 或拆分到单独 skill，避免 agent 主动调用超范围命令。
