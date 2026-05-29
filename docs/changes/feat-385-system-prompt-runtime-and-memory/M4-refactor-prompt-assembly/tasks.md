# feat-385-M4: refactor-prompt-assembly — Tasks

> 对齐: ../design.md §M4重构:系统提示词构造集中化 (决策 15–21)

## 目标

把"段散落 + order 隐式排序 + 通用 assembler"重构成:
- 每产品一个显式装配函数 `build_<product>_system_prompt()`（对齐 CC getSystemPrompt）
- 顺序 = 编排列表位置，`PromptSection.order` 字段删除
- 段渲染自包含 banner，`MemoryStore` 只返回数据（content + pct）
- preview 与 runtime 共用同一装配函数，差异仅在 `render_mode`（RUNTIME / PREVIEW）
- preview 占位符逻辑下沉 core 段 render（删 global_routes.py 的 `_make_volatile_placeholder_section`）

## 退出标准

- [ ] `[worker]` runtime 实际输出 golden 测试**字节不变**（behavior-preserving）
- [ ] `[worker]` `PromptSection` 无 `order` 字段
- [ ] `[worker]` banner 字符串（`══`/`MEMORY (your personal notes)`）只在 core 段 render 出现、不在 `MemoryStore`
- [ ] `[worker]` `global_routes.py` 无 `_make_volatile_placeholder_section`，preview 与 runtime 共用同一 `build_<product>_system_prompt` + 同一 `resolve`
- [ ] `[worker]` `core` 零 product import — `tests/contract/test_core_no_platform_imports.py` 绿，且 core 代码 grep 无 `build_pa`/`build_lc`/产品名
- [ ] `[worker]` `pytest tests/unit/ tests/integration/ tests/contract/ -m "not e2e"` 全绿

## 测试策略

- 被测行为（来自退出标准）：
  1. runtime 段式输出字节不变（golden 快照测试）
  2. `PromptSection` 无 `order` 字段（静态结构检查）
  3. banner 只在 core 段（grep / 单元测试）
  4. `global_routes.py` 无 `_make_volatile_placeholder_section`（grep / pytest 测试）
  5. core 零 product import（contract 测试已有）
  6. preview 中 volatile 段含 banner + 占位符（单元测试）
  7. cache_safe 不变量改为列表位置校验（单元测试）
- 已有测试在：`tests/integration/test_prompt_sections_golden.py`（扩展）、`tests/unit/agent/test_prompt_sections.py`（扩展）、`tests/unit/platform/http_api/test_prompt_preview_volatile.py`（扩展）
- 落层/目录/marker：tests/unit/、tests/integration/、tests/contract/ ，marker：无
- 可选依赖 importorskip：无
- 本 milestone 产生的一次性验收证据：无（纯重构，测试即证据）

## Roadpoints

### R1 — 补 runtime golden 快照测试（基线保护）
状态: TODO

- 步骤: 在 `tests/integration/test_prompt_sections_golden.py` 或新测试文件，补一组快照测试捕获当前 runtime 段式输出（含 banner 文案字节），作为 M4 重构基线
- 验证: 快照测试运行通过（当前代码为基线）

### R2 — `PromptSection` 删 `order`，改列表位置校验（决策 16）
状态: TODO

- 步骤: 删除 `base.py` 中的 `order: int` 字段；修改 `assemble_system_prompt` 按传入列表顺序（不排序）；改 `_validate_cache_safe_invariant` 为列表位置校验（volatile 段索引 > 所有 stable 段索引）；更新所有 `PromptSection(order=...)` 构造调用
- 验证: 单测 `test_prompt_sections.py` + contract `test_core_no_platform_imports.py` 通过；golden 快照不变

### R3 — banner 移进 core 段 render，`MemoryStore` 收窄为数据（决策 17+18）
状态: TODO

- 步骤: 给 `PromptContext` 新增 `render_mode: RenderMode` + 字段重构（`memory_block→memory_content`，`user_profile_block→user_profile_content`，`current_datetime/cwd` 改 `str|None`）；`MemoryStore.format_for_prompt` 收窄返回 `MemoryData`（content + pct）；core 段 render 实现三态（PREVIEW/RUNTIME 有数据/RUNTIME 无数据）；更新 `wiring.build_prompt_context_from_metadata` 签名
- 验证: banner 文案测试通过；golden 快照不变

### R4 — 每产品显式装配函数 `build_<product>_system_prompt`（决策 15+20）
状态: TODO

- 步骤: `pa/prompt_sections.py` 新增 `build_pa_system_prompt()` 返回有序列表（显式线性排列 core 积木 + pa 段）；`lc/prompt_sections.py` 新增 `build_lc_system_prompt()`；更新 `pa/profile.py` / `lc/profile.py`；更新 `platform/bootstrap.py` 用 `build_*` 取代无序拼接
- 验证: golden 快照不变；contract test_core_no_platform_imports 通过

### R5 — preview 占位符下沉 core，删 `_make_volatile_placeholder_section`（决策 19）
状态: TODO

- 步骤: 删 `global_routes.py` 的 `_make_volatile_placeholder_section` + stable/volatile 分流；preview 端点只构造 `ctx(render_mode=PREVIEW, …=None)` + 调 `resolve`；core 段 render 按 `render_mode==PREVIEW` 输出 banner + 占位符
- 验证: preview 单测（volatile 段含 banner + `<运行时注入:…>`）通过；全套 golden 通过

### R6 — runtime.py ctx 带 render_mode=RUNTIME（决策 18 收尾）
状态: TODO

- 步骤: `runtime.py` 的 `_run_locked` 构造 ctx 时带 `render_mode=RUNTIME`；确认 memory_content 等字段签名对齐
- 验证: integration golden 通过；runtime 入口测试通过

### R7 — 全套测试更新收尾 + C3 progress.md
状态: TODO

- 步骤: 更新所有受影响测试（PromptContext 字段重命名、order 参数删除）；确认 `pytest -m "not e2e"` 全绿；补 progress.md 各 R 的完整 Evidence
- 验证: `pytest tests/unit/ tests/integration/ tests/contract/ -m "not e2e"` 全绿
