# feat-428-M1 — Progress

<!-- 每个 roadpoint 完成后实时追加。 -->

## R1 — 共享核心 agents_md

- Context: 机制 A/B 都要读 AGENTS.md（含 @import）、机制 B·外要定最外层 git 仓根并逐级收 AGENTS.md。仓内无现成 helper。
- Decision: 新建 `src/agent/core/agent/agents_md.py`，三函数纯 core（仅 pathlib/re）：
  - `load_agents_md(path, *, _seen, _depth)`：读正文 + 行扫描跳 fenced code block（```/~~~）后用 CC 同款正则 `(?:^|\s)@((?:[^\s\\]|\\ )+)` 提 @import，解析 @path/@./@~/@/abs，深度上限 5、Set（绝对路径）防环、不存在静默忽略，展开正文用 `\n\n` 拼接。
  - `find_outermost_git_root(start_dir)`：单次上行到文件系统根，记录最高一层含 `.git`（`.exists()` 覆盖目录与文件两形态）者 = 最外层仓根；无则 None。
  - `iter_agents_md_chain(file_dir, *, top)`：[file_dir … top] 闭区间逐级 yield 存在的 AGENTS.md（nearest-first）。
- Rationale: CC 用 marked Lexer；本仓无等价库，轻量行扫描跳代码块对齐 CC "leaf text only"语义且零新依赖（已报 team-lead）。@import 正则/MAX_DEPTH=5/Set/路径判定逐字核对 CC claudemd.ts 源码。最外层（非最近）仓根 + 单次上行 = design 决策 7。
- Evidence:
  - Tests: `tests/unit/test_agents_md_loader.py` 16 passed（@import 相对/绝对/裸路径/缺失/代码块```与~~~/防环单次/深度上限5；git 无/单仓/.git 文件 worktree 形态/嵌套仓取最外层；chain 范围内存在项/全空）
  - Entry: N/A（纯逻辑 helper，入口验证在 R2/R3 机制层）
  - Frontend State Matrix / Browser QA / Visual: N/A（无 UI）
  - E2E/Regression: N/A（纯单元逻辑，无 e2e 依赖）
- Rollback: 回退到 R1 C1（test commit）即移除实现。
- Commits: C1=test 红测, C2=feat 实现, C3=本段
- Next: R2 机制 A。
- 接管补丁（换 worker 续跑）: orchestrator 要求校核 load_agents_md 跳行内 code span。校核结论 R1 已正确处理（`_CODESPAN_RE` agents_md.py:43 + 93，行内 `@foo` sub 成空格后再提 import），仅缺针对性测试 → 补 `test_import_inside_inline_code_span_not_expanded`（17 passed）。Commit: test(feat-428/M1/R1)。

## R2 — 机制 A：启动注入 system prompt

- Context: 把会话 workspace 根 AGENTS.md（@import 展开）注入 system prompt 稳定前缀末尾，默认恒开、无开关。
- Decision:
  - `base.py` PromptContext 加 `agents_md_content: str | None`。
  - `core_sections.py` `CORE_AGENTS_MD_BLOCK`（cache_safe=True，三态：PREVIEW 出 `<project-instructions>` 包 `<运行时注入：工作区 AGENTS.md>` 占位 / RUNTIME 有内容出 `<project-instructions>` 包正文 / RUNTIME 空 → None），加入 CORE_SECTIONS 导出。
  - `skeleton.py` 插在 `_SLOT_CUSTOM` 之后、`CORE_MEMORY_BLOCK` 之前（稳定前缀末尾，满足 cache_safe 不变量）。
  - `wiring.py` 透传 `agents_md_content`。
  - `runtime.py` MemorySnapshot 加 `agents_md_content` 字段；新 `_read_workspace_agents_md`（读 `workspace_root/AGENTS.md` + @import 展开 + 把根绝对路径预置进 `SessionFileState.loaded_agents_md`，用 `setdefault` 拿与 read.py 同一实例）；三分支快照都带 agents_md_content（AGENTS.md 读盘独立于 memory_curation flag / workspace_config_dirname）；`_invalidate_memory_snapshot`（挂 on_compaction）失效快照 + 清空 loaded_agents_md。
  - `session_file_state.py` 加 `loaded_agents_md: set[str]`（机制 A/B 共享去重集）。
  - import 改 `from agent.core.agent import agents_md as agents_md_loader`（模块级）避开 contract 的 `agent.agent` 子串误判（`agent.agents_md` 含该子串）。
- Rationale: 决策 1（cache_safe=True 按变化画像归稳定前缀）、决策 4（同一 SessionFileState 实例 + 预置根）、并入 MemorySnapshot 生命周期复用既有压缩刷新点。预览照 memory 三态自动出占位，assemble_prompt_preview 零改动。
- Evidence:
  - Tests: `test_agents_md_prompt_section.py`（段三态/cache_safe/skeleton 段位/wiring 透传）+ `test_agents_md_runtime_snapshot.py`（读盘/@import 展开/预置根/空态/失效清空），13 passed；prompt+golden+preview 相关回归 214 passed。
  - Entry: N/A（入口手测留 R3 收尾）。
- Rollback: 回退 R2 C1。
- Commits: C1=test 红测, C2=feat 实现。
- Next: R3 机制 B。

## R3 — 机制 B：read 触发就近加载 + 收尾门禁

- Context: read 工具读文件后按目录链就近带 AGENTS.md（内注入正文 / 外路径提示），nested_memory 默认开。
- Decision:
  - `feature_registry.py` 加 `nested_memory`（default_on=True, layer=core, requires_tool=read, sections=()）；不进 FEATURE_PROJECTIONS（capability_projection 硬编码 tuple 不含它）、不进 list_features 白名单（kernel.py:1128 只放 memory_curation/skill_creation）→ 内核认得、默认开、用户无 toggle。
  - `read.py` `_nested_memory_blocks`：`is_path_in_workspace(file_path.resolve())` 判内外（ctx.repo_root 已被 registry 重写为 workspace_root）；内→`iter_agents_md_chain(file_dir, top=repo_root)` 逐级 `load_agents_md`（@import）出 `<project-instructions path=>`；外→`find_outermost_git_root` 定界 + `iter_agents_md_chain` 逐级列路径出 `<project-instructions-hint>`（英文，文案逐字照 design「注入文案」段，不含正文）；去重靠 `loaded_agents_md`。`nested_blocks` 在 file_unchanged 检查**前**算一次，有待注入则不走 file_unchanged 短路（避开提前返回，支持压缩清空后重注）；image read 同样追加。
  - `safety.py` 清 `is_path_in_workspace` 失效 TODO(bugfix-355)（决策 2 让它重回生产路径）。
  - contract 白名单 `runtime.py:180→185`（机制 A 加字段位移）。
- Rationale: 决策 2/3/5/7；文案逐字照 design.md。file_unchanged 提前返回路径是 design Worker 注意第 3 条钉死的坑。
- Evidence:
  - Tests: `test_nested_memory_read_injection.py` 13 passed（内注入/空态/根去重/同会话去重/压缩重注/外提示/嵌套仓全列/非 git 不提示/外去重/关闭 flag 内外/默认开/registry 条目）；read+contract 回归 157 passed。
  - Full suite: `pytest -m "not e2e"` 2815 passed, 0 failed, 1 skipped；ruff check + ruff format 净。
- Rollback: 回退 R3 C1。
- Commits: C1=test 红测, C2=feat 实现, C3=docs（delta-spec kernel + 本段）。
- Next: DONE。
