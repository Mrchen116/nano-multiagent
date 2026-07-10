# Round 1 — 2026-05-26

## Meta

| 字段 | 值 |
|---|---|
| unit_id | bugfix-380 |
| review_round | 1 |
| reviewer | reviewer-r1 |
| verdict | **fail** |
| Highest Required Action | **fix-implementation** |

## 验收标准覆盖

### Requirement: SSE error 事件必须变成用户可读错误气泡

#### Scenario: 直聊 + provider 配额耗尽

| 字段 | 内容 |
|---|---|
| 期望来源 | incident.md §验收标准 Req-SSE |
| 验证方式 | 集成测试 `test_provider_sse_error_persists_error_assistant_message` + Gateway→IM 端到端路径验证 |
| 证据 | 集成测试 pass；Gateway→IM 端到端路径（清除 SOCKS 代理后）结果：user 消息 `delivery_status=failed`（正确）；agent 消息 `delivery_status=completed, content=''`（错误，应为 `failed + "⚠️ 模型调用失败:..."` 内容） |
| 结果 | **fail** |
| 备注 | 核心 kernel 层链路（SSE error → ModelError → runtime 合成 assistant 消息 → 持久化 → hook dispatch）已由集成测试验证通过。但 Gateway→IM 端到端路径存在 bug：`loop.py` 的 `finally` 块无条件发送 `turn_end`，导致 Gateway 的 `kernel_event_observer` 在 error assistant message 到达之前就发送了 `message_completed(final_content=None)`，IM 把 agent 消息设为 `completed + empty`。之后的 `assistant_message(⚠️ 模型调用失败:...)` 发送的 `message_delta` 无法更新已 `completed` 的消息。见 Issue #2。 |

#### Scenario: 群聊 + 仅其中一个 agent 上游故障

| 字段 | 内容 |
|---|---|
| 期望来源 | incident.md §验收标准 Req-SSE |
| 验证方式 | 未完成（依赖直聊路径先修复） |
| 证据 | N/A |
| 结果 | **inconclusive** |
| 备注 | 群聊场景依赖直聊路径的 Gateway→IM 错误气泡正确渲染，当前直聊路径有 Issue #2，故群聊场景不做单独验证。 |

### Requirement: 任何抛 ModelError 的路径都必须用户可读

#### Scenario: HTTP 4xx/5xx

| 字段 | 内容 |
|---|---|
| 期望来源 | incident.md §验收标准 Req-ModelError |
| 验证方式 | 集成测试（SseErrorLLMClient 模拟等效 ModelError）；provider 单元测试 `test_stream_response_sse_error_event_raises_model_error` |
| 证据 | 12 个 provider 单元测试全绿；集成测试 4 个全绿 |
| 结果 | **pass** |
| 备注 | HTTP 4xx/5xx 已有 `raise_for_status` 路径抛 ModelError，runtime 层统一处理。kernel 层修复完整，但 Gateway→IM 路径受 Issue #2 影响（`turn_end` in finally 覆盖 error 内容）。 |

#### Scenario: 传输层错误（超时 / 连接断 / DNS / SSL）

| 字段 | 内容 |
|---|---|
| 期望来源 | incident.md §验收标准 Req-ModelError |
| 验证方式 | Gateway→IM 实际触发（real Anthropic API 20次重试后超时，`anthropic: stream ended without terminal event`） |
| 证据 | gateway.log: `RuntimeError: LLM generate exceeded 20 retries: anthropic: stream ended without terminal event`；IM: user 消息 `delivery_status=failed`；agent 消息 `delivery_status=completed, content=''`（受 Issue #2 影响） |
| 结果 | **fail** |
| 备注 | kernel 层正确抛 ModelError 并合成 error 消息（集成测试验证），但 Gateway→IM 路径因 Issue #2 仍显示 `completed + empty`。 |

#### Scenario: SSE 流中途断开 / 不完整

| 字段 | 内容 |
|---|---|
| 期望来源 | incident.md §验收标准 Req-ModelError |
| 验证方式 | provider 单元测试 `test_stream_response_incomplete_stream_raises_model_error`（anthropic + openai_compat 各一条） |
| 证据 | 12 个 provider 单元测试全绿 |
| 结果 | **pass** |
| 备注 | 断流路径现在抛 ModelError，不再静默成功。kernel 层修复完整，Gateway→IM 路径受 Issue #2 影响。 |

#### Scenario: provider 返回非法 JSON

| 字段 | 内容 |
|---|---|
| 期望来源 | incident.md §验收标准 Req-ModelError |
| 验证方式 | provider 单元测试覆盖（非法 JSON 行被 `_iter_sse_events` 处理） |
| 证据 | provider 单元测试全绿 |
| 结果 | **pass** |
| 备注 | 非法 JSON 行进入 `except` 路径，不再静默 continue。 |

### Requirement: 失败后 LLM 上下文恢复必须干净

#### Scenario: 配额恢复后用户重新发消息

| 字段 | 内容 |
|---|---|
| 期望来源 | incident.md §验收标准 Req-恢复 |
| 验证方式 | 集成测试 `test_provider_error_not_in_next_llm_history` |
| 证据 | 测试验证：第二轮 LLM history 不含 `is_provider_error` 消息（无 `⚠️` 内容），但第一轮 user message `"first"` 保留 |
| 结果 | **pass** |
| 备注 | `build_chat_messages` 的 `_is_provider_error` filter 正确过滤。 |

### Requirement: Coding CLI 与 IM 行为对齐

#### Scenario: CLI 端遇到同类上游故障

| 字段 | 内容 |
|---|---|
| 期望来源 | incident.md §验收标准 Req-CLI |
| 验证方式 | 未完成（依赖 Gateway→IM 路径先修复后补测） |
| 证据 | N/A |
| 结果 | **inconclusive** |
| 备注 | commands.py 的 run error 透传改动（R4）已在 M1 progress.md 记录，源码层改动存在。CLI 路径是否正确展示 `⚠️` 前缀需环境隔离后补充验证。 |

### Requirement: 不回归既有 happy path 行为

#### Scenario: 上游正常时

| 字段 | 内容 |
|---|---|
| 期望来源 | incident.md §验收标准 Req-不回归 |
| 验证方式 | 集成测试 `test_happy_path_not_broken_by_bugfix380`；全套非 e2e 测试 `pytest -q -m "not e2e"` |
| 证据 | 集成测试 pass；全套 2333 passed，6 个预存在 regression（已在 M1 progress.md 说明，与本 unit 无关） |
| 结果 | **pass** |
| 备注 | happy path assistant 消息不产生 `is_provider_error` 字段；全套测试无新 regression。 |

---

## User Journeys Exercised

| 旅程 | 覆盖 Scenario |
|---|---|
| J1: 集成测试直接路径（SseErrorLLMClient → AgentRuntime） | SSE error → 错误消息持久化；history 过滤；happy path；长文案截断 |
| J2: Gateway→IM 端到端路径（清除 SOCKS 代理后，real Anthropic API 20次重试超时） | user 消息 `delivery_status=failed` 正确；agent 消息 `completed + empty`（Issue #2） |
| J3: 全套单元测试 | provider 层 SSE error / 断流 / 非法 JSON 全路径；prompting filter；session entries round-trip |

---

## Issues

### Issue #1 — major: Gateway→IM 端到端路径 agent 气泡显示 `completed + empty` 而非 `failed + ⚠️`

- **Severity**: major
- **Recommended Action**: fix-implementation
- **Action Rationale**: 端到端路径（清除所有 SOCKS 代理变量后重测）仍然出现 agent 消息 `delivery_status=completed, content=''`，而期望是 `delivery_status=failed, content="⚠️ 模型调用失败:..."`。根本原因定位：

  **根因**：`loop.py` 的 `_execute_loop` 在 `finally` 块中无条件发送 `turn_end` 事件（无论 try 中是否有异常）。Gateway 的 `kernel_event_observer` 收到 `turn_end` 后立即向 IM 发送 `message_completed(final_content=None)`，IM 把 agent 消息设为 `completed + empty`（此时 error assistant message 还没到达）。之后 `runtime.py` except 块合成的 error message 通过 `message_end` hook 发出 `assistant_message` 事件，Gateway 发送 `message_delta`，但 IM 对已经 `completed` 的消息的 delta 更新静默忽略，导致 error 内容永远不显示。

  **修复方向**：选一：在 `loop.py` 的 `finally` 中检查是否有未处理异常，若有则跳过 `turn_end`（或推迟到 runtime except 块处理完 error message 后再发）。选二：Gateway 的 `kernel_event_observer` 在 `run_status=failed` 时发送 `message_completed(content=error_text)` 而不是等 `turn_end`；需要 kernel 在 `run_status=failed` 事件中携带 error content。

  证据：gateway.log 中确认 `RuntimeError: LLM generate exceeded 20 retries`；IM 消息 API 返回 `delivery_status=completed, content=''`（不是 `failed, "⚠️ ..."`）。

### Issue #2 — minor: 全套测试 6 个预存在 regression（与本 unit 无关）

- **Severity**: minor
- **Recommended Action**: no-action（已知问题，不属于本 unit）
- **Action Rationale**: `FakeLLMResponse` 缺 `reasoning_signature` 属性导致的测试失败，已在 M1 progress.md 说明，早于 bugfix-380。

---

## Side Findings

- Gateway→IM 端到端测试时，user 消息的 `delivery_status` 正确更新为 `failed`（`node.delivery_receipt(failed)` 路径正常），说明 Gateway 的 `_emit_relay_lifecycle(phase="failed")` 和 `_relay_lifecycle_callback` 工作正常。仅 agent 消息状态（`turn_end` 先于 error message 到达）不正确。
- `loop.py` 的 `finally` 发送 `turn_end` 是已知设计选择（保证 Gateway 不因 `run_status=failed` 后的 SSE 流 hang 住），但与 bugfix-380 的 "runtime except 块合成 error message 后 raise" 的顺序冲突，导致 Gateway 侧 race condition。
- Refs #52 (out-of-unit: Gateway→kernel HTTP failure raw exception text in IM bubble)

---

## 上层文档同步检查

| 文档 | 状态 |
|---|---|
| `SPEC.md` | 无需更新，bugfix 不改架构 |
| `docs/内核设计SPEC.md` | 无需更新，`is_provider_error` 是内部元数据，不影响公共契约 |
| `AGENTS.md` / `CLAUDE.md` | 无需更新 |
| `docs/CodingCLI-SPEC.md` | 无需更新，CLI 错误输出属于内部改进 |
| `docs/NodeGateway-SPEC.md` | 无需更新 |

---

## 澄清记录

无需澄清，验收标准清晰。Issue #1 是 fix-implementation 范围内的代码 bug，不需要 spec/design 层确认。

---

# Round 2 — 2026-05-26

## Meta

| 字段 | 值 |
|---|---|
| unit_id | bugfix-380 |
| review_round | 2 |
| reviewer | reviewer-r1 |
| verdict | **fail** |
| Highest Required Action | **fix-implementation** |
| Fast-lane commits reviewed | 8d1c31c7 (trust_env fix), 2c60253e (unit tests) |

## 复验范围

基于 round 1 根因定位，验证 fast-lane fix 1（`trust_env`）是否解决了端到端路径的 `completed + empty` 问题。

## 复验结果

### trust_env fix 有效性

`trust_env` fix（8d1c31c7）正确：`kernel_api_client.py` 第 207 行 `AsyncClient` 补传 `trust_env=_should_trust_env(self._config.base_url)`，localhost 不再继承系统代理。这修复了 round 1 报告的 Issue #1（SOCKS proxy ImportError 导致 Gateway→Kernel 通信失败）。

### 端到端路径复验

环境：新端口（IM=59196, API=59197），未 unset 系统代理，Gateway 启动后 trust_env 自动忽略 localhost 代理。

**测试结果**：agent 消息仍然 `delivery_status=completed, content=''`（与 round 1 相同）。

**直接证据**（kernel SSE 流逐帧捕获）：

```
1. run_status=running
2. turn_end        ← loop.py finally 块，LLM 20次重试尚未完成时就发出
3. run_status=failed ← LLM 超时
```

**`assistant_message` 事件完全缺失**：`runtime.py` except ModelError 块合成的错误消息通过 `message_end` hook 触发的 `assistant_message` 事件，在 `run_status=failed` 之后才发出，但 Gateway 的 `_await_terminal_run_async` 在 `run_status=failed` 时已经 `raise RuntimeError`，退出了 `async for` 循环，错误消息事件永远不会被接收。

**根因确认**：`trust_env` fix 只解决了代理干扰问题，未解决"事件顺序错误"的核心 bug：

1. `loop.py` 的 `finally` 块在 LLM 重试完成之前就发送 `turn_end`（等等——这不对，`turn_end` 在 `finally` 里，但 LLM 重试 20 次是在 `_execute_loop` 的 try 块里，所以 `turn_end` 是在 `_execute_loop` 退出 finally 时发的，此时 ModelError 已经抛出）
2. `runtime.py` except 块合成 error message 并触发 `message_end` hook（`assistant_message` 事件）在 `run_status=failed` 之后发出
3. Gateway 在 `run_status=failed` 时已退出 SSE 监听循环，无法接收后续 `assistant_message`

**修复方向**（供 worker 参考）：

选一（推荐）：`runtime.py` except ModelError 块中，在 `raise` 之前先等待 `message_end` hook 完成，**然后**发出 `run_status=failed`，确保 Gateway 在退出 SSE 循环前能接收到 `assistant_message` 事件。这需要 kernel registry 的 `run_status=failed` 在 `runtime.py` 的 `raise` 之后异步触发。

选二：Gateway `_await_terminal_run_async` 在收到 `run_status=failed` 时，不立即 raise，而是继续读几帧 SSE 直到 `assistant_message` 事件到达或超时，然后再 raise。

选三（Gateway observer）：`kernel_event_observer` 在收到 `run_status=failed` 时，检查 `run_context_store` 里的 error content（需要 kernel 在 `run_status=failed` 事件中携带 error_content 字段），发送 `message_completed(content=error_content, delivery_status=failed)`。

## 验收标准覆盖（增量）

| Scenario | Round 1 | Round 2 | 备注 |
|---|---|---|---|
| 直聊 + SSE error（Gateway→IM 路径） | fail | **fail** | trust_env fix 不解决事件顺序 bug |
| 核心链路（集成测试） | pass | pass | 不受影响 |
| delivery_status=failed（用户消息） | pass | pass | `_relay_lifecycle_callback` 路径正常 |

## 结论

Fast-lane fix 1（trust_env）正确且必要，但不足以解决 round 1 发现的根本 bug。需要 round 3 实施"事件顺序修复"后再做 round 3 复验。

---

# Round 3 — 2026-05-26

## Meta

| 字段 | 值 |
|---|---|
| unit_id | bugfix-380 |
| review_round | 3 |
| reviewer | reviewer-r1 |
| verdict | **fail** |
| Highest Required Action | **fix-implementation** |
| Fast-lane commits reviewed | 561dcf51 (loop + runtime + observer round 3 fix) |

## 复验范围

验证 round 3 fix（commit 561dcf51）是否解决了 round 1/2 报告的"事件顺序"bug：  
1. `assistant_message` 事件是否出现在 SSE 流中（不再被 `turn_end` 抢先）  
2. IM agent 气泡内容是否包含 `⚠️ 模型调用失败:` + provider 原文  
3. IM agent 气泡 `delivery_status` 是否为 `failed`  
4. IM agent 气泡是否挂在正确 agent 名下

## 测试环境

- IM: port 52296, Kernel API: port 52297, Fixture SSE error server: port 52399  
- Fixture server 返回 `{"type":"error","error":{"type":"overloaded_error","message":"Overloaded: provider is unavailable"}}`（`retryable=False` 路径）  
- Gateway: worktree venv（`.venv/bin/python3`），config 指向 worktree local，无 SOCKS 代理  
- Kernel SSE 流直接捕获（curl）

## Kernel SSE 流捕获（直接发消息到 kernel API）

```
id: 7
event: assistant_message
data: {"event":"assistant_message","run_id":"run_51204b8097e130c0","turn_id":"turn_efae19417af664f2","message_id":"msg_b6d51c5d541efda2","content":"⚠️ 模型调用失败:anthropic: Overloaded: provider is unavailable","metadata":{},"session_id":"sess_43fd2da841b65349"}

id: 8
event: turn_end
data: {"event":"turn_end","run_id":"run_51204b8097e130c0","turn_id":"turn_efae19417af664f2","completed":false,"stop_reason":null,"session_id":"sess_43fd2da841b65349"}

id: 9
event: run_status
data: {"event":"run_status","run_id":"run_51204b8097e130c0","status":"failed",...}
```

**事件顺序修复完整**：`assistant_message` → `turn_end(completed=False)` → `run_status=failed`，与 round 1/2 的顺序（turn_end → run_status=failed，无 assistant_message）相比有根本改善。

## IM relay 端到端测试结果

| 断言 | 期望 | 实测 | 结果 |
|---|---|---|---|
| (a) agent 气泡内容包含 `⚠️ 模型调用失败:` + provider 原文 | `⚠️ 模型调用失败:anthropic: ...` | `⚠️ 模型调用失败:anthropic: Overloaded: provider is unavailable` | **PASS** |
| (b) agent 气泡 `delivery_status=failed` | `failed` | `running` | **FAIL** |
| (c) agent 气泡挂在 agent 名下 | `sender.type=agent, sender.id=default-agent` | `sender.type=agent, sender.id=default-agent` | **PASS** |

## 根因分析（Round 3 残余 bug）

Round 3 fix 解决了事件顺序问题，但引入了新的 bug：

**症状**：IM agent 气泡的 `delivery_status` 卡在 `running`，而非 `failed`。

**原因**：

1. `turn_end(completed=False)` 被 Gateway `kernel_event_observer` 处理时，跳过了 `message_completed`（round 3 fix 的设计意图，防止空内容覆盖）
2. 但 IM agent 气泡的 `delivery_status` 从 `running` 变为 `failed` 依赖于两个路径之一：
   - `message_completed` → `on_message_completed` → `delivery_status=completed`（round 3 跳过了）  
   - 或 IM 端直接通过某个 `delivery_status=failed` 机制更新 agent 气泡
3. `_relay_lifecycle_callback(phase=failed)` 发送的 `node.delivery_receipt(failed)` 更新的是**用户消息**（relay_task_id 对应用户消息），不更新 agent 气泡
4. 结果：agent 气泡永远停在 `running`，没有最终化

**修复方向**（供 fix-worker 参考）：

选一（最小改动）：在 `turn_end(completed=False)` 路径下，发送 `message_completed` 但不带 `final_content`，仅用于触发 agent 气泡状态最终化。IM 端 `on_message_completed` 需要接受可选的 `delivery_status` 参数（`failed`），或者 Gateway 在 `turn_end(completed=False)` 后单独发一个 `delivery_status=failed` 的 update frame。

选二：在 `_relay_lifecycle_callback(phase=failed)` 时，同时发送一个 `node.streaming_delta(kind=message_completed, delivery_status=failed, message_id=<agent_msg_id>)`，需要 run_context_store 里保留 agent message_id 以供查询。

选三（IM 端）：IM 的 relay watchdog 对所有 `delivery_status=running` 的 agent 消息超时后自动标记为 `failed`（已有 watchdog，但超时可能太长）。

## 验收标准覆盖（增量）

| Scenario | Round 1 | Round 2 | Round 3 | 备注 |
|---|---|---|---|---|
| 直聊 + SSE error，气泡内容 | fail | fail | **pass** | `⚠️ 模型调用失败:` + provider 原文正确 |
| 直聊 + SSE error，delivery_status=failed | fail | fail | **fail** | agent 气泡卡在 running |
| 直聊 + SSE error，挂在 agent 名下 | pass | pass | **pass** | sender.type=agent 正确 |
| 事件顺序（assistant_message 在 turn_end 之前） | fail | fail | **pass** | 顺序修复 |
| 核心链路（集成测试） | pass | pass | pass | 不受影响 |
| delivery_status=failed（用户消息） | pass | pass | pass | _relay_lifecycle_callback 路径正常 |

## 结论

Round 3 fix 解决了事件顺序问题（Scenario a 和 c 通过），但 agent 气泡 `delivery_status` 仍卡在 `running` 而非 `failed`（Scenario b fail）。需要 round 4 fast-lane 修复后复验。
