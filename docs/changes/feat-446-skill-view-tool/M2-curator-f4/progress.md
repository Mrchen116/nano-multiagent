# feat-446-M2 — Progress

## Startup

- Context: 按 `change-impl-worker` full 模式执行，worktree 为 `/Users/czj/Repos/nano-multiagent/.worktrees/feat-446-M2`，分支为 `milestone/feat-446-M2`。
- Evidence:
  - Read: `AGENTS.md`、`SPEC.md`、`CLAUDE.md`、`docs/TESTING_GUIDE.md`、`LOGBOOK.md`、`docs/changes/feat-446-skill-view-tool/spec.md`、`design.md`、`specs/kernel/spec.md`、`specs/gateway/spec.md`、`specs/im/spec.md`、M1 `tasks.md`/`progress.md`、`change-impl-worker/SKILL.md`。
  - Baseline: `PYTHONPATH=src pytest tests/unit/test_skill_view.py tests/unit/test_usage.py tests/contract/test_core_no_platform_imports.py -x` -> 10 passed。

## R1 — curator state machine and archive visibility

- Context: M1 已有 `.usage.json`，但没有消费者；`SkillRegistry` 还会递归发现 `.archive/` 下的 `SKILL.md`，导致 archived skill 无法退出日常候选。
- Decision: 新增 `core/skills/curator.py`，将扫描和执行拆开：`run_curator_scan()` 返回 `CuratorResult` / `CuratorTransition`，`apply_curator_transitions()` 负责写 `.usage.json`、`.curator_state.json` 和执行 `shutil.move`。`SkillRegistry` 默认剪掉 `.archive` 子树。
- Rationale: Curator 放在 core 纯确定性层，不接 LLM、不 import platform；stale 只是 usage state，目录仍留原位所以继续可发现；archived 只有 move 成功才写 state=archived，`.usage.json` 保留审计字段供 M4 dashboard 读取。
- Evidence:
  - Tests: C1 红测 `PYTHONPATH=src pytest tests/unit/test_curator.py tests/contract/test_core_no_platform_imports.py -x` -> 失败，`ModuleNotFoundError: agent.core.skills.curator`；C2 后同命令 -> 6 passed。
  - Entry: `tests/unit/test_curator.py` 覆盖 30 天 F3/F4 stale、90 天 archive 物理移动、F1/F2/unknown 保护、stale recent activity 复活，以及 `.archive/` 默认不被 `SkillRegistry` 发现。
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: R1 是 core 确定性扫描和 skill discovery 行为，永久回归落在 `tests/unit/test_curator.py`；不启动真服务。
  - Visual/Interaction: N/A
- Rollback: revert `36db3f60` and `b962f49e` together to remove R1 implementation/tests.
- Commits: C1=b962f49e, C2=36db3f60, C3=039a09d4
- Next: R2

## R2 — F4 trigger and runtime enqueue dedupe

- Context: M1 的 `bump_skill_usage()` 只更新 counters，没有把 `uses_since_last_B` 越线暴露给 runtime；`skill_view` 也没有 enqueue 能力。
- Decision: `core/skills/usage.py` 新增 `F4Trigger` 纯数据返回和 `reset_uses_since_last_batch()`；`ToolContext` 增加可选 `skill_batch_review_enqueue` 回调；`SkillViewTool` 在成功 bump 后把 trigger 交给该回调，只有 enqueue 返回 true 才 reset；`AgentRuntime.enqueue_skill_batch_review()` 维护 queued/running set 并按 skill name 去重。
- Rationale: core 只产出数据、不 import platform；tool 不直接启动后台任务；runtime 是 per-skill 并发去重的 owner。enqueue 失败或被去重时不 reset counter，避免丢掉后续触发机会。
- Evidence:
  - Tests: C1 红测 `PYTHONPATH=src pytest tests/unit/test_usage.py tests/unit/test_skill_view.py -x` -> 失败，`ImportError: cannot import name 'F4Trigger'`；C2 后同命令 -> 14 passed；`PYTHONPATH=src pytest tests/contract/test_core_no_platform_imports.py -x` -> 1 passed。
  - Entry: `tests/unit/test_usage.py::test_bump_skill_usage_returns_f4_trigger_for_auto_skill_threshold` 覆盖自动 skill 越线返回 trigger；`test_runtime_dedupes_running_or_queued_skill_batch_reviews` 覆盖同 skill queued/running 不并发；`tests/unit/test_skill_view.py::test_skill_view_enqueues_f4_trigger_and_resets_counter` 覆盖 skill_view 成功后即时 enqueue 并 reset；deduped enqueue 不 reset。
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: R2 是内核/tool 执行链路，永久回归落在 usage/skill_view unit tests；不启动真服务。
  - Visual/Interaction: N/A
- Rollback: revert `2f01750b` and `822f6003` together to remove R2 implementation/tests.
- Commits: C1=822f6003, C2=2f01750b, C3=5323b67c
- Next: R3

## R3 — batch review orchestration and housekeeping entrypoints

- Context:
- Decision:
- Rationale:
- Evidence:
  - Tests:
  - Entry:
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression:
  - Visual/Interaction: N/A
- Rollback:
- Commits:
- Next:
