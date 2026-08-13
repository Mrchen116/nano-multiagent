# bugfix-536-M2 — Progress

## R1 — 基线与失败边界定位

- Context: Round 1 verifier 已确认 adopted successor 的 non-completed/no-suffix 分支可遗留 active marker；产品回归在两个独立 Web IM 直聊中确认精确 `/new` 后旧口令仍可见。
- Decision: 从 `dc3173750` 建立独立 M2 worktree；先追踪 `SessionRunCoordinator`、`GatewaySessionBinder` 和 Kernel transcript，再为两条路径建立最窄红测。
- Rationale: `/new` 已创建 fresh Kernel session，必须继续辨别 binding 回写与会话外输入，不能以提示词掩盖用户可见契约。
- Evidence:
  - Tests: M1 aggregate baseline `159 passed in 13.75s`。
  - Entry: 已确认 `/new` 的入口是 exact parser → `new_session` → `prepare_reset` → `publish_reset`；recovery failure 在 nested no-suffix 返回后抛出时只清理原 predecessor。
  - Frontend State Matrix: N/A。
  - Browser QA: N/A；后续用隔离 Web IM 真栈做运行时验收。
  - E2E/Regression: 两条 Round 1 报告已读；红测和真栈结果待 R2/R3 追加。
  - Visual/Interaction: N/A。
  - Prototype Comparison: N/A。
- Rollback: 删除 M2 的提交即可回到 `dc3173750`。
- Commits: `0f2accd16`（M2 plan）

## R2 — 收口无 suffix 的失败 successor

- Context: `test_failed_adopted_successor_without_suffix_releases_session` 在基线失败：`run-2` 已成 active owner，nested handoff 因没有新 suffix 返回 `None`，外层仅按 root `run-1` 清理，`is_session_busy()` 仍为真。
- Decision: 仅在 nested handoff 确认没有可接管 suffix 后，由 recovery owner 用 `claim.run_id` 关闭 active marker；有 suffix 的 nested handoff 原样继续。
- Rationale: successor 的 active ownership 只能由知道 successor identity 的 recovery coordinator 收口；提前关闭会丢失其可能的 re-handoff suffix。
- Evidence:
  - Tests: 红测在基线失败（`is_session_busy('web_relay:recovery:agent-a')` 为真）；修复后 `tests/unit/personal_assistant/test_recovery_handoff_coordinator.py tests/integration/test_session_run_coordinator_recovery.py` 为 `9 passed in 2.33s`。
  - Entry: root/follower 各发一次 failed，active/busy 清空，后续 ordinary message 新提交并回 `ordinary reply`。
  - Frontend State Matrix: N/A。
  - Browser QA: N/A。
  - E2E/Regression: 保留 correlated successor、suffix adoption、`/stop`、`/new`、shutdown recovery cases，均在 focused suite 内通过。
  - Visual/Interaction: N/A。
  - Prototype Comparison: N/A。
- Rollback: 回退本 roadpoint commit 即恢复 `dc3173750` 行为。
- Commits: `88ebc2e93`（recovery closure）

## R3 — 验证精确 `/new` 的真实 transcript 隔离

- Context: Round 1 product report 要求修复 exact `/new` 后旧会话口令可见；现有 coordinator/binder 已走 `prepare_reset` → `publish_reset`，但此前没有真实 Kernel transcript regression。
- Decision: 新建专属 real-Kernel integration，使用请求上下文探针证明先前 sentinel 不会进入 reset 后的模型请求；同时以隔离 Web IM + Gateway 真栈按报告语义重跑。
- Rationale: 基线 `dc3173750` 在真实 reset path 已满足这个契约，未发现可归因的 Gateway/Kernel 复用点；因此不添加会改变用户行为的伪修，而以 durable regression 锁定实际 session 边界。
- Evidence:
  - Tests: `tests/integration/test_session_run_coordinator_reset.py` 为 `1 passed in 2.28s`；其后与 exact `/new`、`/stop` public control tests 为 `3 passed in 2.52s`。
  - Entry: 隔离 Web IM 直聊先写随机 `M2RESET…`，精确 `/new` 后 binding 切至新 session；旧 secret 只在旧 JSONL，新 JSONL 不含它，后续自然语言询问返回 `UNKNOWN`。
  - Frontend State Matrix: N/A。
  - Browser QA: N/A；此路径通过真实 IM REST relay 入口，不依赖浏览器 DOM。
  - E2E/Regression: 真栈在同一脚本中以 `scripts/e2e-up.sh --wt` 起停，因执行环境的默认 Python 缺 PyYAML，显式使用 repository `.venv/bin` 在 PATH；服务由 trap 调 `e2e-down.sh` 清理。
  - Visual/Interaction: N/A。
  - Prototype Comparison: N/A。
- Rollback: 回退本 roadpoint commit 即移除 regression；没有对应 production source 变更。
- Commits: `52317cd69`（real-Kernel reset regression）

## R4 — Aggregate、静态检查与真栈复验

- Context: M2 同时关闭 recovery closure 代码缺陷与 Round 1 exact `/new` 产品回归报告；需要确认 M1 全范围没有退化，并以共同 Gateway/IM 入口复验用户命令边界。
- Decision: 扩展 M1 aggregate 纳入 reset integration，运行 docs/static/diff checks，并在同一 shell 生命周期内起隔离真栈后执行 old-secret → nonexact `/new ...` → exact `/new` → fresh query。
- Rationale: live Gateway children 会在命令会话结束时被环境清理，所以起栈、验证与 `e2e-down.sh` 必须同一 shell；静态 reset test 锁定可重复的 transcript 不变量，真栈锁定用户可见入口。
- Evidence:
  - Tests: M1 aggregate 加 M2 reset integration：`161 passed in 11.58s`。
  - Entry: isolated conversation `0c07d72b488f45688c597afe8d705a8a`；nonexact `/new please…` 回 `M2FINAL1EB8BBABD7`，exact `/new` 回 `已开始新会话。`，fresh session `sess_050904d571dd6819` transcript 无旧 secret，后续回 `UNKNOWN`。
  - Frontend State Matrix: N/A。
  - Browser QA: N/A；Web IM REST relay 是该用户路径的真实公共 ingress，非前端渲染变更。
  - E2E/Regression: `scripts/e2e-up.sh --wt` + IM public REST journey passed；trap 执行 `scripts/e2e-down.sh --wt`，无遗留 PID/runtime 文件。
  - Visual/Interaction: N/A。
  - Prototype Comparison: N/A。
  - Static: Ruff check passed；Ruff format check passed；`scripts/docs_check.py` passed（224 maintained Markdown sources, 70 required routes）；`git diff --check origin/unit/bugfix-536...HEAD` passed。
- Rollback: 回退 M2 commits `88ebc2e93` 与 `52317cd69`（以及本 evidence commit）即可回到 pre-fix behavior。
- Commits: pending

## Promotion Candidates

| Candidate | Suggested owner | Scope | Evidence |
|---|---|---|---|
| None | code-test-CI | N/A | M2 是已批准设计内的行为修复。 |
