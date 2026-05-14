# feat-349-M3 Progress

## 基线

- 分支：`milestone/feat-349-M3` from `unit/feat-349` HEAD `13349a84`
- M1+M2 产物均已就绪

---

### R1 — self_improvement background hook 模块

- Context: M1 已提供 HookEventMode.BACKGROUND + dispatch_background + fork_conversation 注入；需要一个 builtin hook 模块，在 agent_end 时读 nudge 计数并触发 review fork。
- Decision: 用 closure per-session 字典存 `last_skill_iter`/`last_memory_turn`；delta >= interval 触发对应 review；fork_conversation=None 天然防递归（fork 侧链无 background hook runner）；fork 后 publish_session_event("self_evolution_review")。
- Rationale: hermes-reference §2 的 nudge 设计。delta 而非绝对值确保跨轮累积正确触发。
- Evidence:
  - Tests: `pytest tests/unit/test_self_improvement_hook.py` — 10 passed in 0.14s
  - Entry: N/A（纯逻辑 hook 模块，无 HTTP 入口）
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: 单元测试覆盖所有分支（skip/disabled/threshold/combined/accumulate/event）
  - Visual/Interaction: N/A
- Rollback: C1 commit c2168817
- Commits: C1=c2168817, C2=a24b29b8, C3=TBD
- Next: R2 DONE, 见下

---

### R2 — prompting.py 注入 memory block + SKILLS/MEMORY guidance

- Context: build_system_prompt 已有 skills section 注入，需要补 guidance 常量注入（按工具在 toolset 条件）+ memory_block 参数（volatile 段）。
- Decision: 在 prompting.py 中定义 SKILLS_GUIDANCE / MEMORY_GUIDANCE 常量；build_system_prompt 新增 `memory_block: str | None = None` 参数；检查 available_tools 工具名集合决定注入哪些 guidance。
- Rationale: 与 hermes §6 设计一致：guidance 属 stable tier，memory_block 属 volatile tier，两者不影响 prefix cache 的稳定部分。
- Evidence:
  - Tests: `pytest tests/unit/test_agent_prompting.py` — 16 passed
  - Entry: N/A（纯逻辑函数，无 HTTP 入口）
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: 单元测试覆盖注入/不注入两分支
  - Visual/Interaction: N/A
- Rollback: C1 commit 1fe7357b
- Commits: C1=1fe7357b, C2=e89df315, C3=TBD
- Next: R3 DONE，见下

---

### R3 — 两产品接线：toolset + hook 注册 + bootstrap skill_manage/memory 注册

- Context: SkillManageTool 和 MemoryTool 在 builtin_tools() 中故意不包含（需要路径参数）；两产品 DEFAULT_TOOL_IDS 和 DEFAULT_HOOK_MODULES 未包含自进化相关项。
- Decision: LC + PA toolsets 追加 skill_manage + memory；LC + PA hooks 追加 self_improvement；bootstrap_product() 在 config_resolver 可用时实例化并注册两工具。self_improvement.py timeout_ms 修正为 1500（registry 要求正整数，background 模式实际忽略）。
- Rationale: 工具路径在 bootstrap 时通过 config_resolver 解析，是正确的接线位置，符合"产品 bootstrap 而非 builtin_tools()" 设计。
- Evidence:
  - Tests: 44 passed（含 test_local_coding_profile + test_personal_assistant_profile + test_platform_bootstrap + test_self_improvement_hook）
  - Entry: N/A（profile/bootstrap 单元测试覆盖）
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: 单元测试覆盖注册逻辑
  - Visual/Interaction: N/A
- Rollback: C1 commit 94d55884
- Commits: C1=94d55884, C2=617557ce, C3=TBD
- Next: R4 DONE，见下

---

### R4 — local_store seed 位置迁移 + LC workspace 配置读取

- Context: PA 的 MEMORY.md 之前 seed 在 workspace root；M3 需要 MemoryStore 读 .nanoassistant/memory/MEMORY.md。LC 无用户配置文件机制，需补 workspace 级 config.yaml 读取。
- Decision: ensure_workspace_defaults 将 MEMORY.md + USER.md 迁至 <workspace>/.nanoassistant/memory/；HEARTBEAT.md 留 workspace root。bootstrap_product 读取 workspace config.yaml self_evolution 段，注入 ResolvedProductConfig.default_session_metadata；缺失时全开默认。
- Rationale: MemoryStore 路径由 ConfigResolver.user_memory_root() 确定（.nanoassistant/memory/），seed 要对齐；LC workspace config 入口符合设计决策 7。
- Evidence:
  - Tests: 36 passed（local_store 24 + bootstrap 12）
  - Entry: N/A
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: 单元测试覆盖 seed 路径 + 配置读取
  - Visual/Interaction: N/A
- Rollback: C1 commit 7c808324
- Commits: C1=7c808324, C2=9cd2d801, C3=TBD
- Next: R5 — CLI REPL 渲染 self_evolution_review 事件

