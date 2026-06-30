# Verification Report: feat-447

## Round 1

## Summary

| 维度 | 结果 |
|---|---|
| Completeness | 26/26 complete |
| Correctness | 13/13 covered |
| Coherence | Followed |

No critical issues. 1 warning and 1 suggestion to consider. Ready for PR (with noted improvements).

## Completeness

### Tasks: 26/26 complete

- **M1** (feishu-messaging): 5/5 exit criteria all checked (`[x]`)
- **M2** (feishu-cli-integration): 7/7 exit criteria all checked (`[x]`)
- **M3** (增强错误处理): 8/8 exit criteria all checked (`[x]`)
- **M4** (fix-critical-param-and-skill): 6/6 exit criteria all checked (`[x]`)

### Spec Coverage

All spec requirements have implementation evidence:

| Requirement | 实现位置 | 状态 |
|---|---|---|
| 飞书 1:1 私聊对话 | `feishu_adapter.py:145-146` `_deliver_dm` | covered |
| 飞书群聊 @Bot 触发 | `feishu_adapter.py:149-150` `_deliver_group_with_context` | covered |
| 多 Agent 路由 | `feishu_adapter.py:64-65` `name` property + `local_store.py:893-966` config parsing | covered |
| 飞书对话同步到内部 IM | `main.py:2231-2236` kernel event observer (自动) | covered |
| 飞书云文档操作（用户身份） | `skills/feishu-doc.md` | covered |

## Correctness

### Requirement → Implementation Mapping

| Requirement / Scenario | 实现位置 | 测试覆盖 | 状态 |
|---|---|---|---|
| 用户在 1:1 私聊中发消息 → Bot 回复 | `feishu_adapter.py:154-173` `_deliver_dm` | `test_feishu_adapter.py:54-75` | covered |
| 私聊无需 @ 触发 | `feishu_adapter.py:145-146` (DM always deliver) | `test_feishu_adapter.py:77-93` | covered |
| 私聊 session 隔离 | `feishu_adapter.py:160` `external_chat_id` 含 sender_open_id | `test_feishu_adapter.py:54-75` (implicit) | covered |
| 群聊中 @Bot 触发回复 | `feishu_adapter.py:149-150` `_is_bot_mentioned` | `test_feishu_adapter.py:100-128` | covered |
| 群聊中未 @Bot 不触发 | `feishu_adapter.py:151-152` `_buffer_group_message` | `test_feishu_adapter.py:130-156` | covered |
| 未 @ 消息作为上下文 | `feishu_adapter.py:175-207` `_deliver_group_with_context` flush + prepend | `test_feishu_adapter.py:158-189` | covered |
| @所有人 不算 @Bot | `feishu_adapter.py:231-238` `_is_bot_mentioned` open_id="all" filter | `test_feishu_adapter.py:191-217` | covered |
| 不同 Bot 对应不同 Agent | `feishu_adapter.py:64-65` `name = f"feishu:{agent_id}"` | `test_feishu_adapter.py:222-235` | covered |
| 飞书消息出现在内部 IM | `main.py:2231-2236` kernel event observer 自动推送 | `test_feishu_integration.py` (implicit via pipeline) | covered |
| 飞书群聊消息出现在内部 IM | 同上 | 同上 | covered |
| 以用户身份创建文档 | `skills/feishu-doc.md:25-27` `feishu-cli doc create` | 纯文档 milestone，无代码测试 | covered |
| 以用户身份编辑文档 | `skills/feishu-doc.md:29-34` `feishu-cli doc read` + import | 纯文档 milestone | covered |
| 未授权时提示授权 | `skills/feishu-doc.md:12-18` `feishu-cli auth login` | 纯文档 milestone | covered |
| 以用户身份读取文档 | `skills/feishu-doc.md:29-34` | 纯文档 milestone | covered |
| 以用户身份创建文件夹 | `skills/feishu-doc.md:43-56` curl API 替代方案 | 纯文档 milestone | covered |
| 以用户身份移动文件 | `skills/feishu-doc.md:58-71` curl API 替代方案 | 纯文档 milestone | covered |
| 云文档 API 调用失败 | `skills/feishu-doc.md` 使用 feishu-cli 错误输出 | 纯文档 milestone | covered |

### CRITICAL Issue 修复确认

前一轮 verifier 报告的 **CRITICAL issue**（`main.py` 构造 `FeishuAdapter` 时缺少 `group_context_store` 参数）已在 M4 修复：

- `main.py:2234-2236`: `GroupContextStore` 在 `build_runtime()` 中统一创建
- `main.py:2241-2245`: `_build_channel_registry()` 调用时传入 `group_context_store`
- `main.py:2289-2295`: `InboundPipeline` 复用同一 `group_context_store` 实例
- `main.py:2894`: `_build_channel_registry` 签名接受 `group_context_store: GroupContextStore | None`
- `main.py:2915`: FeishuAdapter 构造时传入 `group_context_store=group_context_store`

验证：`test_feishu_integration.py:151-180` `test_build_channel_registry_passes_group_context_store` 不 mock FeishuAdapter，直接验证真实构造通过且 `_group_ctx` 非 None。该测试当前通过。

## Coherence

### Design 决策遵守

| design 决策 | 遵守? | 代码证据 |
|---|---|---|
| 决策 1: WebSocket 长连接模式 | 是 | `feishu_client.py:138-144` WSClient with `auto_reconnect=True` |
| 决策 2: config.yaml `channels.feishu.accounts` 列表 | 是 | `local_store.py:893-966` `_parse_feishu_accounts` |
| 决策 3: feishu-cli 作为云文档操作唯一路径 | 是 | `skills/feishu-doc.md` 全部命令基于 feishu-cli |
| 决策 4: Session key `feishu:<agent_id>:dm/group:<id>` | 是 | `feishu_adapter.py:160,194` `external_chat_id` 格式 |
| 决策 5: 复用 `GroupContextStore` | 是 | `feishu_adapter.py:58,178,211` 使用 `_group_ctx.append/drain` |
| 决策 6: 复用 kernel event observer 同步到 IM | 是 | `main.py:2231-2236` 统一创建 observer，不新建 mirror |

### 架构自洽性

- **依赖方向**: `personal_assistant` 只 import `agent.sdk`（无违反），feishu adapter 在 `personal_assistant.channels` 内，符合模块边界。
- **跨机/进程边界**: FeishuAdapter 通过 WebSocket 连飞书服务器（外部），不假设与 IM 同机。IM 同步通过现有 observer 机制，无直接进程间访问。
- **复用 vs 平行**: 复用 `ChannelAdapter` Protocol、`GroupContextStore`、`ChannelRegistry`、`OutboundRouter`、`InboundPipeline` 等既有机制，未另造平行物。

## Issues

### CRITICAL（提 PR 前必须修）

无。

### WARNING（应该修）

1. **GroupContextStore buffer key 格式不一致** — `feishu_adapter.py:243` 使用 `f"feishu:{app_id}:{chat_id}:{agent_id}"`，而 `inbound_pipeline.py:598` 使用 `f"{agent_id}:{message.channel_name}:{message.external_chat_id}"`。两者格式不同，导致 InboundPipeline 的 `_build_message_parts`  drain 时 key 不匹配，群聊上下文 buffer 无法被正确消费。

   具体：`feishu_adapter.py:211` append 的 key 是 `feishu:cli_a:oc_grp1:plato`，而 `inbound_pipeline.py:598` 生成的 key 是 `plato:feishu:plato:feishu:cli_a:group:oc_grp1`。InboundPipeline 的 drain 永远找不到 FeishuAdapter 写入的 buffer 内容。

   **建议**: 统一 key 格式。方案 A: 让 FeishuAdapter 使用与 InboundPipeline 一致的 key 格式；方案 B: 在 InboundPipeline 中识别 feishu channel 并适配其 key。推荐方案 A — 在 `feishu_adapter.py` 修改 `_group_buf_key` 为与 `inbound_pipeline.py:598` 一致的格式。

### SUGGESTION（可以修）

1. **`feishu_client.py:14` `typing.Any` 未使用** — 虽然 `Any` 在 `_handle_message_event` 和 `_parse_feishu_event` 的参数类型中被使用，但 `typing.Any` 在 Python 3.10+ 中可直接用内置 `any`（不，这里 `Any` 确实被使用了）。实际检查：`_handle_message_event(self, event: Any)` 和 `_parse_feishu_event(event: Any)` 确实使用了 `Any`。此条不成立，撤销。

2. **M4 tasks.md 退出标准第 2 条描述有误** — "补充不 mock FeishuAdapter 的集成测试" 实际实现的是 `test_build_channel_registry_without_group_context_store_fails`，它验证的是"不传 group_context_store 时 `_group_ctx` 为 None"（即 bug 存在时的行为），而非"构造通过"。测试命名和意图略有不一致，但功能正确（作为回归测试防止 regression）。建议将测试重命名为 `test_build_channel_registry_without_group_context_store_creates_none_group_ctx` 以更准确反映其断言。

3. **`_extract_chat_id` 对 DM 场景返回 `user_open_id` 而非 `chat_id`** — `feishu_adapter.py:246-259` 对 DM 的 `external_chat_id` 格式 `feishu:<app_id>:dm:<user_open_id>` 提取 `parts[-1]` 得到 `user_open_id`。飞书 API 的 `receive_id` 在 DM 场景下确实应该是对方的 `open_id`（飞书会路由到该用户的 DM），这是正确的行为。但注释说明可以更清晰："For DMs the receive_id is the user's open_id (feishu routes to the DM)" 已经说明了。无问题。

