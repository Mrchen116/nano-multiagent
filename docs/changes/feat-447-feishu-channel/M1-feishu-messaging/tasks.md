# feat-447-M1: feishu-messaging — Tasks

> 对齐: ../design.md

## 目标

Gateway 新增飞书 channel adapter（FeishuAdapter + FeishuClient），通过飞书 SDK WebSocket 长连接收发消息。支持 1:1 私聊直接响应、群聊 @Bot 触发（未 @ 消息暂存为上下文）、多 Bot 路由到对应 Agent。飞书对话通过现有 kernel event observer 自动同步到内部 IM。

## 退出标准

- [ ] feishu_adapter 单测全绿（1:1 私聊收发、群聊 @Bot 触发、未 @ 不触发、未 @ 消息作为上下文、多 Bot 路由）
- [ ] 飞书 SDK WebSocket 连接建立成功（FeishuClient 封装 lark-oapi WSClient）
- [ ] config.yaml 解析正确（channels.feishu.accounts 结构解析、agentId 绑定验证）
- [ ] mirror 到 IM 服务单测覆盖（InboundMessage 正确设置 agent_id，kernel event observer 自然推送）
- [ ] main.py 注册飞书 adapter、config 解析飞书 accounts 正确构建 FeishuAdapter

## 测试策略

- 被测行为（来自退出标准）：
  1. config.yaml 飞书 accounts 解析（含 appId/appSecret/agentId，缺字段报错）
  2. FeishuClient 启动/停止生命周期（mock lark-oapi WSClient）
  3. 1:1 私聊消息 → InboundMessage（channel_name / agent_id / external_chat_id / is_group=False）
  4. 群聊 @Bot 消息 → InboundMessage（is_group=True, agent_id 正确）
  5. 群聊未 @ 消息 → push 到 GroupContextStore，不触发 on_inbound
  6. 群聊 @Bot 时 flush GroupContextStore 上下文
  7. @所有人 不算 @Bot → 不触发
  8. 多 Bot 各自 agent_id 路由（不同 account 产出不同 channel_name 和 agent_id）
  9. OutboundMessage → 飞书 API 发送（mock send 接口）
  10. mirror 到 IM：InboundMessage.agent_id 正确设置，kernel event observer 覆盖
- 已有测试在：无直接覆盖，新建 `tests/unit/test_feishu_adapter.py`、`tests/unit/test_feishu_config.py`
- 落层/目录/marker：tests/unit/，marker：无
- 可选依赖 importorskip：有，lark-oapi（FeishuClient 测试需 importorskip）
- 本 milestone 产生的一次性验收证据（收尾删除，不进套件）：无（后端 API，测试即验收）

## Roadpoints

### R1 — 飞书 config 解析 + lark-oapi 依赖 `DONE`

- 步骤:
  1. C1: 写 config 飞书 accounts 解析测试（正常解析 + 缺字段报错 + 禁用 accounts 不注册）
  2. C2: pyproject.toml 添加 lark-oapi 依赖；`config/local_store.py` 新增飞书 accounts 解析逻辑（`_parse_feishu_accounts`）；`_build_channel_registry` 扩展支持 `feishu` channel
  3. C3: 更新 tasks.md + progress.md
- 验证: config 解析测试全绿；`_build_channel_registry` 对 `feishu` channel 不再 raise

### R2 — FeishuClient 封装 lark-oapi WSClient `DONE`

- 步骤:
  1. C1: 写 FeishuClient 生命周期测试（start 建立 WSClient / stop 关闭 / 消息回调触发）— mock lark-oapi
  2. C2: 新建 `channels/feishu_client.py`，封装 lark-oapi WSClient（事件分发、消息解析、reply 发送）
  3. C3: 更新 tasks.md + progress.md
- 验证: FeishuClient 测试全绿

### R3 — FeishuAdapter 消息收发 + 群聊 mention 门控 `DONE`

- 步骤:
  1. C1: 写 FeishuAdapter 测试（1:1 → InboundMessage / 群聊 @Bot → InboundMessage / 群聊未 @ → GroupContextStore / @所有人 不触发 / 多 Bot agent_id / send 回飞书）— mock FeishuClient
  2. C2: 新建 `channels/feishu_adapter.py`，实现 ChannelAdapter Protocol（start/send/stop + mention 检测 + GroupContextStore 交互）
  3. C3: 更新 tasks.md + progress.md
- 验证: FeishuAdapter 单测全绿；覆盖所有 spec 验收场景

### R4 — main.py 注册 + 集成测试 `DONE`

- 步骤:
  1. C1: 写集成测试（_build_channel_registry 对 feishu accounts 正确构建多个 FeishuAdapter / config 含 feishu 时 gateway bootstrap 不报错）
  2. C2: main.py `_build_channel_registry` 支持 feishu channel；config.yaml 飞书 accounts → FeishuAdapter 实例
  3. C3: 更新 tasks.md + progress.md + design.md（如有偏差）
- 验证: 全量测试 `pytest -m "not e2e"` 全绿；集成测试覆盖 channel 注册和多 Bot 路由
