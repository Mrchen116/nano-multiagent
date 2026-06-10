# bugfix-402-M2: model-error-semantics — Tasks

> 对齐: ../design.md v1

## 目标

HTTP/SSE/transport 错误由两个 provider 独立解析统一为共享的 provider-neutral 事实 + 分类器；
默认可重试，只有明确永久错误快速失败；重试耗尽保留最后一次真实 provider 错误；
流已产出部分内容时中途故障按最终失败处理，不原位重试（不重复输出）。

## 退出标准

- [ ] HTTP/SSE/transport 共用 `extract_provider_error_facts()` + `classify_retryability()`，无 provider-name 分支
- [ ] 明确永久错误（凭证无效、参数错误、资源不存在等）返回 `retryable=False`，立即 fail-fast
- [ ] 网络、超时、429、5xx、quota/billing 语义均默认 `retryable=True`
- [ ] `RetryingLLMClient` 在已产出部分内容后中途故障时不原位重试，保留真实错误
- [ ] 重试耗尽后抛出保留最后一次真实 provider 错误（message/code/status），不替换为 "exceeded N retries"
- [ ] 新增 `retry_exhausted=True` + `attempts` + `delay` 到 details 作为诊断元数据
- [ ] Kimi/火山代表性 4xx fixtures、永久错误和 exhaustion 测试覆盖
- [ ] `pytest -xvs tests/unit/test_loop_retry.py tests/unit/test_runtime_retry_no_duplicate_user_message.py tests/contract/test_llm_provider_contract.py tests/integration/test_provider_error_user_visible.py` 全绿

## 测试策略

- 被测行为：
  1. `classify_retryability()` 对各类错误的分类（永久 vs 可重试）
  2. 两个 provider client 的 SSE error 事件路径使用共享分类器
  3. `RetryingLLMClient` 已产出内容后不原位重试
  4. `RetryingLLMClient` 重试耗尽保留原始错误
- 已有测试在：
  - `tests/unit/test_loop_retry.py`（扩展）
  - `tests/contract/test_llm_provider_contract.py`（扩展，增加 error 分类测试）
  - `tests/integration/test_provider_error_user_visible.py`（扩展，增加 exhaustion 保留原始错误用例）
- 落层：tests/unit/ + tests/contract/ + tests/integration/
- 可选依赖 importorskip：无
- 一次性验收证据：无

UI 状态矩阵：N/A（纯后端逻辑）

## Roadpoints

### R1 — provider-neutral 错误事实提取与共享分类器 `DONE`

- 步骤：
  1. 在 `src/agent/core/llm/` 新增 `error_classifier.py`，定义 `ProviderErrorFacts` dataclass 和 `classify_retryability()` 函数
  2. 分类规则实现（依据 design.md 决策 4 的优先级）
  3. 修改两个 provider client 的 SSE error 事件处理，使用共享分类器替换硬编码 `retryable=False`
  4. 修改 HTTP 错误提取，提取 status/code/type/body 到 ProviderErrorFacts 再分类
- 验证：`pytest -xvs tests/contract/test_llm_provider_contract.py` 中添加 error classification 测试

### R2 — RetryingLLMClient 增强：已产出内容不重试 + 保留原始错误 `DONE`

- 步骤：
  1. 修改 `RetryingLLMClient.generate()` 追踪是否已 yield 内容
  2. 已产出内容后中途故障：不重试，直接 raise 原始错误
  3. 重试耗尽后：保留最后一次 `ModelError` 的 message/details，追加 `retry_exhausted=True`/`attempts`/`delay` 到 details
- 验证：`pytest -xvs tests/unit/test_loop_retry.py tests/integration/test_provider_error_user_visible.py`
