# M1-impl tasks

## 目标

打通"任何 provider 上游故障 → ModelError → 持久化带 is_provider_error=true 的 assistant 消息 → 用户在 IM/CLI 看到可读错误气泡"不变式，覆盖 incident.md 全部 Scenario。

## 退出标准

- `pytest -q tests/unit/test_llm_anthropic_client_streaming.py tests/unit/test_openai_compat_client_streaming.py tests/unit/test_agent_runtime*.py tests/unit/test_prompting*.py tests/unit/test_session_entries*.py` 全绿
- `pytest -q tests/integration/test_provider_error_user_visible.py` 全绿（端到端 fixture provider 强制 SSE error → IM messages API 看到错误内容且 delivery_status=failed）
- `pytest -q -m "not e2e"` 全绿（无 regression）
- 老的 anthropic/openai_compat 单测中"流不完整 = 静默成功"假设的用例已重写
- reviewer 可覆盖 incident.md 全部 Scenario

## 测试策略

**任务类型**：后端 API bugfix，优先端到端入口测试。

**测试层次**：
1. **单元测试**（provider 层）：对 AnthropicClient / OpenAICompatClient 的 _stream_response，mock httpx 响应，覆盖：SSE error 事件、流提前结束(无 message_stop/finish_reason)、非法 JSON、HTTP 4xx5xx
2. **单元测试**（runtime/prompting/entries 层）：runtime except ModelError 块合成消息、_message_to_entry round-trip is_provider_error、build_chat_messages filter 过滤掉 is_provider_error 消息
3. **集成测试**（端到端）：fixture LLM provider 强制返回 SSE error → 断言 IM messages API 既能看到错误内容，delivery_status=failed

**用户路径分类**：`bug-regression`（必须补 regression case）

## UI 状态矩阵

N/A（纯后端修复，无前端变更）

## Roadpoints

| ID | 标题 | 状态 |
|---|---|---|
| R1 | Provider 层: anthropic/openai_compat SSE error 分支 + 流提前结束 | DONE |
| R2 | Runtime 层: except ModelError 合成可视错误消息 + 持久化 + hook dispatch | DONE |
| R3 | Prompting + Entries: is_provider_error filter + round-trip | DONE |
| R4 | CLI: 透传 run error 文案 | DONE |
| R5 | 集成测试: 端到端 fixture provider → IM messages 断言 | DONE |
