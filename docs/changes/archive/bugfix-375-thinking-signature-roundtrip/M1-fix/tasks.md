# bugfix-375-M1: thinking 块 signature round-trip

## 目标

修复 thinking 块的 signature 在 anthropic provider 中被丢弃，导致 mapper 出站写空签名，
上游每轮把同一段 reasoning 重放，开 thinking 的 agent 在真实多轮工具任务下死循环 / 不收敛。

## 退出标准

1. `_apply_anthropic_delta` 处理 `signature_delta`，把真实 signature 累积进 thinking 块
2. `LLMMessage` 新增 `reasoning_signature: str | None = None` 字段
3. `anthropic/client.py` 的 `content_block_stop` 把真实 signature 传进 `_anthropic_block_to_llm_message`
4. `anthropic/mapper.py` 出站时把真实 signature 写回 thinking 块（不再硬编码 `""`）
5. `loop.py` 的 `_append_llm_message` 合并逻辑保留 `reasoning_signature`
6. contract 测试同步更新 LLMMessage 字段列表
7. 单测全绿
8. e2e：在 IM 给开 thinking 的 agent（kimi K2.6）发 deep-bug-finding prompt，agent 多轮推理后收敛给出答案；LLM proxy 日志无 `invalid_request_error`、`reasoning_content` 不再每轮逐字节重复

## 测试策略

- C1：在现有 `test_llm_anthropic_client_streaming.py` 中新增 test，模拟带 `signature_delta` 的 SSE 流，断言 `reasoning_signature` 被正确解析。在 `test_llm_anthropic_mapper.py` 中更新已有 test，断言 thinking 块出站时 signature 为真实值（非空串）。确认 contract test 因新字段而红。
- C2：最小实现让所有测试绿，包括 contract 更新。
- C3：回填 fix.md 修复段 + progress.md，然后 e2e 验证。

## Roadpoints

| ID | 标题 | 状态 |
|----|------|------|
| R1 | 新增 signature_delta 解析 + reasoning_signature 字段 + 更新 contract | DONE |
| R2 | mapper 出站用真实 signature；loop 合并保留 reasoning_signature | DONE |
| R3 | e2e 验证 + fix.md 回填 | DONE |
