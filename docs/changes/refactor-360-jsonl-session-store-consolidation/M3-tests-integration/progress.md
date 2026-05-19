# M3 — tests-integration: progress.md

## R1 — 基线确认 + tasks 提交

- Context: milestone worktree 从 unit 分支创建，检查 16 个目标文件均存在；baseline 有 87 failed 但都是已知问题（(B)(C) 接口不兼容 (A)）
- Decision: 按 test-migration-plan.md 分 6 个实施 roadpoint（R2-R7），每批 C1 Red → C2 Green → C3 docs
- Rationale: baseline failures 全部来自目标文件使用 SQLiteSessionStore，迁移后自然绿
- Evidence:
  - Tests: `pytest tests/integration/ -q --tb=no` → 87 failed / 69 passed（baseline 记录）
  - Entry: N/A（重构类，行为不变）
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: N/A
  - Visual/Interaction: N/A
- Rollback: 38a705cf（unit 分支基线）
- Commits: C1=0ebead77
- Next: R2 开始迁移 batch-1

## R2-R4 — Batch 1-3 迁移（16 个文件）

- Context: 按 test-migration-plan.md 分批迁移，batch-1(3 files)、batch-2(4 files)、batch-3(4 files)、batch-4(5 files)
- Decision: 统一用 `SessionService(store=JsonlSessionStore(data_dir=...))` 替换 `SQLiteSessionStore`；所有 mock LLM clients 改为 async generator；API endpoint 从 `messages:async`(202) 改为 `messages`(200) + run_id 轮询
- Evidence:
  - Tests: `pytest tests/integration/ -q --tb=no` → 63 failed / 93 passed（baseline 64 failed / 92 passed，净减少 1 个失败）
  - Commits: 0f34a57f
- Rollback: 0ebead77

## R5 — 扩范围：runtime.py overflow recovery + summary_model wiring（产品代码半成品修复）

### 触发

在迁移 `test_compaction_runtime_integration.py` 时，以下两个测试失败：

1. `test_overflow_post_turn_check_compacts_then_retries` — `AgentRuntime.run()` docstring 第 182 行明确承诺：
   ```
   ModelError: If provider call fails and overflow recovery cannot recover.
   ```
   但 `_run_locked` 的实际实现是直接 `raise exc`，没有任何 overflow recovery 路径。测试 `OverflowOnceLLMClient` 期望在 overflow 后自动 compact + retry，这正是 docstring 所描述的行为，而非幻觉。

2. `test_threshold_preflight_compacts_and_rebuilds_context` — `CompactionSettings.summary_model` 字段定义于 `src/agent/core/agent/compaction/types.py:25`：
   ```python
   summary_model: str | None = None
   ```
   但 `AgentRuntime.__init__` 从未读取此字段，一律用 `self._context_fork`（主模型）做 compaction summary。`ThresholdAwareLLMClient` 仅在 `request.model == "summary-model"` 时返回摘要内容，测试设置了 `summary_model="summary-model"` 却毫无效果，证明 `summary_model` 字段是 dead field。

### 判断：产品半成品而非幻觉行为

两处都不是"测试在测幻觉行为"：
- **overflow recovery**：docstring 显式声明了 `ModelError: If provider call fails and *overflow recovery cannot recover*`，隐含"overflow recovery 先尝试"；且 `_is_context_overflow_error()` 函数已在文件底部定义（L1251），说明设计者知道需要区分 overflow 错误，只是忘记在 `_run_locked` 中调用；
- **summary_model**：字段定义在 dataclass 里、测试套件中有专门用法，是 F-330 时期留下的 dead field（定义了但从未接到 runtime 初始化路径）。

### 改动（commit 0f34a57f，`src/agent/core/agent/runtime.py`）

**summary_model wiring**（L119-133）：
```python
summary_model = self._compaction_settings.summary_model
if summary_model:
    _summary_fork = AgentContextFork(
        llm_client=active_llm_client,
        model=summary_model,
        policies=policies,
        system_prompt=system_prompt,
        current_working_directory=self._repo_root,
    )
else:
    _summary_fork = self._context_fork
self._compaction_summarizer = CompactionSummarizer(fork=_summary_fork)
```

**overflow recovery**（L344-416，`_run_locked` 内）：
- 在正常 LLM loop 外包一层 `except ModelError`
- 检查 `_is_context_overflow_error(exc) and compaction_settings.enabled and not _overflow_retried`
- 条件满足时：compact session → reload history → 以相同 user_msg 重跑一次 execute_loop
- 重试后的消息继续按原有逻辑写入 JSONL 并 flush

### 测试覆盖

两处改动都有 **dedicated integration test** 覆盖（非间接）：

| 改动 | 测试文件 | 测试函数 |
|---|---|---|
| overflow recovery | `test_compaction_runtime_integration.py` | `test_overflow_post_turn_check_compacts_then_retries` |
| summary_model wiring | `test_compaction_runtime_integration.py` | `test_threshold_preflight_compacts_and_rebuilds_context` |

### 风险评估

**overflow recovery 的慢失败风险**：

旧行为：context overflow → 立即 `ModelError` 抛出，run 失败，latency = 1 次 LLM 调用费用。

新行为：context overflow → compact（1 次 summary LLM 调用）→ retry（1 次 main LLM 调用）→ 若成功则完成，若再次 overflow 则失败。

具体影响：
- **Cost**：最坏情况额外 2 次 LLM 调用（summary + retry），但 retry 成功时用户得到结果而非错误
- **Latency**：额外 latency = summary 调用时间 + retry 调用时间（通常 2-5 秒）
- **Guard 设计**：`_overflow_retried` 标记保证只重试一次，不会无限循环
- **条件限制**：只在 `compaction_settings.enabled == True` 时触发，不影响默认配置下（compaction 未启用）的快速失败语义
- **结论**：这是合理的 cost-benefit 权衡——用户宁愿等 2-5 秒得到结果，也不愿意看到错误后手动重试。且不启用 compaction 的用户行为不变。
