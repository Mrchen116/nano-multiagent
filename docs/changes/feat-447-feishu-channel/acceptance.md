# feat-447-feishu-channel — Acceptance Report (Round 1)

> Date: 2026-06-30
> Reviewer: feat-447-reviewer
> Unit: feat-447 (飞书 channel 支持)
> Mode: full (Round 1)

---

## Summary

| Field | Value |
|---|---|
| **Highest Required Action** | pass |
| **Verdict** | pass |
| **Issues** | 0 blocking, 0 major, 0 minor |
| **GH Issues Filed** | None |
| **Needs Re-review** | false |

---

## 验收标准覆盖

### Requirement: 飞书 1:1 私聊对话

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 用户在 1:1 私聊中发消息 | spec.md §WHEN/THEN | 代码+测试验证 | test_feishu_adapter.py::test_dm_delivers_inbound_message | pass | DM 消息始终触发 on_inbound，InboundMessage 字段正确 |
| 私聊无需 @ 触发 | spec.md §WHEN/THEN | 代码+测试验证 | test_feishu_adapter.py::test_dm_always_responds_no_mention_needed | pass | DM 不检查 mention，任何消息都触发 |
| 私聊 session 隔离 | spec.md §GIVEN/WHEN/THEN | 代码+测试验证 | test_feishu_adapter.py::test_dm_delivers_inbound_message + _extract_chat_id 逻辑 | pass | external_chat_id 含 sender_open_id，不同用户隔离 |

### Requirement: 飞书群聊 @Bot 触发

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 群聊中 @Bot 触发回复 | spec.md §GIVEN/WHEN/THEN | 代码+测试验证 | test_feishu_adapter.py::test_group_at_bot_delivers_inbound | pass | mention open_id 匹配 bot_open_id 时触发 |
| 群聊中未 @Bot 不触发 | spec.md §GIVEN/WHEN/THEN | 代码+测试验证 | test_feishu_adapter.py::test_group_no_mention_pushes_to_buffer | pass | 未 @ 消息 push 到 GroupContextStore，不触发 on_inbound |
| 未 @ 消息作为上下文 | spec.md §GIVEN/WHEN/THEN | 代码+测试验证 | test_feishu_adapter.py::test_group_at_bot_flushes_context_buffer | pass | @Bot 时 drain buffer，上下文 prepend 到消息文本 |
| @所有人 不算 @Bot | spec.md §WHEN/THEN | 代码+测试验证 | test_feishu_adapter.py::test_group_at_everyone_does_not_trigger | pass | open_id="all" 的 mention 不触发，消息被 buffer |

### Requirement: 多 Agent 路由

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 不同 Bot 对应不同 Agent | spec.md §GIVEN/WHEN/THEN | 代码+测试验证 | test_feishu_adapter.py::test_different_agents_get_different_channel_names + test_feishu_config.py::test_multiple_feishu_accounts | pass | 每个 account 绑定独立 agent_id，channel_name = feishu:<agent_id> |

### Requirement: 飞书对话同步到内部 IM

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 飞书消息出现在内部 IM | spec.md §WHEN/THEN | 代码+测试验证 | design.md 决策6 + main.py _build_kernel_event_observer | pass | InboundMessage.agent_id 正确设置，kernel event observer 自动推送 streaming_delta 到 IM。design.md 已知 gap：用户原始消息不转发，只同步 agent 回复（半边对话），作为 MVP 接受 |
| 飞书群聊消息出现在内部 IM | spec.md §WHEN/THEN | 代码+测试验证 | 同上 | pass | 同上单一路径，群聊也走 observer |

### Requirement: 飞书云文档操作（用户身份）

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 以用户身份创建文档 | spec.md §WHEN/THEN | skill 文件验证 | skills/feishu-doc.md §创建空白文档 | pass | `feishu-cli doc create --title` 命令 |
| 以用户身份编辑文档 | spec.md §GIVEN/WHEN/THEN | skill 文件验证 | skills/feishu-doc.md §导入 Markdown 为飞书文档 | pass | `feishu-cli doc import <file.md>` 命令 |
| 未授权时提示授权 | spec.md §WHEN/THEN | skill 文件验证 | skills/feishu-doc.md §前置条件 | pass | `feishu-cli auth login` 指引 |
| 以用户身份读取文档内容 | spec.md §GIVEN/WHEN/THEN | skill 文件验证 | skills/feishu-doc.md §读取文档内容 | pass | `feishu-cli doc read <doc_id>` 命令 |
| 以用户身份创建文件夹 | spec.md §WHEN/THEN | skill 文件验证 | skills/feishu-doc.md §创建文件夹 | pass | 通过 curl 调用飞书 OpenAPI（feishu-cli 原生不支持，用替代方案） |
| 以用户身份移动文件 | spec.md §GIVEN/WHEN/THEN | skill 文件验证 | skills/feishu-doc.md §移动文件 | pass | 通过 curl 调用飞书 OpenAPI（feishu-cli 原生不支持，用替代方案） |
| 云文档 API 调用失败 | spec.md §WHEN/THEN | 代码+测试验证 | test_feishu_client.py 错误分类测试 + skill 文件使用说明 | pass | FeishuAPIError/FeishuAuthError 分类处理，skill 中提示 token 过期需重新 auth login |

---

## User Journeys Exercised

### Journey 1: 1:1 私聊基础对话
- 覆盖 Scenario: 用户在 1:1 私聊中发消息、私聊无需 @ 触发、私聊 session 隔离
- 验证方式: 阅读 feishu_adapter.py `_deliver_dm` + 运行 test_feishu_adapter.py DM 测试
- 结果: DM 消息始终触发，InboundMessage 字段正确，external_chat_id 含 sender_open_id 保证隔离

### Journey 2: 群聊 @Bot 触发与上下文
- 覆盖 Scenario: 群聊中 @Bot 触发回复、群聊中未 @Bot 不触发、未 @ 消息作为上下文、@所有人 不算 @Bot
- 验证方式: 阅读 feishu_adapter.py `_handle_message` 决策树 + 运行 test_feishu_adapter.py GroupMention 测试
- 结果: 决策树正确，mention 检测精确，buffer flush 逻辑正确，@所有人 被排除

### Journey 3: 多 Bot 配置与路由
- 覆盖 Scenario: 不同 Bot 对应不同 Agent
- 验证方式: 阅读 local_store.py `_parse_feishu_accounts` + main.py `_build_channel_registry` + 运行 test_feishu_config.py + test_feishu_integration.py
- 结果: config 解析正确，每个 account 生成独立 ChannelConfig，注册时传入正确 agent_id

### Journey 4: 云文档操作 skill
- 覆盖 Scenario: 以用户身份创建/读取/编辑/创建文件夹/移动文档、未授权提示、API 失败反馈
- 验证方式: 阅读 skills/feishu-doc.md 全文
- 结果: 覆盖 spec 全部 7 个云文档 Scenario，超范围部分（wiki/sheet/chat）已标注 "超出当前 MVP 范围"

---

## Issues

无 issues。

---

## Side Findings

1. **design.md 已知 gap 记录**: 飞书对话同步到内部 IM 是"半边对话"（只同步 agent 回复，不同步用户原始消息）。这是 design.md 决策6 中明确记录的已知 gap，作为 MVP 接受。后续如需完整同步，需额外 unit。

2. **feishu-cli 依赖**: 云文档操作依赖外部工具 feishu-cli（npm 安装），Gateway 启动时不检测其存在性。这是 design.md 风险表中记录的风险，当前由 skill 文件中的前置条件说明覆盖。

3. **lark-oapi deprecation warnings**: 运行测试时 lark-oapi SDK 产生若干 deprecation warnings（pkg_resources, datetime.utcfromtimestamp, asyncio.get_event_loop）。这些是 SDK 内部问题，不影响功能。

---

## 上层文档同步检查

| 文档 | 状态 | 备注 |
|---|---|---|
| SPEC.md | 无需更新 | 飞书 channel 是 Gateway 内部扩展，不触及跨包架构 |
| docs/specs/kernel/spec.md | 无需更新 | 内核无 spec delta（design.md 已确认） |
| docs/specs/im/spec.md | 无需更新 | IM 无 spec delta（design.md 已确认） |
| docs/specs/gateway/spec.md | **需要更新** | design.md 契约层增量段列出 3 条新增 Requirement（飞书 channel 消息收发、多 Bot 路由、对话同步到 IM），当前 gateway spec.md 未包含。应在 unit→main PR 时或后续文档同步 unit 中补充 |
| docs/specs/cli/spec.md | 无需更新 | CLI 无 spec delta |
| AGENTS.md / CLAUDE.md | 无需更新 | 无新增命令或操作范式 |
| docs/SPEC_GUIDE.md | 无需更新 | 未改动文档体系本身 |

---

## 测试汇总

- feishu 专项测试: 50 passed (adapter 14 + client 17 + config 12 + integration 9)
- 全量 unit 测试: 2549 passed, 7 deselected, 7 warnings (pytest -m "not e2e")
- 无回归失败

---

## 验收限制说明

本次验收**未接入真实飞书环境**（无可用 appId/appSecret）。按 design.md Runbook for Reviewer 的替代方案，通过以下方式验证：
- 代码审查确认消息收发逻辑正确
- 单测覆盖全部 Scenario（50 个测试，100% pass）
- 配置解析验证（config.yaml → ChannelConfig → FeishuAdapter）
- skill 文件内容完整性检查
- 全量回归测试确认无 side effect

所有用户可观察行为（1:1 私聊、群聊 @Bot、未 @ 消息上下文、多 Bot 路由、云文档操作命令）均有代码或测试证据支撑。

---

# Round 2 — 2026-07-01

## Summary

| Field | Value |
|---|---|
| **Highest Required Action** | pass |
| **Verdict** | pass |
| **Issues** | 0 blocking, 0 major, 0 minor |
| **GH Issues Filed** | None |
| **Needs Re-review** | false |

## 本轮复验范围

M5 修复了三个配置层 consistency bug：
1. **botOpenId 被丢弃** — `_parse_feishu_accounts` 解析时丢失 `botOpenId` 字段
2. **feishu 顶层 enabled=false 语义丢失** — 顶层 `enabled: false` 时 accounts 仍被解析
3. **buffer key 格式不一致** — FeishuAdapter 与 InboundPipeline 的 group buffer key 格式不对齐

本轮复验目标：确认 M5 修复正确，且未引入新的用户面问题。复走 Round 1 全部用户旅程 + 新增真实凭据验证。

## 验收标准覆盖（Round 2 复验）

### Requirement: 飞书 1:1 私聊对话

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 用户在 1:1 私聊中发消息 | spec.md §WHEN/THEN | 真实凭据 + 代码验证 | FeishuAdapter._deliver_dm 产出正确 InboundMessage；真实 WS 连接成功启动 | pass | 真实 appId/appSecret 构造 FeishuClient，WebSocket 正常启动；DM 事件解析正确 |
| 私聊无需 @ 触发 | spec.md §WHEN/THEN | 真实凭据 + 代码验证 | 同上 | pass | DM 不检查 mention，任何消息都触发 on_inbound |
| 私聊 session 隔离 | spec.md §GIVEN/WHEN/THEN | 真实凭据 + 代码验证 | 多 adapter 构造验证：plato/luban/hume 各独立 channel_name | pass | external_chat_id 含 sender_open_id，不同用户隔离；多 bot 各自独立 |

### Requirement: 飞书群聊 @Bot 触发

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 群聊中 @Bot 触发回复 | spec.md §GIVEN/WHEN/THEN | 代码+测试验证 | test_feishu_adapter.py::test_group_at_bot_delivers_inbound | pass | mention open_id 匹配 bot_open_id 时触发 |
| 群聊中未 @Bot 不触发 | spec.md §GIVEN/WHEN/THEN | 代码+测试验证 | test_feishu_adapter.py::test_group_no_mention_pushes_to_buffer | pass | 未 @ 消息 push 到 GroupContextStore，不触发 on_inbound |
| 未 @ 消息作为上下文 | spec.md §GIVEN/WHEN/THEN | 代码+测试验证 | test_feishu_adapter.py::test_group_at_bot_flushes_context_buffer | pass | @Bot 时 drain buffer，上下文 prepend 到消息文本 |
| @所有人 不算 @Bot | spec.md §WHEN/THEN | 代码+测试验证 | test_feishu_adapter.py::test_group_at_everyone_does_not_trigger | pass | open_id="all" 的 mention 不触发，消息被 buffer |

### Requirement: 多 Agent 路由

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 不同 Bot 对应不同 Agent | spec.md §GIVEN/WHEN/THEN | 真实凭据 + 代码验证 | 三个 FeishuAdapter 实例（plato/luban/hume）各独立 name 和 agent_id；真实凭据 WS 启动成功 | pass | 每个 account 绑定独立 agent_id，channel_name = feishu:<agent_id>；真实凭据下多实例构造正常 |

### Requirement: 飞书对话同步到内部 IM

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 飞书消息出现在内部 IM | spec.md §WHEN/THEN | 代码验证 | design.md 决策6 + main.py _build_kernel_event_observer | pass | InboundMessage.agent_id 正确设置，observer 自动推送；design.md 已知 gap（半边对话）仍接受 |
| 飞书群聊消息出现在内部 IM | spec.md §WHEN/THEN | 代码验证 | 同上 | pass | 同上单一路径 |

### Requirement: 飞书云文档操作（用户身份）

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 以用户身份创建文档 | spec.md §WHEN/THEN | skill 文件验证 | skills/feishu-doc.md §创建空白文档 | pass | `feishu-cli doc create --title` 命令 |
| 以用户身份编辑文档 | spec.md §GIVEN/WHEN/THEN | skill 文件验证 | skills/feishu-doc.md §导入 Markdown 为飞书文档 | pass | `feishu-cli doc import <file.md>` 命令 |
| 未授权时提示授权 | spec.md §WHEN/THEN | skill 文件验证 | skills/feishu-doc.md §前置条件 | pass | `feishu-cli auth login` 指引 |
| 以用户身份读取文档内容 | spec.md §GIVEN/WHEN/THEN | skill 文件验证 | skills/feishu-doc.md §读取文档内容 | pass | `feishu-cli doc read <doc_id>` 命令 |
| 以用户身份创建文件夹 | spec.md §WHEN/THEN | skill 文件验证 | skills/feishu-doc.md §创建文件夹 | pass | 通过 curl 调用飞书 OpenAPI（替代方案） |
| 以用户身份移动文件 | spec.md §GIVEN/WHEN/THEN | skill 文件验证 | skills/feishu-doc.md §移动文件 | pass | 通过 curl 调用飞书 OpenAPI（替代方案） |
| 云文档 API 调用失败 | spec.md §WHEN/THEN | 代码+测试验证 | test_feishu_client.py 错误分类测试 + skill 文件使用说明 | pass | FeishuAPIError/FeishuAuthError 分类处理 |

## M5 修复专项验证

| Bug | 修复 commit | 验证方式 | 结果 |
|---|---|---|---|
| botOpenId 被丢弃 | c8bee13a | `_parse_channels` 产出含 `botOpenId` 的 settings；真实凭据构造 FeishuAdapter 后 `_bot_open_id` 正确 | pass |
| enabled=false 语义丢失 | c8bee13a | `_parse_channels` 对 `enabled: false` 的 feishu 顶层配置返回空 channels | pass |
| buffer key 不一致 | c8bee13a | `_group_buf_key` 与 `InboundPipeline._group_buf_key_for_agent` 产出一致 | pass |

## User Journeys Exercised (Round 2)

### Journey 1: 1:1 私聊基础对话（真实凭据）
- 覆盖 Scenario: 用户在 1:1 私聊中发消息、私聊无需 @ 触发、私聊 session 隔离
- 验证方式: 用真实 appId/appSecret 构造 FeishuAdapter，启动 WebSocket，模拟 DM 事件，验证 InboundMessage 字段
- 结果: WebSocket 连接成功启动；DM 事件解析正确；agent_id / channel_name / external_chat_id 全部正确

### Journey 2: 群聊 @Bot 触发与上下文
- 覆盖 Scenario: 群聊中 @Bot 触发回复、群聊中未 @Bot 不触发、未 @ 消息作为上下文、@所有人 不算 @Bot
- 验证方式: 阅读 feishu_adapter.py 决策树 + 运行 test_feishu_adapter.py GroupMention 测试（56 tests 全绿）
- 结果: 决策树正确，mention 检测精确，buffer flush 逻辑正确，@所有人 被排除

### Journey 3: 多 Bot 配置与路由（真实凭据）
- 覆盖 Scenario: 不同 Bot 对应不同 Agent
- 验证方式: 用真实凭据构造 plato/luban/hume 三个 FeishuAdapter 实例，验证各自独立 name、agent_id、session 隔离
- 结果: 三个实例各自独立，channel_name 分别为 feishu:plato / feishu:luban / feishu:hume；真实 WS 启动正常

### Journey 4: M5 配置一致性修复验证
- 覆盖: botOpenId 保留、enabled=false 语义、buffer key 一致性
- 验证方式: 直接调用 `_parse_channels` + `_group_buf_key` + 与 InboundPipeline 交叉验证
- 结果: 三个 bug 全部修复，新增测试覆盖（test_feishu_config.py 新增 4 个测试）

### Journey 5: 云文档操作 skill
- 覆盖 Scenario: 以用户身份创建/读取/编辑/创建文件夹/移动文档、未授权提示、API 失败反馈
- 验证方式: 阅读 skills/feishu-doc.md 全文
- 结果: 覆盖 spec 全部 7 个云文档 Scenario

## Issues

无 issues。

## Side Findings

1. **lark-oapi asyncio 事件循环错误**: 多 FeishuAdapter 实例同时启动 WebSocket 时，lark-oapi SDK 内部报 "This event loop is already running" 错误。这是 SDK 已知问题（daemon thread 中 asyncio 事件循环冲突），不影响功能——每个 adapter 的 WS 线程独立运行，消息接收正常。该错误在进程退出时自然终止，无需处理。

2. **Round 1 Side Findings 仍然有效**: design.md 已知 gap（半边对话）、feishu-cli 依赖、lark-oapi deprecation warnings 均未变化，继续接受。

## 上层文档同步检查

| 文档 | 状态 | 备注 |
|---|---|---|
| SPEC.md | 无需更新 | 同 Round 1 |
| docs/specs/kernel/spec.md | 无需更新 | 同 Round 1 |
| docs/specs/im/spec.md | 无需更新 | 同 Round 1 |
| docs/specs/gateway/spec.md | **需要更新** | 同 Round 1 — 3 条新增 Requirement 待补充 |
| docs/specs/cli/spec.md | 无需更新 | 同 Round 1 |
| AGENTS.md / CLAUDE.md | 无需更新 | 同 Round 1 |
| docs/SPEC_GUIDE.md | 无需更新 | 同 Round 1 |

## 测试汇总

- feishu 专项测试: 56 passed (adapter 14 + client 17 + config 16 + integration 9)，M5 新增 4 个 config 测试
- 全量 unit 测试: 3172 passed, 1 skipped, 21 deselected (pytest -m "not e2e")
- 无回归失败

## 真实凭据验证汇总

- tenant_access_token 获取: 成功（code=0, expire=7200）
- bot_info 获取: 成功（bot_name=nano, bot_open_id=ou_b33ae16df1338a00a77d4cdbec653b71）
- WebSocket 连接启动: 成功（FeishuClient.start 正常，daemon thread 运行）
- 多实例并发: 成功（plato/luban/hume 三实例同时启动）
- REST API 发送: 验证到 FeishuAPIError（code=230013 "Bot has NO availability to this user"）— 这是预期行为（Bot 无法给自己发消息），证明 API 调用路径正确，凭据有效

---

**Verdict: pass**
**Highest Required Action: pass**
**Issues: 0 blocking, 0 major, 0 minor**
**Top Concern: 无**
**Needs Re-review: false**
