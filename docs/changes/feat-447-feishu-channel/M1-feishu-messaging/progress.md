# feat-447-M1 — Progress

## R1 — 飞书 config 解析 + lark-oapi 依赖

- Context: 飞书 channel 需要在 config.yaml 中以 `channels.feishu.accounts` 结构配置多个 Bot，每个 account 绑定一个 agentId。现有 `_parse_channels` 只支持平铺 list 格式，需扩展支持 feishu accounts 子列表。
- Decision: 在 `_parse_channels` 中检测 `name == "feishu"` + `"accounts" in item` 时调用新函数 `_parse_feishu_accounts`，将 accounts 展开为独立 `ChannelConfig(name="feishu:<acct_name>")`。每个 ChannelConfig 的 settings 携带 appId/appSecret/agentId 供 adapter 使用。lark-oapi SDK 作为主依赖加入 pyproject.toml。
- Rationale: 跟 design 决策 2 一致（config.yaml 的 channels.feishu.accounts 列表）。复用现有 ChannelConfig 结构，不引入新配置抽象。Disabled accounts 在解析期跳过，不产生 ChannelConfig。
- Evidence:
  - Tests: `pytest tests/unit/test_feishu_config.py` — 11 passed（单 account / 多 account / 禁用排除 / 缺字段报错 / 混合 channel / 空列表 / settings 携带）
  - Entry: N/A（纯配置解析，无运行时入口）
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: N/A — 纯逻辑变更，回归由全量 `pytest -m "not e2e"` 覆盖（3126 passed）
  - Visual/Interaction: N/A
- Rollback: `git revert b433599a` 回退 config 解析；`git revert 1b839230` 回退测试文件
- Commits: C1=1b839230, C2=b433599a
- Next: R2 — FeishuClient 封装 lark-oapi WSClient

## R2 — FeishuClient 封装 lark-oapi WSClient

- Context: 飞书 SDK (lark-oapi) 的 WSClient 是阻塞式的，REST Client 用于发送消息。需要封装为 FeishuClient，提供 start(on_message)/stop()/send_message() 接口。
- Decision: FeishuClient.start() 在 daemon 线程中运行 WSClient.start()（阻塞），避免卡住 gateway bootstrap。消息事件通过 EventDispatcherHandler.register_p2_im_message_receive_v1 注册回调。发送消息通过 lark.Client REST API (im.v1.message.create)。事件解析提取 text/sender/chat_id/mentions，@mention 占位符从文本中剥离。
- Rationale: WSClient.start() 是 SDK 设计的阻塞入口，daemon 线程是最小侵入的包装方式。REST 和 WS 共用同一个 app_id/app_secret，但分属不同 client 实例（SDK 不支持复用）。
- Evidence:
  - Tests: `pytest tests/unit/test_feishu_client.py` — 10 passed（lifecycle start/stop / p2p/group 解析 / text JSON 提取 / mention 剥离 / 空内容 / 非 JSON fallback / mentions 提取 / send_message API 调用）
  - Entry: N/A（mock lark-oapi，无真实连接）
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: N/A — mock 测试，真实连接在 reviewer 验收
  - Visual/Interaction: N/A
- Rollback: `git revert 6b2b178d` 回退 FeishuClient 实现 + 测试
- Commits: C1=5820dc40, C2=6b2b178d
- Next: R3 — FeishuAdapter 消息收发 + 群聊 mention 门控

## R3 — FeishuAdapter 消息收发 + 群聊 mention 门控

- Context: FeishuAdapter 是 ChannelAdapter Protocol 的飞书实现，核心职责：(1) DM 直接响应；(2) 群聊 @Bot 才触发 + 未@ 消息暂存 GroupContextStore；(3) @所有人 不算 @Bot；(4) 多 Bot 各自 agent_id 路由。
- Decision: _handle_message 决策树：DM → deliver；Group + @Bot → drain context + deliver；Group + no @Bot → buffer。bot_open_id 用于 @mention 检测，open_id="all" 视为 @所有人。external_chat_id 按 design 格式 `feishu:<app_id>:dm/group:<id>` 构造，session key 由现有 build_session_key 自动拼接 agent_id。
- Rationale: 复用现有 GroupContextStore（设计决策 5），不新建 buffer。mention 检测逻辑直接比对 open_id，简单可靠。
- Evidence:
  - Tests: `pytest tests/unit/test_feishu_adapter.py` — 11 passed（DM 无需 @ / DM InboundMessage 字段正确 / 群聊 @Bot 触发 / 群聊未@ buffer / @Bot flush context / @所有人 不触发 / 多 Bot 不同 channel_name / agent_id 路由 / send 调 FeishuClient / stop 调 stop）
  - Entry: N/A（mock FeishuClient，无真实飞书连接）
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: N/A — mock 测试覆盖所有 spec 场景，真实连接由 reviewer 验收
  - Visual/Interaction: N/A
- Rollback: `git revert 4dd516e1`
- Commits: C1=109b6b30, C2=4dd516e1
- Next: R4 — main.py 注册 + 集成测试

## R4 — main.py 注册 + 集成测试

- Context: _build_channel_registry 原只支持 web_relay，需扩展支持 feishu channels。feishu channels 由 config 解析产出的 ChannelConfig(name="feishu:<acct>") 驱动。
- Decision: 在 _build_channel_registry 中检测 `channel.name.startswith("feishu:")` 时从 settings 构建 FeishuAdapter。import FeishuAdapter 在 main.py 顶部（跟 WebRelayAdapter 同级）。GroupContextStore 由 adapter 内部构造（复用 gateway 现有实例需要在 bootstrap 阶段传入，当前先用 adapter 自建；后续迭代可注入共享实例）。
- Rationale: 最小侵入改动——只在 _build_channel_registry 的 match 分支加一个 feishu case，不改 bootstrap 流程。GroupContextStore 的注入可以在后续 milestone 统一。
- Evidence:
  - Tests: `pytest tests/unit/test_feishu_integration.py` — 4 passed（单 feishu adapter 注册 / 多 account 注册 / disabled 不注册 / 与 web_relay 共存）
  - Entry: N/A（集成测试通过 mock 验证注册逻辑，无真实飞书连接）
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: N/A — 由全量 pytest 覆盖
  - Visual/Interaction: N/A
- Rollback: `git revert 1949d1a3`
- Commits: C1=af826d3a, C2=1949d1a3
- Next: R4 完成 = M1 所有 roadpoint DONE，进入 §6 集成
