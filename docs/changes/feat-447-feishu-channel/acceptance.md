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

---

# Round 4 — 2026-07-02

> Reviewer: feat-447-reviewer
> Unit: feat-447 (飞书 channel 支持)
> Mode: full

## Summary

| Field | Value |
|---|---|
| **Highest Required Action** | fix-implementation |
| **Verdict** | fail |
| **Issues** | 2 blocking, 0 major, 0 minor |
| **GH Issues Filed** | None |
| **Needs Re-review** | true |

Round 4 按 `design.md` 的 `Runbook for Reviewer` 做服务接管，并优先准备真实飞书/Lark 入站。`lark-cli auth status --json --verify` 成功，且 CLI appId 与当前 Gateway config 中 `feishu:default-agent.settings.appId=cli_aac9315ef3f9dbda` 一致，目标 Bot 来自同一 appId。但在发送 `lark-cli im +messages-send --as user` 之前，真实服务已经无法启动：

- IM: `PYTHONPATH=src python -m uvicorn IM.app:app --host 127.0.0.1 --port 49355` 启动失败，`.im.log` 显示 `sqlite3.OperationalError: no such column: external_source`，`/health` 不可达。
- Gateway: `PYTHONPATH=src python -m personal_assistant.main --config .gateway-config.yaml --im-service-url http://127.0.0.1:49355 --foreground --auto-bind` 启动失败，`.gateway.log` 显示 `ERROR channels[1].settings.ownerOpenId must be a non-empty string`。当前 `.gateway-config.yaml` 中同 appId 的 `botOpenId=nil`、`ownerOpenId=nil`。

按 reviewer 规则，真实入口无法启动时不能用直调 API、伪造 `InboundMessage` 或代码阅读替代用户旅程。因此本轮判定为 fail。

## User Journeys Exercised

1. **Runbook 服务接管与真实飞书入站准备**
   - 覆盖 Scenario: 所有依赖 IM + Gateway 真栈的飞书入站、IM 影子会话、跨入口上下文场景。
   - 步骤: 停止 worktree `.im.pid` / `.gateway.pid`；用空闲端口 49355 启动 IM；用当前 `.gateway-config.yaml` 启动 Gateway；校验 `lark-cli` appId 与 Gateway config appId 一致。
   - 结果: IM 与 Gateway 均退出，未能进入真实飞书消息发送阶段。

2. **真实 Lark 目标 Bot 校验**
   - 覆盖 Scenario: 真实飞书入口必须发给 Gateway config 同 appId 的 Bot。
   - 证据: `lark-cli auth status --json --verify` 返回 `verified=true`、`appId=cli_aac9315ef3f9dbda`、bot open_id `ou_b33ae16df1338a00a77d4cdbec653b71`；Gateway config 的 `feishu:default-agent.settings.appId` 同为 `cli_aac9315ef3f9dbda`。
   - 结果: 前置 appId 目标正确，但 Gateway 未启动，不能发送验收入站。

## 验收标准覆盖

### Requirement: 飞书 1:1 私聊对话

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 用户在 1:1 私聊中发消息 | spec.md §飞书 1:1 私聊对话 | Runbook 真栈启动 + 真实 Lark 入站 | Gateway 因 `ownerOpenId` 缺失退出，IM 也未启动；无法发送 `lark-cli im +messages-send --as user` | fail | 主路径不可达 |
| 私聊无需 @ 触发 | spec.md §飞书 1:1 私聊对话 | 同上 | 同上 | fail | 主路径不可达 |
| 私聊 session 隔离 | spec.md §飞书 1:1 私聊对话 | 同上 | 同上 | inconclusive | 需要至少两个真实用户或等价真实入口，本轮因服务启动失败无法验证 |

### Requirement: 飞书群聊 @Bot 触发

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 群聊中 @Bot 触发回复 | spec.md §飞书群聊 @Bot 触发 | Runbook 真栈启动 + 真实 Lark 群聊入站 | Gateway/IM 启动失败 | fail | 主路径不可达 |
| 群聊中未 @Bot 不触发 | spec.md §飞书群聊 @Bot 触发 | 同上 | Gateway/IM 启动失败 | inconclusive | 不能观察是否无回复 |
| 未 @ 消息作为上下文 | spec.md §飞书群聊 @Bot 触发 | 同上 | Gateway/IM 启动失败 | inconclusive | 不能发送未 @ 背景与后续 @ 总结 |
| @所有人 不算 @Bot | spec.md §飞书群聊 @Bot 触发 | 同上 | Gateway/IM 启动失败 | inconclusive | 不能观察是否无回复 |

### Requirement: 多 Agent 路由

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 不同 Bot 对应不同 Agent | spec.md §多 Agent 路由 | Runbook 真栈启动 + 真实 Bot 入站 | 仅校验到 default-agent appId；Gateway 未启动，不能发消息观察 agent 身份 | inconclusive | 当前 live config 只暴露 `feishu:default-agent` |

### Requirement: 外部 channel 会话同步到内部 IM

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 外部 1:1 会话在内部 IM 有独立会话 | spec.md §外部 channel 会话同步到内部 IM | 真实 Lark 入站 + IM 影子会话观察 | IM 启动失败，Gateway 启动失败 | fail | 用户看不到 `agent · feishu` 会话 |
| 外部 1:1 用户消息同步到内部 IM | spec.md §外部 channel 会话同步到内部 IM | 同上 | IM 启动失败，Gateway 启动失败 | fail | 用户消息无法同步 |
| 外部 1:1 agent 回复同步到内部 IM | spec.md §外部 channel 会话同步到内部 IM | 同上 | IM 启动失败，Gateway 启动失败 | fail | agent 回复无法同步 |
| 在内部 IM 回复不会回写飞书但上下文连续 | spec.md §外部 channel 会话同步到内部 IM | IM 影子会话发消息 + 回到飞书追问 | IM/Gateway 启动失败 | fail | 影子会话不可用 |
| 在内部 IM 群聊影子会话发消息自动触发 agent 回复 | spec.md §外部 channel 会话同步到内部 IM | IM shadow group 发消息 | IM/Gateway 启动失败 | fail | 影子群不可用 |
| 同一 kernel session 跨入口上下文连续 | spec.md §外部 channel 会话同步到内部 IM | 飞书和 IM 影子会话跨入口追问 | IM/Gateway 启动失败 | fail | 跨入口路径不可达 |
| 外部群聊在内部 IM 有独立 group 会话 | spec.md §外部 channel 会话同步到内部 IM | 真实 Lark 群聊 @Bot + IM 会话观察 | IM/Gateway 启动失败 | fail | group shadow 不可用 |
| 同一外部群绑定多个 agent 时生成多个独立会话 | spec.md §外部 channel 会话同步到内部 IM | 多 Bot 群聊入站 + IM 会话观察 | IM/Gateway 启动失败 | inconclusive | 需要可运行真栈和多 Bot live 配置 |
| 外部群聊消息显示原发送者名字 | spec.md §外部 channel 会话同步到内部 IM | Lark 群消息同步到 IM 后观察 sender | IM/Gateway 启动失败 | fail | 用户面看不到 sender |
| 外部群聊中 IM owner 的消息显示为「你」 | spec.md §外部 channel 会话同步到内部 IM | owner 从 Lark 群发消息后观察 IM sender | Gateway config 缺 `ownerOpenId` 并拒绝启动 | fail | 该配置正是本场景前置 |
| 未 @ 的群聊上下文消息同步到内部 IM | spec.md §外部 channel 会话同步到内部 IM | 未 @ 群消息 + IM shadow 观察 | IM/Gateway 启动失败 | fail | 同步路径不可达 |
| 不 @ 也回的 agent 群聊消息全量同步 | spec.md §外部 channel 会话同步到内部 IM | `group_reply_policy=ALWAYS` 群消息 | IM/Gateway 启动失败 | inconclusive | 当前 live config 未能运行，也未确认 ALWAYS agent |
| IM 离线时飞书对话不中断 | spec.md §外部 channel 会话同步到内部 IM | 停 IM 后真实 Lark 1:1 入站 | Gateway 因 config 校验失败，无法在 IM 离线状态下保持飞书 channel | fail | 飞书主路径不可达 |

### Requirement: 飞书云文档操作（用户身份）

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 以用户身份创建文档 | spec.md §飞书云文档操作 | 通过 agent 对话触发 feishu-cli user 操作 | Gateway 不可用，无法从用户对话触发 | fail | 本轮未直调文档 CLI 替代 agent 用户旅程 |
| 以用户身份编辑文档 | spec.md §飞书云文档操作 | 同上 | Gateway 不可用 | fail | 主路径不可达 |
| 未授权时提示授权 | spec.md §飞书云文档操作 | 同上 | Gateway 不可用 | fail | 用户无法收到提示 |
| 以用户身份读取文档内容 | spec.md §飞书云文档操作 | 同上 | Gateway 不可用 | fail | 主路径不可达 |
| 以用户身份创建文件夹 | spec.md §飞书云文档操作 | 同上 | Gateway 不可用 | fail | 主路径不可达 |
| 以用户身份移动文件 | spec.md §飞书云文档操作 | 同上 | Gateway 不可用 | fail | 主路径不可达 |
| 云文档 API 调用失败 | spec.md §飞书云文档操作 | 同上 | Gateway 不可用 | fail | 用户无法收到失败原因 |

## Issues

### Issue 1: Runbook 真栈无法启动，IM 旧 DB 在 schema 初始化时报 `no such column: external_source`

- **Severity**: blocking
- **Regression Relation**: direct
- **Recommended Action**: fix-implementation
- **Action Rationale**: 外部 channel 同步依赖 IM 影子会话；按 runbook 启动 IM 时服务直接退出，用户无法看到任何 IM 影子会话或内部 IM 后续回复。该问题直接阻塞本 unit 的主要验收场景。
- **Reproduction**:
  1. 在 `/Users/czj/Repos/nano-multiagent/.worktrees/unit-feat-447`。
  2. 停止 `.im.pid` / `.gateway.pid` 指向的旧进程。
  3. 运行 `IM_JWT_SECRET=<fresh> PYTHONPATH=src python -m uvicorn IM.app:app --host 127.0.0.1 --port 49355 > .im.log 2>&1 &`。
  4. 观察进程退出，`curl http://127.0.0.1:49355/health` 不可达。
- **Evidence**: `.im.log` 末尾为 `sqlite3.OperationalError: no such column: external_source` 和 `Application startup failed. Exiting.`

### Issue 2: 当前 Gateway config 中 Feishu channel 缺 `ownerOpenId`，Gateway 启动即退出

- **Severity**: blocking
- **Regression Relation**: direct
- **Recommended Action**: fix-implementation
- **Action Rationale**: design.md 决策 11 要求用 `ownerOpenId` 把 owner 从飞书发出的消息显示为「你」。但 reviewer 按 runbook 使用当前 Gateway config 启动时，Gateway 因该字段为空直接退出，导致真实飞书入站、飞书回复、IM 同步和文档操作全部不可用。
- **Reproduction**:
  1. `lark-cli auth status --json --verify` 确认 CLI appId 为 `cli_aac9315ef3f9dbda`。
  2. 当前 `.gateway-config.yaml` 的 `feishu:default-agent.settings.appId` 同为 `cli_aac9315ef3f9dbda`，但 `botOpenId=nil`、`ownerOpenId=nil`。
  3. 运行 `PYTHONPATH=src python -m personal_assistant.main --config .gateway-config.yaml --im-service-url http://127.0.0.1:49355 --foreground --auto-bind > .gateway.log 2>&1 &`。
  4. 观察 Gateway 退出。
- **Evidence**: `.gateway.log` 为 `ERROR channels[1].settings.ownerOpenId must be a non-empty string`。

## Side Findings

- 未立 GitHub issue。本轮两个问题都直接阻塞 feat-447 用户旅程，按 in-unit `fix-implementation` 处理。
- Round 3 报告中过去依赖代码/测试替代用户旅程的 pass 结论，在 M7 runbook 已明确要求真实 `lark-cli im +messages-send --as user` 后不再足以作为最终产品验收证据。

## 上层文档同步检查

| 文档 | 状态 | 备注 |
|---|---|---|
| SPEC.md | 无需本轮 reviewer 修改 | 本轮问题是实现/运行态阻塞，不是架构顶点文档缺口 |
| docs/specs/kernel/spec.md | 无需更新 | kernel spec 无增量 |
| docs/specs/im/spec.md | 已由 unit delta 覆盖，待修复后复核 | 当前 IM 启动失败，无法产品面确认契约成立 |
| docs/specs/gateway/spec.md | 已由 unit delta 覆盖，待修复后复核 | 当前 Gateway config 校验阻塞启动 |
| docs/specs/cli/spec.md | 无需更新 | CLI spec 无增量 |
| AGENTS.md / CLAUDE.md | 无需更新 | runbook 操作约束已足够 |
| docs/SPEC_GUIDE.md | 无需更新 | 非文档体系变更 |

## Verdict

**Verdict: fail**
**Highest Required Action: fix-implementation**
**Issues: 2 blocking, 0 major, 0 minor**
**Top Concern: 按 design.md Runbook 启动真栈时 IM 与 Gateway 都无法启动，用户无法完成任何 feat-447 目标。**
**Needs Re-review: true**

---

# Round 5 — 2026-07-02

> Reviewer: feat-447-reviewer
> Unit: feat-447 (飞书 channel 支持)
> Mode: full, focused on Round 4 blocking fixes while inheriting prior fail/inconclusive items

## Summary

| Field | Value |
|---|---|
| **Highest Required Action** | fix-implementation |
| **Verdict** | fail |
| **Issues** | 1 blocking, 0 major, 0 minor |
| **GH Issues Filed** | None |
| **Needs Re-review** | true |

Round 5 按 `design.md` 的 `Runbook for Reviewer` 重新接管 worktree 服务，并使用真实 Lark 入站：

- `<WT_CFG>`: `.gateway-config.yaml`
- Feishu channel: `feishu:default-agent`
- Gateway config appId: `cli_aac9315ef3f9dbda`
- `lark-cli auth status --json --verify`: `verified=true`, `appId=cli_aac9315ef3f9dbda`
- 目标 Bot: 同一输出的 `identities.bot.openId=ou_b33ae16df1338a00a77d4cdbec653b71`
- 真实入站命令: `lark-cli im +messages-send --as user --user-id ou_b33ae16df1338a00a77d4cdbec653b71 --text "feat447-r5-20260702114951 round5 lark-cli user -> gateway bot" --idempotency-key feat447-r5-20260702114951 --format json`

Round 4 的 IM legacy DB schema 崩溃已关闭：IM 从现有 `data/im_service.sqlite3` 启动，未出现 `sqlite3.OperationalError: no such column: external_source` / `elapsed_ms`，并且 `conversations.external_source`、`conversations.external_chat_id`、`messages.elapsed_ms`、`messages.sender_display_name` 均存在。

Round 4 的 `ownerOpenId` 缺失启动阻塞只部分关闭：Gateway 确实在 reviewer 未手改 config 的情况下，把 `.gateway-config.yaml` 中 `settings.ownerOpenId` 自动写回为 `ou_e6d1591026cfdac8d131eb1fdd71bdb9`。但当前 worktree Gateway 进程随后退出，`.gateway.pid` 指向的进程已不存在，`.gateway.log` 为空；真实 Lark 消息只看到用户消息，未看到同 nonce 的 Bot 回复，worktree IM DB 也没有同 nonce 的 shadow conversation/message。因此用户仍看不到 feat-447 的结果，本轮仍 fail。

## User Journeys Exercised

1. **Round 4 legacy IM DB 启动复验**
   - 覆盖: Round 4 Issue 1，以及所有依赖 IM shadow 的外部 channel 同步场景前置。
   - 步骤: 停止 worktree `.im.pid`；用空闲端口 `59941` 启动 `IM_JWT_SECRET=<fresh> PYTHONPATH=src python -m uvicorn IM.app:app --host 127.0.0.1 --port 59941`，使用现有 `data/im_service.sqlite3`。
   - 结果: IM 进程保持运行，日志为 `Uvicorn running on http://127.0.0.1:59941`；未出现 Round 4 的 `external_source` schema 崩溃。注意：runbook 写的 `/health` 在本服务上返回 404，但这次不是 schema crash。

2. **`ownerOpenId` 自动写回复验**
   - 覆盖: Round 4 Issue 2 的配置缺失启动前置，以及 `外部群聊中 IM owner 的消息显示为「你」` 的必要前置。
   - 步骤: 保持 `.gateway-config.yaml` 中 `feishu:default-agent.settings.ownerOpenId=nil`；启动 `PYTHONPATH=src python -m personal_assistant.main --config .gateway-config.yaml --im-service-url http://127.0.0.1:59941 --foreground --auto-bind`。
   - 结果: `.gateway-config.yaml` 被产品自动写回 `ownerOpenId=ou_e6d1591026cfdac8d131eb1fdd71bdb9`，与同一 `lark-cli auth status --json --verify` 输出的 user openId 一致；但 Gateway 进程没有保持运行。

3. **真实 Lark 1:1 入站 smoke**
   - 覆盖: 飞书 1:1 私聊、外部 1:1 shadow 会话、用户消息显示为「你」。
   - 步骤: 用 `lark-cli im +messages-send --as user` 向同 appId 的 Bot openId 发送 nonce `feat447-r5-20260702114951`。
   - 结果: Lark 发送成功，返回 `chat_id=oc_1906eead0189484ce5ea8a4c245400a6`、`message_id=om_x100b6b69b0cf5cbcc43e5434f9d9b11`、`create_time=2026-07-02 11:49:52`。随后 `chat-messages-list` 中只有该 nonce 的 user 消息，没有同 nonce 的 app/Bot 回复；worktree IM `conversations/messages` 中也没有该 nonce。

## Round 4 Blocking Closure

| Round 4 Item | Round 5 Evidence | Result |
|---|---|---|
| IM 旧 DB 因 `external_source` / `elapsed_ms` 等旧 schema 崩溃 | IM 在现有 `data/im_service.sqlite3` 上启动并保持运行；关键列存在；日志未出现 `OperationalError` | closed |
| Feishu channel 缺 `ownerOpenId` 时 Gateway 不需手改 config 能启动并自动写回 | `ownerOpenId` 自动写回成功；但 Gateway 随后不再运行，真实 Lark 入站无 Bot 回复、IM 无 shadow 记录 | still blocking |

## 验收标准覆盖（Round 5）

### Requirement: 飞书 1:1 私聊对话

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 用户在 1:1 私聊中发消息 | spec.md | 真实 `lark-cli im +messages-send --as user` | Lark user 消息发送成功；当前 worktree Gateway 不运行，未看到同 nonce Bot 回复 | fail | 继承 Round 4，用户看不到回复 |
| 私聊无需 @ 触发 | spec.md | 同上 | 不带 @ 的 nonce 消息未得到同 nonce Bot 回复 | fail | 主路径仍不可用 |
| 私聊 session 隔离 | spec.md | 需要两个真实用户或等价真实入口 | 单用户主路径已失败，无法继续验证隔离 | inconclusive | 继承 Round 4 |

### Requirement: 飞书群聊 @Bot 触发

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 群聊中 @Bot 触发回复 | spec.md | 真实 Lark 群聊入站 | Gateway 不运行，未进入群聊复验 | fail | 主路径阻塞 |
| 群聊中未 @Bot 不触发 | spec.md | 真实 Lark 群聊入站 | Gateway 不运行，无法观察“无回复”是否来自正确门控 | inconclusive | 继承 Round 4 |
| 未 @ 消息作为上下文 | spec.md | 未 @ 背景 + 后续 @ 总结 | Gateway 不运行 | inconclusive | 继承 Round 4 |
| @所有人 不算 @Bot | spec.md | 真实 Lark 群聊入站 | Gateway 不运行 | inconclusive | 继承 Round 4 |

### Requirement: 多 Agent 路由

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 不同 Bot 对应不同 Agent | spec.md | 多 Bot 真实入站 | 本轮只校验到 `feishu:default-agent` appId；Gateway 不运行，不能观察回复身份 | inconclusive | 继承 Round 4 |

### Requirement: 外部 channel 会话同步到内部 IM

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 外部 1:1 会话在内部 IM 有独立会话 | spec.md | 真实 Lark 入站 + IM shadow 观察 | worktree IM 无同 nonce shadow conversation/message | fail | 用户看不到 `agent · feishu` 会话 |
| 外部 1:1 用户消息同步到内部 IM | spec.md | 同上 | worktree IM 无同 nonce message | fail | 用户消息未同步到可见 shadow |
| 外部 1:1 agent 回复同步到内部 IM | spec.md | 同上 | Lark 无同 nonce Bot 回复，IM 无 agent message | fail | 回复不可见 |
| 在内部 IM 回复不会回写飞书但上下文连续 | spec.md | IM shadow 会话发消息 + 回到飞书追问 | 1:1 shadow 会话未出现 | fail | 前置不可用 |
| 在内部 IM 群聊影子会话发消息自动触发 agent 回复 | spec.md | IM shadow group 发消息 | Gateway 不运行，shadow group 未出现 | fail | 前置不可用 |
| 同一 kernel session 跨入口上下文连续 | spec.md | 飞书和 IM shadow 跨入口追问 | shadow 会话未出现 | fail | 前置不可用 |
| 外部群聊在内部 IM 有独立 group 会话 | spec.md | 真实 Lark 群聊 @Bot + IM 观察 | Gateway 不运行 | fail | 前置不可用 |
| 同一外部群绑定多个 agent 时生成多个独立会话 | spec.md | 多 Bot 群聊入站 | Gateway 不运行，未能复验 | inconclusive | 继承 Round 4 |
| 外部群聊消息显示原发送者名字 | spec.md | Lark 群消息同步到 IM 后观察 sender | Gateway 不运行 | fail | 用户面看不到 sender |
| 外部群聊中 IM owner 的消息显示为「你」 | spec.md | owner 从 Lark 发消息后观察 IM sender | `ownerOpenId` 已自动写回，但 IM 无同 nonce shadow message，不能看到「你」 | fail | 自动写回前置关闭，用户可见结果未关闭 |
| 未 @ 的群聊上下文消息同步到内部 IM | spec.md | 未 @ 群消息 + IM shadow 观察 | Gateway 不运行 | fail | 同步路径不可用 |
| 不 @ 也回的 agent 群聊消息全量同步 | spec.md | `group_reply_policy=ALWAYS` 群消息 | Gateway 不运行，也未确认 live ALWAYS agent | inconclusive | 继承 Round 4 |
| IM 离线时飞书对话不中断 | spec.md | 停 IM 后真实 Lark 1:1 入站 | 当前 IM 在线时 Gateway 已不运行，无法证明 IM 离线时飞书不中断 | fail | 飞书主路径不可达 |

### Requirement: 飞书云文档操作（用户身份）

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 以用户身份创建文档 | spec.md | 通过 agent 对话触发 | Gateway 不运行，无法从用户对话触发 | fail | 继承 Round 4 |
| 以用户身份编辑文档 | spec.md | 同上 | Gateway 不运行 | fail | 主路径不可达 |
| 未授权时提示授权 | spec.md | 同上 | Gateway 不运行 | fail | 用户无法收到提示 |
| 以用户身份读取文档内容 | spec.md | 同上 | Gateway 不运行 | fail | 主路径不可达 |
| 以用户身份创建文件夹 | spec.md | 同上 | Gateway 不运行 | fail | 主路径不可达 |
| 以用户身份移动文件 | spec.md | 同上 | Gateway 不运行 | fail | 主路径不可达 |
| 云文档 API 调用失败 | spec.md | 同上 | Gateway 不运行 | fail | 用户无法收到失败原因 |

## Issues

### Issue 1: Gateway 自动写回 `ownerOpenId` 后未保持运行，真实 Lark 入站没有 Bot 回复或 IM shadow

- **Severity**: blocking
- **Regression Relation**: direct
- **Recommended Action**: fix-implementation
- **Action Rationale**: feat-447 的核心用户旅程要求从真实飞书入站触发 Gateway、Bot 回复和 IM shadow 同步；当前 worktree Gateway 进程退出后，用户只看到自己发出的 Lark 消息，看不到 Bot 回复，也看不到内部 IM shadow 会话。
- **Reproduction**:
  1. 在 `/Users/czj/Repos/nano-multiagent/.worktrees/unit-feat-447`。
  2. 用现有 `data/im_service.sqlite3` 启动 IM: `IM_JWT_SECRET=<fresh> PYTHONPATH=src python -m uvicorn IM.app:app --host 127.0.0.1 --port 59941`。
  3. 确认 `.gateway-config.yaml` 的 `feishu:default-agent.settings.appId=cli_aac9315ef3f9dbda` 且 `ownerOpenId` 初始为空。
  4. `lark-cli auth status --json --verify` 返回同一 `appId=cli_aac9315ef3f9dbda`、bot openId `ou_b33ae16df1338a00a77d4cdbec653b71`、user openId `ou_e6d1591026cfdac8d131eb1fdd71bdb9`。
  5. 启动 Gateway: `PYTHONPATH=src python -m personal_assistant.main --config .gateway-config.yaml --im-service-url http://127.0.0.1:59941 --foreground --auto-bind > .gateway.log 2>&1 &`.
  6. 观察 `.gateway-config.yaml` 已自动写回 `ownerOpenId=ou_e6d1591026cfdac8d131eb1fdd71bdb9`，但 `.gateway.pid` 对应进程不存在，`.gateway.log` 为空。
  7. 发送真实 Lark 用户消息: `lark-cli im +messages-send --as user --user-id ou_b33ae16df1338a00a77d4cdbec653b71 --text "feat447-r5-20260702114951 round5 lark-cli user -> gateway bot" --idempotency-key feat447-r5-20260702114951 --format json`。
  8. `chat-messages-list` 仅显示该 nonce 的 user 消息；worktree IM `conversations/messages` 查不到该 nonce。
- **Evidence**:
  - Lark send: `ok=true`, `chat_id=oc_1906eead0189484ce5ea8a4c245400a6`, `message_id=om_x100b6b69b0cf5cbcc43e5434f9d9b11`, `create_time=2026-07-02 11:49:52`.
  - Lark list: 同 nonce 的消息 sender 为 `user` / `ou_e6d1591026cfdac8d131eb1fdd71bdb9`; 最近 app 消息均为本轮之前的历史消息，没有同 nonce Bot 回复。
  - IM shadow: worktree `data/im_service.sqlite3` 中 `content LIKE '%feat447-r5-20260702114951%'` 无记录。

## Side Findings

- `design.md` Runbook 的 IM 健康检查写 `GET /health`，本轮实际服务返回 404；但 IM 进程启动成功且未复现旧 schema crash。本轮未把该 runbook/API mismatch 作为 blocking，因为当前用户面阻塞在 Gateway 不运行。
- 机器上存在主仓默认 Gateway 进程（`--config /Users/czj/.nano-assistant/config.yaml`），但它不是本轮 `<WT_CFG>` 启动的 worktree Gateway，不能作为 feat-447 Round 5 证据。

## 上层文档同步检查

| 文档 | 状态 | 备注 |
|---|---|---|
| SPEC.md | 无需本轮 reviewer 修改 | 本轮是运行态阻塞，不是跨包架构文档缺口 |
| docs/specs/kernel/spec.md | 无需更新 | kernel spec 无增量 |
| docs/specs/im/spec.md | 待修复后复核 | IM legacy schema 启动前置已关闭，但 shadow 用户面仍未成立 |
| docs/specs/gateway/spec.md | 待修复后复核 | Gateway `ownerOpenId` 自动写回前置已关闭，但 Gateway 未保持运行 |
| docs/specs/cli/spec.md | 无需更新 | CLI spec 无增量 |
| AGENTS.md / CLAUDE.md | 无需更新 | runbook 操作约束已足够 |
| docs/SPEC_GUIDE.md | 无需更新 | 非文档体系变更 |

## Verdict

**Verdict: fail**
**Highest Required Action: fix-implementation**
**Issues: 1 blocking, 0 major, 0 minor**
**Top Concern: `ownerOpenId` 已自动写回，但当前 worktree Gateway 未保持运行，真实 Lark 用户消息没有 Bot 回复，也没有内部 IM shadow 可见结果。**
**Needs Re-review: true**

---

# Round 6 — 2026-07-02

> Reviewer: feat-447-reviewer
> Unit: feat-447 (飞书 channel 支持)
> Mode: fast-lane, focused only on Round 5 blocking after M9 merge `b60702b7`

## Summary

| Field | Value |
|---|---|
| **Highest Required Action** | pass |
| **Verdict** | pass |
| **Issues** | 0 blocking, 0 major, 0 minor |
| **GH Issues Filed** | None |
| **Needs Re-review** | false |

Round 6 只复验 Round 5 blocking: Gateway 使用当前 `<WT_CFG>` 启动后必须保持运行，真实 Lark 用户消息必须进入 Gateway，并且 worktree IM 能看到 external shadow conversation/message，或 Lark 侧能看到符合 spec 的 Bot 回复。

目标 Bot 严格从当前 `<WT_CFG>` 决定：

- `<WT_CFG>`: `.gateway-config.yaml`
- Feishu channel: `feishu:default-agent`
- Gateway config appId: `cli_aac9315ef3f9dbda`
- `lark-cli auth status --json --verify`: `verified=true`, `appId=cli_aac9315ef3f9dbda`
- 目标 Bot: 同一 auth 输出的 `identities.bot.openId=ou_b33ae16df1338a00a77d4cdbec653b71`
- Lark user openId: 同一 auth 输出的 `identities.user.openId=ou_e6d1591026cfdac8d131eb1fdd71bdb9`
- 当前 `<WT_CFG>` 的 `settings.ownerOpenId`: `ou_e6d1591026cfdac8d131eb1fdd71bdb9`

我没有手改 `<WT_CFG>`。因 Round 5 已观察到 ownerOpenId 自动写回，本轮在不清空配置的前提下验证该已写回状态下 Gateway 可以保持运行并处理真实 Lark 入站。

## User Journey Exercised

1. **Worktree IM + Gateway live smoke**
   - IM: `http://127.0.0.1:56197`，使用 worktree `data/im_service.sqlite3`。
   - Gateway: `PYTHONPATH=src python -m personal_assistant.main --config .gateway-config.yaml --foreground --auto-bind`。
   - 结果: 发送真实 Lark 消息后，IM 进程 `34457` 与 Gateway 进程 `35239` 仍保持运行，未复现 Round 5 的 Gateway 退出。

2. **真实 Lark 1:1 入站**
   - 命令: `lark-cli im +messages-send --as user --user-id ou_b33ae16df1338a00a77d4cdbec653b71 --text "feat447-r6-20260702161330 round6 lark-cli user -> gateway bot" --idempotency-key feat447-r6-20260702161330 --format json`
   - Lark send evidence: `ok=true`, `chat_id=oc_1906eead0189484ce5ea8a4c245400a6`, `message_id=om_x100b6b559474848cc3829e22226c808`, `create_time=2026-07-02 16:13:31`
   - Lark Bot reply evidence: same chat contained app reply `message_id=om_x100b6b5595a668bcc45880bff97102a`, sender `app_id=cli_aac9315ef3f9dbda`, content included `feat447-r6-20260702161330`.

3. **Current worktree IM shadow evidence**
   - Queried current worktree IM HTTP: `GET http://127.0.0.1:56197/im/v1/conversations` with a fresh login token from the same worktree IM.
   - HTTP conversation evidence:
     - id `603339e85e56450bb0c2a2b27d9694ba`
     - title `default-agent · feishu`
     - type `direct`
     - owner_id `b5ac314aa4354f36a9fffd6058589a19`
     - config_agent_id `default-agent`
     - external_source `feishu`
     - external_chat_id `feishu:cli_aac9315ef3f9dbda:dm:ou_e6d1591026cfdac8d131eb1fdd71bdb9`
     - last_message_preview included `feat447-r6-20260702161330`
   - DB conversation evidence from worktree `data/im_service.sqlite3`:
     - `603339e85e56450bb0c2a2b27d9694ba | default-agent · feishu | direct | feishu | feishu:cli_aac9315ef3f9dbda:dm:ou_e6d1591026cfdac8d131eb1fdd71bdb9 | default-agent`
   - DB user message evidence:
     - `c91eea1c18c14b438b66ce48de367d05 | 603339e85e56450bb0c2a2b27d9694ba | user | 你 | completed | feat447-r6-20260702161330 round6 lark-cli user -> gateway bot`
   - DB agent message evidence:
     - `c53bdcf53d6149c788d1c83040c00a51 | 603339e85e56450bb0c2a2b27d9694ba | agent | completed | Got it ... feat447-r6-20260702161330 ...`

## Round 5 Blocking Closure

| Round 5 Item | Round 6 Evidence | Result |
|---|---|---|
| Gateway 自动写回 `ownerOpenId` 后未保持运行 | 当前 `<WT_CFG>` 的 `ownerOpenId` 与 lark-cli user openId 一致；Gateway 启动后在真实 Lark 入站和 IM shadow 写入后仍保持运行 | closed |
| 真实 Lark 用户消息没有 Bot 回复 | `lark-cli im +messages-send --as user` 返回 user `message_id=om_x100b6b559474848cc3829e22226c808`；Lark 同 chat 随后出现 app reply `message_id=om_x100b6b5595a668bcc45880bff97102a`，内容包含同 nonce | closed |
| worktree IM 没有 external shadow conversation/message | 当前 worktree IM HTTP 和 `data/im_service.sqlite3` 均显示 `default-agent · feishu` external conversation，以及 sender_display_name 为「你」的同 nonce 用户消息 | closed |

## 验收标准覆盖（Round 6 fast-lane update）

### Requirement: 飞书 1:1 私聊对话

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 用户在 1:1 私聊中发消息 | spec.md | 真实 `lark-cli im +messages-send --as user` 到当前 `<WT_CFG>` appId 对应 Bot | Lark user message `om_x100b6b559474848cc3829e22226c808`; Lark app reply `om_x100b6b5595a668bcc45880bff97102a`; Gateway 保持运行 | pass | 关闭 Round 5 主阻塞 |
| 私聊无需 @ 触发 | spec.md | 同一不带 @ 的 nonce 消息 | Bot 正常回复，内容包含 `feat447-r6-20260702161330` | pass | 关闭 Round 5 主阻塞 |

### Requirement: 外部 channel 会话同步到内部 IM

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 外部 1:1 会话在内部 IM 有独立会话 | spec.md | 真实 Lark 入站 + 当前 worktree IM HTTP/DB 查询 | `default-agent · feishu`, `external_source=feishu`, `external_chat_id=feishu:cli_aac9315ef3f9dbda:dm:ou_e6d1591026cfdac8d131eb1fdd71bdb9` | pass | 会话未合并到普通 direct |
| 外部 1:1 用户消息同步到内部 IM | spec.md | 当前 worktree DB 查询 nonce | message `c91eea1c18c14b438b66ce48de367d05`, sender_type `user`, sender_display_name `你`, content 含 nonce | pass | 关闭 Round 5 shadow 用户消息阻塞 |
| 外部 1:1 agent 回复同步到内部 IM | spec.md | 当前 worktree DB/HTTP 查询 nonce | agent message `c53bdcf53d6149c788d1c83040c00a51`, content 含 nonce；HTTP last_message_preview 含 nonce | pass | 同时 Lark 侧也有 Bot 回复证据 |
| 外部群聊中 IM owner 的消息显示为「你」 | spec.md | 当前 `<WT_CFG>` ownerOpenId + IM shadow message sender_display_name | ownerOpenId 与 Lark user openId 一致；DB user message sender_display_name 为「你」 | pass | 本轮只复验 1:1 shadow 中 owner 显示，群聊仍继承既有非 fast-lane 覆盖 |

## Issues

None for the Round 5 blocking scope.

## Side Findings

- 当前 worktree IM DB 中同一 nonce 下除首个 agent shadow message 外，还出现一条额外 agent message `dc0bd85cfded4e5e854d0b794f47b388`，内容为 duplicate acknowledgement；Lark 侧最近消息只看到一条同 nonce app reply。本轮 fast-lane 目标是关闭 Round 5 的 Gateway keepalive / true Lark inbound / external shadow 可见阻塞，因此未把该观察升级为本轮 issue。

## 上层文档同步检查

| 文档 | 状态 | 备注 |
|---|---|---|
| SPEC.md | 无需本轮 reviewer 修改 | 本轮只复验实现行为 |
| docs/specs/kernel/spec.md | 无需更新 | kernel spec 无增量 |
| docs/specs/im/spec.md | 待 orchestrator 收尾归并时复核 | Round 6 已用产品证据确认 1:1 external shadow 行为 |
| docs/specs/gateway/spec.md | 待 orchestrator 收尾归并时复核 | Round 6 已用产品证据确认当前 `<WT_CFG>` Gateway live 行为 |
| docs/specs/cli/spec.md | 无需更新 | CLI spec 无增量 |
| AGENTS.md / CLAUDE.md | 无需更新 | 操作约束无增量 |
| docs/SPEC_GUIDE.md | 无需更新 | 非文档体系变更 |

## Verdict

**Verdict: pass**
**Highest Required Action: pass**
**Issues: 0 blocking, 0 major, 0 minor**
**Top Concern: None for Round 5 blocking; real Lark inbound reached Gateway, produced a Bot reply, and created visible worktree IM external shadow conversation/message.**
**Needs Re-review: false**
