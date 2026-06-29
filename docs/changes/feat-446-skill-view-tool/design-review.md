# Design 评审: feat-446-skill-view-tool

**结论**: Issues Found

---

## 核实台账（逐条核过的承重原子）

### 现状断言

| 断言 | 核实动作 | 结论 + 证据 |
|---|---|---|
| skill_manage 当前有 7 个 action 含 view | 读 skill_manage.py | ✓ `_SUPPORTED_ACTIONS` 含 7 个：create/edit/patch/view/list/write_file/remove_file（skill_manage.py:27-29） |
| formatter.py 引导用 read 读 SKILL.md | 读 formatter.py | ✓ `SKILLS_GUIDANCE` 明确写 "Use the read tool to load a skill's file"（formatter.py:8-13） |
| self_improvement tool_allowlist 硬编码 skill_manage | 读 self_improvement.py | ✓ `tool_allowlist = ("skill_manage",)` 直接硬编码（self_improvement.py:209-217） |
| kernel.py 注册 SkillManageTool | 读 kernel.py | ✓ `_register_self_evolution_builtins()` import + register SkillManageTool（kernel.py:564-597），经 `build_kernel() → _build_kernel_base()` 生产路径 |
| CORE_SKILLS_GUIDANCE 用 has_tool("skill_manage") 门控 | 读 core_sections.py | ✓ `_skills_guidance_enabled` 检查 `ctx.has_tool("skill_manage")`（core_sections.py:247-251） |
| feature_registry skill_creation requires_tool="skill_manage" | 读 feature_registry.py | ✓ `requires_tool="skill_manage"`（feature_registry.py:62-69），字段类型 `str | None` |
| coding_cli DEFAULT_ENABLED_TOOLS 含 skill_manage | 读 product.py | ✓ 列表含 `"skill_manage"`（coding_cli/product.py:56-65），经 `create_session(enabled_tools=...)` 生产路径 |
| PA DEFAULT_TOOL_IDS 含 skill_manage | 读 personal_assistant/product.py | ✓ 列表含 `"skill_manage"`（personal_assistant/product.py:67-78），经 `resolve_enabled_tools()` 生产路径 |
| PA reporter PA_DEFAULT_TOOL_IDS 含 skill_manage | 读 capability_projection.py | ✓ tuple 含 `"skill_manage"`（capability_projection.py:39-50） |
| session metadata 有 workspace_root + workspace_config_dirname | 读 session/models.py | △ 部分成立：`workspace_root` 是 Session 一等字段（models.py:21），`workspace_config_dirname` 存在 `metadata` dict 中非一等字段 |
| SkillRegistry 有 list_skills / find_skill | 读 registry.py | ✗ `list_skills` 存在（registry.py:26），**`find_skill` 不存在**。查找需手动 `next((s for s in skills if s.name == name), None)`（skill_manage.py:433） |
| atomic_write + fcntl.flock 在 core/utils/fileio.py | 读 fileio.py | ✗ `atomic_write` 存在（fileio.py:16，tempfile+fsync+os.replace），**`fcntl.flock` 完全不存在**。无文件锁机制 |
| compaction 用 compact_boundary JSONL entry + summary turn | 读 runtime.py + jsonl_store.py | ✓ runtime 写 `compact_boundary` + summary turn（runtime.py:2099-2127），jsonl_store 只保留 boundary 后的 turns（jsonl_store.py:236-269） |

### 决策

| 决策 | 核实动作 | 结论 + 证据 |
|---|---|---|
| 决策 1: skill_view 独立工具 | 四问 | ✓ 拍死、无歧义、无矛盾、有 spec 驱动（Q1） |
| 决策 2: 使用统计数据模型 | 四问 | ✓ 拍死、无歧义、无矛盾、有 spec 驱动（Q4/Q10） |
| 决策 3: Compaction 存活机制 | 四问 | ✗ 拍死但有歧义：`_message_to_entry` 白名单未提及需加 `is_skill_reinjection`（runtime.py:2306-2339 只白名单特定 metadata key），worker 可能遗漏导致 re-injection 失效 |
| 决策 4: Curator 状态机 | 四问 | ✗ 两处问题：(1) activity 定义正文只说"30 天未用"，伪代码写 `max(last_used_at, created_at)`，worker 可能只读正文；(2) spec 说"归档前先打 tar.gz 快照"，design 决策 4 直接拒绝改为 `shutil.move`，spec/design 矛盾未标注 |
| 决策 5: Curator 存储 | 四问 | ✓ 拍死、无歧义、无矛盾、有 spec 驱动 |
| 决策 6: Feature gate 策略 | 四问 | ✗ 拍死但有遗漏：`feature_registry.py` 的 `requires_tool` 类型是 `str | None`（feature_registry.py:26-35），不支持 OR 逻辑。design 说"改为检查两个工具"但没说怎么改。渲染文案也需条件处理（只有 skill_view 在场时不应引导调 skill_manage） |
| 决策 7: F4 Batch 触发 | 四问 | ✗ 拍死但有歧义："异步执行"机制未定义（asyncio task / threading / 顺序执行？），uses_since_last_B 重置与 batch 启动的顺序关系未文档化 |
| 决策 8: skill_view 工具接口 | 四问 | ✗ 自相矛盾：`is_concurrency_safe = True` 声称"只读，不写文件"，但 run 方法第 4 步 `bump_use()` 写 .usage.json |

### spec 约束

| Requirement | 核实动作 | 结论 + 证据 |
|---|---|---|
| skill_view 独立只读工具 | design 有落点 | ✓ 决策 1+8 覆盖 |
| skill_manage 不含 view action | design 有落点 | ✓ 决策 1 + 现状分析表覆盖 |
| 使用统计追踪 | design 有落点 | ✓ 决策 2 覆盖，/skill 路径通过 formatter 引导统一指向 skill_view |
| 压缩存活 | design 有落点 | ✓ 决策 3 覆盖 |
| Curator 生命周期管理 | design 有落点 | ✓ 决策 4 覆盖 |
| session 引用记录 | design 有落点 | ✓ 决策 2 覆盖 |
| F2 蒸馏 skill | design 有落点 | △ M4 覆盖但退出标准偏薄，未描述 PA/agent 级 skill_root 选择行为 |
| F4 Batch 优化 | design 有落点 | ✓ 决策 7 覆盖 |
| 系统提示词引导 skill_view | design 有落点 | ✓ 决策 6 + formatter 改动覆盖 |
| 使用统计面板 | design 有落点 | ✓ M5 + 前端原型覆盖 |
| 所有引用点迁移 | design 有落点 | ✓ 现状分析表逐文件列出 |

### delta-spec 条目

| 条目 | 核实动作 | 结论 + 证据 |
|---|---|---|
| kernel: ADDED skill_view | 读 delta-spec + kernel spec | ✗ 遗漏：kernel spec 第 393 行内置工具列表需加入 skill_view，第 440 行结构化 detail 列表需加入 skill_view。delta-spec 只覆盖了工具可用 + skill_manage 移除 view，漏了两处列表更新 |
| kernel: MODIFIED skill_manage action | 读 delta-spec | ✓ MODIFIED 用法正确，Scenario THEN 无内部实现泄露 |
| im/gateway/cli: no spec delta | design 声明 | ✓ 合理：面板是前端展示层，不改对外行为契约 |

### milestone

| milestone | 核实动作 | 结论 + 证据 |
|---|---|---|
| M1 skill-view-core | 垂直 vs 横切 | ✓ 端到端：新工具 + 统计 + compaction + 迁移，可独立验收 |
| M2 curator | 依赖 M1，垂直 | ✓ 端到端：状态机 + 扫描 + 归档 + 复活，可独立验收 |
| M3 f4-batch | 依赖 M1，垂直 | △ 端到端但 F4 分析流程选型未完成（spec 说"留 design 阶段"），M3 退出标准不够具体 |
| M4 f2-distill | 无依赖，垂直 | △ 独立但退出标准偏薄（只一句"蒸馏 skill 可用"），未覆盖写入行为 |
| M5 dashboard | 依赖 M1，垂直 | ✓ 端到端：三视图 + npm test 全绿 |
| 并行组 A(M1+M4) 范围无交集 | 检查文件范围 | ✓ M1 改 agent 核心，M4 只产出 SKILL.md 文件 |
| 并行组 B(M2+M3) 范围无交集 | 检查文件范围 | ✗ M2 和 M3 都改 `agent/curator.py`（M2 新建，M3 扩展 check_f4_triggers），worktree 并行会撞 |

---

## 架构进攻（四角度逐个走）

| 角度 | 攻的对象 | 发现 + 长远代价 |
|---|---|---|
| 归属 | Curator 放 `agent/` 根目录 | ✗ 根目录不属于 core/platform/sdk 任何一层，违反分层硬规则。Curator 读 .usage.json（core）+ shutil.move（文件系统）+ F4 batch 调 LLM（platform）。应放 `core/skills/curator.py`（确定性扫描）或 platform（含 LLM 调用）。长远代价：维护者无法从目录判断 import 规则，F4 LLM 调用可能拉 platform 依赖进根目录 |
| 归属 | usage.py 引入 flock | △ `core/utils/fileio.py` 无 flock，design 说"复用 MemoryStore 模式"但 MemoryStore 也无 flock。usage.py 需自行实现或下沉 platform。长远代价：core 层引入 OS 特定机制 |
| 归属 | F4 batch job LLM 注入 | ✗ 决策 7 未明确 F4 batch job 的 LLM client 注入路径。hermes 走 fork 机制。本项目若在 Curator 里直接调 LLM，拉 platform 依赖进根目录 |
| 该不该存在 | .curator_state.json 独立文件 | △ "避免锁竞争"理由不成立（Curator 7 天一次 vs usage 每次调用，概率极低）。多一个文件增加管理成本。应补充损坏回退方案 |
| 该不该存在 | is_skill_reinjection 标记 | △ JSONL 存完整 skill content（单 skill ≤ 2000 tokens）会膨胀。可接受 tradeoff 但应明确增长上限 |
| 深还是浅 | _resolve_writer_registry 复用 | ✗ skill_manage._resolve_writer_registry() 是私有方法（30 行），design 说"复用"但没说怎么复用。不提取共享函数 → worker 复制 → 维护漂移 |
| 深还是浅 | Compaction 注入机制 | ✓ 合理 first step。通用化（register_compaction_survival_provider）可留后续 |
| 治本还是补丁 | requires_tool or 链 | ✗ `FeatureEntry.requires_tool` 类型 `str | None`，or 链是临时补丁。应改为 `requires_any_tool: tuple[str, ...] \| None`。长远代价：再加 skill 工具又要改 or 链 |
| 治本还是补丁 | session_refs cap 50 | ✗ cap 和 F4 阈值 20 无数学关系。F4 阈值改为 100 时 cap 不够。应 `cap = threshold * K` 或改 append-only JSONL |

---

## Issues

- **[CRITICAL] [Milestone 表] M2+M3 并行组范围交集**：M2（curator 新建）和 M3（curator 扩展 check_f4_triggers）都改 `agent/curator.py`，worktree 并行会撞文件。退回合并为单 M 或重新划分范围使文件不重叠。

- **[CRITICAL] [现状分析] Curator 归属违反分层硬规则**：design 说放 `agent/curator.py`（根目录），但项目三层架构 core→platform→sdk，根目录不属于任何一层。Curator 涉及 core（读 .usage.json）+ platform（F4 LLM 调用），放在根目录会导致 import 方向无法约束。退回明确归属层：`core/skills/curator.py`（确定性扫描）+ platform 层 F4 runner（LLM 调用）。

- **[CRITICAL] [现状分析] fcntl.flock 不存在**：design 说 usage/curator 持久化"复用 atomic_write + fcntl.flock（MemoryStore 模式）"，但 `core/utils/fileio.py` 只有 atomic_write，无 flock，MemoryStore 也无 flock。worker 按 design 实现会找不到 flock 基础设施。退回：要么在 fileio.py 补 flock helper，要么明确 usage.py 自行实现（需在 design 中说明），要么取消 flock 依赖（risk 3 说"并发低"可能不需要）。

- **[CRITICAL] [现状分析] find_skill 方法不存在**：design 说复用 `SkillRegistry.find_skill()`，但实际只有 `list_skills()`。worker 按 design 调 `find_skill()` 会 AttributeError。退回修正为 `list_skills()` + 手动过滤，或在 design 中说明需新增该方法。

- **[CRITICAL] [delta-spec] 遗漏 kernel spec 内置工具列表更新**：kernel spec 第 393 行内置工具列表和第 440 行结构化 detail 列表需加入 skill_view。delta-spec 只覆盖了工具可用 + skill_manage 移除 view，漏了两处列表。退回补 MODIFIED 条目。

- **[WARNING] [决策 3] _message_to_entry 白名单未覆盖 is_skill_reinjection**：runtime.py:2306-2339 的 `_message_to_entry()` 只白名单特定 metadata key。worker 不检查此函数则 `is_skill_reinjection` 不会被写入 JSONL，resume 时无法识别 re-injection 消息，invoked skills 丢失。退回在 design 中明确需修改 `_message_to_entry` 白名单。

- **[WARNING] [决策 4] tar.gz 快照 spec/design 矛盾**：spec 用户场景说"归档前先打 tar.gz 快照（best-effort）"，design 决策 4 直接拒绝改为 `shutil.move`。两个文档矛盾，worker 不知按哪个。退回对齐：要么改 spec 删 tar.gz，要么 design 恢复快照。

- **[WARNING] [决策 4] activity 定义正文与伪代码不一致**：决策 4 正文说"30 天未用"，Curator 扫描流伪代码写 `last_activity = max(last_used_at, created_at)`。worker 只读正文可能漏掉 created_at 兜底。退回在正文显式写明 `last_activity = max(last_used_at, created_at)`。

- **[WARNING] [决策 6] feature_registry requires_tool 不支持 OR 逻辑**：`FeatureEntry.requires_tool` 类型是 `str | None`，design 说"改为检查两个工具"但没说怎么改。or 链是临时补丁。退回明确机制：扩展类型为 `requires_any_tool: tuple[str, ...] | None`，或在 `_skills_guidance_enabled` 里显式 hardcode 并注释原因。

- **[WARNING] [决策 6] 渲染文案未条件化**：`_render_skills_guidance` 仍然引导调 skill_manage（"save with skill_manage"）。当只有 skill_view 在场而 skill_manage 不在时，模型会尝试调不存在的工具。退回说明是否需要条件渲染不同文案。

- **[WARNING] [决策 7] "异步执行"机制未定义**：batch job 是 asyncio task / threading.Thread / 顺序执行？未说明。影响 Curator 是否等 batch 完成再 save_state，以及 batch 失败时 uses_since_last_B 已重置的数据丢失风险。退回明确机制。

- **[WARNING] [决策 8] is_concurrency_safe 声明自相矛盾**：`is_concurrency_safe = True` 声称"只读，不写文件"，但 run 方法第 4 步 bump_use() 写 .usage.json。worker 可能误判并发行为。退回改为 False（与 skill_manage 一致）或保留 True 但显式说明 flock 保证并发安全。

- **[WARNING] [Milestone M3/M4] 退出标准不够具体**：F4 分析流程选型（spec 说"留 design 阶段"）未完成；M4 退出标准只一句"蒸馏 skill 可用"，未覆盖 PA/agent 级 skill_root 选择。退回补全。

- **[WARNING] [归属] _resolve_writer_registry 复用方式未明确**：skill_manage._resolve_writer_registry() 是私有方法，design 说"复用"但没说怎么复用。退回明确提取为共享函数或说明复用路径。

- **[WARNING] [归属] F4 batch job LLM 注入路径未明确**：batch job 需要 LLM client，Curator 在根目录无法合法 import platform 层。退回明确走 runtime.fork_conversation 还是参数注入。

- **[WARNING] [治本] session_refs cap 50 与 F4 阈值无数学关系**：cap 应绑定阈值（如 `threshold * 3`），否则 F4 阈值改大后 cap 不够。退回修正 cap 计算方式。

---

## Recommendations（不阻断门禁）

- Curator 状态机图（决策 4 的 ASCII 图）缺少 `archived → active` 的 restore 路径（纯手动），可在图上标注 "manual restore only"。
- `.curator_state.json` 损坏的回退方案未提及（risk 3 只提 .usage.json），建议补充。
- compaction 注入的 token 上限（8000）应该可配置，避免不同部署环境的 token 预算差异。
- `FeatureEntry.requires_tool` 扩展为 `requires_any_tool` 是 feature_registry 层的通用改进，不仅服务于本 unit，建议作为 M1 的一部分一并处理。

---

## 复核建议

回到 `change-design-author` 修以下 4 处 CRITICAL + 重点 WARNING：
1. **M2+M3 并行组范围交集** — 合并或重新划分
2. **Curator 归属层** — 从根目录移到 core/skills/ 或拆分
3. **fcntl.flock 不存在** — 补基础设施或取消依赖
4. **find_skill 不存在** — 修正复用声明
5. **delta-spec 遗漏** — 补 kernel spec 内置工具列表 MODIFIED
6. **_message_to_entry 白名单** — 补说明
7. **tar.gz spec 偏差** — 对齐 spec 和 design

修完后可进 `change-orchestrator`。
