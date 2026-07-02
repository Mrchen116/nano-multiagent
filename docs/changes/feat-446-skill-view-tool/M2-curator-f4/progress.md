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
