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

---

# Round 4 — M3 final-state full verification

> Validation snapshot: `ee32b85b51ec70009b47d2fd2b49700a53f07ab6 → 02d9b7740da4dd476d5524f8bc33b4e3d52ab8d0`

## Summary

Mode: full

Delta range: N/A

Focus issues: M3 true update receipt、originating trace、per-run route、Feishu / shadow IM 双出口、CLI outcome、Feishu worker startup deadline，以及 Round 4 route-anchor / CLI 验收修复。

requires_full_verification: false

| 维度 | 结果 |
|---|---|
| Completeness | 18/18 M1–M3 退出标准完成；incident 4/4 Requirements、8/8 Scenarios 均有实现与证据 |
| Correctness | 4/4 active delta Requirements、22/22 delta Scenarios 与最终实现、测试和 canonical current specs 一致 |
| Coherence | Followed；D1–D7、启动 side finding 与包依赖边界均被遵守 |

## Completeness

- Tasks: M1 `5/5`、M2 `6/6`、M3 `7/7`，合计 `18/18`。M3 的实施记录和专用验收 locator 位于 `M3-external-system-notice/progress.md:10-139` 与 `evidence/`；本轮不把这些一次性产品观察代替永久回归。
- Prototype / Reference: N/A。该 unit 不改变前端结构或视觉，shadow IM 继续使用既有 `node.system_message` schema，飞书继续使用普通 Bot 文本出口。
- M3 true-receipt、trace、route、delivery、CLI、startup 与 Round 4 harness 退出标准均可从当前代码和长期测试直接复查；专用 Feishu 与真实 PTY 结果另有 nonce/message-id/transcript 证据。

## Correctness

| Requirement / Scenario | 实现位置 | 永久测试 / 证据 | 状态 |
|---|---|---|---|
| self-evolution raw prompt/tool/turn/完成确认保持私有；memory/Skill 持久副作用保留 | `src/agent/core/agent/context_fork.py:18-36,203-304` 仅在显式 policy 下转发 source-marked `skill_created`；`src/agent/platform/hooks/builtins/self_improvement.py:269-313` 单独发布 truthful receipt | `tests/integration/test_self_evolution_output_visibility.py:37-249` 通过 public Kernel 真实执行 memory add / Skill create，断言 raw event 不进入父 stream、文件落盘且业务事件保留 | covered |
| no-save、list/read、失败均静默；`completed=False` 但已有成功写入仍报告真实 target | `self_improvement.py:153-194` 按 call id 关联结果，只认可 memory `add/replace/remove` 与 Skill `create/edit/patch/write_file/remove_file`，拒绝 error 与 structured `success=false`；`:296-313` 只在非空 target 时发布 | `tests/unit/test_self_improvement_hook.py:326-543` 覆盖 read-only、全部失败、call-id 不匹配、八类 action、legacy flags 与 incomplete partial success | covered |
| RunRecord trace 贯通 TurnRequest 与当前 HookContext，review event 携带 originating trace | `src/agent/core/session/types.py:141-150`；`src/agent/core/runs/registry.py:212-246`；`src/agent/core/agent/runtime.py:280-301,403-433`；`self_improvement.py:311` | `tests/unit/agent/runs/test_runs_registry_executor.py` 守住 request trace；`test_self_improvement_hook.py:300-324,486-543` 与 `test_self_evolution_output_visibility.py:130-134,240-244` 断言 exact trace | covered |
| coordinator submit 前冻结 route，submit 失败撤销；manager 精确消费、missing/replay fail-closed、4096 oldest-first | `src/personal_assistant/gateway/session_run_coordinator.py:878-899`；`background_subscriptions.py:83-110,209-223` | `tests/unit/personal_assistant/test_session_run_coordinator_notice_routes.py:54-114`；`test_background_subscription_routes.py:49-180` | covered |
| 飞书来源：原 chat 一行 Bot 文本 + shadow structured notice；IM 来源只留 IM；两路独立 best-effort、稳定 identity 去重 | `src/personal_assistant/gateway/runtime_delivery/background.py:24-165,241-283`；`composition.py:466-505` 复用现有 sender/OutboundRouter | `tests/unit/personal_assistant/test_self_evolution_notice_delivery.py:71-304` 覆盖 source switching、identity、缺 IM、external/shadow 各自失败与未来 notice 关闭；`tests/integration/test_self_evolution_gateway_notice_routing.py:143-266` 覆盖真实 fork/tool/trace overlap | covered |
| internal telemetry 不外发；普通 background Agent 输出、ordinary Skill owner 与 post-terminal Skill 激活不回归 | `src/personal_assistant/gateway/background_session_events.py:197-253`；`runtime_delivery/observer.py:524-538`；`background_subscriptions.py:254-269` | `test_background_session_events.py:590-654`、`test_tool_end_detail_passthrough.py:171-257`、`tests/integration/test_self_evolution_gateway_skill_sync.py` | covered |
| CLI 只显示 memory / skills / both 的真实 updated line，无写入无提示，raw review 不进入终端 | `src/coding_cli/events/background_runs.py:15-23,70-96` | `tests/unit/test_cli_background_runs.py:98-146`；真实 PTY 六场景 transcript 为 `M3-external-system-notice/evidence/coding-cli-self-evolution.txt` | covered |
| Feishu worker 启动预算与短 shutdown join 解耦，并完整消费 monotonic deadline；Round 4 route-anchor 先停旧 Gateway 再写 fixture，CLI 走 public PTY | `src/personal_assistant/channels/feishu/worker.py:237-250,311-338`；`scripts/e2e-feishu-self-evolution.py:151-180,653-689`；`scripts/e2e-cli-self-evolution.py:220-256,349-475` | `tests/unit/personal_assistant/test_feishu_worker_runtime.py:235-269` 覆盖 early-False deadline；`tests/e2e/critical_paths/test_stub_stack_lifecycle_critical_path.py:22-74` 覆盖真实栈失败清理；最终专用 Feishu 与 PTY 证据见 M3 `evidence/` | covered |

### Corrected Delta Reconciliation

| Delta item | Implementation / test evidence | Canonical merge status | Outcome |
|---|---|---|---|
| `specs/kernel/runs.md`：真实更新 gate、raw privacy、source-marked Skill、incomplete partial success 与 originating trace | `self_improvement.py:153-194,296-313`、`context_fork.py:18-36`、trace chain 与 hook/integration tests | 语义逐行归并到 `docs/specs/kernel/runs.md:261-293` | aligned |
| `specs/gateway/routing-delivery.md`：structured-only、无更新静默、普通后台结果不变 | `background.py:24-165`、`background_session_events.py:197-253` 及 delivery/background tests | 逐行归并到 `docs/specs/gateway/routing-delivery.md:308-329` | aligned |
| `specs/gateway/external-channels.md`：同源路由、no-write 静默、telemetry 默认不外发 | trace route + delivery callback + external metadata helper；notice delivery unit/integration 与专用 Feishu evidence | 与 current requirement 语义一致地归并到 `docs/specs/gateway/external-channels.md:146-232`；原有控制/background scenarios 保持不变 | aligned |
| `specs/cli/interactive-repl.md`：只显示真实更新对象 | `background_runs.py:70-96` 与 CLI unit/PTY evidence | 逐行归并到 `docs/specs/cli/interactive-repl.md:110-126`；`docs/specs/cli/spec.md:21` 的 Interactive REPL Requirement count 已由 7 更新为 8 | aligned |

Uncovered Observable Behavior: None。Feishu worker 的 30 秒 startup deadline 是 design Changelog 明确批准的同一启动生命周期修复，不是新的 channel 用户协议；Skill config-sync 并发收敛已由 canonical `gateway/agent-capabilities.md` 承载，active M3 delta 无需复制实现锁。

Outcome: **aligned**.

## Coherence

| Design 决策 | 遵守? | 代码证据 |
|---|---|---|
| D1：generic fork 默认 inherit，self-improvement 显式选择 private policy | 是 | `context_fork.py:203-232,249-304`；`self_improvement.py:269-278` |
| D2：source-marked `skill_created` 只归 persistent manager | 是 | `observer.py:524-538`；`background_session_events.py:220-238` |
| D3：复用既有 config-sync，不建第二套 mutation/queue | 是 | `background_subscriptions.py:254-269`；`composition.py:466-505` |
| D4：cursor + 单 owner + 既有幂等承担重放 | 是 | `background_session_events.py:180-282`；manager ensure-once 与 route consume-once tests |
| D5：永久回归跨 public Kernel / production Gateway failure seam | 是 | 两份 self-evolution integration 分别观察真实持久副作用、config-sync 和 external/shadow routing，不止断言 event 存在 |
| D6：只有真实 update receipt 外发，telemetry 继续内部化 | 是 | `self_improvement.py:153-194,296-313`；`background.py:54-65` |
| D7：originating trace 关联本轮 immutable ReplyContext，并复用既有 sender | 是 | `session_run_coordinator.py:878-899`；`background_subscriptions.py:87-110,209-223`；`background.py:94-113` |

实现没有引入 `personal_assistant → agent.core/platform`、`coding_cli → agent.core/platform`、`IM → agent` 或 `core → platform` 依赖；route 表是 Gateway 内进程短期状态，未伪造 durable/exactly-once 保证。新增测试文件均低于 400 行，并按 unit / integration / e2e failure seam 分层。

## Verification evidence

- Focused final-state matrix: **128 passed, 8 warnings in 33.84s**。覆盖 fork/hook、trace、manager/coordinator route、delivery、CLI、Feishu worker、raw privacy、Skill sync 与 overlap integration。
- Architecture contracts: **7 passed in 1.67s**。
- Quality: targeted changed-production `ruff check` passed；docs-check passed（**245** maintained Markdown sources / **67** required routes）；`git diff --check ee32b85b..02d9b774` passed。
- Worker 在同一 report head 记录的 full non-E2E：**3235 passed, 28 warnings in 79.64s**；本轮没有重复执行该已覆盖且代码未变化的整套门禁。

## Issues

### CRITICAL（提 PR 前必须修）

- None.

### WARNING（提 PR 前必须修）

- None.

### SUGGESTION（可以修）

- None.

All checks passed. Ready for PR.

---

# Round 5 — code-review fix delta verification

> Validation range: `16397bbad69978198a89ad8bb3ea87e8d8b2ab59..a2a180535271d9a27fca9f84360b8c7943849ad9`

## Summary

Mode: delta

Focus issues: F1 cron/heartbeat persistent owner、F2 external sender offload、F3 shared config mutation lock、F4 Feishu startup fail-fast、F5 subscriber callback envelope。

requires_full_verification: false

| Dimension | Result |
|---|---|
| Completeness | F1–F5 均在原设计 seam 完成，新增测试覆盖真实 cron origin、heartbeat terminal-late、事件循环非阻塞、跨入口并发 PATCH、真实 spawn pre-ready exit 与三类 callback shutdown。 |
| Correctness | 变更保留 single persistent owner、event/source allowlist、event-specific notice route、ordinary background route、external/shadow best-effort、selection mode、30 秒 monotonic startup 总预算与 callback 分类优先级。 |
| Coherence | Followed；与 approved incident/design、已归并 canonical current specs 和 Round 4 corrected delta 一致，没有新增 schema、durability、retry 或 channel-specific sender。 |

## F1–F5 mapping

| Finding | Implementation and permanent evidence | Result |
|---|---|---|
| F1 — cron/heartbeat session 也必须有 persistent Skill owner | `runtime_delivery/stream.py:38-70` 在 owner-direct per-run stream 前以同一 run anchor admission production manager；cron provider、heartbeat runner 与 composition 共用同一 manager（`cron_gateway_runtime.py:45-106`、`heartbeat_runner.py:55-81,221-234`、`composition.py:502-507,603-613`）。`test_owner_direct_stream_admits_one_persistent_skill_owner` 分别覆盖 cron terminal 前和 heartbeat terminal 后事件；`test_owner_direct_cron_skill_create_reaches_gateway_config_sync` 以 public Kernel `RunOrigin.CRON` 穿过真实 Skill write、persistent subscriber/to-thread handler 与 catalog sync。后续 foreground ensure 返回 `already_active`，证明没有第二 owner。 | covered |
| F1 — owner-direct 先 admission 不得吞普通后台结果 | manager 将 session 的第一个非空普通 background route 复制并冻结（`background_subscriptions.py:83-84,123-150,230-259,279-313`），notice 仍只按 originating trace 从独立 route 表 consume（`:88-111,214-228`）。新增 route-upgrade 测试断言 heartbeat-first 后普通 `BACKGROUND_TASK` assistant output 仍到原 conversation；既有 ensure-once 测试继续断言后续 ensure 不覆盖原 route。 | covered |
| F2 — 同步 external sender 不阻塞 Gateway event loop | `background.py:95-115` 只把现有 external sender 调用移入 `asyncio.to_thread`，再以 `inspect.isawaitable` 保留 async sender；external failure 仍被局部捕获，shadow 分支继续执行。新增 timing regression 证明 10ms loop tick 先于 100ms 同步 sender 完成且 sender 不在 loop thread；async sender、external failure 和 shadow failure 用例均通过。 | covered |
| F3 — Feishu activation 与 self-evolution 共享 mutation lock | `_enable_skills_for_agent()` 在既有 `threading.RLock` 内覆盖 selection gate、GET、merge、full PATCH 与 publish（`agent_config_sync.py:1057-1115`）；`handle_skill_created` 的 global multi-agent 外层锁仍可重入，未增加 retry。新增确定性 race 在首个 GET 阻塞期间并发 Feishu activation，最终 remote profile 与 live catalog 精确保留两项新 Skill；default discovery、explicit-empty、scope 既有测试同时通过。 | covered |
| F4 — pre-ready child exit fail-fast | `worker.py:320-340` 保留一个 30 秒 monotonic deadline，只将每次 Event wait 限为 50ms 并检查 child liveness；stop 的 join/terminate/kill 路径不变。新增真实 spawn child pre-bootstrap exit 在 5 秒测试预算前失败并完成 reap；controlled early-False 测试证明短 slice 不消耗或重置总预算。 | covered |
| F5 — callback helper 不改变分类与 shutdown | `_invoke_callback()` 仅集中 clear/await/warn/finally-set envelope（`background_session_events.py:39-60`）；原来的 ordinary background → marked Skill → structured notice `if/elif` 顺序、三个 callback、三条 warning 文案和外层 `CancelledError` 终止语义保持不变（`:204-268`）。参数化 regression 证明三类 accepted callback 都在 `aclose` 前完成。 | covered |

## No-regression and corrected-delta reconciliation

- Foreground exactly-once / route: coordinator 的 submit-before route registration、4096 oldest-first、missing-route fail-closed 和 submit rollback 没有在本 delta 修改；相关 route/coordinator tests 通过。
- Raw privacy / telemetry: `context_fork.py`、`self_improvement.py` 和 observer event classification 没有在本 delta 修改；public Kernel raw-visibility、hook true-update/no-write 与 tool telemetry tests 通过。
- Ordinary background / Feishu source routing: callback event allowlist、external metadata helper、notice text/schema 和 Feishu ordinary-message sender 均未改；ordinary background route-upgrade、source switching、IM-source no-Feishu、external/shadow independent failure tests 通过。
- CLI: `src/coding_cli/` 未修改；true update/no-write formatter regressions 通过。

Canonical current specs and the M3 corrected delta are unchanged by this range. F1 closes a missing production owner admission under the already approved D2 single-owner contract; F2–F5 are lifecycle/concurrency implementation closures that do not broaden an observable contract. Kernel true-update/raw-privacy, Gateway routing/external-channel, CLI Interactive REPL (Requirement count 8), and Gateway capability selection-mode claims remain aligned.

Corrected delta status: **aligned**.

## Verification evidence

- Patch-focused and no-regression matrix: **151 passed, 8 warnings in 19.53s**. This includes all eight changed test owners plus Kernel privacy/hook, per-trace routing, ordinary background, telemetry and CLI seams.
- Architecture contracts: **7 passed in 0.98s** (`cli_sdk_only`, `core_no_platform`, `platform_no_sdk`, `bg_origin_constant`).
- Quality: targeted Ruff passed; docs-check passed (**245** maintained Markdown sources / **67** required routes); `git diff --check 16397bbad..a2a180535` passed.
- The implementation owner recorded the final non-E2E suite on this patch head as **3245 passed, 28 warnings in 63.03s**. This delta verifier did not repeat full product Feishu/CLI journeys because the range does not change their product behavior and the task explicitly scoped verification to F1–F5.

## Issues

### CRITICAL

- None.

### WARNING

- None.

### SUGGESTION

- None.

Verdict: **pass**. The patch needs no implementation or corrected-delta change and does not require another full verification.

---

# Round 6 — corrected-delta reconciliation（F6/F7 + F8/F9）

> Validation snapshot: `f517d8554c729c93e413937dd33e3b300f6b3fda → a65dab64b6daca1c66f9bcc7dd4111d9f6656ec9`

## Corrected Delta Reconciliation

| Delta item | Final implementation evidence | Regression evidence | Outcome |
|---|---|---|---|
| `specs/kernel/runs.md` — raw side-chain 私有、真实 receipt、originating trace、no-write/incomplete 语义 | F6–F9 未触及 `context_fork.py`、`self_improvement.py` 或 trace chain；现行 Kernel hook 仍只以非空 `updated_targets` 发布 receipt | `test_self_improvement_hook.py`、`test_self_evolution_output_visibility.py` 通过 | aligned |
| `specs/gateway/routing-delivery.md` — structured-only notice、无更新静默、ordinary background 文本继续投递 | `runtime_delivery/background.py:25-39` 将同步 channel 调用统一移出 loop；`:212-258` 保留原 metadata、dedupe、external-first best-effort 和随后 IM mirror | `test_external_visible_delivery.py:97-208` 证明 ordinary background 的同步 sender 不阻塞、async sender 仍回到 loop、external failure 不阻断 shadow IM | aligned |
| `specs/gateway/external-channels.md` — 同源外发、shadow-only、telemetry 不外发 | `runtime_delivery/observer.py:249-331` 复用同一 offload seam，但保留原 phase、`reply_dedupe_key`、silence gate、external-context 条件；observer-local lock 保持 provider-facing normal reply 顺序 | `test_external_visible_delivery.py:318-484` 覆盖 intermediate/final 非阻塞、async sender、external failure 后 final IM；self-evolution notice/source-route suites 通过 | aligned |
| `specs/cli/interactive-repl.md` — 真实 target 才显示 CLI line | F6–F9 未修改 `src/coding_cli/` 或 CLI formatter | `test_cli_background_runs.py` 通过 | aligned |

本轮新增的普通外发 offload、IM readiness 诊断和 worker bootstrap 文案没有改变 self-evolution 的 true-receipt gate、触发源 route owner、raw privacy、CLI 文案或 canonical specs。`scripts/e2e-up.sh:171-176` 的 dedicated Bot lock 在启动 IM 前仍保持独立 owner 错误；`:255-275` 仅将 child exit 与 alive-but-not-ready deadline 区分为准确诊断。`worker.py:320-344` 的 "bootstrap readiness" 只描述 `_worker_bootstrap` handoff，不宣称 SDK/WebSocket 已连接。

E2E 默认冷启动预算由 `test_worktree_stack_lifecycle_e2e.py:219-252` 黑盒锁定：移除继承环境值后，真实 IM child 延迟 7 秒仍能经默认 budget 启动；`:256-321` 分别锁住 child exit 与 readiness timeout 的不同报错和 cleanup。

Uncovered Observable Behavior: None. 普通 external delivery 的内容、phase、dedupe、source routing 与 IM completion 都保持原有契约；新增线程切换和 E2E 报错分类是已批准的运行/验收边界收敛，不需要扩大本 unit 的 Kernel/Gateway/CLI delta-spec。

Outcome: **aligned**.

## Verification evidence

- `test_external_visible_delivery.py` — **12 passed**；`test_feishu_worker_runtime.py` — **11 passed**；`test_worktree_stack_lifecycle_e2e.py` — **4 passed**；observer/shadow lifecycle — **67 passed**。
- true-receipt/raw privacy/source routing/CLI focused matrix — **50 passed**。
- `bash -n scripts/e2e-up.sh scripts/e2e-down.sh`、targeted Ruff、docs-check（226 maintained Markdown sources / 67 required routes）与 `git diff --check f517d855..a65dab64` 均通过。

All checks passed. Ready for PR.
