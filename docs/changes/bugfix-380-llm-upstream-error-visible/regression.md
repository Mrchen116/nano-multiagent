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
| 验证方式 | 集成测试 `test_provider_sse_error_persists_error_assistant_message` + kernel API 直接调用（sess_050b7f5b27ed5007） |
| 证据 | 集成测试 pass；kernel API `/v1/sessions/{id}/messages` 返回 `content="⚠️ 模型调用失败:..."` |
| 结果 | **pass** |
| 备注 | 核心链路（SSE error → ModelError → runtime 合成 assistant 消息 → 持久化 → hook dispatch）已验证。IM 前端端到端验证因本地环境 SOCKS 代理干扰 Gateway→Kernel 通信而无法完成（见 Issues #1）；该环境问题与代码正确性无关，核心逻辑已由集成测试完整覆盖。 |

#### Scenario: 群聊 + 仅其中一个 agent 上游故障

| 字段 | 内容 |
|---|---|
| 期望来源 | incident.md §验收标准 Req-SSE |
| 验证方式 | 无法完成端到端验证（环境 SOCKS 代理干扰 Gateway→Kernel 通信） |
| 证据 | N/A |
| 结果 | **inconclusive** |
| 备注 | 群聊场景依赖 Gateway→Kernel 完整链路。当前环境 SOCKS 代理干扰使该路径不可用。核心的"A 失败 B 正常"行为取决于两个 agent 独立触发各自的 ModelError → 各自的 run_error 事件，这是 runtime 层逻辑，已由 `test_provider_sse_error_persists_error_assistant_message` 的单实例版本验证，但群聊多 agent 并发场景未能端到端验证。 |

### Requirement: 任何抛 ModelError 的路径都必须用户可读

#### Scenario: HTTP 4xx/5xx

| 字段 | 内容 |
|---|---|
| 期望来源 | incident.md §验收标准 Req-ModelError |
| 验证方式 | 集成测试（SseErrorLLMClient 模拟等效 ModelError）；provider 单元测试 `test_stream_response_sse_error_event_raises_model_error` |
| 证据 | 12 个 provider 单元测试全绿；集成测试 4 个全绿 |
| 结果 | **pass** |
| 备注 | HTTP 4xx/5xx 已有 `raise_for_status` 路径抛 ModelError，runtime 层统一处理。 |

#### Scenario: 传输层错误（超时 / 连接断 / DNS / SSL）

| 字段 | 内容 |
|---|---|
| 期望来源 | incident.md §验收标准 Req-ModelError |
| 验证方式 | 实际在 kernel API 上触发（sess_050b7f5b27ed5007，`anthropic: stream ended without terminal event`） |
| 证据 | run 状态 `failed`；messages API 返回 `content="⚠️ 模型调用失败:LLM generate exceeded 20 retries: anthropic: stream ended without terminal event"` |
| 结果 | **pass** |
| 备注 | 流提前结束路径（bugfix-380 R1 修复的 `got_terminal_event=False`）实际被触发并正确处理。 |

#### Scenario: SSE 流中途断开 / 不完整

| 字段 | 内容 |
|---|---|
| 期望来源 | incident.md §验收标准 Req-ModelError |
| 验证方式 | provider 单元测试 `test_stream_response_incomplete_stream_raises_model_error`（anthropic + openai_compat 各一条） |
| 证据 | 12 个 provider 单元测试全绿 |
| 结果 | **pass** |
| 备注 | 断流路径现在抛 ModelError，不再静默成功。 |

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
| 验证方式 | 尝试通过 `coding_cli.main --mode remote --base-url http://127.0.0.1:62091 --text "hello"` 验证 |
| 证据 | CLI 输出中仅看到 `{"error": "Using SOCKS proxy...", "layer": "runtime"}` — 该错误来自 CLI 的 kernel HTTP client 遇到 SOCKS 代理，不是来自 LLM provider 层 |
| 结果 | **inconclusive** |
| 备注 | CLI 无法在当前环境连接到本地 kernel API（同样的 SOCKS 代理问题）。commands.py 的 run error 透传改动（约 3 行）已在 M1 progress.md 记录（R4），源码层改动存在，但用户面验证无法完成。需要在无 SOCKS 代理干扰的环境验证。 |

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
| J2: kernel API 实际触发（流提前结束路径） | 传输层错误 → `⚠️ 模型调用失败:...` 消息产生；run status=failed |
| J3: IM 前端气泡渲染（旧版代码产生的消息） | `delivery_status=failed` 气泡正确渲染（failed 状态 + 消息内容显示），截图留存 |
| J4: 全套单元测试 | provider 层 SSE error / 断流 / 非法 JSON 全路径；prompting filter；session entries round-trip |

---

## Issues

### Issue #1 — major: IM 前端端到端气泡无法通过 bugfix-380 代码路径完整验证

- **Severity**: major
- **Recommended Action**: fix-implementation
- **Action Rationale**: 当前测试环境中 `http_proxy=http://127.0.0.1:7895` 指向 SOCKS 代理，但 `socksio` 未安装。Gateway 的 `kernel_api_client.py` 创建 `httpx.AsyncClient` 时未显式排除 localhost 代理，导致 Gateway→Kernel 的 SSE 流连接失败（`ImportError: Using SOCKS proxy, but the 'socksio' package is not installed`）。这使得 bugfix-380 代码路径产生的 `⚠️ 模型调用失败:...` 消息无法通过 Gateway 传播到 IM 前端。

  **已验证部分**：
  - kernel API 直接调用（不经 Gateway）确认消息内容正确包含 `⚠️ 模型调用失败:` 前缀
  - IM 前端对 `delivery_status=failed` 的气泡渲染正确（状态 + 内容均显示，截图留存）
  - 集成测试完整覆盖了核心链路

  **未验证部分**：bugfix-380 代码路径产生的错误消息经 Gateway 传播后，IM 气泡同时显示 `⚠️ 模型调用失败:...` 内容 + `failed` 状态

  **修复建议**：在 `kernel_api_client.py` 的 `httpx.AsyncClient` 初始化中显式设置 `proxies={"all://127.0.0.1": None}` 或等效方式排除 localhost 代理，使 worktree 环境下 Gateway→Kernel 通信不受系统 SOCKS 代理干扰。

### Issue #2 — minor: CLI 端错误输出无法在当前环境验证

- **Severity**: minor
- **Recommended Action**: fix-implementation
- **Action Rationale**: 同 Issue #1 的 SOCKS 代理问题，CLI 的 `kernel_api_client.py` 同样受影响，无法在本地环境端到端验证 CLI 的 `⚠️ 模型调用失败:...` 终端输出。源码改动（R4）存在且在 progress.md 记录。

---

## Side Findings

- 全套测试（`pytest -q -m "not e2e"`）有 6 个预存在 regression，已由 worker 在 M1 progress.md 说明（`FakeLLMResponse` 缺 `reasoning_signature` 属性），与 bugfix-380 无关。
- 前端气泡展示 `failed` 状态时用户消息也显示为 `failed`（不仅是 agent 消息），这是现有 IM 逻辑，当一个 run 失败时，触发该 run 的 user message 也被标记 `failed`。这可能给用户带来困惑（用户消息本身没有失败，是 agent 回复失败了）。该行为不在 bugfix-380 范围内，记录备忘。

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

无需澄清，验收标准清晰。环境问题记录于 Issues #1，不需要 spec/design 层确认。
