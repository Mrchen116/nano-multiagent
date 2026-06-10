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

