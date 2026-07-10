# bugfix-443-M1 — Progress

## 启动澄清

- M1 milestone 子目录 design-author 未创建（空），worker 建目录 + 写 tasks.md/progress.md。
- 已核对 design「现状分析」行号与基线一致；contract line-pin `runtime.py:208` 在新增 accessor（约 1031 行）之上，不移位（contract 全绿验证）。

## R1 — runtime accessor + subagent 三派发点透传（根因 A）

- Context: bugfix-429 per-run model 机制只覆盖 `kernel.submit → RunsRegistry` 透传链；subagent 自 bugfix-418 起绕过该链直接 `submit_foreground(runtime.run(...))` / `runner.start(...)`，三派发点都不传 model → subagent 新 run 不登记 `_active_run_models`，它和脚下整棵侧链（压缩/fork/hook）全 miss → 回退构造期全局默认。
- Decision:
  - `runtime.py` 加公开 `resolve_run_model(session_id) -> str | None`，读同一张 `_active_run_models` 表（决策1）。
  - `interfaces.py` `BackgroundSubagentRunner.start` + `runtime_runner.py` `RuntimeRunner.start` 加 `model: str | None = None`，透传 `runtime.run(model=model)`（决策3）。
  - `agent.py` 三派发点取父模型透传：后台 `start()`（用 `ctx.session_id`）、前台 `submit_foreground(runtime.run(..., model=))`（用 `ctx.session_id`）、`_resume_subagent` 的 `start()`（用 `parent_session_id`，即活跃的调用 run）。
- Rationale: 派发时父 run 正活跃，`_active_run_models[parent]` 必已登记父模型；沿用 hook/压缩侧链已读的同一张表 = 单一事实源。accessor 返回裸值（决策2），由 `runtime.run` 既有 `model_override or self._model` 单点兜底，不新增报错面。
- Evidence:
  - Tests: 新增 8 个单测全绿。三派发点：`test_{background_launch,resume,foreground}_inherits_parent_run_model`（断言 runner.start / runtime.run 收到 `model="mimo-model"`，且 background 断言 `resolve_run_model` 以 `"parent_1"` 调用）。accessor：`test_resolve_run_model_exposes_active_run_model_mid_run`（input hook mid-run 读到运行模型而非构造默认）+ `test_resolve_run_model_returns_none_for_unknown_or_missing_session`（未登记/None → None）。透传：`tests/unit/test_runtime_runner_model.py`（RuntimeRunner.start 把 model 透传进 runtime.run）。
  - Entry: 真实入口（mimo agent 派发 subagent，proxy 日志验请求模型）= reviewer 轨真栈，design Runbook 已定；worker 轨单测覆盖三派发点拿到父模型的数据流。
  - Frontend State Matrix: N/A（纯内核模型路由）。
  - Browser QA: N/A。
  - E2E/Regression: 全树 `pytest -m "not e2e"` = 3044 passed, 0 failed；contract 129 passed（line-pin 未移位）。
  - Visual/Interaction: N/A。
- 测试桩同步（接口契约增长的必要 fixture 更新，非生产改动）：4 个 `tests/integration/background_tasks/*.py` 的 `_RuntimeStub` 加 `resolve_run_model` + `run(model=)`；`tests/unit/test_runtime_compact_boundary.py` 的 `_FakeCompactionSummarizer.summarize` 加 `model_override`。
- Rollback: `git revert` C2 实现 commit（纯增量：加参数 + 取值透传，无数据迁移）。
- Commits: C1=红测, C2=实现（见 git log bugfix-443/M1）。

## R2 — loop 主动阈值压缩 model_override（根因 B）

- Context: `loop.py:910` 主动阈值压缩调 `summarize()` 漏传 `model_override`，summarizer 用构造期默认 fork 模型而非本 run 模型；runtime 另两个 `summarize()` 调用方（overflow / 手动）已传。这是与 `_active_run_models` 表无关的独立断点——即便根因 A 修好让 subagent `active_model`=父模型，loop 这处仍会用错模型。
- Decision: `loop.py:910` summarize 补 `model_override=(None if self._compaction_settings.summary_model else active_model)`（决策4），`active_model` 已在 `_maybe_compact` 作用域内。
- Rationale: 配了 `summary_model` 时 fork 是固定独立模型（传 None 不覆盖）；没配时 fork 是共享 fork（传 `active_model` 才跟随父 run），与 runtime 1937 处语义对齐（runtime 用派生 bool `_summary_fork_has_dedicated_model`，loop 侧用 settings 更直接、等价）。
- Evidence:
  - Tests: `test_loop_proactive_compaction_uses_run_model_when_no_summary_model`（无 summary_model → `model_override="run-model"`）+ `test_loop_proactive_compaction_keeps_dedicated_summary_model`（配 summary_model → `None`，回归守护现状不变量）。
  - Entry: reviewer 轨真栈验「同 run 内 subagent 触发压缩调用模型一致」；worker 轨单测两态。
  - 其余维度 N/A（非前端）。
- Rollback: 同 R1（一行 model_override 增量）。
- Commits: 与 R1 同 C2（根因 A/B 必须复合修复，单修一处压缩仍可能用错模型，故同 commit）。

## R3 — 全树回归 + contract + 文档

- Evidence:
  - 全树 `pytest -m "not e2e"`: 3044 passed, 2 skipped, 0 failed。
  - contract: 129 passed（`runtime.py:208` line-pin 未移位——新增 accessor 在其下方）。
  - ruff check + format: 全部通过。
- Next: 本 milestone 完成，集成到 unit 分支。

## fix1 — code-review 反馈循环小修（reviewer/verifier pass 后）

走 §FL 小修快车道（复用本 worker 上下文）。三处 fix + 一处 doc，红测先行（行为类 fix 不豁免红测）。

- **C1（CONFIRMED 真 bug）**：`src/agent/platform/background_tasks/wiring.py` 的 `_NoOpSubagentRunner.start`（BackgroundSubagentRunner 第二个实现者）未加 model 参数 → AgentTool 三派发点现都传 `model=` → 无 AgentRuntime 配置的 fallback 路径会 `TypeError: start() got unexpected keyword argument 'model'`，替代 graceful on_fail()，任务卡 RUNNING。修：加 `model: str | None = None`（接受并忽略，仅调 on_fail）。
  - 红测：`test_noop_subagent_runner_start_accepts_and_ignores_model`（start(model="x") 仍正常 on_fail、不 TypeError）。
- **C4（resume 跨 run 边缘）**：`_resume_subagent` 原从 `parent_session_id`（registry-resume 传 `record.parent_session_id`=原始 launcher，可能已结束 → `_active_run_models` 已 pop → None → 回退全局默认）解析 model。修：加 `resuming_session_id` 参数 = `ctx.session_id`（当前活跃 resuming run），model 从它解析；path/grouping/llm_session_id 仍用 `parent_session_id`。
  - 红测：`test_resume_inherits_current_run_model_across_run_boundary`（record.parent_session_id 已不在表→None，但当前 run 在表→子 agent 继承当前 run 模型；并断言 llm_session_id 仍 = launcher）。
- **altitude #3（互斥下沉）**：`None if <dedicated> else override` 三元式原散落 loop.py:910 + runtime `_compact_session`。收口：`CompactionSummarizer(has_dedicated_model)` 内部决定（持独立 fork 则忽略 override），runtime 构造时传 `bool(summary_model)`；loop/runtime 调用点统一只传 active run model。
  - 测试：loop 两态改为「恒传 active_model」（互斥非 loop 职责），dedicated 抑制下沉到 summarizer 层新测 `test_compaction_summarizer_ignores_override_when_fork_is_dedicated`。语义等价，覆盖不减。
- **doc**：`docs/changes/bugfix-429-per-agent-model-selection/verification.md:99` 脚注更正（「所有真实调用方现均传 model_override」在 bugfix-429 收口时不成立，subagent_runner + loop 主动压缩当时未传，已由 bugfix-443 补全）。
- **否决项（未做）**：不把继承下沉到 `_run_locked()` 据 parent_session_id 自动继承——后台 subagent 的 runtime.run 异步执行，父 run 可能在它解析前已 pop `_active_run_models[parent]`→拿到 None；当前「派发时同步捕获 model 显式传入」才是正确设计。
- Evidence: 全树 `pytest -m "not e2e"`（结果见 fix1 集成回报）；contract + ruff 全绿。`reviewer=pass`（真栈实证 subagent 用 mimo）、`verifier=pass` 已在 fix 前取得。
- Commits: fix1 红测 + fix1 实现（见 git log milestone/bugfix-443-fix1）。

## 给 orchestrator 的契约说明

对外行为变更（归 orchestrator 收尾归并 canonical `docs/specs/kernel/spec.md`）：内核为某 run 派发的子 agent（前台/后台/续跑）及该 run 的自动上下文压缩摘要，复用该 run 的 model，不回退内核构造期全局默认（独立 summary_model 优先）。delta-spec 已在 `specs/kernel/spec.md` 写好（design-author 产出），worker 未改 canonical。
