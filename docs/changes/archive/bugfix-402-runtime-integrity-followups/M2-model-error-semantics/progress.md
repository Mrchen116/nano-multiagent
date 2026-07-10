# bugfix-402-M2 — Progress

## R1 — provider-neutral 错误事实提取与共享分类器

- Context: 两个 provider client 各自硬编码了错误的 retryability（SSE error 事件统一为 `retryable=False`，HTTP 错误未按语义分类）。需要引入共享分类器，消除 provider-name 分支。
- Decision: 新增 `src/agent/core/llm/error_classifier.py`，定义 `ProviderErrorFacts` dataclass 和 `classify_retryability()` 函数。两个 provider client 的 HTTP 错误和 SSE error 事件均改为提取 facts 后调用分类器。
- Rationale: 分类器按照 design.md 决策 4 的优先级顺序（billing/quota → structured type/code → HTTP status → text pattern → default retryable）实现，billing/quota 文本匹配放在 HTTP 状态检查之前，确保 403 "overdue" 类响应仍为可重试。
- Evidence:
  - Tests: `pytest -xvs tests/unit/test_llm_error_classifier.py tests/contract/test_llm_provider_contract.py` — 54 passed
  - Entry: 纯逻辑层改动，无 HTTP 入口；contract test 以 MockTransport 覆盖真实 HTTP 调用链 N/A
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: N/A — 无运行时服务依赖
  - Visual/Interaction: N/A
- Rollback: git revert C2 commit
- Commits: C1=test commit, C2=feat commit
- Next: R2

## R2 — RetryingLLMClient 已产出内容不重试 + 保留原始错误

- Context: 当前 `RetryingLLMClient` 在流已产出内容后如果发生 retryable 错误仍然重试整个请求（最多 21 次），会导致内容重复输出和 transcript 损坏。重试耗尽后创建了新的 "exceeded N retries" 包装文案，丢失了真实 provider 错误。
- Decision: 在 `generate()` 中追踪 `yielded_content` 标志；一旦有内容 yield 后遇到错误，直接 re-raise（不重试）。耗尽时保留 `exc.message` 和 `exc.details`，只追加 `retry_exhausted=True`/`attempts`/`delay` 诊断字段。
- Rationale: 已产出内容意味着调用方（agent loop）已经将其流给用户或持久化；重放整个请求会重复这些内容。保留原始错误让用户看到真实 provider 原因，不被重试基础设施遮盖。
- Evidence:
  - Tests: `pytest -xvs tests/unit/test_retrying_llm_client.py tests/unit/test_loop_retry.py tests/integration/test_provider_error_user_visible.py` — 60 passed（新增 6 个 RetryingLLMClient 专项测试）
  - Entry: 纯逻辑层改动；全测试树 `tests/unit/ tests/contract/ tests/integration/` — 2310 passed
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: N/A
  - Visual/Interaction: N/A
- Rollback: git revert R2 C2 commit
- Commits: C1=test commit, C2=fix commit
- Next: milestone DONE

