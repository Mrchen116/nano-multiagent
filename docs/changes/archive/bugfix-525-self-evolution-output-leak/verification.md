# Verification Report: bugfix-525

> Validation snapshot: `cd071e649d3fe4fe7a2f392643a49c8f87825898 → 30a701a522f52ef337141806c39fa3848b93358e`

## Summary

Mode: full

Delta range: N/A

Focus issues: N/A

requires_full_verification: false

| 维度 | 结果 |
|---|---|
| Completeness | 5/5 M1 退出标准完成；3/3 incident Requirements 与全部 6 个 Scenario 均有实现和长期保护 |
| Correctness | 3/3 delta Requirements、6/6 delta Scenarios 与 incident 目标一致 |
| Coherence | Followed |

## Completeness

- Tasks: 5/5 complete。`M1-lifecycle-routing/tasks.md:11-15` 的 policy、真实副作用、单 owner、跨层回归和质量门禁均有对应实现与本轮实际结果。
- Spec 覆盖：fork 在 `src/agent/core/agent/context_fork.py:18-36,200-290` 依 source policy 隔离 raw event；hook 在 `src/agent/platform/hooks/builtins/self_improvement.py:219-256` 显式选择 policy 并保持 structured notice；Gateway 在 `src/personal_assistant/gateway/background_session_events.py:192-258`、`background_subscriptions.py:172-253`、`runtime_delivery/observer.py:524-538`、`composition.py:466-506` 完成唯一 owner 与既有 config-sync 接线。
- Prototype / Reference 覆盖：N/A。该 M1 是 Kernel/Gateway 生命周期修复，`tasks.md:40` 明确无 UI/prototype contract；R4 隔离真栈的可复查 locator、限制和清理记录在 `M1-lifecycle-routing/progress.md:58-75`，不被当作永久回归测试。

## Correctness

| Requirement / Scenario | 实现位置（file:line） | 测试覆盖 | 状态 |
|---|---|---|---|
| incident「self-evolution 原始过程保持后台私有」：memory review 正常完成；kernel delta「memory review 不产生第二条 assistant 输出」 | `context_fork.py:18-36,244-290` 只让 self-evolution policy 转发 source-marked `skill_created`；`self_improvement.py:219-256` 仍发布最终 structured review notice | `tests/integration/test_self_evolution_output_visibility.py:36-141` 从 public Kernel 真正执行 `memory(add)`，断言前台文本唯一、review tool/raw output 不在 parent stream、`USER.md` 已写入并收到 notice | covered |
| incident「无保存内容或 review 失败」；routing delta「无更新或失败保持私有」 | allowlist 是 event-kind 而非回复文案过滤（`context_fork.py:18-36`）；hook fork 失败仅记录异常并返回（`self_improvement.py:219-231`），不会影响已完成前台 run | `tests/unit/test_background_hook_fork.py:747-794` 以任意 raw assistant/tool event 证明 content-agnostic filter；`tests/unit/test_background_hook_fork.py:98-116` 覆盖 background handler error isolation | covered |
| incident「skill review 创建新 Skill」；kernel delta「skill review 暴露可归属创建事件」 | `context_fork.py:29-35` 保留 payload 并追加 `source=self_evolution`；`background_session_events.py:220-238` 只把标记事件交业务 callback | `tests/integration/test_self_evolution_output_visibility.py:143-247` 用真实 `skill_manage(create)` 断言 Skill 文件、单一 source-marked event、无 raw review output 与最终 notice | covered |
| incident / capabilities delta「fast、slow review 在 terminal 前后均调和」 | coordinator 以 run start anchor 交给 session manager（`session_run_coordinator.py:880-929`）；manager 以 request 的 agent identity 调既有 handler（`background_subscriptions.py:215-253`） | `tests/unit/personal_assistant/test_background_subscription_manager.py:65-109` 参数化 replay/live；`tests/integration/test_self_evolution_gateway_skill_sync.py:52-179` 让真实 review 在 terminal 后完成，穿过真实 `IMAgentConfigSync` 观察 catalog revision 和落盘 Skill | covered |
| incident / capabilities delta「后续 turn、reconnect/replay 不漏激活、不重复」 | manager 每 session 只建一个 subscriber（`background_subscriptions.py:92-122,233-253`）；subscriber 在每个事件推进 cursor 后按 `after_sequence` 重连（`background_session_events.py:180-282`） | `tests/unit/personal_assistant/test_background_subscription_manager.py:112-157` 覆盖 already-active 的第二轮；`tests/unit/personal_assistant/test_background_session_events.py:163-219` 覆盖 disconnect 后 cursor 8→9，无重复 callback | covered |
| Gateway current contract 与 capabilities delta 的 default/explicit（含显式空）skill 规则 | `agent_config_sync.py:1006-1048` 复用 scope/root validation；`agent_config_sync.py:1050-1099` 保持 default discovery、更新 explicit selection；`agent_config_sync.py:1101-1153` 保留 selection mode | `tests/unit/personal_assistant/test_gateway_im_config_sync.py:465-601` 覆盖 global Skill 对 default、显式非空和显式空 allowlist 的收敛及 revision；`:604-703` 覆盖 agent scope 只影响执行 Agent | covered |
| incident / routing delta「普通 background Agent 用户可见结果不变」 | marked-skill 路由与 `BACKGROUND_TASK` assistant relay 是互斥分支，后者未改为 self-evolution filter（`background_session_events.py:197-238`）；manager 保留原 reply/dedupe path（`background_subscriptions.py:186-213`） | `tests/unit/personal_assistant/test_background_session_events.py:590-654` 与 `test_background_subscription_manager.py:161-197` 覆盖 ordinary background relay；`test_tool_end_detail_passthrough.py:171-257` 证明 unmarked foreground skill 仍属 per-run observer | covered |
| production composition 不会遗漏 persistent owner 的 config-sync 依赖 | 同一个 `IMAgentConfigSync.handle_skill_created` bound method 同时注入 per-run observer 和 manager（`composition.py:466-506`） | `tests/unit/personal_assistant/test_gateway_build_runtime.py:238-265` 捕获 production composition 并断言 manager 获得该 bound method；与上述真实 Kernel→manager→`IMAgentConfigSync` integration 共同覆盖故障 seam | covered |

### Verification evidence

- Focused affected matrix: `102 passed, 2 warnings in 9.12s`，命令覆盖 fork/hook、subscriber/manager/observer、production composition、mode-aware config sync 与两份 self-evolution integration tests。
- Full non-E2E: `3193 passed, 26 deselected, 22 warnings in 232.87s`，命令：`PYTHONPATH=src pytest -q -m 'not e2e'`。
- Quality gates: `ruff check .`、`./scripts/docs-check`（224 maintained Markdown sources / 67 required routes）、`git diff --check 48d19d8..HEAD` 均通过。
- Architecture contracts: `tests/contract/test_cli_sdk_only_contract.py`、`test_core_no_platform_imports.py`、`test_platform_no_sdk_imports.py` 与 `test_bg_origin_constant_contract.py` 共 `7 passed`。实现继续让 product 只消费 `agent.sdk`（`background_subscriptions.py:20-22`），没有引入 `core → platform`、产品互相 import 或 IM→agent 依赖。

## Coherence

| design 决策 | 遵守? | 代码证据（file:line） |
|---|---|---|
| D1：通用 fork 默认 inherit，self-improvement 显式选择 private policy | 是 | `context_fork.py:200-227,263-273` 默认 `inherit` 且拒绝未知值；`self_improvement.py:219-225` 是唯一显式 `self_evolution` caller；`test_background_hook_fork.py:659-812` 分别保护 generic inherit、opt-in filter/source 与拒绝路径 |
| D2：标记 `skill_created` 始终由 persistent manager 单独拥有，per-run fail-closed 跳过 | 是 | `runtime_delivery/observer.py:524-538` 先跳过 marked event；`background_session_events.py:220-238` 与 `background_subscriptions.py:215-231` 唯一接收并转交；fast/slow、already-active 与 replay 测试见上表 |
| D3：复用既有 `AgentConfigSync.handle_skill_created()`，不新增 config mutation 通道 | 是 | `background_subscriptions.py:215-222` 只在线程中调用注入 handler；`composition.py:466-506` 复用同一 bound method；`agent_config_sync.py:1006-1153` 仍是唯一 mode-aware mutation owner |
| D4：cursor、单 owner 与既有 config-sync 收敛承担 replay idempotency | 是 | `background_session_events.py:183-195,254-282` 在 reconnect 使用最后 sequence；`background_subscriptions.py:92-122` ensure-once；`test_background_session_events.py:163-219` 和 `test_background_subscription_manager.py:112-157` 保护其时序 |
| D5：永久回归必须跨真实 failure seam，避免只证明 Kernel stream | 是 | Kernel 可见性/持久副作用和 Gateway lifecycle 分列 `tests/integration/test_self_evolution_output_visibility.py`（247 lines）与 `test_self_evolution_gateway_skill_sync.py`（179 lines），共享 118-line controlled driver；后者实际观察 `IMAgentConfigSync` 后 catalog revision 和 Skill 文件，不只断言 event 存在 |

实现未新增平行 queue、配置同步或跨机读写机制；按 event source 分配 owner，保留 ordinary `BACKGROUND_TASK` 文本 route。测试按 `docs/development/testing.md` 的最低 failure seam 分层：Kernel private visibility、subscriber lifecycle、per-run ownership、composition wiring 与 real config-sync result 各自保护不同风险；新增文件均低于 400 行，未发现长期重复或一次性验收证据伪装为 test。

## Prototype / Reference Contract

N/A.

## Issues

### CRITICAL（提 PR 前必须修）

- None.

### WARNING（提 PR 前必须修）

- None.

### SUGGESTION（可以修）

- None.

All checks passed. Ready for PR.

---

# Round 2 — fix-delta verification

> Validation snapshot: `30a701a522f52ef337141806c39fa3848b93358e → 874f0af6c70d721a39fc1e41d828ffba4ae8a42f`

> Review mode: delta, with final-state mapping of the approved incident, design, M1/M2 exits, and three delta-specs.

## Summary

Mode: delta

Delta range: `830c0aa67b60638df10630823bf7af12665b5556..874f0af6c70d721a39fc1e41d828ffba4ae8a42f`

Focus issues: concurrent `skill_created` reconciliation, partial-start cleanup, replacement interpreter, and external-cwd runner invocation.

requires_full_verification: false

| Dimension | Result |
|---|---|
| Completeness | 5/5 M1 exits and 6/6 M2 exits remain implemented; all 3 incident Requirements and 5 incident Scenarios map to current code plus permanent evidence. |
| Correctness | The RLock fixes the only identified lost-update window without changing source classification, default discovery, explicit-empty semantics, or global-scope selection. M2 remains a test/harness-only change. |
| Coherence | Followed: D1--D5, the three delta-specs, current capability/routing contracts, test placement rules, worktree-runtime isolation, and package import boundaries. |

## Final-state requirement and scenario mapping

| Approved requirement / scenario | Current implementation | Permanent evidence | Status |
|---|---|---|---|
| Private self-evolution raw output; successful memory update still reaches only the structured result | `context_fork.py:18-36,200-290` makes raw fork assistant/tool/turn events private only under the explicit policy; `self_improvement.py:219-256` keeps the structured review result. | Kernel public-stream and real-memory coverage remains in `test_self_evolution_output_visibility.py`; the M2 real-stack runner includes the same private-delivery boundary. | covered |
| No-save or failure does not produce a raw bubble or change foreground completion | The allowlist is event-kind based, never a `Saved:`/`Nothing to save.` content filter (`context_fork.py:18-36`); hook failures return after logging (`self_improvement.py:219-231`). | `test_no_save_review_stays_private_after_foreground_completion:130-207` observes `delivery_status=completed`, fixture-owned `no_save_review_completed`, exactly two foreground Agent messages, zero raw/error text, and one structured notice through IM's public relay. | covered |
| New self-evolution Skill is private but becomes usable after foreground terminal | Marked `skill_created` is forwarded with source (`context_fork.py:29-35`), then handled by the persistent manager and existing config-sync owner (`background_subscriptions.py:215-231`, `agent_config_sync.py:1006-1106`). | `test_terminal_late_skill_create_replays_and_activates_in_a_new_session:65-215` proves the real create, IM explicit allowlist update, workspace Skill, one structured notice, no raw bubble, and real next-session `skill_view` persisted in the IM Agent message `tool_calls`. | covered |
| Terminal/manager handoff, later turns, and reconnect/replay neither lose nor duplicate activation | Subscriber advances its cursor before dispatch and reconnects from it (`background_session_events.py:180-282`); manager admission is once per session (`background_subscriptions.py:92-122,233-253`); the per-run observer fail-closed skips the marked event (`runtime_delivery/observer.py:524-538`). | The real-stack journey forces one disconnect before marked-event yield and asserts one same-sequence replay and one notice (`test_self_evolution_skill_activation_critical_path.py:119-174`); focused subscriber/manager matrix passed. | covered |
| Ordinary non-self-evolution `BACKGROUND_TASK` output stays user-visible | The `assistant_message`/`background_task` relay branch remains prior to special self-evolution routing (`background_session_events.py:197-239`), with its existing reply/dedupe path intact. | `test_background_session_events.py` and `test_background_subscription_manager.py` passed in the focused matrix; Round 1 product evidence remains applicable because this delta does not alter that branch. | covered |

The three delta-specs are therefore met: Kernel exposes only source-marked business events and the structured review (`specs/kernel/runs.md:5-22`); Gateway keeps raw/no-save/failure private while preserving ordinary background delivery (`specs/gateway/routing-delivery.md:5-25`); and terminal/replay config reconciliation preserves default versus explicit mode (`specs/gateway/agent-capabilities.md:5-21`).

## Design and milestone exit mapping

| Decision / exit | Verification |
|---|---|
| D1 and M1 policy exit: generic forks default to `inherit`; only self-improvement opts in; unknown policy rejects | `fork_conversation(... event_policy="inherit")` and its validation are at `context_fork.py:200-227`; the only self-improvement invocation is explicit at `self_improvement.py:219-225`. The 76-test M1 matrix covers generic inherit, opt-in source filtering, and caller selection. |
| D2 and M1 owner exit: a source-marked Skill has one session-lifetime owner | The observer skips only source-marked `skill_created` (`observer.py:524-531`); manager executes the injected handler on its persistent subscription (`background_subscriptions.py:215-231`). Existing foreground Skill ownership and ordinary background output remain separate. |
| D3 and M1 reuse exit: no new config mutation path | Production composition obtains one existing bound `IMAgentConfigSync.handle_skill_created` and passes it to both owner sites (`composition.py:466-506`). The subscriber only calls it with `asyncio.to_thread`; it does not alter YAML/IM data itself. |
| D4 and M1 replay exit: cursor + single owner + existing convergence | Cursor update precedes all callbacks (`background_session_events.py:192-195`), admission is ensure-once, and config-sync retains its existing mode-aware convergence. M2's forced same-sequence replay verifies the real transport seam rather than only an event list. |
| D5 and M1 cross-boundary exit | `test_self_evolution_gateway_skill_sync.py:115-168` runs a real Kernel review through `BackgroundSubscriptionManager` into `IMAgentConfigSync`, waiting for completion of the actual worker-thread handler before asserting catalog revision and durable Skill state. M2 raises this to isolated IM + production Gateway + public relay. |
| M2 no-save, Skill/replay, next-session, single-command, and cleanup exits | `scripts/e2e-self-evolution.sh:6-44` creates a worktree-local runtime, uses the current worktree, and removes only its guarded prefix. Independent external-cwd execution completed `2 passed in 86.05s` and printed its cleanup confirmation. |
| M2 review-fix exits: partial start, interpreter, external cwd | `_cleanup_stub_stack()` always runs `e2e-down.sh` then terminates/reaps the stub (`test_agent_config_context_continuity_critical_path.py:205-225`); `restart_gateway()` uses `sys.executable` for both entrypoint shapes (`_im_gateway.py:100-108`); absolute common-dir resolution is at runner line 8. Their focused lifecycle, interpreter, and invocation tests passed. |

### Concurrent skill reconciliation review

`IMAgentConfigSync` already owns the shared reentrant `_operation_lock` (`agent_config_sync.py:242-246`). The delta holds that same `RLock` across validation, profile fetch, merge, optimistic PATCH, durable persistence, and catalog publication (`:1006-1106`, `:1384-1406`). Consequently a second `skill_created` observes the first committed profile rather than PATCHing the same old version. It does not add a caller-specific lock or a new queue.

`test_concurrent_skill_created_events_merge_into_one_explicit_allowlist:708-808` deliberately holds the first GET at profile version 1 while another owner enters. The final persisted and live allowlist is exactly `old-skill, skill-a, skill-b`; that test passed as part of the 31-test config-sync group. Because the locked methods do not reacquire this lock, a plain lock would also suffice locally; retaining the pre-existing `RLock` preserves the class's established reentrant config-operation contract and introduces no lock-order inversion. The lock serializes its synchronous IM transaction by design, so it avoids the observed concurrent optimistic-write loss rather than silently retrying or dropping an activation.

Mode and scope semantics remain unchanged inside the protected transaction: default discovery only republishes (`agent_config_sync.py:1067-1072`); explicit mode merges missing names and preserves `skills_selection_mode` in the PATCH (`:1079-1151`); agent roots/scope are validated (`:1026-1040`); global events traverse all configured Agents (`:1041-1055`). Existing tests passed for global scope/default/explicit-empty (`test_gateway_im_config_sync.py:467-604,895-934`) and agent scope isolation (`:606-705`). This conforms to `docs/specs/gateway/agent-capabilities.md:333-364`, including the explicit-empty no-fallback contract.

## Quality, architecture, and isolation checks

- Test layering is non-duplicative under `docs/development/testing.md`: config mutation race lives in its existing config-sync unit owner; the integration test covers the actual Kernel -> manager -> config-sync seam; the two E2E tests cover only isolated real-process/public-relay risks. Fixture and lifecycle helpers are reused from their existing critical-path owner rather than copied.
- The only changed production file in this delta is `src/personal_assistant/gateway/agent_config_sync.py`; runner/fixture/lifecycle/interpreter/path changes reside in `scripts/` or `tests/`. Thus M2 does not change the user-facing Kernel/Gateway/IM product contract.
- `tests/contract/test_cli_sdk_only_contract.py`, `test_core_no_platform_imports.py`, `test_platform_no_sdk_imports.py`, and `test_bg_origin_constant_contract.py`: **7 passed**. The delta adds no `IM -> agent`, product-to-product, or product-to-`agent.core`/`agent.platform` import.
- `docs/development/worktree-runtime.md` isolation is honored: the runner passes its own guarded `--basetemp`, uses isolated IM/Gateway/fixture processes, and the independent run left no `.e2e-self-evolution.*` directory.
- Coding guidance is met: the concurrency comment explains the optimistic-version invariant, and new/revised public helper docstrings state cleanup or interpreter behavior rather than restating syntax.

## Verification evidence

- Config-sync concurrency/default/scope + completion-boundary + runner/interpreter regressions: **31 passed in 4.63s**.
- M1 fork/hook/subscriber/manager/observer/composition/Kernel integration matrix: **76 passed, 2 warnings in 15.25s**.
- Independent M2 external-cwd real-stack command: `PYTHON=.../.venv/bin/python /absolute/path/scripts/e2e-self-evolution.sh` from a temporary external directory: **2 passed in 86.05s**; runtime cleanup confirmed.
- Partial-start cleanup E2E: **1 passed in 5.27s**. Architecture contracts: **7 passed in 4.88s**.
- `ruff check .`: passed. `scripts/docs-check`: passed (`228` maintained Markdown sources / `67` routes). `git diff --check 830c0aa67..874f0af6c`, full unit diff check, and `bash -n scripts/e2e-self-evolution.sh`: passed.
- A final full non-E2E run on this exact head was already recorded by the implementation owner as **3197 passed, 29 deselected, 22 warnings in 391.28s**. This verifier did not repeat that 6.5-minute suite because the scoped independent matrix above exercised every changed runtime/test/harness seam.

## Issues

### CRITICAL

- None.

### WARNING

- None.

### SUGGESTION

- None.

Verdict: **pass**. No delta introduces a condition requiring full re-verification.

---

# Round 3 — corrected-delta verification

> Validation snapshot: `18774792e5ceadeb279f3f33c289d9345a0a2e62` (unit branch after merge of `origin/main` `ee32b85b51ec70009b47d2b49700a53f07ab6`)

> Review mode: corrected-delta. Scope is the three unmerged bugfix-525 delta-specs against final code and latest canonical specifications; no production implementation was changed in this round.

## Verdict

**pass** — the three delta-specs are accurate, have no conflict with current canonical contracts, make no inappropriate durability or locking promise, and can be safely folded into their named canonical files. No delta/canonical change is required before that fold.

## Canonical and implementation mapping

| Delta | Current code and canonical contract | Correctness / merge decision |
|---|---|---|
| `specs/kernel/runs.md` | `context_fork.py:18-36` forwards only source-marked `skill_created`; `:203-280` defaults generic forks to `inherit` and isolates only explicit `self_evolution`. `self_improvement.py:219-259` explicitly selects that policy and separately publishes the structured review. | Accurately adds a session-stream visibility contract: raw side-chain assistant/tool/turn data is private, while durable memory/Skill effects plus necessary business/structured events remain observable. It belongs in `docs/specs/kernel/runs.md`, whose purpose is consumer-visible Kernel session/run behavior. |
| `specs/gateway/routing-delivery.md` | The special source-marked event is not a per-run reply (`runtime_delivery/observer.py:524-538`); persistent delivery keeps normal `BACKGROUND_TASK` assistant output on its existing relay branch (`background_session_events.py:197-239`). | Accurately constrains only self-evolution maintenance output to system notification delivery and explicitly preserves the pre-existing ordinary background-task result contract. It neither invents a text filter nor changes external-channel behavior beyond suppressing raw maintenance content. |
| `specs/gateway/agent-capabilities.md` | `BackgroundSubscriptionManager` owns session-level marked-Skill delivery (`background_subscriptions.py:92-122,215-253`); composition injects the existing config-sync handler (`composition.py:466-506`); `IMAgentConfigSync` retains default discovery and explicit allowlist semantics (`agent_config_sync.py:1006-1151`). | Accurately states the observable result for terminal timing and replay: the created Skill is converged using the existing mode-aware rule, with no duplicate owner outcome. This directly extends canonical `agent-capabilities.md:333-364` without restating its entire selection-mode state machine. |

The delta docs contain no changes relative to the already verified pre-main-sync report parent (`66a5ed4a5`), so the main merge did not silently alter their intended claims. `git diff --check origin/main...HEAD` and the documentation integrity gate both pass.

## bugfix-527 F3 provenance compatibility

The main merge adds `metadata_overrides` to the fork callable and makes self-improvement pass `{"skill_creation_source": "F3"}` only when `review_skills` is true (`self_improvement.py:219-228`). This is independent from the simultaneous `event_policy="self_evolution"`:

- metadata is copied only into the fork HookContext (`context_fork.py:262-280`) and is consumed by Skill usage provenance (`agent/core/skills/usage.py:166-169`);
- event policy only selects the parent-session publisher (`context_fork.py:272-278`), whose allowlist emits a source-marked `skill_created` and no raw realtime events (`:18-36`);
- the new canonical source rule is already complete in `docs/specs/kernel/skills.md:104-121`: automatic Skill Review create is `F3`; memory-only review, ordinary fork/user create, and `skill_view` do not fabricate or overwrite it.

Therefore bugfix-525's Kernel-runs delta must not claim `F3`: that would incorrectly make a Skill usage-record provenance detail part of the public session-stream contract and duplicate bugfix-527's authority. The two capabilities coexist without a metadata/event-source collision, as confirmed by the focused suite: **26 passed in 4.18s** across F3 integration, generic fork inheritance/private-policy, and self-improvement caller tests. The unit's reported broader merge-conflict seam (`75 passed`) remains consistent with this independent subset.

## Concurrency wording decision

Do **not** add the RLock to the delta. The shared `IMAgentConfigSync._operation_lock` is an implementation mechanism that serializes its read/merge/optimistic-PATCH/publish transaction (`agent_config_sync.py:242-246,1006-1106`); it is not a new Gateway public contract. The capabilities delta already states the correct durable behavior — existing mode-aware config sync converges and the same creation result is not handled twice. Naming a lock would over-constrain a later equivalent implementation and would not improve a consumer's observable guarantee.

## Evidence

- Independent F3/policy source suite: **26 passed in 4.18s**.
- Reported unit merge-conflict focused seam: **75 passed**.
- `PYTHON=.../.venv/bin/python scripts/docs-check`: passed (`241` maintained Markdown sources / `67` routes).
- `git diff --check origin/main...HEAD`: passed.

## Required changes

- None.
