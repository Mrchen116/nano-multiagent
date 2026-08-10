# bugfix-525-M1 — Progress

## Baseline

- Context: finalized Full incident/design/design-review and all delta-specs read at unit head `4fae135b6`; prior commits through `dbc21ad5b` are investigation evidence, not final lifecycle design.
- Decision: preserve useful Kernel privacy/side-effect tests, then replace the generic-fork assumption and add the missing production Gateway persistent route.
- Evidence:
  - Tests: pre-change focused matrix `82 passed, 2 warnings in 6.96s`.
  - Command: `PATH=/Users/czj/Repos/nano-multiagent/.venv/bin:$PATH PYTHONPATH=src pytest -q tests/unit/test_background_hook_fork.py tests/unit/test_self_improvement_hook.py tests/unit/personal_assistant/test_background_session_events.py tests/unit/personal_assistant/test_background_subscription_manager.py tests/unit/personal_assistant/test_tool_end_detail_passthrough.py tests/unit/personal_assistant/test_gateway_im_config_sync.py tests/integration/test_self_evolution_output_visibility.py`.
  - Production symptom (read-only, raw logs not committed): Kernel session `sess_5f9eeb9f7479dd13`; LLM session dir `/Users/czj/Repos/LLM_PROXY/logs/session/2026-08-09_20-27-23_509_sess_5f9eeb9f7479dd13/`; request `2026-08-10_09-41-03_357-req-anthropic_messages.json`; response `2026-08-10_09-41-09_400-non-stream-res-anthropic_messages.json`; screenshot `/var/folders/mf/fxm1x6xs7pbf34h6rnmvjz1c0000gn/T/codex-clipboard-ea146fbc-d9d7-41d9-aded-947376fc38e4.png`.
- Rollback: N/A (baseline only).
- Commits: pending plan commit.

## R1 — 显式 fork event policy 与 Kernel 业务事件标记

- Context: `make_fork_conversation()` 是所有 background hook 共用能力，旧 investigation 实现把 self-evolution filter 固定为通用默认，既破坏普通 caller 事件继承，也缺少 Gateway 可识别 source。
- Decision: callable 新增默认 `inherit` 的显式 policy；仅 self-improvement 传 `self_evolution`。该 policy 只替换 session publisher，过滤 raw assistant/tool/turn，并在白名单 `skill_created` 的复制 payload 上添加 `source=self_evolution`；未知值在执行 fork 前拒绝。
- Rationale: 业务 caller 选择身份，fork seam 在事件离开 side-chain 前统一分类；不改变 parent model、tools、permission、workspace 或 background run origin。
- Evidence:
  - Tests (red): focused suite `5 failed, 21 passed`，分别命中 default inherit、policy 参数/拒绝、hook 显式选择与 source 缺失。
  - Tests (green): `26 passed in 2.65s` — `tests/unit/test_background_hook_fork.py tests/unit/test_self_improvement_hook.py tests/integration/test_self_evolution_output_visibility.py`。
  - Quality: targeted Ruff passed；`git diff --check` passed。
  - Entry: public Kernel integration 真实执行 `memory(add)` / `skill_manage(create)`；raw assistant/tool 不进 parent stream、durable 文件 side effect 保留、skill event 带 source。
  - Frontend State Matrix / Browser QA / Visual / Prototype: N/A。
- Rollback: revert R1 commit restores the prior implicit generic filter (but reopens generic visibility and unmarked-event defects).
- Commits: pending R1 commit.

## R2 — Gateway persistent 单 owner 路由

- Status: pending.

## R3 — Production composition 到 config-sync 的跨层闭环

- Status: pending.

## R4 — 比例验证与真实入口

- Status: pending.

## Promotion Candidates

| Candidate | Suggested owner | Scope | Evidence |
|---|---|---|---|
| None | — | — | — |
