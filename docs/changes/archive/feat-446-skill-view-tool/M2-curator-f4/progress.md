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
- Commits: C1=b962f49e, C2=36db3f60, C3=526ae82d
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
- Commits: C1=822f6003, C2=2f01750b, C3=fb788cf5
- Next: R3

## R3 — batch review orchestration and housekeeping entrypoints

- Context: R2 只把 `F4Trigger` 放进 runtime queued/running set，没有 platform 层消费队列，也没有 CLI/Gateway 启动时的确定性 Curator housekeeping 入口。session JSONL 生产路径是 `<workspace>/<workspace_config_dirname>/sessions/<session_id>.jsonl`，可从 `trigger.skill_root.parent / "sessions"` 反查 transcript。
- Decision: 新增 `agent.platform.background.skill_batch_review`，提供 sync/async 两个入口；过滤已写入 `.curator_state.json` 的 reviewed session、缺失/空 transcript，只在至少 2 个未复盘 session 证据存在时调用 runtime 注入的 background fork callable。fork 调用只传 `tool_allowlist=("skill_view", "skill_manage")`，prompt 明确要求先 `skill_view`、只 `skill_manage(action="patch")`、不得 create/rename/archive/delete/改其他 skill。`AgentRuntime` 将 queued trigger 升级为可 drain 的 trigger dict，SDK 暴露 `run_skill_maintenance()` 和 `run_queued_skill_batch_reviews()`；CLI 打开 session 前跑一次 maintenance，Gateway ready 前对每个 agent workspace 跑 best-effort maintenance。
- Rationale: batch 编排属于 platform，core 只保存 usage/curator 纯数据，满足 core 不 import platform 的边界；F4 触发链路不等待 7 天 Curator，而 deterministic lifecycle housekeeping 仍遵守 Curator 的 7 天 interval。reviewed session id 只在 background fork 完成后写入 `.curator_state.json`，避免少于 2 条证据时误消费证据。
- Evidence:
  - Tests: C1 红测 `PYTHONPATH=src pytest tests/unit/test_skill_batch_review.py -x` -> 失败，`ModuleNotFoundError: No module named 'agent.platform.background'`；C2 后 `PYTHONPATH=src pytest tests/unit/test_skill_batch_review.py tests/unit/test_usage.py tests/unit/test_skill_view.py -x` -> 17 passed；`PYTHONPATH=src pytest tests/contract/test_core_no_platform_imports.py -x` -> 1 passed。
  - Entry: `tests/unit/test_skill_batch_review.py::test_batch_review_skips_when_less_than_two_transcripts` 覆盖少于 2 session 不 fork/不 patch；`test_batch_review_filters_already_reviewed_sessions` 覆盖 reviewed session 不重复采纳；`test_batch_review_invokes_patch_only_background_fork` 覆盖 allowlist 只含 `skill_view`/`skill_manage`、prompt patch-only/no-create、完成后记录 reviewed session ids。
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: R3 是 platform background 编排和启动 housekeeping 接线，永久回归落在 unit/contract；不启动真 Gateway/CLI 服务。
  - Visual/Interaction: N/A
- Rollback: revert `5a4e1ae8` and `70b2deb0` together to remove R3 implementation/tests.
- Commits: C1=70b2deb0, C2=5a4e1ae8, C3=this docs commit
- Next: Final verification

## Exit Criteria Evidence

- 30 天未用的 F3/F4 skill 标记 stale: `tests/unit/test_curator.py::test_curator_marks_idle_auto_skill_stale_after_30_days`。
- stale skill 仍出现在 `<available_skills>` 和 `/skill:` 候选并在统计面板标记 stale: R1 只写 `.usage.json` state=stale，不移动目录；`test_curator_marks_idle_auto_skill_stale_after_30_days` 断言 skill 目录仍存在且 state=stale。候选仍由 registry 发现原目录；M4 dashboard/API 读取同一 usage state。
- 90 天归档到 `.archive/` 后默认退出 `<available_skills>` 和 `/skill:` 候选，但统计面板 archived 过滤视图可审计: `tests/unit/test_curator.py::test_curator_archives_idle_auto_skill_after_90_days_and_registry_hides_archive` 断言目录移动到 `.archive/`、usage state=archived、`SkillRegistry` 不发现 archived skill。
- stale skill 被重新读取后复活: `tests/unit/test_curator.py::test_curator_revives_recently_used_stale_skill` 和 `tests/unit/test_skill_view.py::test_skill_view_updates_usage_sidecar` 覆盖 stale/recent activity active 转换与 skill_view bump 记录 `last_used_at`。
- F1/F2 skill 不被自动流转: `tests/unit/test_curator.py::test_curator_ignores_f1_f2_and_unknown_sources`。
- `skill_view` 成功后 `uses_since_last_B` 越线即 enqueue per-skill 批量复盘，不等待 7 天 Curator: `tests/unit/test_skill_view.py::test_skill_view_enqueues_f4_trigger_and_resets_counter`。
- 同一 skill running/queued 时不并发启动第二个 batch: `tests/unit/test_usage.py::test_runtime_dedupes_running_or_queued_skill_batch_reviews`。
- ≥2 session 证据才采纳: `tests/unit/test_skill_batch_review.py::test_batch_review_skips_when_less_than_two_transcripts` 和 `test_batch_review_filters_already_reviewed_sessions`。
- 只 patch 不创建: `tests/unit/test_skill_batch_review.py::test_batch_review_invokes_patch_only_background_fork` 断言 allowlist 与 prompt 中的 `skill_manage(action="patch")` / `Do not create`。
