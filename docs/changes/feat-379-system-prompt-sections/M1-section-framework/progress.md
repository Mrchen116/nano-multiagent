# feat-379-M1 — Progress

<!-- 每个 roadpoint 完成后追加 -->

## R1 — PromptSection/PromptContext/assemble/resolve 核心数据结构与组装器

- Context: 段式体系的基础契约——所有后续段都依赖这个框架。
- Decision: 创建 `src/agent/core/agent/prompt_sections/base.py`，实现 PromptContext（frozen dataclass）、PromptSection（frozen dataclass + 两个纯函数）、assemble_system_prompt（排序+门控+join）、resolve_effective_prompt（override 优先级）。包含 cache_safe 不变量校验（决策 8）。
- Rationale: 纯 core，不 import product；resolve_effective_prompt 是决策 9 的单一来源决议点，和 CC buildEffectiveSystemPrompt 同构。
- Evidence:
  - Tests: `pytest tests/unit/agent/test_prompt_sections.py` — 18 passed
  - Entry: N/A（纯内部逻辑层，无用户入口；入口验证在 R7 golden 测试）
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: N/A（纯逻辑层，单测覆盖完整）
  - Visual/Interaction: N/A
- Rollback: `git revert edd2180c`
- Commits: C1=dfe3b931, C2=edd2180c, C3=（本次）
