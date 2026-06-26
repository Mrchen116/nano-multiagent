# feat-439-M1 — Progress

<!-- 每个 roadpoint 完成后实时追加。 -->

## R1 — 内核侧缓存字段贯穿

- Context: 上游 usage 真带缓存字段（Anthropic `cache_read_input_tokens`、OpenAI `prompt_tokens_details.cached_tokens`），但解析层要么把缓存折进 prompt_tokens 没单独存（Anthropic），要么整段丢（OpenAI）。命中率 = 命中量 ÷ 总 input，需把分子/分母按整轮口径带到前端。
- Decision: TokenUsage 追加 `cache_read_tokens` / `cache_total_input_tokens`（默认 0）；两家 provider 的 client.py + mapper.py 的 `_parse_*_usage` 各追加两字段（Anthropic 复用已算出的 cache_read；OpenAI 补读 cached_tokens）；`_accumulate_usage` 把两字段归入「累加」一类。**prompt_tokens 计算一字未改**。
- Rationale: 决策 1/2/3。两字段与 prompt_tokens 平行而非替代——prompt_tokens 保持「最后快照」口径（驱动 context_used / 已用上下文，不可动），缓存字段走「整轮累加」口径（命中率 = Σcache_read / Σcache_total_input）。逐请求 `cache_total_input_tokens == prompt_tokens`，两家归一后累加口径一致。mapper.py 被 `test_llm_anthropic_mapper.py` 覆盖，按 design Rec2 同步改以免两份漂移。
- Evidence:
  - Tests: `pytest tests/unit/test_llm_anthropic_mapper.py test_llm_openai_compat_mapper.py test_llm_anthropic_client_streaming.py test_openai_compat_client_streaming.py test_agent_loop.py` → 58 passed。含「prompt_tokens 不变」「cache_total_input == prompt_tokens 归一」「整轮累加 270/400」「旧数据默认 0」断言。回归：`test_cli_turn_usage / test_hook_builtin_usage_metrics / test_loop_compact` 41 passed（CLI 忽略新字段、turn usage 累计无回归）。
  - Entry: 后端数据层，真实入口在 R3（前端 token 气泡）/ reviewer 真栈。本 R 为纯解析逻辑，单测即入口契约。
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: 单测即回归（解析归一 + 累加口径固化，防 qwen 式分母错）。
  - Visual/Interaction: N/A
- Rollback: revert C2 commit；字段带默认值，回滚后旧数据/旧代码互不影响。
- Commits: C1=test red, C2=feat impl（见 git log feat-439/M1/R1）
- Next: R2 — Gateway + IM 透传与持久化

## R2 — Gateway + IM 透传与持久化

- Context: 缓存字段已在内核 TokenUsage 累加好，但透传链上有多个「白名单」跳——只挑选字段、不透明复制，缓存字段会被丢弃。
- Decision: 显式在每个白名单跳补带 cache 两字段：
  1. `loop.py:587` turn_end_payload `usage` dict（**design 只点了 main.py，这里是同文件内的第二个白名单跳**——realtime_stream `dict(usage)` 透明复制它，源 dict 不带则全链断在源头）→ 加 `cache_read_tokens`/`cache_total_input_tokens`。
  2. `personal_assistant/main.py` turn_end `token_usage_payload`（design 点明的真拦截点）→ 读 usage_raw 的 cache 字段，以短键 `cache_read`/`cache_total_input` 带出。
  3. IM `gateway_handler._parse_token_usage` → 读短键 `cache_read`/`cache_total_input` 落入 domain TokenUsage。
  4. IM domain `TokenUsage` 加 `cache_read_tokens`/`cache_total_input_tokens`（默认 0）。
  5. repo `_encode_token_usage`/`_decode_token_usage` → JSON 持久化往返（decode 缺键兜底 0，同 total 兜底思路）。
  6. 两条序列化出口：WS `event_types.token_usage_to_dict` + REST `routes/messages.py:to_message_response`（`TokenUsagePayload` 加字段）→ 恒带 `cache_read_tokens`/`cache_total_input_tokens`。
- Rationale: 决策 3 透传链。短键 vs 全名沿用既有惯例（gateway 短键 `prompt`→domain `context_used`→frontend `context_used`）。恒带（含 0）保证空态行可渲染。
- Evidence:
  - Tests: 新增/扩展 observer 透传、`_parse_token_usage` 读 cache、repo 往返、event_types、REST `to_message_response` 共 8 红→绿；`prompt`/`completion` 不变断言保留。
  - Entry: WS `message_completed` payload + REST GET /messages 两条真实出口的序列化均断言带 cache（REST 经 `to_message_response`）。
  - Frontend State Matrix / Browser QA / Visual: N/A（本 R 为后端透传）
  - E2E/Regression: 全量 `pytest -m "not e2e"` → 2980 passed, 2 skipped（无 sibling 回归）。
- Rollback: revert C2；字段默认值 0，旧库行 decode 兜底 0、回滚保留空列无迁移风险。
- Commits: C1=test red, C2=feat impl（见 git log feat-439/M1/R2）
- Next: R3 — 前端渲染 + 浏览器验收

### [实现细节记录] R2: loop.py:587 也是白名单跳（design 未点）

- 现状方案: design §1.9/§3 把 cache 透传的拦截点定位在 `main.py:3596-3622`，并称 realtime_stream `dict(usage)` 为「透明透传」。
- 实际: realtime_stream 复制的源 dict 来自 `loop.py:587` turn_end_payload，**它本身也是只挑 prompt/completion/total 的白名单**——不在此补带，main.py 永远读不到 cache。
- 处理: 在 `loop.py:587` 同步补带两字段。loop.py 本就在 M1 范围（design 列了 `_accumulate_usage`），此为同文件内的 additive 细节、与决策 3 数据流意图一致，非方案冲突，无需回 design-author，仅记录在案。
