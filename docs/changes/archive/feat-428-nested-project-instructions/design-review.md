# Design 评审:feat-428-nested-project-instructions

> 独立评审者视角,只审 design.md 文档质量,不写代码、不验实现。
> 对齐:design.md v1 / spec.md v1 / specs/kernel/spec.md(delta)

**结论**:Approved(含 1 条值得作者权衡的 WARNING,不阻断门禁)

## 核实台账

逐条核过的承重原子;结论附评审者**自己追到的**证据(非 design 替引的行)。

| 原子 | 核实动作 | 结论 + 证据 |
|---|---|---|
| 现状:`assemble_system_prompt` 强制 volatile 段在稳定段后 | 读 base.py 校验逻辑 | ✓ 成立,`_validate_cache_safe_invariant` 在 `base.py:146` 起,违反 raise ValueError |
| 现状:`CORE_MEMORY_BLOCK` 是 cache_safe=False volatile 尾区范例 | 读 core_sections + skeleton | ✓ `core_sections.py:425` cache_safe=False;`skeleton.py:118-122` 排在 _SLOT_CUSTOM 后 |
| 现状:`_render_memory_block` 走 `PromptContext.memory_content` 渲染 | 读 core_sections | ✓ `core_sections.py:403` `ctx.memory_content or ctx.memory_block` |
| 现状:`PromptContext` 持 memory_content 字段、可加新字段 | 读 base.py | ✓ `base.py:86` `memory_content: str\|None=None`,加 `agents_md_content` 同构 |
| 现状:runtime 首轮 `_ensure_memory_snapshot` 读盘冻结、session 级缓存 | 读 runtime | ✓ `runtime.py:1732` lazy freeze + `_memory_snapshots[session_id]`;`agents_md` 可照搬 |
| 现状:runtime 持 `config.workspace_root` 绝对 Path | 追 _run_locked | ✓ `runtime.py:348` `session_workspace_root = config.workspace_root`,透传进 ctx/metadata |
| 现状:`SessionFileState` 是 session 级容器、同一实例可共享 | 追 wiring | ✓ `runtime.py:1706` `_session_file_states.setdefault(...)` → `registry.py:252` 同实例;机制 A 预置/机制 B 读写同 dict 可行(决策 4 风险已自识) |
| 现状:`ToolContext` 有 `session_metadata` + `session_file_state` | 读 base.py | ✓ `base.py:140/142`,`with_session` 透传(`registry.py:252`) |
| 现状:`ctx.repo_root` 被重写为 workspace_root | 读 `_resolve_execution_context` | ✓ `registry.py:586-598` `repo_root=resolved_cwd(=cwd metadata=workspace_root)`,决策 2 锚点成立 |
| 现状:`is_path_in_workspace(resolved)` 锚 repo_root | 读 safety | ✓ `safety.py:107` `resolved.relative_to(self.repo_root)` |
| **现状:read 允许读 workspace 外文件**(机制 B 外部前提) | 读 read.py 边界 | ✓ `read.py:160` 注释「bugfix-355: boundary check removed — read is allowed from any path」——外部场景可触发,前提成立 |
| 现状:FEATURE_REGISTRY 是 TypedDict、加条目模式 | 读 feature_registry | ✓ `FeatureEntry(TypedDict)`;design 的 `["default_on"]` 下标写法正确(非 dataclass) |
| **现状:`list_features()` 显式只报 memory_curation/skill_creation(白名单)** | 读 kernel | ✓ `kernel.py:1128` `if key not in ("memory_curation","skill_creation"): continue`——加 nested_memory 不自动冒 toggle,决策 5 核心前提成立 |
| **现状:FEATURE_PROJECTIONS 是独立 opt-in 表** | 读 capability_projection | ✓ `capability_projection.py:77` 硬编 4 条;不投影 nested_memory,PA 前端无 toggle,决策 5 成立 |
| 现状:agent_features 是 feature flag metadata 键 | 追 wiring + kernel | ✓ `wiring.py:143` `metadata.get("agent_features")`;`kernel.py:755` create_session 注入,默认走 registry default_on |
| 现状:read.py(platform)可 import core FEATURE_REGISTRY | 读 read.py imports + 依赖规则 | ✓ platform→core 允许;read.py 已 import `agent.core.tools.base` |
| 现状:core 做文件 IO 有先例 | 找 MemoryStore | ✓ `core/memory/store.py` 在 core 读盘,`load_agents_md` 同层落点成立 |
| 决策 1:机制 A 注 system prompt | 拍死?有据? | ✓ 拍死,spec Q5 驱动;但 cache_safe 选择见 WARNING |
| 决策 2:内/外边界 = is_path_in_workspace | 自洽?锚点对? | ✓ 锚 repo_root(=workspace_root),与机制 A 同源 |
| 决策 3:注 read tool_result content blocks | 拍死?数据流闭合? | ✓ 当轮即生效,去重集合在 ToolContext 手边 |
| 决策 4:去重 = SessionFileState.loaded_agents_md | 实例一致性? | ✓ 同 session 同实例(runtime `_session_file_states`),风险已自识 |
| 决策 5:不投影、全局关 | 与现状分层对齐? | ✓ 上两行白名单/projection 证据支撑 |
| 决策 6:不截断 + @import | 对齐 CC、作用域清晰? | ✓ 仅注入内容路径生效,外部提示不展开;深度 5 + 防环 |
| 决策 7:单次上行定最外层 git 根逐级收 | 语义/复杂度自洽? | ✓ O(深度) 单趟,等价逐级判属,覆盖嵌套仓 |
| spec 全 13 Scenario | 逐条找落点 | ✓ 机制A(根/空态/两产品/@import)、机制B内(子目录/空态/去重)、机制B外(命中/多份/无正文/边界/去重)、关闭(不触发/A不受影响)均有对应决策/接口落点 |
| delta-spec kernel ADDED 用法 | 锚 canonical?THEN 可观察? | ✓ 现状无任何项目指令注入(spec Q5),真·新增用 ADDED 正确;THEN 全为消费者可观察(系统提示含内容/工具结果含文本),无内部符号断言 |
| delta im/gateway/cli「no spec delta」 | 是否合理 | ✓ 开关不投影,PA 对外无新字段;CLI 行为变化由 kernel delta 覆盖 |
| 非目标(add-dir/CLAUDE.md/bash 触发/外部全文/截断) | design 有无越界 | ✓ 全部尊重,无夹带 |
| M1 单 milestone | 垂直 vs 横切 | ✓ 垂直端到端,机制 A/B 共享核心无法真并行,举证充分(<800 行/无分阶段) |

## Issues

- **[WARNING] [决策 1 / 接口·机制 A]**:`CORE_AGENTS_MD_BLOCK` 选 `cache_safe=False`(volatile 尾区),理由仅「照 `_render_memory_block` 范例」。但 `memory_block` 之所以 volatile 是因 MEMORY.md 会被 compaction 改;而 AGENTS.md 是**首轮冻结、整 session 不变**的静态文档,且决策 6 明确**不截断**(可能很大)。把一份大而恒定的文档放进**不进前缀缓存**的 volatile 尾区,每轮都未命中地重发,直接打在本项目「稳定前缀越长越好」的缓存取向上。它更应是 `cache_safe=True`、落在稳定前缀(与 `_SLOT_CUSTOM` 自定义指令同区)。
  - **不改的下游坏事**:静态大文档逐轮挤出缓存,token/延迟回归。
  - **建议**:复核此处 cache_safe 取值;若确有必须 volatile 的理由,在决策 1 补一句说明。

## Recommendations(不阻断门禁,作者自行取舍)

- `safety.is_path_in_workspace` 带 `TODO(bugfix-355): ...only used by test code. Remove when...`——机制 B 决策 2 会让它重新成为生产代码,worker 落地时顺手清掉这条已失效的 TODO。
- 决策 5 的 `requires_tool="read"` 在 read.py 直读 `default_on` 的取数路径里不产生任何运行时 gating(纯文档性),可保留,但别让 worker 误以为它起开关作用。
- 机制 B 注入点需避开 `read.py:187` 的 `file_unchanged` 提前返回路径——属 worker 实现细节,design 无需改,提示一句即可。

## 路由建议

可放心进 `change-orchestrator`。唯一一条 WARNING(机制 A 的 cache_safe 取值)建议回 `change-design-author` 顺手定夺,不构成阻断。
