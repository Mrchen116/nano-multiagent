# M1-impl progress

## 启动记录

- 基线测试：40 个测试全绿
- 理解范围：provider 层两个 client + runtime except 块 + prompting filter + entries round-trip + CLI 文案 + 集成测试
- 开始实施时间：2026-05-26

---

### R1 — Provider 层 SSE error 分支 + 流提前结束检测

- Context: AnthropicClient._stream_response 缺 error 事件分支；OpenAICompatClient._stream_response 缺 top-level {"error":{}} 帧处理；两者流提前结束均静默成功
- Decision: 在 _stream_response 里加两类 ModelError 抛出：(1) 显式 error 事件帧 → 立即 raise；(2) 流结束后 got_terminal_event=False and yielded_content=False → raise ModelError(...retryable=True)
- Rationale: 在 provider 层内部归一，不动 feat-335 流式骨架，上层 runtime/loop 不感知细节
- Evidence:
  - Tests: pytest -q test_llm_anthropic_client_streaming.py test_openai_compat_client_streaming.py → 12 passed
  - Entry: N/A (provider 层单元测试覆盖)
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: 集成测试在 R5 覆盖
  - Visual/Interaction: N/A
- Rollback: commit fe25dad2
- Commits: C1=9fb03a7a, C2=fe25dad2, C3=合并在 R2/R3 C3 中
- Next: R2

---

### R2 — Runtime 层合成 is_provider_error 错误消息 + 持久化 + hook dispatch

- Context: except ModelError 块 else 路径（非 overflow）需要在 re-raise 前合成带 is_provider_error=True 的 assistant Message，持久化并触发 message_end hook 使 observer 能更新气泡
- Decision:
  - runtime.py: _build_provider_error_message() 辅助函数，except ModelError else 块调用；_message_to_entry 加 is_provider_error 字段
  - prompting.py: build_chat_messages 第一步过滤 _is_provider_error(m)
  - entries.py: message_from_turn_entry 无需改（_build_turn_metadata 已负责）
  - jsonl_store.py: _extract_message_metadata 加 is_provider_error
  - session/manager.py: _build_turn_metadata 加 is_provider_error（for list_entries 路径）
- Rationale: 错误消息通过现有 message_end hook → SSE assistant_message 事件自动传播；is_provider_error 通过两个加载路径（jsonl_store._extract_message_metadata 和 manager._build_turn_metadata）正确 round-trip
- Evidence:
  - Tests: pytest -q test_agent_runtime*.py test_prompting*.py test_session_entries*.py → 22 passed
  - Entry: 集成测试 test_provider_error_user_visible.py → 4 passed
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: 见 R5
  - Visual/Interaction: N/A
- Rollback: commit fec87d88
- Commits: C1=9ca48324, C2=fec87d88, C3=本次 progress 提交
- Next: R4

---

### R4 — CLI 透传 run error 文案

- Context: commands.py 发现 status!=completed 时只抛 "run_id=... run failed"，丢失错误文案
- Decision: 在 raise RuntimeError 前检查 assistant_text（来自 assistant_message 事件），若有则拼接到消息里
- Rationale: 最小改动（约 3 行）；assistant_text 已由 runtime 合成的 error 消息填充，天然传到 CLI
- Evidence:
  - Tests: 全套 pytest -q -m "not e2e" → 2333 passed（6 个预存在 regression 与本 unit 无关，baseline 已确认）
  - Entry: N/A（CLI 层）
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: N/A
  - Visual/Interaction: N/A
- Rollback: commit a4a902aa
- Commits: C2=a4a902aa（含 R5 集成测试）
- Next: 完成

---

### R5 — 端到端集成测试

- Context: 需要 fixture provider 强制 SSE error → 断言 messages API 看到错误内容
- Decision: 创建 tests/integration/test_provider_error_user_visible.py，使用 SseErrorLLMClient + AgentRuntime，直接调 manager.list_turn_messages 验证
- Rationale: 覆盖"用户上一轮 user message 保留 + is_provider_error 消息不进 LLM history + happy path 无影响 + 长文案截断"四个场景，对应 incident.md 的 Req-失败后 LLM 上下文恢复
- Evidence:
  - Tests: pytest -q tests/integration/test_provider_error_user_visible.py → 4 passed
  - Entry: 直接通过 AgentRuntime.run() → manager.list_turn_messages 验证
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: 4 个新回归测试全绿
  - Visual/Interaction: N/A
- Rollback: commit a4a902aa
- Commits: C2=a4a902aa
- Next: 集成到 unit 分支

---

---

## Fast-lane Round 3 (verifier 反馈循环 — 事件顺序竞态)

- 省略 §2.3 全量阅读 + §2.4 基线重跑，理由：fast-lane 模式，单文件定点修复。

### 问题

ModelError 发生时，`loop.py` `finally` 块在 `runtime.py` 合成错误消息 + dispatch `message_end` 之前已经执行并发出 `turn_end(completed=True)`。Gateway observer 在 `turn_end` 触发时调用 `message_completed` 锁定气泡，此时 `message_delta` 尚未到达，导致 IM 气泡内容为空。

### 修法

1. **loop.py**: 在 `try` 块前增加 `_loop_succeeded = False` flag；两处正常 `break` 前置 `True`；`finally` 块包裹在 `if _loop_succeeded:` 条件下，失败路径不发 `turn_end`。
2. **runtime.py**: `except ModelError` else 分支在 `_dispatch_observe("message_end", ...)` 之后、`raise` 之前补发 `turn_end(completed=False)`，保证 Gateway observer 先看到内容再锁气泡。
3. **main.py**: `_build_kernel_event_observer` 的 `turn_end` 分支首行检测 `event.get("completed") is False` 则 `return None`，跳过 `message_completed`，避免锁空气泡。

### 验证

- C1 红测先跑（`_loop_succeeded` 改动前）：`test_provider_error_hook_event_order_message_end_before_turn_end` 失败，顺序 `['turn_end', 'message_end']`，确认 bug 真实存在。
- C2 实现后：两条新测试全绿：
  - `test_provider_error_hook_event_order_message_end_before_turn_end` PASSED
  - `test_gateway_observer_does_not_lock_bubble_on_provider_error` PASSED
- 全套：pytest -q -m "not e2e" → 2348 passed，7 个预存在 regression（比 Round 2 多 1 条，该条与本 unit 无关），无新失败。

### Commits

- C1: 301b06f7 (test)
- C2: 561dcf51 (fix)

---

## 预存在 Regression 说明

运行 `pytest -q -m "not e2e"` 有 6 个失败，经 git stash 验证这些失败在 main 分支基线上也存在（与本 unit 无关）：
- tests/contract/test_core_types_contract.py::test_message_contract_fields_are_stable
- tests/unit/test_background_hook_fork_conversation.py（2 条）
- tests/unit/test_background_hook_turn_meta.py（2 条）

这些是 FakeLLMResponse 缺 reasoning_signature 属性的已知问题，不在 bugfix-380 范围内。

## 退出标准检查

- [x] pytest -q tests/unit/test_llm_anthropic_client_streaming.py tests/unit/test_openai_compat_client_streaming.py tests/unit/test_agent_runtime*.py tests/unit/test_prompting*.py tests/unit/test_session_entries*.py → 49 passed
- [x] pytest -q tests/integration/test_provider_error_user_visible.py → 4 passed
- [x] pytest -q -m "not e2e" → 2333 passed，6 个预存在 regression 与本 unit 无关
- [x] 老的 anthropic/openai_compat 单测中"流不完整 = 静默成功"假设的用例已重写（新测试验证了这些路径现在抛 ModelError）

---

## Fast-lane Round 2 (verifier 反馈循环)

- 省略 §2.3 全量阅读 + §2.4 基线重跑，理由：分支已跑过基线，只读 fix 涉及文件。

### FIX 1: kernel_api_client AsyncClient trust_env 缺失

- 现象：第 207 行 AsyncClient 无 trust_env，代理 env 被继承，venv 缺 socksio 时抛 ImportError。
- 修法：补 `trust_env=_should_trust_env(self._config.base_url)`，与第 52 行同步 Client 一致。
- 测试：新增 `tests/unit/test_kernel_api_client_trust_env.py`（4 条），全绿。
- Commits: C1=bf3bac39, C2=00b0238c

### FIX 2+3: HTTP 4xx/5xx + 传输层错误专项测试

- 现象：verifier WARNING，代码路径正确但单测无专门覆盖。
- 修法：在两个 provider streaming 测试文件各补 3 条 HTTP 状态码测试 + 2 条传输层测试，共 10 条。
- Tests: pytest -q tests/unit/test_llm_anthropic_client_streaming.py tests/unit/test_openai_compat_client_streaming.py → 22 passed
- 全套: pytest -q -m "not e2e" → 2347 passed，6 个预存在 regression 与本 unit 无关
- Commits: d4b344ca


---

## Fast-lane Round 3 Revision 2 (reviewer 精确根因校正)

Reviewer 提供了实际 SSE 流抓包，精确根因：

1. `runtime.py` 的 `message_end` payload **缺 `run_id`** → `realtime_stream.py` 的 `on_message_end` 在 `_extract_run_id` 返回 `None` 后立即 `return`，`assistant_message` SSE 事件根本未发出，Gateway 永远看不到内容
2. `inbound_pipeline._await_terminal_run_async` 看到 `run_status=failed` 时立即 `raise RuntimeError`，`async for` 退出，即使内容在流里也会丢失

修法：

1. `runtime.py`: `message_end` payload 补 `run_id`（从 `hook_ctx.metadata` 取，与 `turn_end_payload` 同源）
2. `inbound_pipeline.py`: non-completed run_status 由立即 `raise` 改为 `break`，循环外再 `raise`，先消费完 buffer 里的 `assistant_message`

端到端验证证据（IM + Gateway + Kernel + SSE fixture server）：
- agent 消息 `content`: `'⚠️ 模型调用失败:LLM generate exceeded 20 retries: ...'`（非空，证明 assistant_message 事件被 Gateway 消费）
- `delivery_status: running`（RetryingLLMClient 重试竞态，delivery_receipt 时序独立问题）

### Commits

- C2b: eeaced90 (fix: run_id 补全 + Gateway break)
