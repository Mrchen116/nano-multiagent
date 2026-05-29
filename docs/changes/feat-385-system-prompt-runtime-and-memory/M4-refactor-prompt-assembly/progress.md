# feat-385-M4 — Progress

## R1 — M4 重构前 runtime golden 快照基线

- Context: M4 是 behavior-preserving 重构，需要先拍基线保护，确保重构前后 banner 字节不变。
- Decision: 新建 `tests/unit/agent/prompt_sections/test_m4_golden_baseline.py`，覆盖 MemoryStore banner 格式契约 + runtime assembly 中 banner 位置和内容。
- Rationale: 先有 golden 再动刀，防止无感知退化。R1 的测试在重构后仍然通过，证明行为字节不变。
- Evidence:
  - Tests: 14 个 golden baseline 测试全绿
  - Entry: N/A（纯基线拍摄，不涉及入口）
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: N/A
  - Visual/Interaction: N/A
- Rollback: `git revert 4c58fca9`
- Commits: C1=4c58fca9

## R2+R4 — 删 PromptSection.order + 列表位置装配 + 每产品显式 build_* 函数

- Context: R2 和 R4 紧密耦合 — 删 order 后，必须同时有正确的显式编排函数才能通过 cache_safe 不变量。
- Decision:
  1. `base.py`：删 `PromptSection.order` 字段，`assemble_system_prompt` 改为按传入列表位置顺序，`_validate_cache_safe_invariant` 改为列表位置校验。
  2. `core_sections.py`：导出大写名 building blocks（CORE_SYSTEM 等），保留下划线别名向后兼容。
  3. `pa/prompt_sections.py`：新增 `build_pa_system_prompt()` 显式线性编排（stable 前 volatile 尾）。
  4. `lc/prompt_sections.py`：新增 `build_lc_system_prompt()` 同理。
  5. `products/base.py`：`ProductProfile` 加 `prompt_sections_builder` 可选字段。
  6. `bootstrap.py`：优先用 `prompt_sections_builder()`，fallback 旧合并路径。
  7. `pa/profile.py`、`lc/profile.py`：引用 build 函数。
  8. 受影响测试全部更新（去掉 order= 参数、旧式合并改用 build 函数）。
- Rationale: 对齐 CC getSystemPrompt 模式，一眼看出段顺序。删 order 后不能再用 `CORE_SECTIONS + PA_SECTIONS` 合并（volatile 夹 stable 之间违反 cache_safe 不变量），必须用 build 函数显式编排。
- Evidence:
  - Tests: 624 passed, 22 skipped, 2 xfailed（与基线持平，无新失败）
  - Entry: N/A（架构重构）
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: `test_prompt_sections_golden.py` 全绿（golden 行为不变）
  - Visual/Interaction: N/A
- Rollback: `git revert 297f7afd`
- Commits: C2=297f7afd, C3（合并在 C2 中）

## R3+R5+R6 — banner 移进 core 段 + MemoryStore 收窄 + RenderMode + 删 _make_volatile_placeholder_section

- Context: 三个 roadpoint 紧密耦合——banner 移进 core 段（R3）需要 PromptContext 新字段（R3），preview 端点才能删掉 hack（R5），runtime ctx 带 render_mode（R6）。
- Decision:
  1. `base.py`：新增 `RenderMode` 枚举（RUNTIME/PREVIEW）；`PromptContext` 新增 `memory_content`/`memory_pct`/`user_profile_content`/`user_pct`/`render_mode` 字段；保留旧 `memory_block`/`user_profile_block` 向后兼容。
  2. `store.py`：`format_for_prompt` 返回纯内容（无 banner）；新增 `format_pct_for_prompt` 返回百分比；`_load_snapshot` 存纯内容和 pct。
  3. `core_sections.py`：新增 `_render_banner_block` helper；`_render_memory_block` 和 `_render_user_profile_block` 实现三态（PREVIEW→banner+占位 / RUNTIME+数据→banner+真值 / RUNTIME+无数据→None）；`_memory_block_enabled`/`_user_profile_block_enabled` 在 PREVIEW 模式始终激活。
  4. `wiring.py`：`build_prompt_context_from_metadata` 加 `memory_content`/`memory_pct`/`user_profile_content`/`user_pct`/`render_mode` 参数。
  5. `runtime.py`：`MemorySnapshot` TypedDict 改为 `memory_content`/`memory_pct`/`user_profile_content`/`user_pct`；`_ensure_memory_snapshot` 调 `format_for_prompt`（纯内容）和 `format_pct_for_prompt`；`_run_locked` ctx 构造带 `render_mode=RUNTIME`。
  6. `global_routes.py`：删 `_make_volatile_placeholder_section` 和 stable/volatile 分流；preview 端点构造 `ctx(render_mode=PREVIEW)` + 直接调 `assemble_system_prompt`。
  7. 受影响测试全部更新。
- Rationale: 决策 17：banner 是 prompt 表现层，属于段；存储层只管数据。决策 19：preview 逻辑下沉 core 段，platform 不再 hack volatile 段。决策 21：三态覆盖所有场景。`_make_volatile_placeholder_section` 是 M3 遗留的 platform hack，M4 正式删除。
- Evidence:
  - Tests: 1867 passed, 22 skipped, 3 xfailed（全绿）
  - Entry: /v1/prompt-preview 端点行为验证：banner 出现在 preview 输出中（含 ═ 分隔线 + 标题 + `<运行时注入:…>` 占位符）
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: `test_prompt_preview_runtime_parity.py`（contract 测试）全绿；`test_prompt_sections_golden.py` 全绿
  - Visual/Interaction: N/A
- Rollback: `git revert 9903392c` (C2), `git revert 9b246ab9` (修复测试)
- Commits: C1=a98c7506, C2=9903392c, C3（合并）, 修复=9b246ab9
