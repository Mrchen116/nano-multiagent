# bugfix-525-M3 — Progress

## Readback 与基线

- Baseline: `68707b70363282feb2a238aacbe0ed48c18b18cb`，`milestone/bugfix-525-M3` 从 synced `origin/unit/bugfix-525` 创建；worktree 初始 clean。
- Readback: 完整读取 current `incident.md`、`design.md`、全部 M3 delta-spec、canonical Kernel/Gateway/CLI specs、`AGENTS.md`、coding/testing/evidence/worktree runtime 规范，以及 design 范围内生产实现和既有测试。
- Scope: true update receipt、opaque trace propagation、manager per-run route、existing external sender 双投、CLI projection、专用 Feishu 验收；不重开 M1 raw event policy/Skill owner，不改 IM schema/UI 或普通 background Agent 输出。
- Baseline gate: `PYTHONPATH=src /Users/czj/Repos/nano-multiagent/.venv/bin/python -m pytest -m 'not e2e' -n 4 --dist worksteal --durations=20 --durations-min=0.5` → `3203 passed, 28 warnings in 235.59s`。

## R1 — 真实更新回执与 Kernel trace

- Context: 旧 hook 用“本轮 review 了什么”代替“什么真实写成功”，因此 no-save/read/failure 也发布 updated notice；`RunRecord.trace_id` 未进入 `TurnRequest`/HookContext。
- Decision: 按 call id 关联 `TurnResult.tool_calls/tool_results`，只认可批准的八类 mutating action、无 `error` 且 structured `success` 不为 false；仅非空真实目标发布兼容投影和 `originating_trace_id`。同一 trace 由 registry 经 `TurnRequest` 进入当前 turn HookContext。
- Rationale: 写入事实由工具结果拥有，review 范围不能证明 side effect；opaque run trace 是既有跨层 correlation seam，不引入 channel 数据。
- Evidence:
  - Tests: 红测 `7 failed, 1 passed`，分别缺 updated targets/trace、no-write gate 与 TurnRequest trace；Green focused/affected `39 passed in 5.87s`。
  - Entry: public Kernel integration 真实执行 `memory(add)`、`skill_manage(create)`，持久文件存在、raw assistant/tool/turn 私有，review event 携带 submit 的 exact trace 与真实 target。
  - Frontend State Matrix: N/A。
  - Browser QA: N/A。
  - E2E/Regression: `tests/integration/test_self_evolution_output_visibility.py`；更高真栈在 R4/R5。
  - Visual/Interaction: N/A。
  - Prototype Comparison: N/A。
- Rollback: revert `b577820a7`。
- Commits: `b577820a7`。
- Next: R2 manager/coordinator per-run route 生命周期。

## R2 — 精确 per-run route 生命周期

- Context: persistent subscriber 跨多轮长驻，原实现捕获首次 `request.reply_context`；共享 Kernel session 在飞书/shadow 交替与 review overlap 时会串到旧目标。
- Decision: manager 维护最多 4096 项 `trace_id -> ReplyContext` oldest-first 表，notice 只按 `originating_trace_id` 原子消费一次；缺失/重放 fail-closed。coordinator 在同步 submit 前注册并传同一随机 trace，submit 抛错立即撤销。
- Rationale: 本轮 admission 是路由事实 owner；注册先于 submit 覆盖 fast review，消费后删除同时避免 replay 重复。未触发 review 的 route 只由固定容量淘汰，不读取首次或 latest binding 猜测。
- Evidence:
  - Tests: 红测 `5 failed`（manager 无 route API、submit 未传 trace/未撤销）；Green manager/coordinator/SDK affected `28 passed in 6.91s`。
  - Entry: coordinator public dispatch 测试从真实 binding 构造 ReplyContext，观察 register 在 Kernel submit 前、trace 完全相同，失败路径 route 为空。
  - Frontend State Matrix: N/A。
  - Browser QA: N/A。
  - E2E/Regression: 新建语义 owner `test_background_subscription_routes.py` 与 `test_session_run_coordinator_notice_routes.py`；真实 Kernel/Gateway overlap 在 R4。
  - Visual/Interaction: N/A。
  - Prototype Comparison: N/A。
- Rollback: revert `66d791976`。
- Commits: `66d791976`。
- Next: R3 复用现有 external sender，实现 structured notice 双出口和独立 best-effort。

## R3 — structured notice 双出口与 composition

- Status: DOING

## R4 — CLI、跨层与真栈 fixture

- Status: TODO

## R5 — 专用 Feishu 验收与收尾门禁

- Status: TODO

## Promotion Candidates

None.
