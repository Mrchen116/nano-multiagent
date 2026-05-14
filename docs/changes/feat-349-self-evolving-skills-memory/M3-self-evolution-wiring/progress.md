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
- Next: R3 — 两产品接线：toolset + hook 注册 + workspace 配置透传

