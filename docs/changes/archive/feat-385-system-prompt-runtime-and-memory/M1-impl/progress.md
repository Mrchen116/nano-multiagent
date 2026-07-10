# feat-385-M1: impl — Progress

## Roadpoints

### R1 — core/memory/path.py: derive_memory_root helper

- Context: MemoryTool 写路径与 runtime freeze 读路径必须从同一 helper 派生，确保物理路径一致（decision 9）。core 层不能 import platform，需要一个轻量的共享 helper。
- Decision: 新增 `src/agent/core/memory/path.py`，包含 `derive_memory_root(workspace_root, workspace_config_dirname) -> Path`，返回 `workspace_root / workspace_config_dirname / "memory"`。
- Rationale: 简单纯函数，零副作用，core 层可调，platform 层也可调。两个路径使用同一实现消除漂移风险。
- Evidence:
  - Tests: `tests/unit/agent/memory/test_memory_path.py` — 4 passed
  - Entry: N/A（helper）
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: N/A
  - Visual/Interaction: N/A
- Rollback: revert `9b96d123`
- Commits: C1=`e97d231a`, C2=`9b96d123`, C3=（combined with plan）

### R2 — PromptContext.user_profile_block + wiring 更新

- Context: design decision 6 要求 USER.md 独立段（hermes 两段模式），需要在 PromptContext 加字段并更新 wiring.py。
- Decision: `base.py` 新增 `user_profile_block: str | None = None` 字段；`wiring.build_prompt_context_from_metadata` 加同名参数（默认 None，向后兼容）。
- Rationale: 最小改动，向后兼容所有既有调用（wiring 调用方不需要立即更新）。
- Evidence:
  - Tests: `tests/unit/agent/prompt_sections/test_user_profile_block.py` — 4 passed; 全套 2155 passed
  - Entry: N/A（数据结构）
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: N/A
  - Visual/Interaction: N/A
- Rollback: revert `dcb03aa8`
- Commits: C1=`3eed7534`, C2=`dcb03aa8`

### R3 — core_sections: 删 runtime_tools + 加 user_profile_block 段

- Context: design decision 8 删 `core.runtime_tools`（工具描述走 API tools=[] 通道），decision 6 加 `core.user_profile_block`（order=960, cache_safe=False）。
- Decision: 删 `_render_runtime_tools` + `_CORE_RUNTIME_TOOLS` + `ORDER_CORE_RUNTIME_TOOLS`；加 `_CORE_USER_PROFILE_BLOCK`（order=960, cache_safe=False）；更新 `CORE_SECTIONS` tuple；更新 golden 测试。
- Rationale: `## Available Tools` 是 token 浪费 + 与 API tools=[] 重复，spec Q6 明确不兜底。golden 测试更新反映新 design 意图。
- Evidence:
  - Tests: R3 专属测试 9 passed；golden + contract 测试全绿；全套 2164 passed
  - Entry: N/A
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: N/A
  - Visual/Interaction: N/A
- Rollback: revert `3f6bbd9d`
- Commits: C1=`0d00ef87`, C2=`3f6bbd9d`

### R4 — runtime 切段式装配 + _ensure_memory_snapshot

- Context: runtime._run_locked 当前调 `build_system_prompt`（老 f-string 路径）。需要改为段式装配：先 freeze memory snapshot，再 build PromptContext，再 resolve_effective_prompt。
- Decision:
  1. `AgentRuntime.__init__` 加 `prompt_sections` 参数 + `_memory_snapshots: dict` + `_prompt_sections: list`
  2. 新增 `_ensure_memory_snapshot(session_id, metadata)` 方法（lazy freeze, cache hit, gate logic）
  3. 新增 `_invalidate_memory_snapshot(session_id)` 方法（compaction callback 用）
  4. `_run_locked` 在 hook 优先级判断后：若有 `_prompt_sections` 则调 snapshot + build ctx + resolve_effective_prompt，结果通过 `pre_rendered_system_prompt` 传给 loop
  5. `AgentLoop.run()` 加 `pre_rendered_system_prompt` 参数：非 None 时跳过 `build_system_prompt`
  6. `app.py` 构造 AgentRuntime 时注入 `prompt_sections`
- Rationale: 对齐 design decision 12 / hermes `_cached_system_prompt` 模式 / CC `buildEffectiveSystemPrompt`。
- Evidence:
  - Tests: `tests/unit/agent/runtime/test_memory_snapshot.py` — 10 passed；全套 2174 passed
  - Entry: N/A（改造 runtime 逻辑）
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: N/A
  - Visual/Interaction: N/A
- Rollback: revert `d526534e`
- Commits: C1=`c1646313`, C2=`d526534e`

### R5 — MemoryTool 隔离修复 + bootstrap 改动

- Context: `MemoryTool._resolve_memory_root` 旧实现有 `.nano` 硬编码 fallback，bootstrap.py 传 fixed memory_root 导致所有 agent 共用一份文件（违背 feat-349 Q3）。
- Decision:
  1. `MemoryTool._resolve_memory_root` 改为从 `session_metadata["workspace_root"] + ["workspace_config_dirname"]` via `derive_memory_root` 派生；无 fallback，缺少 key 直接 raise RuntimeError
  2. `MemoryTool.__init__` `_fixed_memory_root` 保留（测试脚手架用）
  3. `bootstrap.py` 构造 `MemoryTool()` 不再传 `memory_root=memory_root`
  4. `bootstrap.py` 在 `default_session_metadata` 中加 `workspace_config_dirname = profile.workspace_config_dirname`
  5. 已有测试 `test_memory_root_resolved_from_session_metadata` 更新为新 API
- Rationale: MemoryTool 写路径和 runtime freeze 读路径必须从同一 `derive_memory_root` 派生，满足 per-agent 隔离契约（feat-349 spec Q3）。
- Evidence:
  - Tests: `tests/unit/agent/tools/test_memory_tool_isolation.py` — 6 passed；全套 2180 passed
  - Entry: N/A
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: N/A
  - Visual/Interaction: N/A
- Rollback: revert `75853823`
- Commits: C1=`62c86935`, C2=`75853823`

### R6 — 老 f-string 模板退役 + pa.memory_intro 删除

- Context: products/{lc,pa}/prompts.py 包含老 f-string 模板，profile.py 引用它们作为 `default_system_prompt`。design decision 11 要求删除这些文件，decision 7 要求删 `pa.memory_intro` 段。
- Decision:
  1. 删 `src/agent/products/local_coding/prompts.py` 整文件
  2. 删 `src/agent/products/personal_assistant/prompts.py` 整文件
  3. 两个 `profile.py` 中 `default_system_prompt=""` + 移除 prompts 导入
  4. `PA_SECTIONS` 移除 `_PA_MEMORY_INTRO`；保留注释说明删除原因
  5. 更新受影响测试（test_product_profiles, test_local_coding_profile, test_personal_assistant_profile, test_communication_context_bugfix358, golden tests, bootstrap integration tests）
  6. 注意：`local_store.py` seed 位置已经正确（`.nanoassistant/memory/`），无需修改（decision 14 pre-addressed）
- Rationale: 退役老路径，避免"两条并存路径"迷惑后续 worker；`pa.memory_intro` 指向错误文件路径（workspace root 的 MEMORY.md vs MemoryTool 的 memory_root/MEMORY.md）。
- Evidence:
  - Tests: R6 测试 5 passed；全套 2185 passed
  - Entry: N/A
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: N/A
  - Visual/Interaction: N/A
- Rollback: revert `6e07b59d`（文件删除可通过 `git checkout HEAD~1 -- <file>` 恢复）
- Commits: C1=`64028f60`, C2=`6e07b59d`

### R7 — contract 测试无新 hardcode workspace dirname

- Context: design decision 10 要求建立 contract 测试，防止新 hardcode `.nano`/`.nanoassistant`/`.nanocode` 出现在 product defaults.py 之外的代码中。
- Decision: 新增 `tests/contract/test_no_hardcoded_workspace_dirname.py`，grep `src/agent`, `src/personal_assistant`, `src/coding_cli`，白名单化 pre-existing 合法用法（platform default dirs、docstring 等），新出现的立即报错。
- Rationale: 防回归，让"per-workspace 路径必须走 profile.workspace_config_dirname + derive_memory_root"这个原则有自动化保障。
- Evidence:
  - Tests: contract 测试 1 passed；全套 2186 passed
  - Entry: N/A
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: N/A
  - Visual/Interaction: N/A
- Rollback: revert `3c4b50fd`
- Commits: C1=（included in C2）, C2=`3c4b50fd`
- Next: milestone M1 全部 roadpoint DONE，准备集成到 unit/feat-385 分支
