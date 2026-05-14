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
- Next: R2 — prompting.py 注入 memory block + SKILLS/MEMORY guidance

