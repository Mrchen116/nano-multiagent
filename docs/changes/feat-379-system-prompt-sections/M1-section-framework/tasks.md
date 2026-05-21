# feat-379-M1: section-framework — Tasks

> 对齐: ../design.md v1

## 目标

建立段式组装机制（PromptSection/PromptContext/assemble_system_prompt/resolve_effective_prompt）和特性注册表骨架，把 PA、LC 现有 system prompt 纯结构迁移成段集合（golden 等价、零内容变更），退役 communication_context hook 的 prompt 旁路注入，接通 scenario。

## 退出标准

- [ ] `pytest tests/.../test_prompting*` + 段单测全绿
- [ ] golden 测试断言 PA/LC 在单聊/群聊/有无 memory 工具/有无 custom 场景下组装产物与重构前逐段等价（含 bugfix-358 mention 文案逐字），唯一例外：core.background_tasks 改为按 Agent 工具门控
- [ ] 不变量测试：所有 cache_safe=False 段 order 严格大于所有 cache_safe=True 段（决策 8）
- [ ] resolve_effective_prompt 的 override 直通分支覆盖子 agent fork 路径（决策 9）
- [ ] 每个段定义处带 Provenance: 注释（决策 10，迁移段标 new + 原位置）
- [ ] tests/contract/ 依赖方向不破（core 不 import 产品段）

## 测试策略

- 被测行为（来自退出标准）：
  1. assemble_system_prompt 按 (order, name) 排序、enabled_when 门控、render 过滤 None、"\n\n" join
  2. cache_safe=False 段 order 严格大于 cache_safe=True 段（不变量）
  3. PA golden：单聊/群聊/有无 memory 工具/有无 custom_prompt 场景组装产物等价重构前
  4. LC golden：无群聊/有无 memory 工具场景组装产物等价重构前
  5. resolve_effective_prompt：override 直通 > 段式组装（决策 9）
  6. core 不 import 产品段（contract 测试已有，延用）

- 已有测试在：`tests/unit/test_agent_prompting.py`（扩展现有文件，段单测）；新建 `tests/unit/agent/test_prompt_sections.py`（assemble/resolve/不变量）；新建 `tests/integration/test_prompt_sections_golden.py`（PA/LC golden 等价）

- 落层/目录/marker：
  - `tests/unit/agent/` — 纯逻辑单测（无 IO）
  - `tests/integration/` — golden 集成（需要产品 prompts 模块），无 e2e marker
  - `tests/contract/` — 依赖方向（延用已有 test_core_no_platform_imports.py）

- 可选依赖 importorskip：无

- 本 milestone 产生的一次性验收证据：无（全部进永久套件）

UI 状态矩阵：N/A（纯后端）

## Roadpoints

### R1 — PromptSection/PromptContext/assemble/resolve 核心数据结构与组装器

- 步骤: 创建 `agent/core/agent/prompt_sections/` 包，实现 `base.py`（PromptContext、PromptSection、assemble_system_prompt、resolve_effective_prompt）和 `__init__.py`
- 验证: 段单测全绿（assemble 排序、门控、None 过滤、join；cache_safe 不变量；resolve override 直通）
- 状态: DONE

### R2 — 特性注册表骨架

- 步骤: 实现 `feature_registry.py`（FEATURE_REGISTRY 常量骨架，含 memory_curation、skill_creation 两条记录，不填充实现细节，留 M2 填充）
- 验证: import 不报错，单测骨架字段结构
- 状态: TODO

### R3 — core 段迁移（core_sections.py）

- 步骤: 实现 `core_sections.py`，迁移 core.*（system 现有文案、tool_rules 现状、runtime_tools、skills_listing、memory_guidance、skills_guidance、background_tasks 改为 Agent 工具门控、runtime_footer）；M4 的新增/改写段留存文件占位注释但不实现内容变更
- 验证: 段单测 + LC golden 部分通过
- 状态: TODO

### R4 — PA 产品段迁移（personal_assistant/prompt_sections.py）

- 步骤: 实现 PA 段集合（pa.identity/runtime/memory_intro/heartbeat/platform_policy/guidelines/routing/user_custom/communication_context），从现有 `prompts.py` 逐字搬迁，更新 PA profile 注册 prompt_sections
- 验证: PA golden 等价测试全绿（bugfix-358 文案逐字验证）
- 状态: TODO

### R5 — LC 产品段迁移（local_coding/prompt_sections.py）

- 步骤: 实现 LC 段集合（lc.identity/guidelines），从 `prompts.py` 逐字搬迁，更新 LC profile
- 验证: LC golden 等价测试全绿
- 状态: TODO

### R6 — ProductProfile.prompt_sections 字段 + bootstrap 装配

- 步骤: `products/base.py` 新增 `prompt_sections` 字段；`bootstrap.py` 把 core 段 + 产品段合并 → `ResolvedProductConfig` 暴露 `prompt_sections` + `resolved_prompt_sections` 列表
- 验证: contract 测试不破；产品 profile 能正确注册段
- 状态: TODO

### R7 — runtime/loop scenario 接线 + communication_context hook 退役

- 步骤: `runtime._run_locked` 把 hook_metadata 里的 scenario 字段打包成 PromptContext；loop.run 改为传 PromptContext 到 assemble_system_prompt；communication_context.py 中 before_agent_start 的 prompt 改写逻辑删除（hook setup 保留但 prompt 改写分支移除）；文档化退役注释
- 验证: 全套 golden 测试（含群聊场景）通过；pytest -m "not e2e" 全绿
- 状态: TODO
