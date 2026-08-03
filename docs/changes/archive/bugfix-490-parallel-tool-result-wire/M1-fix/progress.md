# bugfix-490-M1 progress

## 实现

- `AnthropicMapper.map_generate_request`：连续仅含 `tool_result` 的 user 合并为一条（对齐 CC `normalizeMessagesForAPI`）。
- 单测：`test_map_generate_request_merges_consecutive_parallel_tool_results`。

## 真实上游证据（本机 LLM_PROXY + deepseek）

对照请求 `model=deepseek:deepseek-v4-flash` via `http://127.0.0.1:4000/v1/messages`：

| 形态 | 结果 |
|---|---|
| SPLIT：assistant 两 tool_use 后两条各含一个 tool_result 的 user | `invalid_request_error`：`tool_use ids were found without tool_result blocks immediately after: call_B` |
| MERGED：同一条 user 含两个 tool_result | `200` |
| 经 worktree `AnthropicMapper` 映射后的 payload | `200` |

详见 `evidence/local-deepseek-wire.txt`。

## Spec delta

no spec delta（Anthropic 上线规范化，不改 SDK/消费者可观察契约）。
