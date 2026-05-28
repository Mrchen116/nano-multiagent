# Verification Report: bugfix-380

## Summary

| 维度 | 结果 |
|---|---|
| Completeness | 5/5 tasks complete; 4/5 spec requirements covered; 1 requirement 缺 HTTP 4xx/5xx 专项测试 |
| Correctness | 5 scenarios covered; 2 scenarios 缺专项单元测试 (HTTP 4xx/5xx, 传输层) |
| Coherence | 6/6 关键决策遵守 |

No critical issues. 2 warning(s) to consider. Ready for PR (with noted improvements).

## Completeness

### Tasks: 5/5 complete

tasks.md 所有 roadpoint 标 DONE：R1/R2/R3/R4/R5 均完成，退出标准已在 progress.md 逐项核验。

### Spec Requirement 覆盖

| Requirement | 状态 |
|---|---|
| SSE error 事件变成用户可读错误气泡 | covered |
| 任何抛 ModelError 的路径都必须用户可读 | 部分 covered：SSE error / 流断有测试；HTTP 4xx/5xx / 传输层实现正确但无专项测试 |
| 失败后 LLM 上下文恢复干净 | covered（集成测试验证） |
| Coding CLI 与 IM 行为对齐 | covered |
| 不回归既有 happy path 行为 | covered |

## Correctness

| Requirement / Scenario | 实现位置 | 测试覆盖 | 状态 |
|---|---|---|---|
| 直聊 + SSE error → 错误气泡 | `anthropic/client.py:122-130` (raise ModelError on `error` event); `runtime.py:447-469` (合成 error 消息 + dispatch message_end) | `test_llm_anthropic_client_streaming.py::test_stream_response_sse_error_event_raises_model_error`; `test_provider_error_user_visible.py::test_provider_sse_error_persists_error_assistant_message` | covered |
| HTTP 4xx/5xx → 错误气泡 | `anthropic/client.py:83-90`; `openai_compat/client.py:70-77` (httpx.HTTPStatusError → ModelError) | 无专项单元测试 | ⚠️ WARNING |
| 传输层错误 → 错误气泡 | `anthropic/client.py:91-95`; `openai_compat/client.py:78-82` (httpx.HTTPError → ModelError) | 无专项单元测试 | ⚠️ WARNING |
| SSE 流中途断 / 不完整 → 错误气泡 | `anthropic/client.py:178-184`; `openai_compat/client.py:154-160` (got_terminal_event=False + 无内容 → ModelError) | `test_stream_response_incomplete_stream_raises_model_error` (两个 provider 均有) | covered |
| provider 返回非法 JSON → 静默 continue，全流非法 → 触发流断检测 | `anthropic/client.py:206-209`; `openai_compat/client.py:182-185` (`except ValueError: continue`) | 无专项测试，但全流非法 JSON 由 got_terminal_event 检测覆盖 | covered (by stream truncation detection) |
| 配额恢复后下一轮 LLM 上下文不含错误消息 | `prompting.py:98` (`_is_provider_error` filter in build_chat_messages) | `test_provider_error_not_in_next_llm_history` | covered |
| 配额恢复后失败那轮 user message 保留 | `runtime.py:311-318` (user_msg 先于错误消息写入 history) | `test_provider_error_not_in_next_llm_history` (断言 "first" 在 user_msgs) | covered |
| CLI 打印 ⚠️ 错误行 | `coding_cli/commands.py:548-553` (assistant_text 透传 + RuntimeError) | R4 已由全套 pytest 验证 (2333 passed) | covered |
| happy path 不回归 | `anthropic/client.py:291-321`; `openai_compat/client.py:180-213` | `test_stream_response_happy_path_not_affected_by_bugfix380` (两个 provider); `test_happy_path_not_broken_by_bugfix380` (集成) | covered |
| is_provider_error 消息有 1KB 截断 | `runtime.py:1403-1427` (`_PROVIDER_ERROR_MAX_CHARS = 1024`) | `test_provider_error_message_truncated_at_1kb` | covered |

## Coherence

| design 决策 | 遵守? | 代码证据 |
|---|---|---|
| 决策 1: 错误合成为 role=assistant Message，通过 message_end hook 链路传到 SSE | 是 | `runtime.py:448-469`: `_build_provider_error_message` + `_dispatch_observe("message_end", ...)` + `raise` |
| 决策 2: build_chat_messages 第一步过滤 is_provider_error | 是 | `prompting.py:98`: `tuple(m for m in history_messages if not _is_provider_error(m))` |
| 决策 3: is_provider_error 顶层 JSONL 字段 round-trip，向后兼容老 entry | 是 | 写: `runtime.py:1380-1382`; 读: `jsonl_store.py:423` + `manager.py:353` 两条路径均含 is_provider_error; 兼容: `entry.get("is_provider_error")` 不存在时不报错 |
| 决策 4: 文案格式 = `⚠️ 模型调用失败:<provider 原文>` + 1KB 截断 | 是 | `runtime.py:1420-1421`: `content = f"⚠️ 模型调用失败:{raw_text}"` |
| 决策 5: anthropic + openai_compat 都覆盖显式 error 事件 + 流提前结束 | 是 | anthropic: `client.py:122-130` (error event) + `178-184` (流断); openai_compat: `client.py:97-105` (top-level error) + `154-160` (流断) |
| 决策 6: PA observer 零改动，CLI 约 3 行修改，IM 前端零改动 | 是 | PA main.py observer 未加新分支; `commands.py:548-553` 约 4 行修改; 前端无变更 |

### 不变量核对：feat-335 流式骨架

- yield 顺序 / content block 粒度：未改变，error 分支在 `_stream_response` 的新条件里 raise，不影响既有 content_block 处理流
- controller 取消传播：不涉及
- tool 执行与 LLM 流并行：不涉及

## Issues

### CRITICAL（提 PR 前必须修）

无。

### WARNING（应该修）

**W1: HTTP 4xx/5xx 失败形态缺专项单元测试**

incident.md Requirement "任何抛 ModelError 的路径都必须用户可读" 的 HTTP 4xx/5xx 场景（Scenario: HTTP 4xx/5xx）在实现上正确（`anthropic/client.py:83-90`; `openai_compat/client.py:70-77` 通过 `httpx.HTTPStatusError` → `ModelError` 处理），但 tasks.md 退出标准要求"incident.md 全部 Scenario"覆盖，而测试文件中无对应单元测试。

建议：在 `tests/unit/test_llm_anthropic_client_streaming.py` 和 `tests/unit/test_openai_compat_client_streaming.py` 各加一条 test，使用 `httpx.MockTransport` 返回 401/429/500 响应（`httpx.Response(429, ...)`），断言 `generate()` 抛 `ModelError` 且 `details["status_code"]` 为对应值。

**W2: 传输层错误（超时 / 连接断）缺专项单元测试**

同样属于 incident.md Q4 覆盖范围，`httpx.HTTPError`（含 `ConnectError`/`TimeoutException`）已被 `anthropic/client.py:91-95` 和 `openai_compat/client.py:78-82` 捕获并包装为 `ModelError`，但无单元测试证明这条路径的 `ModelError` 文案正确传播。

建议：在两个 provider 的测试文件各加一条 test，令 `httpx.MockTransport` 的 handler 抛 `httpx.ConnectError`，断言 `generate()` 抛 `ModelError` 且 message 含 "transport error" 关键词。

### SUGGESTION（可以修）

无。
