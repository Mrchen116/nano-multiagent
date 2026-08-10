# Verification Report: feat-517

> Validation snapshot: `cd071e649d3fe4fe7a2f392643a49c8f87825898 → 7d77880234ccefdcfed03f3d630a1db450afb591`

## Summary

Mode: `full`  
Delta range: N/A  
Focus issues: N/A  
requires_full_verification: `false`

| 维度 | 结果 |
|---|---|
| Completeness | 14/18 independently satisfied（文档标记为 18/18；4 项退出标准被运行时证据否定） |
| Correctness | 5/11 top-level requirements fully covered；其余 6 项存在缺实现或错误实现 |
| Coherence | 有 5 项关键决策偏离，另有 2 项普通设计偏离 |

本轮结论：**fail**。5 critical issue(s), 2 warning(s) found. Fix before PR.

## Completeness

- Tasks: 两个 milestone 的 `tasks.md` 共 18/18 标记完成；独立核对后 14/18 满足。
  - M1 exit criterion 1（primitives / deterministic resume）不成立：`pipeline()` 与 shipped canonical example 不兼容，resume 丢失 terminal ordinal 0。
  - M1 exit criterion 2（manager / worktree / terminal notification）不成立：dirty worktree locator 未进入 snapshot，Workflow terminal task record 丢 usage，failed 终态还丢 result/duration/tool count。
  - M1 exit criterion 5（CLI progress/details）不完整：没有 Agent result/usage/duration/worktree 下钻信息。
  - M2 backend exit criterion 4（`/workflows` query/detail）不完整：Web/外部 IM 详情只显示 Agent 完成计数，不显示 phase/Agent tree、任务与结果、逐层 usage/duration。
- Spec 覆盖：能力开关、opt-in、Python compiler/sandbox、saved discovery、权限路由、后台 carrier、Web typed sidecar 与既有 process surface 均有实现；确定性 pipeline、resume session/terminal-order、完整 terminal payload、细粒度进度/成本和 large-workflow advisory 未完整实现。
- Delta specs：kernel、CLI、Gateway、IM 的新增 surface 均已投影到代码；受 C1-C5 影响的 kernel primitives/resume/observability/notification contract 及 Gateway/IM 查询与后台返回字段不满足 delta 的完整语义。
- Prototype / Reference：4 个 must-match contract 均投影到 M2 tasks/progress，12 张 desktop/mobile PNG 是仓库内 durable evidence；组件实现和 focused tests支持 input-first/result-second、现有 PermissionCard、background-return 独立 process item。终态 Workflow evidence 使用合法持久记录喂给 production REST/history，但真实 manager 产生的 Workflow terminal record 缺 usage，failed record 还缺 partial result/duration/tool count，因此 completed/failed/stopped must-match 只在 seeded UI 数据层成立，真实纵向链不成立（C3）。

## Correctness

主 `spec.md` 共 11 个 requirement / 52 个 scenario。下表逐 requirement 列出全部 scenario 的核对结论；`偏离` 行中的未通过 scenario 均由 Issues 中的具体修复项覆盖。

| Requirement / Scenario | 实现位置 | 测试覆盖 | 状态 |
|---|---|---|---|
| Workflow 在所有 Agent 产品入口可用且由工具选择完整开关（CLI 启用、PA 勾选/取消、运行中修改） | `src/coding_cli/product.py:224-286`; `src/personal_assistant/gateway/agent_config_service.py`; `src/agent/sdk/runtime.py:91-129` | `tests/unit/test_cli_workflows.py`; `tests/unit/personal_assistant/test_agent_config_sync_ownership.py`; `tests/integration/test_workflow_sdk_management.py` | covered（4/4） |
| 默认模式只响应明确 opt-in，ultracode 可自主编排（keyword、自然语言、普通任务、standing mode、非人工来源） | `src/agent/core/workflows/activation.py`; `src/agent/core/agent/runtime.py:421-442`; `src/agent/platform/llm/mappers.py` | `tests/unit/agent/core/workflows/test_activation.py`; `tests/unit/agent/platform/llm/test_workflow_turn_system.py` | covered（5/5） |
| 生成和运行可检查、可编辑、可复用 Python 脚本（生成、修改重跑、primitives、sandbox、args） | `src/agent/core/workflows/compiler.py`; `src/agent/platform/workflows/store.py:12-57`; `src/agent/platform/tools/builtins/workflow.py:151-215` | compiler/tool/manager focused tests | covered（5/5） |
| 确定性多 Agent 编排（parallel、pipeline、控制流、child stop/error、whole-run terminal、中间结果） | `src/agent/core/workflows/runtime.py:120-229`; `src/agent/platform/workflows/manager.py:315-523` | `tests/unit/agent/core/workflows/test_primitives.py`; manager lifecycle tests | **偏离（5/6）**：pipeline 首 stage 的实际参数与 canonical prompt 不同，真实 example 无 child dispatch（C1） |
| 后台运行且各入口可查看/控制进度（async launch、查看、pause/resume、stop、complete） | `src/agent/platform/workflows/manager.py`; `src/agent/sdk/kernel.py`; CLI/PA workflow commands | SDK/CLI/PA management tests | **缺实现（4/5）**：run 总量存在，但 phase usage/duration、Agent duration/session/worktree 及 Web/外部 IM 下钻缺失（C4） |
| Web IM 对后台 Workflow/Agent 显示原始返回（Workflow、Agent、原始/综合分层、空正文、realtime/history/replay） | core notification carrier；IM `background_returns`; frontend `ToolCallsPanel` / `BackgroundReturnRow` | Python carrier tests；`workflow-surfaces.test.tsx`; reducer/history tests；durable screenshots | **偏离（4/5）**：UI 能显示字段，但真实 Workflow manager 未把 usage 写入 task record，failed 又不写 partial result/duration/tool count（C3） |
| 最长相同 Agent 调用前缀恢复（未完成、修改后续、完全相同、退出 session） | `src/agent/core/workflows/resume.py`; `src/agent/core/workflows/runtime.py:273-347`; `src/agent/platform/workflows/manager.py:525-542` | core prefix tests；manager same-session happy path | **偏离（2/4）**：跨 session run 可直接复用；terminal ordinal 0 经 `or index` 被改写，无法保持原 terminal 顺序（C2） |
| 保存、发现、分发并按名称运行（project、personal、precedence、bundled/plugin、disabled） | `src/agent/platform/workflows/saved.py`; CLI/PA dynamic command discovery | saved registry、CLI、capability tests | covered（5/5） |
| 启动与 child tool 调用遵循权限语义（default approval、ultracode/noninteractive、inherit、extra permission、no stage input） | Workflow permission hook、child adapter、CLI/PA background permission binding | workflow tool / child / permission binding tests | **偏离（4/5）**：launch question 只含 name，不含 design/spec 要求的 phase 与 scale/usage reminder（C5） |
| 规模、成本和模型路由（实时成本、large warning、guideline、hard limits、model/effort） | tool prompt guideline；shared budget；manager warning；child model resolver | activation/tool/manager/SDK tests | **缺实现（3/5）**：无 phase/Agent duration，small/medium/large boundary 不控制 warning，也无 1.5M-token advisory；CLI 不查找最近 workspace config（C4、C5、W1） |
| 错误可定位且不破坏主会话（invalid Python、background failed、历史诊断） | compiler/tool preflight；run store/journal；background notification | compiler、manager、notification tests | **偏离（2/3）**：failed task record 只保留 error，丢失已有 result/duration/tool count/usage，使 Web 原始失败返回不完整（C3） |

### Delta-spec reconciliation

| Delta area | 实现 / 测试证据 | 状态 |
|---|---|---|
| `specs/kernel/workflows.md` | core compiler/runtime/manager/SDK tests | partial：pipeline、resume、per-phase/Agent telemetry、terminal notification 和 advisory 不满足 |
| `specs/kernel/background-tasks.md`, `runs.md`, `sdk-boundary.md` | generic registry/carrier、SDK DTO、run event tests | partial：carrier 与边界正确，但 manager terminal writer 没有填满 record；DTO 可选字段未被生产实现写入 |
| `specs/cli/interactive-repl.md` | CLI config/command/TTY tests | partial：query/control 可用；Agent result/usage/duration/worktree 下钻与 nearest workspace config 不满足 |
| `specs/gateway/workflows.md`, `agent-capabilities.md`, routing/relay | PA commands、permission binding、subscription/relay tests | partial：capability/permission/relay covered；详情 renderer 不暴露 phase/Agent telemetry |
| `specs/im/workflows.md`, `tool-timeline.md`, relay/agent deltas | IM persistence/realtime/history + frontend focused 110 tests + screenshots | partial：UI contract covered，但真实 Workflow terminal payload 缺字段 |

## Coherence

| design 决策 | 遵守? | 代码证据 |
|---|---|---|
| 1. active `Workflow` tool 是唯一开关 | 是 | `src/agent/sdk/runtime.py:91-129`; product capability tests |
| 2. prompt 以 capture 为真源并做 Python 机械变换 | 是（prompt 本身）；与 runtime 发生行为冲突 | `workflow_tool_prompt.md:74-103`；C1 是 runtime 偏离而非 prompt surrogate |
| 3. AST 辅助 + 真编译执行 | 是 | `src/agent/core/workflows/compiler.py` |
| 4. primitives 只表达编排，effect 进入同一 manager | **否** | `runtime.py:204` 破坏 prompt/example 的首 stage contract；C1 |
| 5. 复用 child Agent loop + return/structured tool | 是 | `src/agent/platform/workflows/child.py:107-238` |
| 6. append-only journal + atomic snapshot | 部分 | atomic store 在 `store.py:42-57`；restart 只读 `run.json`（`manager.py:218-239`），没有设计承诺的 journal rebuild（W2） |
| 7. chained-v2 最长相同前缀 | **否** | `manager.py:525-542` 未校验 parent session 且改写 ordinal 0；C2 |
| 8. 复用 broker，child permission 回父交互面 | 部分 | binding/consumer 路径已实现；launch question `workflow.py:132-135` 缺 phase/规模提醒；C5 |
| 9. 只在可信人工入口加 reminder，无第二道 runtime gate | 是 | activation + provider golden |
| 10. saved Workflow 沿 config roots，命令为显式 invocation | 是 | saved registry / capability command implementation |
| 11. Workflow 自有短生命周期 worktree adapter | **否（部分）** | create/clean behavior在 `child.py:255-297`；dirty path 未回写 Agent snapshot 或 `/workflows` 详情；C4 |
| 12. SDK 只暴露 query/control，不泄漏 manager | 是 | `src/agent/sdk/kernel.py`; contract tests；产品只 import `agent.sdk` |
| 13. background return 是 notification sidecar，不是 ToolCall | **否（纵向接线）** | projection owner正确；manager completed/stopped/failed terminal writes不传完整 snapshot数据（`manager.py:487-521`）；C3 |

架构边界检查通过：全量 contract suite 通过；未发现 `coding_cli` / `personal_assistant` import `agent.core/platform`、IM import agent、或 core 反向依赖 platform。没有新增 IM Workflow run projection/event 或独立进度页面。

### Prototype / Reference Contract

| Reference contract | Milestone projection | Implementation evidence | Durable evidence | Status |
|---|---|---|---|---|
| permission pending 只显示现有 PermissionCard；deny 直接 terminal row | M2 frontend exit 4 + browser matrix | `permission-card`, Workflow denied renderer tests | `evidence/desktop-collapsed.png`, `desktop-workflow-denied.png`, `mobile-workflow-permission.png` | covered |
| running / async-launched：input-first、result-second；pending 无 result | M2 frontend exit 4 | `workflow-surfaces.test.tsx` | desktop/mobile running/launched PNG | covered |
| completed / failed / stopped：后续普通消息 + 可展开 Workflow background return | M2 frontend exit 3/6 | renderer、sidecar persistence/reducer/history | completed/failed/stopped desktop/mobile PNG | **critical**：seeded UI 状态成立，production manager payload 缺 usage；failed 还缺 result/duration/tool count（C3） |
| background Agent 与 Workflow 共用独立 process item，不计 tool/approval | M2 frontend exit 2/3 | `ToolCallsPanel` process union/count tests | `desktop-workflow-and-agent-background-returns.png`, mobile background PNG | covered |

## Verification execution evidence

- Reproduced canonical pipeline example shape: result `[None]`, `child_calls=[]`.
- Reproduced cross-session resume: session B replayed session A result, live child called only once.
- Reproduced terminal-order loss: original `[('slow', 1), ('fast', 0)]`, resumed `[('slow', 1), ('fast', 1)]`.
- Reproduced terminal payload loss: run snapshot usage `15`, generic task and `BackgroundReturnInfo` usage both `None`.
- Reproduced small-guideline boundary miss: 5 Agents with `small` yielded no warning.
- Focused Workflow Python: `66 passed`.
- Full Python non-E2E: `3277 passed, 26 deselected, 22 warnings`.
- Focused frontend Workflow/process: `4 files / 110 tests passed`.
- Full frontend first run under default parallel workers: `5 failed / 651 passed`; all 5 failures passed when the 3 affected files were rerun with one worker (`80 passed`), so this is recorded as a resource-sensitive suite signal rather than a feat-517 correctness finding.
- Frontend production build passed; existing Vite chunk-size warning remains.
- Ruff check, Ruff format check, docs integrity and `git diff --check` passed.

## Issues

### CRITICAL（提 PR 前必须修）

- **C1 — `pipeline()` cannot run the canonical Workflow generated from its own tool prompt.** `src/agent/core/workflows/runtime.py:201-206` passes `None` as the first argument of stage 0, while `src/agent/platform/tools/builtins/workflow_tool_prompt.md:74-95` and `design.md:177-197` use the first argument as the current item. The shipped example therefore catches `TypeError`, produces `[None]`, and starts zero Agents. Make stage 0 receive the original item in its first position (while preserving `(previous, original, index)` for later stages), execute the canonical example in a permanent primitive/tool integration test, and stop masking the mismatch in `tests/unit/agent/core/workflows/test_primitives.py:67-70` by naming the first argument `_previous`.

- **C2 — resume is neither session-scoped nor terminal-order preserving.** `src/agent/platform/workflows/manager.py:315-318,525-542` loads any known run id without comparing `previous.parent_session_id` to `handle.context.parent_session_id`; a session B launch replays session A's cached Agent result. The same code uses `item.get("terminal_ordinal") or index`, so a valid ordinal `0` is replaced by the start-order index; an observed `[1,0]` completion order became `[1,1]` after resume. Pass the current parent session into resume validation and reject mismatches before starting the background run; use an explicit `is None` fallback for ordinal; add manager-level cross-session rejection and out-of-start-order 100% replay tests.

- **C3 — the real Workflow terminal writer drops fields required by task notification and Web background-return.** The run snapshot aggregates usage at `manager.py:371-383,611-616`, but completed/stopped calls at `manager.py:492-506` omit `usage`; failed/exception paths at `manager.py:507-521` call `BackgroundTaskRegistry.fail()`, whose API (`src/agent/core/background_tasks/registry.py:181-195`) cannot carry result, usage, duration or tool count. The existing notification test (`tests/unit/agent/background_tasks/test_workflow_notifications.py:48-72`) injects a fully populated registry record directly and therefore bypasses the broken production wiring. Extend the failure terminal API as needed, write the same snapshot result/error/usage/duration/tool count into completed/failed/stopped records, and add manager→registry→`build_background_notification()` integration tests for all three terminal states including partial failed/stopped result.

- **C4 — required progress/cost detail and Agent drill-down fields are declared but never produced or rendered.** Initial phases at `manager.py:124-131` contain no timing/usage fields and `_merge_usage()` only updates the run total. Agent records at `manager.py:321-332` never get duration, child session id, or retained worktree path even though public DTOs expose them (`src/agent/sdk/dto.py:422-450`) and the child adapter has the values (`child.py:154-188,255-291`). CLI detail (`src/coding_cli/commands.py:1748-1779`) omits prompt/result/error/per-Agent usage/duration/worktree, and PA detail (`src/personal_assistant/gateway/workflow_commands.py:103-127`) reduces all Agents to one completed count. Instrument child/phase start and terminal timestamps, expose child session + retained dirty worktree locators to manager, aggregate phase usage, and render phase/Agent task/result/usage/duration in CLI and PA ordinary detail replies; add SDK snapshot and both product formatter tests.

- **C5 — launch approval and large-run advisory ignore the approved scale contract.** `src/agent/platform/tools/builtins/workflow.py:113-135` asks only `Run Python Workflow '<name>'?`, without phase or scale/usage reminder. `manager.py:333-341` warns only when zero-based ordinal reaches 25, regardless of selected `small <5`, `medium <15`, or `large <50`, and there is no estimated-1.5M-token warning. The warning also appears only after children are already starting, not in the launch approval information. Resolve the applicable threshold from guideline/explicit-selection state, include phase/scale information in the approval question, emit the 25-Agent or 1.5M-token `Large workflow` advisory while respecting ultracode suppression, and add small/medium/large/unrestricted plus token-estimate tests. Warnings must remain advisory, not pause execution.

### WARNING（提 PR 前必须修）

- **W1 — CLI does not resolve the nearest applicable workspace config.** Design requires global plus nearest workspace `.nanocode/config.yaml`, but `src/coding_cli/product.py:95-125` checks only the exact supplied cwd. Starting the CLI below a repo-level config silently falls back to global/default; `tests/unit/test_cli_workflows.py:91-114` only covers an exact-path config. Walk from cwd toward git root, select the nearest applicable workspace config, and add nested-cwd precedence/read tests; use the same resolved location consistently for `/config` persistence.

- **W2 — startup recovery cannot rebuild a snapshot from the append-only journal.** Decision 6 says the journal is the diagnostic/resume truth and startup can rebuild from it, but `src/agent/platform/workflows/manager.py:218-239` only globs and parses `run.json`; `src/agent/platform/workflows/store.py` has no journal reader/reducer. Implement the specified journal replay fallback when `run.json` is missing/corrupt and add restart recovery tests that remove/corrupt only the snapshot while retaining `journal.jsonl`.

### SUGGESTION（可以修）

None.

5 critical issue(s), 2 warning(s) found. Fix before PR.

# Round 2

> Validation snapshot: `3a73723f63c383114844cd8adef598f68125fe86 → 7339804c7256830a71172b1d27b0ce102a3e6291`

## Verification Report: feat-517

### Summary

Mode: `targeted-closure`

Delta range: `3a73723f63c383114844cd8adef598f68125fe86..7339804c7256830a71172b1d27b0ce102a3e6291`

Focus issues: `C1, C2, C3, C4, C5, W1, W2`，以及 Round 1 acceptance 的 6 个 implementation findings

requires_full_verification: `false`

| 维度 | 结果 |
|---|---|
| Completeness | 7/7 focus issues 均有实现与永久回归测试 |
| Correctness | 13/13 targeted checks 通过（7 个 verifier findings + 6 个 acceptance findings） |
| Coherence | Followed；fix delta 没有引入新的跨包依赖、平行权限/投递链或 IM 运行投影 |

本轮结论：**pass**。Round 1 的 5 个 CRITICAL 和 2 个 WARNING 均已关闭；acceptance Round 1 的 6 个 implementation findings 均已有代码与回归测试闭环。

### Focus issue closure

| Issue | 独立核对结果 | 实现与测试证据 | 状态 |
|---|---|---|---|
| C1 — canonical `pipeline()` 首 stage | 首 stage 现在获得 `(current=item, original=item, index)`，后续 stage 仍获得 `(previous, original, index)`；运行实现与 tool prompt 的 canonical lambda 形状一致。 | `src/agent/core/workflows/runtime.py:195-219`; `tests/unit/agent/core/workflows/test_primitives.py:58-83` | closed |
| C2 — resume session scope / terminal order | launch 在启动新 thread 前加载同 session durable run，拒绝不同 parent session；terminal ordinal 改为显式 `is None` fallback，保留合法的 `0`。restart 后同 session 可 100% replay，跨 session 给出明确错误。 | `src/agent/platform/workflows/manager.py:116-136,603-650`; `tests/unit/agent/platform/workflows/test_manager_lifecycle.py:145-207`; `tests/unit/agent/platform/workflows/test_manager_resume_restart.py:25-84` | closed |
| C3 — terminal notification payload | completed/failed/stopped 统一从 snapshot 写入 partial result、error、usage、duration 和 tool count；`BackgroundTaskRegistry.fail()` 可持久化相同字段。manager→registry→notification 的三终态测试断言原始返回与 snapshot 一致。 | `src/agent/platform/workflows/manager.py:517-601`; `src/agent/core/background_tasks/registry.py:181-207`; `tests/unit/agent/platform/workflows/test_manager_observability.py:149-236` | closed |
| C4 — phase/Agent observability | manager 产生 phase 与 Agent usage/duration，child 保留 session/transcript/dirty-worktree locator；SDK snapshot、CLI 和 Gateway 详情都展示 task/result/error/usage/duration/artifact。worktree 测试覆盖 completed/failed/stopped 及 cleanup failure。 | `src/agent/platform/workflows/manager.py:363-436,807-891`; `src/agent/platform/workflows/child.py:110-190,259-284`; `src/coding_cli/commands.py:1835-1897`; `src/personal_assistant/gateway/workflow_commands.py:100-167`; `tests/integration/test_workflow_sdk_management.py:304-346`; `tests/unit/agent/platform/workflows/test_child_worktree_observability.py:114-224` | closed |
| C5 — launch scale / Large workflow advisory | approval question 含 phases、resolved guideline 边界和 1.5M-token advisory；manager 对 default `>25`、显式 small/medium/large 边界、unrestricted 和 token threshold 产生 advisory，ultracode 抑制 warning，不暂停已授权 run。 | `src/agent/platform/tools/builtins/workflow.py:170-203,402-425`; `src/agent/platform/workflows/manager.py:762-804`; `tests/unit/agent/platform/tools/test_workflow_tool.py:226-240`; `tests/unit/agent/platform/workflows/test_manager_observability.py:23-91` | closed |
| W1 — nearest CLI workspace config | CLI 从 cwd 向 git root 查找最近 `.nanocode/config.yaml`，workspace 覆盖 global，`/config` 写回同一 resolved file；回归测试覆盖 nested cwd 和就近优先级。 | `src/coding_cli/product.py:96-170`; `tests/unit/test_cli_workflows.py:89-159` | closed |
| W2 — journal recovery | terminal journal 保存完整 snapshot checkpoint；启动加载在 `run.json` 缺失或损坏时选取 journal 最新 checkpoint。独立测试删除/损坏 snapshot 后，restart query 恢复与终态 snapshot 完全相同。 | `src/agent/platform/workflows/store.py:59-80`; `src/agent/platform/workflows/manager.py:255-282,515-516,538-544`; `tests/unit/agent/platform/workflows/test_manager_lifecycle.py:210-247` | closed |

### Acceptance Round 1 implementation closure

| Acceptance finding | 相关契约与闭环证据 | 状态 |
|---|---|---|
| A1 — CLI interactive launch 无批准界面 | REPL 现在以单一 input-owner coordinator 等待并显示 broker 的 Once/Always/Deny options，将精确 decision 返回 kernel；测试覆盖 `allow_always` 且无 `can_use_tool raised`。`src/coding_cli/commands.py:95-158,329-403,769-775`; `tests/unit/test_cli_async_repl_sdk.py:183-227` | closed |
| A2 — Web completion 缺 background-return | 非用户 pending notification 的 `injection_consumed` 不再被 steer identity 过滤，background sidecar 进入既有 delivery observer，与主 Agent reply 落到同一 IM message；邻接测试同时覆盖 sidecar-only persistence/realtime/history。`src/personal_assistant/gateway/session_run_coordinator.py:1697-1710,1750-1764`; `tests/unit/personal_assistant/test_session_run_coordinator_admission.py:942-989`; `tests/im_service/unit/test_event_bridge.py:73-134` | closed |
| A3 — Workflow tool detail 只有空标题 | tool-owned presenter 在 start/end 输出稳定的 input-first/result-second 字段，realtime hook 用 session guideline 调用 presenter；前端回归断言 script、status、name、run/task 与 artifacts 皆可读。`src/agent/platform/tools/builtins/workflow.py:49-127`; `src/agent/platform/hooks/builtins/realtime_stream.py:29-51,94-137`; `src/IM/frontend/src/features/chat/components/workflow-surfaces.test.tsx:26-153` | closed |
| A4 — Web/飞书 child 未继承 Luna/effort | Workflow tool 在 parent turn 内捕获 resolved model/effort/tools/skills，child manager thread 使用该 snapshot；PA factory 透传 `NANO_MULTIAGENT_WORKFLOW_SUBAGENT_MODEL`。测试使 active ContextVar 不可用，仍断言 child 采用指定 Luna 和捕获的 effort。`src/agent/platform/tools/builtins/workflow.py:231-255,353-376`; `src/agent/platform/workflows/child.py:110-190`; `src/personal_assistant/product.py:424-438`; `tests/unit/agent/platform/workflows/test_child_control.py:167-205`; `tests/unit/personal_assistant/test_product_workspace_layout.py:46-66` | closed |
| A5 — disabled CLI `/help` 仍暴露 Workflow commands | help 和 slash suggestions 均由 resolved Workflow capability 过滤；disabled 时 `/workflows`、`/config`、`/effort` 与 saved commands 不可发现。`src/coding_cli/commands.py:750-767,1294-1320`; `src/coding_cli/input/repl_commands.py:11-36`; `tests/unit/test_cli_repl_commands.py:81-94` | closed |
| A6 — 另一 CLI 的 completed-run resume 笼统失败 | 新 manager 在 Workflow tool 带 `resumeFromRunId` 启动时先从同 session durable store 加载 run，相同脚本/参数创建新 run 并全量 replay cached child；跨 session 返回明确 owner 错误。`src/agent/platform/workflows/manager.py:116-136,255-282,603-650`; `src/agent/platform/tools/builtins/workflow.py:247-258`; `tests/unit/agent/platform/workflows/test_manager_resume_restart.py:25-84` | closed |

### Verification execution evidence

- Focused runtime / SDK / CLI / Gateway / IM Python suite: `173 passed`.
- Background notification, run-carrier, delivery-observer and IM persistence adjacency suite: `221 passed`.
- Frontend production Workflow/process surface: `workflow-surfaces.test.tsx` — `10 passed`.
- Changed Python files: Ruff check passed; Ruff format check passed (`49 files already formatted`).
- Documentation integrity: `225 maintained Markdown sources, 67 required routes` passed.
- `git diff --check 3a73723f63c383114844cd8adef598f68125fe86..7339804c7256830a71172b1d27b0ce102a3e6291` passed.
- 按 targeted-closure 约束未重跑真实 Chrome/飞书或 LLM；本轮不替代 product acceptance reviewer 的真实产品旅程复验。

### Issues

#### CRITICAL（提 PR 前必须修）

None.

#### WARNING（提 PR 前必须修）

None.

#### SUGGESTION（可以修）

None.

All checks passed. Ready for PR.
