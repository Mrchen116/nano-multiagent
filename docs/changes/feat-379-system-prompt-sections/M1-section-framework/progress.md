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
- Commits: C1=dfe3b931, C2=edd2180c, C3=（see R2-R7 below, bulk C3 commit）

## R2 — 特性注册表骨架

- Context: feature_registry.py 作为 flag→段→工具→默认值的单一来源（决策 7），R2 只建骨架。
- Decision: FEATURE_REGISTRY dict，两条记录（memory_curation / skill_creation），FeatureEntry TypedDict。
- Evidence: `pytest tests/unit/agent/test_feature_registry.py` — 10 passed
- Commits: C1=e3f2a001, C2=bundled with R3

## R3 — core 段迁移

- Context: core_sections.py 迁移 11 段，core.background_tasks 改为按 agent 工具门控（golden 等价唯一例外）。
- Decision: M4 stub 段（actions_care / tool_rules / tone_style）render 返回 None 保证 golden 等价；memory_guidance/skills_guidance 分别由 flag 门控。
- Evidence: `pytest tests/unit/agent/test_prompt_sections.py tests/integration/test_prompt_sections_golden.py` — 全绿（LC golden 通过）
- Commits: bundled multi-roadpoint

## R4 — PA 产品段迁移

- Context: PA 9 段，含 pa.communication_context（order=900, cache_safe=False）委托给 _build_communication_context_block 以保持 bugfix-358 mention 文案逐字等价。
- Evidence: `pytest tests/integration/test_prompt_sections_golden.py` — PA golden 全绿含群聊场景
- Commits: bundled multi-roadpoint

## R5 — LC 产品段迁移

- Context: LC 3 段（lc.identity/guidelines/tools_footer），零内容变更。
- Evidence: LC golden 通过
- Commits: bundled multi-roadpoint

## R6 — ProductProfile.prompt_sections 字段 + bootstrap 装配

- Context: products/base.py 新增 prompt_sections 字段；PA/LC profile 各自注册段集合。
- Evidence: `pytest tests/unit/agent/test_product_profile_prompt_sections.py` — 5 passed；contract 测试不破
- Commits: C1=191a88d0, C2=4e0d9236

## R7 — scenario 接线 + communication_context hook 退役

- Context: 建立 wiring.py（build_prompt_context_from_metadata），将 hook_metadata 的 scenario 字段打包为 PromptContext；communication_context hook setup() → pass，prompt 注入由 pa.communication_context segment 承接。
- Decision: _build_communication_context_block() 保留在 hook 模块供 segment 复用，避免重复 bugfix-358 文案。wiring.py 只拷贝 metadata 中实际存在的 key（_copy_if_present），不预设默认值。
- Evidence: `pytest tests/unit/ tests/integration/test_prompt_sections_golden.py tests/contract/ --ignore=...background_hook*` — 1861 passed, 2 xfailed（2 pre-existing failures unrelated to M1）
- Commits: C1=77cd673b, C2=bc2c4ffc, C3=（本次）
