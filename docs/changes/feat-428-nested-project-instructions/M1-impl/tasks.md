# feat-428-M1: 目录级项目指令自动加载 — Tasks

> 对齐: ../design.md v1

## 目标

外部观察者可见的变化：
- agent 会话启动即自带其 workspace 根 `AGENTS.md`（机制 A，含 @import 展开），无需 operator 手填 / agent 主动 read；空态照常启动。
- agent 经 read 读 workspace 内子目录文件，tool_result 带上链上 `AGENTS.md` 正文（机制 B·内）；读 workspace 外 git 仓内文件，tool_result 带英文路径提示（机制 B·外）；不属任何 git 仓不提示。
- 同一份 AGENTS.md 一会话只生效一次（含机制 A 已注入的根），压缩后清空可重注。
- 关闭 nested_memory（全局 default_on=False）后机制 B 不触发，机制 A 不受影响。

## 退出标准

- [ ] 共享核心 `load_agents_md`（@import 递归+防环+深度上限5+不存在静默忽略+跳代码块）、`find_outermost_git_root`（单次上行找最外层 .git，目录/文件形式）、`iter_agents_md_chain` 落 `agent/core/`
- [ ] 机制 A：PromptContext.agents_md_content + CORE_AGENTS_MD_BLOCK（cache_safe=True，PREVIEW 占位三态）+ skeleton 段位（_SLOT_CUSTOM 后、CORE_MEMORY_BLOCK 前）+ wiring 透传 + runtime 并入 MemorySnapshot（读 AGENTS.md + on_compaction 失效 + 预置根到 loaded_agents_md）
- [ ] 机制 B：feature_registry 加 nested_memory（不进 list_features 白名单 / FEATURE_PROJECTIONS）+ SessionFileState.loaded_agents_md + read.py 注入（内正文 / 外提示，文案逐字照 design，避开 file_unchanged 提前返回，去重）
- [ ] 顺手清 is_path_in_workspace 的失效 TODO(bugfix-355)
- [ ] 新单测覆盖：@import 递归+防环+深度上限、git 外层仓根定界（嵌套仓 e~z）、内外判定、去重一次性（含压缩后清空可重注）、关闭 flag 行为
- [ ] `pytest -m "not e2e"` 全绿 + ruff check + ruff format 净

## 测试策略

> 规范见 docs/TESTING_GUIDE.md。

- 被测行为（来自退出标准）：
  - load_agents_md：@import 展开（@./ @~/ @/abs @rel）、防环、深度上限5、不存在静默忽略、跳代码块内的 @
  - find_outermost_git_root：单次上行取最外层（非最近）仓根；嵌套仓；.git 目录与 .git 文件（worktree）；无 .git 返回 None
  - iter_agents_md_chain：闭区间逐级 yield 存在的 AGENTS.md
  - 机制 A：PromptContext 携带 → CORE_AGENTS_MD_BLOCK 渲染（RUNTIME 出正文 / PREVIEW 出占位 / 空态 None）；skeleton 段位满足 cache_safe 不变量；runtime snapshot 读盘 + on_compaction 失效重读 + 预置根
  - 机制 B：read 工作区内注入正文块、工作区外注入提示块、不属 git 仓不注入、去重一次性、压缩清空后可重注、关闭 flag 不注入
- 已有测试在：核心 helper 无现成文件，新建 `tests/unit/test_agents_md_loader.py`（共享核心）、`tests/unit/test_agents_md_prompt_section.py`（机制 A 段渲染）、`tests/unit/test_nested_memory_read_injection.py`（机制 B read 注入）。runtime snapshot 行为扩展 `tests/unit/` 内现有 runtime 测试或新建窄文件。
- 落层/目录/marker：tests/unit/，无 marker（纯逻辑 + 进程内 read 工具调用，不需 e2e 运行时）
- 可选依赖 importorskip：无
- 本 milestone 产生的一次性验收证据：CLI 真实入口手测（read 工作区内/外文件看 tool_result 带标签）记 progress，不进套件
- 前端：N/A（纯内核改动，无 UI；预览段 enabled_when PREVIEW 恒 True 由段单测覆盖，IM 前端零改动）

## Roadpoints

### R1 — 共享核心：load_agents_md + find_outermost_git_root + iter_agents_md_chain

- 步骤: 新建 `agent/core/agent/agents_md.py`（或合适 core 落点），实现三函数；@import 解析对齐 CC（正则 + 跳 fenced code block + @path/@./@~/@/abs + MAX_DEPTH=5 + Set 防环 + 不存在静默忽略）。
- 验证: `tests/unit/test_agents_md_loader.py` 红→绿，覆盖 @import 递归/防环/深度/不存在/代码块、git 外层定界（嵌套仓 e~z、.git 文件形式）、chain 闭区间。

### R2 — 机制 A：启动注入 system prompt

- 步骤: base.py 加 PromptContext.agents_md_content；core_sections.py 加 CORE_AGENTS_MD_BLOCK（三态渲染，cache_safe=True）；skeleton.py 插段位；wiring.py 透传；runtime.py MemorySnapshot 加字段 + _ensure_memory_snapshot 读 AGENTS.md + 预置根到 loaded_agents_md + _invalidate 清 loaded_agents_md。
- 验证: 段渲染单测（RUNTIME/PREVIEW/空态）；assemble cache_safe 不变量；runtime snapshot 读盘 + compaction 失效；assemble_prompt_preview 出占位。

### R3 — 机制 B：read 触发就近加载 + 收尾门禁

- 步骤: feature_registry 加 nested_memory；SessionFileState 加 loaded_agents_md set + on_compaction 清空已在 R2 接好；read.py 注入逻辑（内/外、去重、避开 file_unchanged、文案逐字）；清 is_path_in_workspace TODO。
- 验证: `tests/unit/test_nested_memory_read_injection.py`（内注入/外提示/空态/不属 git 仓/去重/压缩重注/关闭 flag）；全量 `pytest -m "not e2e"` + ruff check + ruff format；CLI 真实入口手测记 progress。
