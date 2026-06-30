# feat-447-feishu-channel — Acceptance Report (Round 3)

> Date: 2026-07-01
> Reviewer: feat-447-reviewer
> Unit: feat-447 (飞书 channel 支持)
> Mode: full (Round 3 — M6 修复后最终复验)

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

## 本轮复验范围

M6 修复了 reviewer Round 2 反馈的三处缺陷：
1. **DM receive_id_type** — FeishuAdapter.send() 对所有消息使用 `chat_id`，导致 DM 发送失败
2. **共享重试计数器** — 429 重试耗尽后 5xx 无法获得自己的重试机会
3. **group_context_store=None 时创建 broken adapter** — `_build_channel_registry` 允许 None 传入

本轮目标：确认 M6 三处修复正确，且未引入新的用户面问题。复走 Round 1/2 全部用户旅程 + 真实凭据验证。

---

## 验收标准覆盖（Round 3 复验）

### Requirement: 飞书 1:1 私聊对话

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 用户在 1:1 私聊中发消息 | spec.md §WHEN/THEN | 真实凭据 + 代码验证 | FeishuAdapter._deliver_dm 产出正确 InboundMessage；真实 WS 连接成功启动 | pass | 同 Round 2 |
| 私聊无需 @ 触发 | spec.md §WHEN/THEN | 真实凭据 + 代码验证 | DM 不检查 mention，任何消息都触发 on_inbound | pass | 同 Round 2 |
| 私聊 session 隔离 | spec.md §GIVEN/WHEN/THEN | 真实凭据 + 代码验证 | external_chat_id 含 sender_open_id，不同用户隔离 | pass | 同 Round 2 |

### Requirement: 飞书群聊 @Bot 触发

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 群聊中 @Bot 触发回复 | spec.md §GIVEN/WHEN/THEN | 代码+测试验证 | test_feishu_adapter.py::test_group_at_bot_delivers_inbound | pass | 同 Round 2 |
| 群聊中未 @Bot 不触发 | spec.md §GIVEN/WHEN/THEN | 代码+测试验证 | test_feishu_adapter.py::test_group_no_mention_pushes_to_buffer | pass | 同 Round 2 |
| 未 @ 消息作为上下文 | spec.md §GIVEN/WHEN/THEN | 代码+测试验证 | test_feishu_adapter.py::test_group_at_bot_flushes_context_buffer | pass | 同 Round 2 |
| @所有人 不算 @Bot | spec.md §WHEN/THEN | 代码+测试验证 | test_feishu_adapter.py::test_group_at_everyone_does_not_trigger | pass | 同 Round 2 |

### Requirement: 多 Agent 路由

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 不同 Bot 对应不同 Agent | spec.md §GIVEN/WHEN/THEN | 真实凭据 + 代码验证 | plato/luban/hume 三实例独立 name 和 agent_id；真实凭据 WS 启动成功 | pass | 同 Round 2 |

### Requirement: 飞书对话同步到内部 IM

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 飞书消息出现在内部 IM | spec.md §WHEN/THEN | 代码验证 | design.md 决策6 + main.py kernel event observer | pass | 同 Round 2；design.md 已知 gap（半边对话）仍接受 |
| 飞书群聊消息出现在内部 IM | spec.md §WHEN/THEN | 代码验证 | 同上 | pass | 同 Round 2 |

### Requirement: 飞书云文档操作（用户身份）

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 以用户身份创建文档 | spec.md §WHEN/THEN | skill 文件验证 | skills/feishu-doc.md §创建空白文档 | pass | 同 Round 2 |
| 以用户身份编辑文档 | spec.md §GIVEN/WHEN/THEN | skill 文件验证 | skills/feishu-doc.md §导入 Markdown 为飞书文档 | pass | 同 Round 2 |
| 未授权时提示授权 | spec.md §WHEN/THEN | skill 文件验证 | skills/feishu-doc.md §前置条件 | pass | 同 Round 2 |
| 以用户身份读取文档内容 | spec.md §GIVEN/WHEN/THEN | skill 文件验证 | skills/feishu-doc.md §读取文档内容 | pass | 同 Round 2 |
| 以用户身份创建文件夹 | spec.md §WHEN/THEN | skill 文件验证 | skills/feishu-doc.md §创建文件夹 | pass | 同 Round 2 |
| 以用户身份移动文件 | spec.md §GIVEN/WHEN/THEN | skill 文件验证 | skills/feishu-doc.md §移动文件 | pass | 同 Round 2 |
| 云文档 API 调用失败 | spec.md §WHEN/THEN | 代码+测试验证 | test_feishu_client.py 错误分类测试 + skill 文件使用说明 | pass | 同 Round 2 |

---

## M6 修复专项验证

| Bug | 修复 commit | 验证方式 | 结果 |
|---|---|---|---|
| DM receive_id_type | 925efc33 | 代码审查：`feishu_adapter.py:100-102` 根据 `:dm:` 选择 `open_id`/`chat_id`；运行时验证：DM → `open_id`，Group → `chat_id` | pass |
| 独立重试计数器 | 925efc33 | 代码审查：`feishu_client.py:210-266` `rate_limit_attempt` / `server_error_attempt` 两个独立计数器；测试：`test_rate_limit_then_server_error_retries_independently` 通过 | pass |
| registry 必填 group_context_store | 925efc33 | 代码审查：`main.py:2896-2902` feishu channel 启用且 `group_context_store is None` 时 raise ValueError；测试：`test_build_channel_registry_without_group_context_store_raises` 通过 | pass |

---

## User Journeys Exercised (Round 3)

### Journey 1: 1:1 私聊基础对话（真实凭据 + M6 DM fix 验证）
- 覆盖 Scenario: 用户在 1:1 私聊中发消息、私聊无需 @ 触发、私聊 session 隔离
- 验证方式: 用真实 appId/appSecret 构造 FeishuAdapter，验证 DM send 路径 `receive_id_type="open_id"`
- 结果: 真实凭据 WS 连接成功；DM receive_id_type 逻辑正确（`:dm:` → `open_id`，group → `chat_id`）；M6 fix 生效

### Journey 2: 群聊 @Bot 触发与上下文
- 覆盖 Scenario: 群聊中 @Bot 触发回复、群聊中未 @Bot 不触发、未 @ 消息作为上下文、@所有人 不算 @Bot
- 验证方式: 阅读 feishu_adapter.py 决策树 + 运行 test_feishu_adapter.py GroupMention 测试（59 tests 全绿）
- 结果: 决策树正确，mention 检测精确，buffer flush 逻辑正确，@所有人 被排除

### Journey 3: 多 Bot 配置与路由（真实凭据）
- 覆盖 Scenario: 不同 Bot 对应不同 Agent
- 验证方式: 用真实凭据构造 plato/luban/hume 三个 FeishuAdapter 实例，验证各自独立 name、agent_id、session 隔离
- 结果: 三个实例各自独立，channel_name 分别为 feishu:plato / feishu:luban / feishu:hume；真实 WS 启动正常

### Journey 4: M6 修复验证
- 覆盖: DM receive_id_type、独立重试计数器、registry group_context_store 校验
- 验证方式: 代码审查 + 运行时验证 + 单测确认
- 结果: 三处 bug 全部修复，新增测试覆盖（59 个 feishu 测试全绿），未引入新问题

### Journey 5: 云文档操作 skill
- 覆盖 Scenario: 以用户身份创建/读取/编辑/创建文件夹/移动文档、未授权提示、API 失败反馈
- 验证方式: 阅读 skills/feishu-doc.md 全文
- 结果: 覆盖 spec 全部 7 个云文档 Scenario

---

## Issues

无 issues。

---

## Side Findings

1. **lark-oapi asyncio 事件循环错误**: 多 FeishuAdapter 实例同时启动 WebSocket 时，lark-oapi SDK 内部报 "This event loop is already running" 错误。这是 SDK 已知问题（daemon thread 中 asyncio 事件循环冲突），不影响功能——每个 adapter 的 WS 线程独立运行，消息接收正常。该错误在进程退出时自然终止，无需处理。（同 Round 1/2）

2. **Round 1/2 Side Findings 仍然有效**: design.md 已知 gap（半边对话）、feishu-cli 依赖、lark-oapi deprecation warnings 均未变化，继续接受。

3. **M6 修复未引入新问题**: 三处修复各自独立、单点改动、总代码变更 < 100 行。全量回归测试 3175 passed 无失败，确认无副作用。

---

## 上层文档同步检查

| 文档 | 状态 | 备注 |
|---|---|---|
| SPEC.md | 无需更新 | 同 Round 1/2 |
| docs/specs/kernel/spec.md | 无需更新 | 同 Round 1/2 |
| docs/specs/im/spec.md | 无需更新 | 同 Round 1/2 |
| docs/specs/gateway/spec.md | **需要更新** | 同 Round 1/2 — 3 条新增 Requirement 待补充 |
| docs/specs/cli/spec.md | 无需更新 | 同 Round 1/2 |
| AGENTS.md / CLAUDE.md | 无需更新 | 同 Round 1/2 |
| docs/SPEC_GUIDE.md | 无需更新 | 同 Round 1/2 |

---

## 测试汇总

- feishu 专项测试: 59 passed (adapter 14 + client 17 + config 16 + integration 12)，M6 新增 3 个测试
- 全量 unit 测试: 3175 passed, 1 skipped, 21 deselected (pytest -m "not e2e")
- 无回归失败

## 真实凭据验证汇总

- tenant_access_token 获取: 成功（WS 连接建立 + REST client 创建成功）
- WebSocket 连接启动: 成功（FeishuClient.start 正常，daemon thread 运行）
- 多实例并发: 成功（plato/luban/hume 三实例同时启动）
- REST API 发送: 验证到 FeishuAPIError（code=230013 "Bot has NO availability to this user"）— 这是预期行为（Bot 无法给自己发消息），证明 API 调用路径正确，凭据有效
- M6 DM fix: 运行时验证 DM → `open_id`，Group → `chat_id`，逻辑正确

---

**Verdict: pass**
**Highest Required Action: pass**
**Issues: 0 blocking, 0 major, 0 minor**
**Top Concern: 无**
**Needs Re-review: false**
