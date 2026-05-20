# bugfix-375-M1 progress

## R1 + R2 — signature 全链路 round-trip（interfaces / client / mapper / loop）

- Context: thinking 块的 cryptographic signature 经 `signature_delta` SSE 事件下发，但 `_apply_anthropic_delta` 不处理该 delta_type → signature 在源头丢失。`LLMMessage` 无字段存 signature，mapper 出站时硬写 `signature: ""`，上游每轮把同一段 reasoning 重放 → 多轮死循环（bugfix-375）。
- Decision: 四处最小改动构成完整 round-trip 链路：① `interfaces.py` 新增 `reasoning_signature` 字段；② `client.py:_apply_anthropic_delta` 累积 `signature_delta`，`_stream_response` 提取 `turn_signature` 并传入 `_anthropic_block_to_llm_message`；③ `mapper.py` 出站时写 `message.reasoning_signature or ""`；④ `loop.py:_append_llm_message` 合并时保留 `reasoning_signature`（对称 `reasoning_content` 的处理）。
- Rationale: 保持与 bugfix-373 完全对称的修复路径，所有 signature 相关字段命名与 `reasoning_content` 平行。loop 调用处也同步传 `reasoning_signature=llm_msg.reasoning_signature` 确保历史不丢签名。
- Evidence:
  - Tests: `pytest tests/unit/test_llm_anthropic_client_streaming.py tests/unit/test_llm_anthropic_mapper.py tests/contract/test_llm_interfaces_contract.py tests/unit/test_agent_loop.py -q` → 37 passed
  - Entry: 见 R3 e2e
  - Frontend State Matrix: N/A（后端修复）
  - Browser QA: N/A
  - E2E/Regression: 见 R3
  - Visual/Interaction: N/A
- Rollback: 上一稳定 = C1 commit 41d4aea4（红测试）
- Commits: C1=41d4aea4, C2=455d1456, C3=TODO
- Next: R3 — e2e 验证 + fix.md 回填

## R3 — e2e 验证 + fix.md 回填

_TODO_
