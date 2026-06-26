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
