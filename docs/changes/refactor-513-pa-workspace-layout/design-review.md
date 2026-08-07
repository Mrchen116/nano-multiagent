# Design Review: refactor-513-pa-workspace-layout

## Round 1

### Metadata

- reviewer: `/root/refactor_513_design_reviewer`
- review_mode: `full`
- mode_reason: 首轮独立审查；设计、delta-spec 与 milestone 尚未进入实现。
- started_at: `2026-08-07T14:28:23+0800`
- completed_at: `2026-08-07T14:38:36+0800`
- duration: `10m 13s`

### Verdict

Issues Found — 5 CRITICAL / 2 WARNING

设计把“按 workspace 选择产品目录”提升为 core 的纯路径模块、并把 PA/CLI 的产品差异留在 SDK 装配面，方向符合架构边界；M1 是必要的先决纵切，M2/M3 的并行关系也成立。但目前的 execution-scope 安全 seam、IM 的默认 workspace 所有权、五份 delta 的可合并性，以及 JWT runbook 都还没有达到可派发实现的程度。

### Coverage

| 载体 | 覆盖内容 | 结论 |
|---|---|---|
| motivation | 全部 8 个 Requirement、18 个澄清及范围/非目标/人工迁移 | 覆盖；R2 chat-history 缺 delta（R1-C4），R3 的默认 Agent 还遗漏 IM owner（R1-C2），JWT 场景受 R1-C5 影响。 |
| design | 现状分析、7 项决策、SDK/data flow、迁移、风险、reviewer runbook、M1–M3 | 覆盖；关键执行 scope、迁移顺序和 runbook 有缺口。 |
| kernel delta | `tools-hooks.md` 的 ADDED+MODIFIED 与 `background-tasks.md` 的 ADDED | 背景输出新增契约可合并；tools MODIFIED 丢失既有场景（R1-C3）。 |
| gateway delta | `heartbeat-cron.md` MODIFIED、`service-lifecycle.md` ADDED+MODIFIED | 均覆盖到；两个 MODIFIED 不可按规则合并（R1-C3）。 |
| CLI delta | `product-integration.md` MODIFIED | 覆盖到；丢失既有装配场景（R1-C3）。 |
| 长期契约与架构 | `SPEC.md:151-161`、`docs/specs/CONTRIBUTING.md:114-155`、上述 4 个 canonical spec | 已核对；核心/SDK 分层方向正确，delta 完整替换纪律未满足。 |
| 现状代码与运维 | kernel/engine/platform loaders、PA Gateway/IM、CLI、JWT 与 E2E/prod runbook | 已核对；下列 Issues 均有当前事实证据。 |

### 核实台账

#### Motivation requirements and scenarios

| Requirement / scenarios | 设计与 delta 对应 | 核验结果 |
|---|---|---|
| R1 kernel default (`motivation.md:139-143`) | D1、D2、M1、kernel deltas | OK；`build_kernel` 已以 `.nano` 作为未传参默认（`src/agent/sdk/kernel.py:229-243`）。 |
| R2 PA state: 新状态 / chat 副本 / migrated heartbeat (`motivation.md:145-159`) | D4–D5、M2、gateway deltas | Partial；heartbeat 有目标，chat-history 的用户契约没有 delta（R1-C4）。 |
| R3 PA home/default workspace: 新 Agent、全局迁移、遗留文件、冲突、JWT、外部 workspace (`motivation.md:161-190`) | D5–D7、M2、gateway lifecycle delta | Partial；Gateway 目标正确，但 IM 对 managed default 的独立计算没有进入范围（R1-C2），JWT 顺序冲突（R1-C5）。 |
| R4 CLI state (`motivation.md:192-196`) | D1–D4、M3、CLI delta | Conditional；实现分层合理，但 CLI MODIFIED delta 不可合并（R1-C3）。 |
| R5 shared extensions: PA / CLI / collision / post-migration change (`motivation.md:198-218`) | D2、D6、M1–M3 | Conditional；scope/cache/priority 有明确方向，需先封住同一 scope 的 policy/hook seam（R1-C1）。 |
| R6 policy: migration / PA+CLI command (`motivation.md:220-230`) | D3–D4、M1 | Blocked；现有 pre-tool policy 不是随 `ToolContext` 自动选址，设计尚未给出可实现的传递契约（R1-C1）。 |
| R7 legacy data and Git (`motivation.md:232-241`) | D6、migration table、M2/M3 | OK；“不加 runtime fallback、不改 `.gitignore`”与范围一致。 |
| R8 terminal-only runtime (`motivation.md:243-248`) | D6、M2/M3 | Conditional；目标清楚，运行态兼容未被引入；迁移操作的 secret 顺序仍需修正（R1-C5）。 |

#### Clarifications and non-goals

| Clarification | Design coverage | Result |
|---|---|---|
| Q1 directory selection (`motivation.md:39-46`) | D1, M1 | OK. |
| Q2 extension fork (`motivation.md:48-50`) | D6, migration table | Conditional on the explicit manual runbook; no runtime import is proposed. |
| Q3 target collision (`motivation.md:52-54`) | D6, migration table | OK: stop/no-overwrite rule is present. |
| Q4 legacy runtime files (`motivation.md:56-58`) | D6 | OK: no automatic relocation. |
| Q5 readable chat copy (`motivation.md:60-62`) | D5, M2 | Missing permanent contract carrier (R1-C4). |
| Q6 no subsequent extension sync (`motivation.md:64-66`) | D6 | OK. |
| Q7 PA heartbeat relocation (`motivation.md:68-70`) | D5, Gateway deltas | Conditional on the mergeable lifecycle/heartbeat delta correction (R1-C3). |
| Q8 no Git changes (`motivation.md:72-74`) | D6, R7 | OK. |
| Q9 CLI has no PA chat history (`motivation.md:76-78`) | D5, M3, CLI delta | Conditional on the mergeable CLI delta correction (R1-C3). |
| Q10 legacy heartbeat copy (`motivation.md:80-82`) | D6, migration table | OK as a manual-only operation. |
| Q11 global/default workspace is in scope (`motivation.md:84-86`) | D5, M2 | Incomplete: IM's related default resolver is omitted (R1-C2). |
| Q12 one PA global home (`motivation.md:88-93`) | D5 | Incomplete for the same IM default owner (R1-C2). |
| Q13 legacy global/default roots (`motivation.md:95-97`) | D6, migration table | OK, subject to conflict handling. |
| Q14 retain relative legacy files after move (`motivation.md:99-101`) | D6, migration table | OK. |
| Q15 conflicts retain both sides (`motivation.md:103-105`) | D6, migration table | OK. |
| Q16 all migration is manual (`motivation.md:107-109`) | D6 | OK; supersedes the earlier “first launch” wording. |
| Q17 policy migration and terminal selection (`motivation.md:111-113`) | D4, M1 | Blocked by unresolved pre-hook layout contract (R1-C1). |
| Q18 stable IM JWT move (`motivation.md:115-117`) | D7, M2 | Blocked by contradictory migration order (R1-C5). |
| Scope/non-goals (`motivation.md:250-261`) | D1/D5/D6, M1–M3 | Covered; no new compatibility state machine or Git mutation is introduced. |

#### Current-state assertions, constraints, and decisions

| Carrier | Current evidence | Result |
|---|---|---|
| shared build-time tools/hooks assertion (`design.md:13-16`) | build 初始化确实绑定 workspace loader/registry（`src/agent/sdk/kernel.py:550-590`, `742-806`）；engine 后续将共享 registry 注入 hook context（`src/agent/core/agent/runtime.py:1444-1461`） | Confirmed；D2/D3 选 session scope 是正确根因方向。 |
| PA/CLI directory assertion (`design.md:15-16`) | PA 传 `.nanoassistant`（`src/personal_assistant/product.py:39-63`），CLI 传 `.nanocode`（`src/coding_cli/product.py:30-51`） | Confirmed。 |
| core/platform/sdk constraints (`design.md:21-24`) | 架构契约为 product → sdk、platform → core、core 不依赖 platform（`SPEC.md:151-161`） | Confirmed；D1 core layout、D2 SDK resolver 的归属符合该方向。 |
| D1 `WorkspaceLayout` (`design.md:63-67`) | `derive_memory_root` 已是纯路径模式（`src/agent/core/memory/path.py:15-29`） | Sound。 |
| D2 workspace capability scope (`design.md:69-75`) | loaders 有 workspace/global 分层和 replace 行为（`src/agent/platform/tools/loader.py:37-91`, `src/agent/platform/hooks/loader.py:27-82`） | Sound direction；须与 D3/D4 的 pre-hook scope 一并落地（R1-C1）。 |
| D3 immutable per-turn scope (`design.md:77-81`) | engine 当前把共享 `_tool_registry` 与 `_repo_root` 放入 `HookContext`（`src/agent/core/agent/runtime.py:1444-1461`） | Incomplete（R1-C1）。 |
| D4 all artifacts use session layout (`design.md:83-87`) | background output 现在在 build-time root 固化（`src/agent/platform/background_tasks/file_output.py:13-71`）；bash permission check 走 pre-hook（`src/agent/platform/tools/builtins/bash.py:217-268`） | Incomplete（R1-C1）；dangerous-path 现状表述也不准确（R1-W1）。 |
| D5 PA home/default workspace (`design.md:89-93`) | IM 仍独立使用 `~/nano-assistant/workspace/<agent>` 判定 managed workspace（`src/IM/domain/models.py:8-41`） | Incomplete（R1-C2）。 |
| D6 manual-only migration (`design.md:95-99`) | 目标不保留 compatibility runtime；与 R8 一致 | Sound。 |
| D7 JWT no rotation (`design.md:101-103`) | IM 未设环境变量会生成进程内随机 secret（`src/IM/application/auth_service.py:223-233`） | Intended guarantee is necessary, but migration flow contradicts it（R1-C5）。 |

#### Delta-spec requirements

| Delta carrier | Requirement | Result |
|---|---|---|
| `specs/kernel/tools-hooks.md:5-16` | SDK session-local extension discovery | Sound ADDED requirement. |
| `specs/kernel/tools-hooks.md:20-27` | built-in tools and workspace safety | Blocked: MODIFIED omits the canonical timeout/output/query scenarios（R1-C3）。 |
| `specs/kernel/background-tasks.md:5-12` | background output follows session directory | Sound ADDED requirement. |
| `specs/gateway/heartbeat-cron.md:5-12` | heartbeat/cron location | Blocked: MODIFIED drops the original 11 scenarios（R1-C3）。 |
| `specs/gateway/service-lifecycle.md:5-11` | global home/default workspace | Conditional: Gateway behavior is stated, but IM's managed-default owner is missing（R1-C2）。 |
| `specs/gateway/service-lifecycle.md:15-17` | IM heartbeat preview RPC | Blocked: tries to MODIFY a canonical scenario rather than its containing requirement（R1-C3）。 |
| `specs/cli/product-integration.md:5-12` | CLI product integration | Blocked: MODIFIED drops the canonical product-assembly scenario（R1-C3）。 |

#### Milestones and reviewer handoff

| Carrier | Result |
|---|---|
| M1 (`design.md:205`) | Necessary first milestone and its tests enumerate main/subagent/slash/fork/compaction paths. It cannot meet the policy criterion until R1-C1 gives an explicit hook-scope contract. |
| M2 (`design.md:206`) | Correctly owns PA persistence and operations, but its listed code/test range omits IM managed-workspace code and its contract impact（R1-C2）；JWT acceptance is inconsistent（R1-C5）。 |
| M3 (`design.md:207`) | M1 dependency and M2 parallelism are justified; scope is independent after M1. Delta merge failure remains blocking（R1-C3）。 |
| Reviewer runbook (`design.md:188-197`) | Worktree isolation and real-stack intent are useful; stated health checks do not prove Gateway registration/RPC path（R1-W2）。 |

### 架构进攻

1. **Ownership.** `WorkspaceLayout` belongs in core because it is pure path derivation, and a resolver that loads platform extensions belongs in SDK; this respects `platform → core` and keeps PA/CLI identities out of core. The proposed M2 must nevertheless update IM's *own* managed-default calculation rather than having IM import PA or agent; otherwise a cross-product boundary violation would merely replace the omitted behavior.
2. **Deletion / smallest seam.** A single immutable capability scope is warranted because one shared Kernel currently owns both registry and hook runner. No new product-profile abstraction is needed. The missing part is not another module: it is an explicit scope-to-`HookContext` and policy-loader contract at the existing pre-tool gate.
3. **Depth.** D1 removes repeated literal path construction, and D2 makes workspace extension precedence one policy. Leaving auto-mode fallback, Bash policy override selection, and hook registry lookup implicit would reintroduce three shallow special cases, each capable of selecting a different workspace during one turn.
4. **Root cause.** Manual migration correctly removes the pressure for permanent old-path compatibility. It does not solve the release-order problem: verifying the stable JWT source only after IM is stopped creates the exact accidental key-loss path D7 forbids.

### Issues

#### R1-C1 — CRITICAL: The execution-scope design does not specify how the security pre-hook receives the selected workspace layout

**Carrier:** D3/D4 and the SDK/core seam (`design.md:77-87`, `109-117`); M1 exit criteria (`design.md:205`).

**Evidence:** today `AgentEngine._build_hook_context` writes the shared engine registry and build-time repo root into every `HookContext` (`src/agent/core/agent/runtime.py:1444-1461`). `auto_mode_gate` reads that context's registry and, without an injected loader, falls back to `<repo_root>/.nanocode` (`src/agent/platform/hooks/builtins/auto_mode_gate.py:775-798`). Bash permission classification runs at this pre-tool point (`src/agent/platform/tools/builtins/bash.py:217-268`), while the only override loader is hard-wired to `<repo_root>/.nano/policy.toml` (`src/agent/platform/tools/builtins/bash_policy.py:145-163`).

**Why this blocks implementation:** D4 states the desired result but not the contract that carries a scope-specific registry, layout/config loader, and policy overrides through `HookContext` before `BashTool.check_permissions`. Two workers could each make the normal tool path session-local yet leave the auto-mode/policy chain shared or hard-coded. That would let PA Agent A evaluate Agent B's tool/policy, or let either product ignore its selected directory, violating R5/R6's isolation and security behavior.

**Required correction:** specify the one per-turn scope object/metadata contract and owner that `AgentEngine` uses for *all* hook events; name how `auto_mode_gate` obtains the same registry and auto-mode config and how `BashTool.check_permissions` receives the layout's policy override. Add M1 acceptance tests that run two workspaces with conflicting policy/auto-mode/tool definitions through the real pre-hook gate, in addition to discovery tests.

#### R1-C2 — CRITICAL: M2 leaves the IM service's managed-default workspace algorithm on the retired path

**Carrier:** PA home/default decision and M2 scope (`design.md:89-93`, `171-176`, `205-207`).

**Evidence:** IM independently derives and classifies a managed workspace as `~/nano-assistant/workspace/<agent-id>` (`src/IM/domain/models.py:8-41`). The design lists `im: no spec delta` and M2 lists only `personal_assistant`/operations/Gateway work, despite promising `~/.nanoassistant/workspaces/<agent-id>` for newly created default Agents.

**Why this blocks implementation:** Gateway can create the new directory while IM continues to report/classify the old one as default. That corrupts the IM-facing profile/default semantics and can route a heartbeat/cron request with the old workspace mirror. The needed change must be IM-owned (or redefine the IM-facing contract), not a forbidden `IM → personal_assistant` or `IM → agent` import.

**Required correction:** make an explicit decision for IM's managed-default resolver and existing persisted/default profiles, add its source and tests to M2, and add/modify the appropriate IM/Gateway observable spec carrier. State that IM remains independently deployed and receives no product/internal imports.

#### R1-C3 — CRITICAL: Four MODIFIED delta requirements are not mergeable because they omit canonical content or target a scenario

**Carrier:** all MODIFIED deltas.

**Evidence:** delta rules require a MODIFIED requirement to reproduce the complete updated requirement and replace only its same-named canonical entry (`docs/specs/CONTRIBUTING.md:124-155`). The kernel delta keeps only its new override scenario (`specs/kernel/tools-hooks.md:20-27`) and drops canonical output/timeout/list-session-tools scenarios (`docs/specs/kernel/tools-hooks.md:14-28`). The heartbeat delta keeps only one new scenario (`specs/gateway/heartbeat-cron.md:5-12`) but replaces a requirement with eleven canonical scenarios (`docs/specs/gateway/heartbeat-cron.md:14-95`). The lifecycle delta's title is a canonical *scenario* (`specs/gateway/service-lifecycle.md:15-17` versus `docs/specs/gateway/service-lifecycle.md:90-100`), while the containing requirement starts at `docs/specs/gateway/service-lifecycle.md:62` and also owns cron RPC scenarios. The CLI delta omits canonical “CLI 装配保持在产品包” (`specs/cli/product-integration.md:5-12` versus `docs/specs/cli/product-integration.md:20-33`).

**Why this blocks implementation:** applying these deltas would silently erase stable user contracts and gives verifiers no unambiguous target. The lifecycle file cannot be mechanically or semantically merged at all.

**Required correction:** rewrite each MODIFIED entry as the complete canonical requirement with only the intended path changes; preserve every existing scenario verbatim unless deliberately changed, then include the changed/new scenario. Modify the lifecycle *requirement* and preserve its heartbeat and cron RPC scenarios.

#### R1-C4 — CRITICAL: The required human-readable PA chat-history behavior has no delta-spec carrier

**Carrier:** PA workspace state (`motivation.md:145-154`), D5 (`design.md:89-93`), delta inventory (`design.md:171-176`).

**Evidence:** the motivation explicitly retains a user/assistant text copy at `.nanoassistant/chat_history/`; D5 repeats it. None of the five declared delta files contains `chat_history`, and no corresponding canonical PA behavior has been selected for modification.

**Why this blocks implementation:** this is an explicit user-observable persistence guarantee, distinct from session transcript, but it would have no merge target or acceptance contract. A worker can move the hook while the permanent spec loses the guarantee.

**Required correction:** add an appropriate Gateway/PA delta requirement (and identify/create its canonical home) that specifies the readable copy, its `.nanoassistant/chat_history/` location, and that it does not replace the transcript. Include it in M2 verification.

#### R1-C5 — CRITICAL: The JWT migration order contradicts the no-rotation guarantee

**Carrier:** D7 (`design.md:101-103`) versus migration graph/table (`design.md:147-167`) and M2 acceptance (`design.md:206`).

**Evidence:** D7 requires the secret to be verified non-empty *before* IM stops. The graph begins by stopping IM and performs secret verification later; the table says “停 IM 后移动”. If the new environment is empty, IM falls back to a new process-random secret (`src/IM/application/auth_service.py:223-233`), exactly breaking the no-rotation/login-continuity goal. Current production guidance also says to read/reuse the secret before stopping IM (`docs/operations/prod-fleet.md:40`).

**Why this blocks implementation:** operators have two contradictory authoritative paths during a production migration; the unsafe one can revoke every Web IM login session.

**Required correction:** replace the graph/table/runbook with one ordered, fail-closed procedure: inspect and validate the old non-empty secret and its contents/permissions before stopping IM; copy/move to the new path without generation; validate equality and `0600` at the new path; only then stop/restart with `IM_JWT_SECRET` sourced from that exact new path. Define the recovery point before deleting the old source.

#### R1-W1 — WARNING: The `dangerous_paths` baseline asserted by D4 is factually incomplete

**Carrier:** D4 (`design.md:87`).

**Evidence:** D4 says `.nano`, `.nanocode`, and old `.nano-assistant` protections “保持不变” while adding `.nanoassistant`. The actual protected set contains `.nanocode` and `.nano-assistant`, but not `.nano` (`src/agent/platform/tools/dangerous_paths.py:46-55`).

**Impact:** a worker following the stated delta may add only `.nanoassistant`, leaving the default SDK directory contrary to the claim and to the product-managed persistence safety rationale.

**Recommendation:** correct the current-state statement and declare the intended terminal protected set explicitly, then cover it in M1 safety tests.

#### R1-W2 — WARNING: The reviewer runbook's health checks do not establish a functioning Gateway/IM path

**Carrier:** reviewer runbook (`design.md:188-197`).

**Evidence:** the worktree health check proves only IM OpenAPI responds and that a Gateway PID file exists (`design.md:192`). A PID file can remain after a failed registration; normal fleet availability requires both nodes to be online (`docs/operations/prod-fleet.md:42-49`).

**Impact:** the reviewer can incorrectly pass a path-migration change without proving the IM → Gateway heartbeat/cron RPC or the expected per-workspace file paths.

**Recommendation:** add a concrete post-start assertion for registered/online test node(s), then execute `node.heartbeat.md.request` and cron list/delete against a PA workspace and assert `.nanoassistant` paths/content. Keep the stated real CLI journey, but name its temporary workspace tool/background-output assertion as well.

### Recommendations

1. Resolve R1-C1 through R1-C5 and regenerate the delta files before design approval; their corrections change implementation scope and canonical acceptance, not merely wording.
2. After the scope contract is explicit, make M1's isolation test use two concurrent sessions with conflicting workspace tool, hook, auto-mode, and policy inputs. This exercises the exact shared-Kernel failure mode rather than only loader discovery.
3. Keep M2/M3 parallel after M1, but add IM source/tests to M2 and use the strengthened runbook as the reviewer-owned cross-product proof.

### Author Resolutions

| Issue | Resolution |
|---|---|
| R1-C1 | D3 now defines `WorkspaceExecutionScope` ownership, creation timing and the exact immutable `HookContext` metadata contract. It names the scope-provided registry, auto-mode config loader and bash policy overrides consumed at the actual pre-tool gate; M1 now requires two concurrent workspaces with conflicting tool/hook/auto-mode/policy inputs through `auto_mode_gate`. |
| R1-C2 | D5, M2 and a new IM delta make `IM.domain` independently own `~/.nanoassistant/workspaces/<agent-id>` and `workspace_is_default`, with no PA/agent import. The manual migration now includes exact old-default `agent_profiles.workspace_root` rewrite while preserving external paths. |
| R1-C3 | Rewrote all four MODIFIED entries as complete replacement requirements. `tools-hooks`, `heartbeat-cron` and CLI preserve every canonical scenario; service lifecycle now modifies its containing Gateway↔IM requirement and preserves heartbeat plus cron RPC scenarios. |
| R1-C4 | Added `specs/gateway/routing-delivery.md` for PA's readable `.nanoassistant/chat_history/<conversation-id>.jsonl` copy and its transcript-nonreplacement guarantee; M2 verification includes it. |
| R1-C5 | Reordered the migration graph, table and reviewer runbook: validate/copy/compare the non-empty `0600` secret while IM is still running, retain source through new IM plus two-Gateway online verification, then delete source. No step generates a key. |
| R1-W1 | Corrected the factual baseline and made the terminal protected set explicit: `.nano`, `.nanoassistant`, `.nanocode`, `.nano-assistant`; M1 owns tests. |
| R1-W2 | Reviewer worktree health check now logs in to the isolated IM, asserts the generated node is `online` from `/im/v1/nodes`, then M2 executes the existing heartbeat/cron RPC journey and verifies product-directory files. |

Review request: please re-review the frozen design, all delta-spec files and milestones as Round 2. Record an Approved verdict only if all critical/warning findings are resolved; otherwise append only newly discovered findings.

## Round 2

### Metadata

- reviewer: `/root/refactor_513_design_reviewer`
- review_mode: `full`
- mode_reason: R1 findings caused changes to the shared core/SDK execution seam, a new SDK public parameter, an IM-owned contract, four rewritten and two new delta areas, plus M2 scope and migration flow. These are high-risk cross-module interface and shared-contract changes, so closure/delta review could not bound their effects.
- started_at: `2026-08-07T14:50:07+0800`
- completed_at: `2026-08-07T14:53:43+0800`
- duration: `3m 36s`

### Verdict

Issues Found — 4 CRITICAL / 0 WARNING

R1's scope isolation, IM ownership, MODIFIED-entry preservation, chat-history carrier, dangerous-path baseline and reviewer-node health evidence are now closed. The frozen set still omits three necessary current-spec carriers and lets the first migration action overwrite a conflicting JWT target before conflict detection. It is therefore not ready for `change-orchestrator`.

### Coverage

| Carrier | Re-checked scope | Result |
|---|---|---|
| R1 resolutions | All 5 CRITICAL and 2 WARNING resolutions against frozen design, delta, milestones and current source | 6 closed; R1-C5 has a narrower unclosed target-conflict case recorded as R2-C4. |
| Motivation | 8 Requirements, Q1–Q18, scope/non-goals and migration (`motivation.md:39-281`) | All re-read; security-policy contract and conflict safety remain uncovered in permanent carriers (R2-C3, R2-C4). |
| Design | Current assertions, D1–D7, public SDK table, data flow, migration, risks, reviewer runbook, M1–M3 (`design.md:9-212`) | Core architecture is now coherent; public API/delta and migration collision gaps remain. |
| Delta spec | 9 ADDED/MODIFIED entries in 7 area files | Existing MODIFIED entries are complete; missing SDK Boundary and package-index delta carriers leave the set incomplete (R2-C1, R2-C2). |
| Current contracts/code | `docs/specs/*`, SDK/engine/platform, PA hook, IM resolver/config/persistence, operations | Rechecked where each resolution changes an observable or ownership boundary. |

### 历史问题闭环

| 历史项 | Author Resolution | 本轮核实 | 状态 |
|---|---|---|---|
| R1-C1 | `WorkspaceExecutionScope` specifies immutable metadata, registry, config loader and policy overrides. | D3 explicitly fixes `repo_root`, immutable metadata fields, pre-tool auto-mode loader and `BashTool.check_permissions` input (`design.md:77-83`); M1 invokes conflicting workspaces through the actual pre-tool chain (`design.md:210`). This addresses the current shared `HookContext` seam (`src/agent/core/agent/runtime.py:1444-1461`). | closed |
| R1-C2 | IM owns the new managed-default resolver without importing PA/agent. | D5 says IM remains independent (`design.md:91-95`); M2 includes IM domain/config/persistence/API/tests (`design.md:211`); IM delta makes the path and external-workspace classification observable (`specs/im/agents-nodes.md:5-16`). This covers current independent resolver/config use (`src/IM/domain/models.py:8-41`, `src/IM/application/config_service.py:221-249`). | closed |
| R1-C3 | All four MODIFIED requirements were rewritten as complete replacements. | Kernel, Gateway heartbeat/lifecycle and CLI deltas now retain the canonical scenarios and lifecycle modifies its containing Requirement (`specs/kernel/tools-hooks.md:20-39`, `specs/gateway/heartbeat-cron.md:5-86`, `specs/gateway/service-lifecycle.md:15-53`, `specs/cli/product-integration.md:5-18`). | closed |
| R1-C4 | New Gateway routing/delivery delta owns readable chat copy. | The ADDED requirement preserves readable JSONL, terminal path and transcript distinction (`specs/gateway/routing-delivery.md:5-16`), matching M2 reviewer proof (`design.md:211`). | closed |
| R1-C5 | Source secret is verified and retained through fleet verification. | The source-side order is now correct (`design.md:103-105`, `149-160`, `172-174`). However, copying occurs before testing whether a pre-existing target differs; that unresolved case is R2-C4. | superseded by R2-C4 |
| R1-W1 | Protected-set baseline corrected. | D4 now accurately states current set and explicitly defines terminal `.nano`, `.nanoassistant`, `.nanocode`, `.nano-assistant` (`design.md:89`). | closed |
| R1-W2 | Runbook verifies authenticated online node, then RPC journey. | Worktree health authenticates, checks the named node's online status, and M2 requires heartbeat/cron RPC proof (`design.md:197`, `211`). | closed |

### 核实台账

#### Current assertions and decisions

| Carrier | Evidence | Result |
|---|---|---|
| Shared build-time extension state (`design.md:13-16`) | SDK currently loads workspace tools/hooks during build (`src/agent/sdk/kernel.py:550-590`, `742-806`); engine currently injects shared registry/root into hooks (`src/agent/core/agent/runtime.py:1444-1461`). | Grounding remains correct; D2/D3 address the actual seam. |
| PA/CLI existing directory inputs (`design.md:15-16`) | PA passes `.nanoassistant` (`src/personal_assistant/product.py:421-432`); CLI passes `.nanocode` (`src/coding_cli/product.py:144-154`). | Confirmed. |
| Core/platform/product boundary (`design.md:21-24`) | `SPEC.md:151-161` requires product → SDK, platform → core, and no core → platform. | D1/D2 ownership remains compliant. |
| D1 layout (`design.md:63-67`) | Existing memory path derivation is a pure core pattern (`src/agent/core/memory/path.py:15-29`). | Sound. |
| D2 extension scope (`design.md:69-75`) | Platform loaders already express global/workspace layering and replace semantics (`src/agent/platform/tools/loader.py:37-91`, `src/agent/platform/hooks/loader.py:27-82`). | Sound. |
| D3 scope and public API (`design.md:77-83`, `111-117`) | Scope-to-hook contract is now specific; its new `global_config_root` changes public `build_kernel` yet current public signature/contract do not contain it (`src/agent/sdk/kernel.py:229-246`, `docs/specs/kernel/sdk-boundary.md:47-61`). | Scope closed; public API carrier missing (R2-C2). |
| D4 artifacts/policy (`design.md:85-89`) | Current Bash policy loader is `.nano`-literal (`src/agent/platform/tools/builtins/bash_policy.py:145-163`), and current `BashTool` pre-check does not supply overrides (`src/agent/platform/tools/builtins/bash.py:217-268`). | Design contract is adequate, but its user-observable policy selection has no delta assertion (R2-C3). |
| D5 default home (`design.md:91-95`) | IM currently normalizes/defaults workspace paths independently (`src/IM/application/config_service.py:221-249`) and PA chat hook currently writes workspace-root history (`src/personal_assistant/hooks/chat_history.py:92-113`). | New IM and chat deltas correctly own both changes. |
| D6/D7 migration (`design.md:97-105`, `147-174`) | Current production guidance preserves source secret before shutdown (`docs/operations/prod-fleet.md:40`); IM missing `IM_JWT_SECRET` generates a random process key (`src/IM/application/auth_service.py:223-233`). | Source ordering fixed; pre-existing target conflict is not safe (R2-C4). |

#### Motivation requirements, clarifications, and non-goals

| Item | Frozen design/delta coverage | Result |
|---|---|---|
| R1 default `.nano` | D1, M1, kernel tools/hooks delta | Covered. |
| R2 PA workspace state and chat copy | D4/D5, M2, Gateway deltas | Covered. |
| R3 PA home/default workspace and JWT | D5–D7, M2, IM/Gateway deltas | Default path covered; target-secret conflict remains R2-C4. |
| R4 CLI workspace state | D1–D4, M3, CLI delta | Covered. |
| R5 extension fork/precedence | D2/D6, M1–M3 | Covered. |
| R6 product-directory policy | D3/D4, M1 | Missing observable delta requirement (R2-C3). |
| R7 legacy data/Git | D6, M2/M3 | Covered; no runtime compatibility or Git mutation. |
| R8 terminal-only runtime | D6, M2/M3 | Covered, subject to safe manual migration (R2-C4). |
| Q1 directory selection | D1/M1 | Covered. |
| Q2 extension fork | D6/table | Covered as manual-only. |
| Q3 extension collision | D6/table | Covered. |
| Q4 legacy runtime files | D6 | Covered. |
| Q5 readable chat copy | D5/M2/routing-delivery delta | Covered. |
| Q6 no re-sync | D6 | Covered. |
| Q7 heartbeat relocation | D5/heartbeat+lifecycle deltas | Covered. |
| Q8 no Git changes | D6 | Covered. |
| Q9 CLI no chat history | D5/M3/CLI delta | Covered. |
| Q10 manual heartbeat copy | D6/table | Covered. |
| Q11 global/default scope | D5/M2/IM delta | Covered. |
| Q12 single PA home | D5/M2/IM delta | Covered. |
| Q13 old global/default roots | D6/table | Covered subject to R2-C4. |
| Q14 retain relative legacy files | D6/table | Covered. |
| Q15 conflict preserves both sides | D6/table | Not met for the secret target (R2-C4). |
| Q16 no runtime migration | D6 | Covered. |
| Q17 policy migration/terminal selection | D4/M1 | Missing permanent policy behavior carrier (R2-C3). |
| Q18 stable JWT move | D7/M2 | Not met when target already differs (R2-C4). |
| Scope and non-goals (`motivation.md:250-261`) | D1/D5/D6, M1–M3 | No out-of-scope compatibility state machine or Git mutation; covered. |

#### Delta-spec and milestone inventory

| Carrier | Result |
|---|---|
| kernel `tools-hooks` ADDED (`specs/kernel/tools-hooks.md:5-16`) | Extension behavior is consumer-facing and complete. |
| kernel `tools-hooks` MODIFIED (`specs/kernel/tools-hooks.md:20-39`) | Canonical scenarios preserved, but does not state selected-directory policy behavior (R2-C3). |
| kernel `background-tasks` ADDED (`specs/kernel/background-tasks.md:5-12`) | Complete. |
| Gateway `heartbeat-cron` MODIFIED (`specs/gateway/heartbeat-cron.md:5-86`) | Complete replacement and correct new heartbeat path. |
| Gateway `service-lifecycle` ADDED+MODIFIED (`specs/gateway/service-lifecycle.md:5-53`) | Complete replacements. |
| Gateway `routing-delivery` ADDED (`specs/gateway/routing-delivery.md:5-16`) | Correct canonical owner for chat copy. |
| IM `agents-nodes` ADDED (`specs/im/agents-nodes.md:5-16`) | Correct independent-IM consumer contract. |
| CLI `product-integration` MODIFIED (`specs/cli/product-integration.md:5-18`) | Complete replacement. |
| kernel `sdk-boundary` | Required public `global_config_root` change has no delta (R2-C2). |
| kernel/gateway/IM package indexes | New Requirements would make current counts stale unless their `spec.md` entries are updated; no carrier is included (R2-C1). |
| M1 (`design.md:210`) | Correct prerequisite and reviewer/worker tracks; needs R2-C2/R2-C3 contract completion. |
| M2 (`design.md:211`) | IM range now belongs here and is independent; needs R2-C1/R2-C4 correction. |
| M3 (`design.md:212`) | Correctly depends only on M1 and has no concurrent file-range collision with M2. |

### 架构进攻

1. **Ownership.** `WorkspaceLayout` in core, SDK-owned resolver/scope construction, platform loaders, and independent IM default-path calculation now follow the dependency graph. No product identity leaks into core and IM still does not import PA/agent.
2. **Deletion test.** A single immutable execution scope remains necessary to prevent shared-Kernel registry/hook mutation. The newly explicit metadata port avoids a second policy-specific bridge; no needless ProductProfile or product-specific core abstraction appears.
3. **Depth.** The scope concentrates path, registry and security selection in one boundary and gives workers an unambiguous pre-tool path. The permanent spec set, however, still fails to expose two necessary external seams: SDK consumers cannot rely on the new public argument, and consumers cannot rely on their selected `policy.toml` (R2-C2/R2-C3).
4. **Root cause.** Manual migration remains the right removal of obsolete runtime compatibility. Copying a JWT target before testing the target is the same overwrite class the manual migration was chosen to avoid; it leaves a production data-loss/security branch (R2-C4).

### Issues

#### R2-C1 — CRITICAL: Added requirements have no package-index update carrier, so the merged current specs cannot remain mechanically valid

**Carrier:** delta inventory (`design.md:176-181`) and M1/M2 (`design.md:210-211`).

**Evidence:** each package's `Canonical Areas` count is mechanically checked against `### Requirement:` headings (`docs/specs/CONTRIBUTING.md:94-100`). The frozen deltas add one requirement to kernel Background Tasks and Tools/Hooks (`specs/kernel/background-tasks.md:5-12`, `specs/kernel/tools-hooks.md:5-16`), Gateway Service Lifecycle and Routing/Delivery (`specs/gateway/service-lifecycle.md:5-11`, `specs/gateway/routing-delivery.md:5-16`), and IM Agents/Nodes (`specs/im/agents-nodes.md:5-16`). Current indexes still say kernel `4`/`10` (`docs/specs/kernel/spec.md:25-27`), Gateway `5`/`13` (`docs/specs/gateway/spec.md:21-24`), and IM `20` (`docs/specs/im/spec.md:26`). No `specs/{kernel,gateway,im}/spec.md` carrier appears in the frozen inventory.

**Why this blocks implementation:** after the otherwise-correct area deltas are merged, `scripts/docs-check` will fail or the index will advertise stale counts. The workers and final verifier have no declared artifact telling them to update those current contracts.

**Required correction:** add the three package-entry updates to the delta/merge inventory and M1/M2 scope, changing the derived counts to kernel Background Tasks `5`, Tools and Hooks `11`; Gateway Routing and Delivery `14`, Service Lifecycle `6`; and IM Agents and Nodes `21`.

#### R2-C2 — CRITICAL: The new public `build_kernel(global_config_root=...)` contract has no SDK Boundary delta

**Carrier:** D3 and public interface table (`design.md:79`, `111-117`).

**Evidence:** the design makes `global_config_root` a public `agent.sdk.build_kernel` argument, passed by both products and used by the scoped auto-mode loader. The current public composition contract explicitly lists the `build_kernel` surface and its extension roots (`docs/specs/kernel/sdk-boundary.md:47-61`), while current code lacks the new argument (`src/agent/sdk/kernel.py:229-246`). The frozen kernel deltas contain only `tools-hooks.md` and `background-tasks.md`; neither modifies `sdk-boundary.md`.

**Why this blocks implementation:** an SDK consumer-facing API change will ship without the one canonical contract that defines the public assembly surface. A worker can implement it but a third consumer cannot learn its purpose, optional/default behavior, or product-neutral boundary from current specs.

**Required correction:** add a complete MODIFIED `SDK Boundary` composition requirement that includes `global_config_root`, specifies its omission behavior and product-neutral use for global auto-mode configuration, and preserve every existing scenario in that requirement. Add it to M1's delta/verification scope.

#### R2-C3 — CRITICAL: The permanent kernel delta still does not state the required product-directory `policy.toml` behavior

**Carrier:** R6/Q17 (`motivation.md:220-230`, `111-113`), D4 (`design.md:85-89`), and kernel tools/hooks delta (`specs/kernel/tools-hooks.md:20-39`).

**Evidence:** the accepted requirement says PA/CLI commands must apply their own product-directory `policy.toml`, not old `.nano/policy.toml`. D4 defines the mechanism, but the only modified consumer-facing tool requirement changes workspace *tool* discovery and has no policy path or scenario. The CLI requirement mentions a generic safety policy (`specs/cli/product-integration.md:5-18`), but there is no PA equivalent and neither one says a command is governed by `<workspace>/<workspace_config_dirname>/policy.toml`.

**Why this blocks implementation:** a worker can satisfy every frozen delta by moving extensions while leaving policy selection untested or permanently undocumented. That loses the explicit user security promise at canonical merge and makes the selected directory behavior ambiguous for non-PA/CLI SDK consumers.

**Required correction:** extend the complete kernel `tools-hooks` MODIFIED requirement with the product-neutral policy location and a consumer-observable scenario that custom `.consumer/policy.toml` governs the Bash permission decision while `.nano/policy.toml` does not; retain the currently preserved scenarios. M1 should execute that scenario through its existing real pre-tool-chain test.

#### R2-C4 — CRITICAL: JWT preflight can overwrite a conflicting new-path secret before conflict detection

**Carrier:** D6/D7 migration and table (`design.md:97-105`, `149-174`); Q15/Q18 (`motivation.md:103-117`).

**Evidence:** the flow first copies the source secret to the new location (`design.md:149-150`) and only afterwards reaches the generic old/new conflict inspection (`design.md:151-154`). The table likewise says to copy and then compare (`design.md:172`), while Q15 requires different same-name targets to be retained without overwrite. If `~/.nanoassistant/im-jwt-secret` already exists with different content, a normal copy replaces it and the subsequent `cmp -s` merely compares the source to the newly overwritten target.

**Why this blocks implementation:** a production migration can destroy the target's signing key and then falsely report success, violating conflict preservation and potentially invalidating a separately active IM deployment's login state.

**Required correction:** make secret preflight test target existence/content *before* copying: missing target may receive a copy; identical target may be retained; different target must stop migration with both files untouched. Only then run the source/target equality and `0600` checks, retain both recovery paths through fleet verification, and state this branch in the operations runbook and M2 acceptance.

### Recommendations

1. Return to `change-design-author` to add the missing canonical carriers and target-conflict branch, then request a closure re-review; no implementation should begin against this frozen set.
2. When the new `sdk-boundary` delta is written, keep the SDK parameter optional and explicitly preserve the no-global-config omission behavior so ordinary SDK consumers retain their current fallback semantics.

### Author Resolutions (Round 2)

| Issue | Resolution |
|---|---|
| R2-C1 | Added index delta carriers for `kernel/spec.md`, `gateway/spec.md` and `im/spec.md`; the affected canonical-area counts are explicitly 5/11, 14/6 and 21. The design inventory and M1/M2 scopes now include these entries. |
| R2-C2 | Added `specs/kernel/sdk-boundary.md`, a complete replacement of the public composition requirement. It documents optional `global_config_root`, its product-neutral purpose, and the no-global-root omission behavior while retaining every existing composition scenario. |
| R2-C3 | Extended the complete kernel tools/hooks replacement to make `<workspace_root>/<workspace_config_dirname>/policy.toml` the only selected session policy source, with an observable custom-directory conflict scenario exercised through the real pre-tool chain. |
| R2-C4 | Secret preflight now classifies the target before any write: missing copies, identical retains, different stops with both paths untouched. The flowchart, migration table, risk row, reviewer runbook and M2 exit criteria all carry this branch; source remains until fleet verification. |

Review request: please perform Round 3 closure review of the now-frozen design, all delta-spec carriers (including package indexes) and milestones. Append an Approved verdict only when there are 0 CRITICAL and 0 WARNING findings; otherwise append only new unresolved findings.

## Round 3

### Metadata

- reviewer: `/root/refactor_513_design_reviewer`
- review_mode: `delta`
- mode_reason: R2 fixes are bounded to three package indexes, one public SDK Boundary replacement, one policy scenario, and the secret target preflight/runbook/M2 criteria. The dependency graph, scope model, non-goals, unchanged delta carriers, and M3 retain their R2 evidence; the changed atoms and their direct downstream contracts were fully rechecked.
- started_at: `2026-08-07T15:02:36+0800`
- completed_at: `2026-08-07T15:03:35+0800`
- duration: `59s`

### Verdict

Approved — 0 CRITICAL / 0 WARNING

The frozen design is ready to enter `change-orchestrator`.

### Coverage

| Rechecked carrier | Evidence | Result |
|---|---|---|
| Complete frozen delta manifest | All 11 carriers, including kernel/Gateway/IM package indexes, were enumerated and their Requirement/Scenario headings checked. | Complete; MODIFIED requirements retain their canonical scenarios and new carriers are present. |
| R2-C1 package indexes | Added Requirement deltas increase current counts from kernel `4/10`, Gateway `13/5`, and IM `20`; index deltas declare `5/11`, `14/6`, and `21` respectively (`specs/kernel/spec.md:5-8`, `specs/gateway/spec.md:5-8`, `specs/im/spec.md:5-7`). | closed. |
| R2-C2 SDK public surface | Complete SDK Boundary replacement includes optional `global_config_root`, product-neutral purpose, supplied-root and omission scenarios (`specs/kernel/sdk-boundary.md:5-62`); M1 owns the index/boundary and omission test (`design.md:212`). | closed. |
| R2-C3 policy contract | The kernel tool requirement selects `<workspace_root>/<workspace_config_dirname>/policy.toml` without cross-directory fallback, and its custom-directory pre-tool scenario observes the conflict result (`specs/kernel/tools-hooks.md:20-44`). | closed. |
| R2-C4 target-secret conflict | D7, graph, migration table, risk row, production reviewer runbook and M2 all choose missing/same/different before a write and preserve conflicting paths (`design.md:103-105`, `149-176`, `192`, `200`, `213`). | closed. |
| retained_from: Round 2 | D1/D2/D3 scope ownership, D5 independent IM ownership, chat-history carrier, complete Gateway/CLI MODIFIED entries, product dependency boundaries, and M3 had no semantic changes after R2. | retained. |

### 历史问题闭环

| 历史项 | Author Resolution | 本轮核实 | 状态 |
|---|---|---|---|
| R2-C1 | Added kernel/Gateway/IM `spec.md` index carriers and exact counts. | Current canonical area counts are `4/10`, `13/5`, `20`; each index delta correctly reflects exactly its area's one ADDED Requirement. This satisfies the mechanical count rule (`docs/specs/CONTRIBUTING.md:94-100`). | closed |
| R2-C2 | Added complete `sdk-boundary.md` MODIFIED requirement. | It preserves all seven existing composition scenarios and adds supplied/omitted global-root scenarios; the public `build_kernel` contract in D3 and M1 is now traceable. | closed |
| R2-C3 | Added selected-policy statement and conflict scenario to the complete tools/hooks replacement. | The carrier is SDK-consumer-facing, describes the exact custom path and proves `.nano` is not a fallback, matching Q17/R6 and D4. | closed |
| R2-C4 | Classified secret target before any write everywhere the migration is described. | Missing copies, same retains, and differing targets stop with both paths untouched; source remains through fleet verification. No conflicting migration path remains. | closed |

### Rechecked architecture impact

1. **Ownership.** `global_config_root` remains a consumer-supplied SDK input, not a product branch or a core/platform reverse dependency; its public carrier now matches that boundary.
2. **Depth.** The policy scenario reinforces the one `WorkspaceExecutionScope` seam instead of introducing another product-specific policy bridge.
3. **Root cause.** The target classification removes the last overwrite path from the manual migration while preserving the deliberate absence of runtime compatibility code.

### Issues

None.

### Recommendations

None.
