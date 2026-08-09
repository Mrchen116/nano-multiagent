# Verification Report: bugfix-520

> Validation snapshot: `1d0c2cb45b887162912402b0fb489cdf3a1ad9c9 → 4b8046e25c4b1661b2fb2d9d727a9b4c1f6f9c1f`

## Summary

Mode: full
Delta range: N/A
Focus issues: N/A
requires_full_verification: false

| 维度 | 结果 |
|---|---|
| Completeness | 1/2 milestones fully proven |
| Correctness | 12/13 delta scenarios have valid permanent coverage |
| Coherence | 5/6 key design decisions followed; E2E oracle deviates |

1 critical issue(s), 0 warning(s) found. Fix before PR.

## Completeness

- Tasks: milestone 文档中 10/10 个退出标准已勾选；实际核验中 M2 完成，M1-C2/M1-C3 的投影、catalog 和进程隔离成立。
- M1-C1 未被当前长青 E2E 证明：recording stub 在进入 `post_summary` 状态后不检查本次请求是否携带压缩摘要/目标，便直接回传 sentinel。因此压缩后和 Gateway restart 后的上下文即使丢失，旅程仍可能绿。
- Spec 覆盖：无假摘要、三入口失败原子性、session-owned bounded retry、assistant-before-failed、typed terminal diagnostic 和 durable projection 都有实现与低层回归；含工具历史的真进程 restart 连续性缺有效 oracle。
- Prototype / Reference 覆盖：N/A。无前端原型或 must-match artifact；Claude Code no-replacement/bounded-retry 原则已投影为明确 design 决策。

## Correctness

| Requirement / Scenario | 实现位置（file:line） | 测试覆盖 | 状态 |
|---|---|---|---|
| Requirement: 只有有效摘要 + durable commit 才替换上下文，工具关系可恢复 | `src/agent/core/session/transcript.py:171`, `src/agent/core/session/transcript.py:688`, `src/agent/core/agent/loop.py:1022`, `src/agent/core/agent/runtime.py:1983` | `tests/unit/test_session_persistence_fidelity.py:349`; focused suite | covered |
| Scenario: 手动触发压缩 | `src/agent/core/agent/runtime.py:308`, `src/agent/core/agent/runtime.py:1940` | `tests/integration/test_conversation_compaction_integration.py:233` | covered |
| Scenario: focus 只指导手动摘要 | `src/agent/core/agent/runtime.py:1986`, `src/agent/core/agent/runtime.py:1993` | `tests/unit/test_loop_compact.py:583` | covered |
| Scenario: 手动摘要/持久化失败不改上下文 | `src/agent/core/agent/runtime.py:2005`, `src/agent/core/agent/runtime.py:2077` | `tests/unit/agent/test_kernel_manual_compact.py:61`, `tests/unit/agent/test_kernel_manual_compact.py:100`, `tests/unit/agent/test_kernel_manual_compact.py:139` | covered |
| Scenario: 自动阈值摘要失败不伪装成功 | `src/agent/core/agent/loop.py:1027`, `src/agent/core/agent/loop.py:1038` | `tests/unit/test_loop_compact.py:397`, `tests/integration/test_conversation_compaction_integration.py:378` | covered |
| Scenario: 连续自动失败第三次熔断且 assistant-before-failed | `src/agent/core/agent/loop.py:1010`, `src/agent/core/agent/runtime.py:684`, `src/agent/core/agent/runtime.py:1910` | `tests/integration/test_conversation_compaction_integration.py:378` | covered |
| Scenario: overflow 摘要失败保留原 overflow cause，不重试 | `src/agent/core/agent/runtime.py:692`, `src/agent/core/agent/runtime.py:1995`, `src/agent/core/agent/runtime.py:2005` | `tests/integration/test_conversation_compaction_integration.py:444` | covered |
| Scenario: compaction record 持久化失败不半提交 | `src/agent/core/agent/loop.py:1095`, `src/agent/core/agent/runtime.py:2077` | `tests/unit/agent/test_kernel_manual_compact.py:100`, `tests/integration/test_conversation_compaction_integration.py:518`, `tests/integration/test_conversation_compaction_integration.py:588` | covered |
| Scenario: 含工具历史的压缩在 Gateway/process restart 后继续任务 | `src/agent/core/session/transcript.py:210`, `src/agent/core/session/transcript.py:688`; durable summary 已实现 | `tests/e2e/critical_paths/test_context_compaction_continuity_critical_path.py:71` 的 oracle 无法阻断上下文丢失 | missing valid E2E |
| Scenario: 自动压缩不继承手动 focus | `src/agent/core/agent/runtime.py:1986`, `src/agent/core/agent/runtime.py:1993` | `tests/unit/test_loop_compact.py:583` + call-site inspection | covered |
| Scenario: 相同 manual operation identity 不重复压缩 | `src/agent/core/agent/runtime.py:1953`, `src/agent/core/agent/runtime.py:2084` | `tests/unit/agent/test_kernel_manual_compact.py:165` | covered |
| Scenario: 按当前轮模型窗口判定压缩 | `src/agent/core/agent/loop.py:934`, `src/agent/core/agent/loop.py:948` | `tests/unit/test_loop_compact.py:660` | covered |
| Scenario: 未声明/非正窗口回退默认 | `src/agent/core/agent/loop.py:934` | `tests/unit/test_loop_compact.py:677` | covered |
| Scenario: workspace-bound session 压缩后透明继续 | `src/agent/core/agent/runtime.py:1965`, `src/agent/core/agent/runtime.py:2055` | `tests/integration/test_conversation_compaction_integration.py:103`, `tests/integration/test_conversation_compaction_integration.py:233` | covered |

## Coherence

| design 决策 | 遵守? | 代码证据（file:line） |
|---|---|---|
| `load()` / compaction event 共享 latest-boundary active/recovery projection | 是 | `src/agent/core/session/transcript.py:210`, `src/agent/core/session/transcript.py:684`, `src/agent/core/session/transcript.py:688` |
| summarizer 只返回有效文本或 `None`，无 `strict`/fallback | 是 | `src/agent/core/agent/compaction/summarizer.py:32`, `src/agent/core/agent/compaction/summarizer.py:72` |
| tracker 归属稳定 `ConversationSession`，reload/LRU 保留，成功重置 | 是 | `src/agent/core/session/conversation.py:182`, `src/agent/core/session/conversation.py:423`, `src/agent/core/agent/loop.py:1121`, `src/agent/core/agent/runtime.py:2109` |
| durable commit 仍由 `append_compaction()` 单 owner，stale/persistence/summary 分流 | 是 | `src/agent/core/session/transcript.py:381`, `src/agent/core/agent/loop.py:1095`, `src/agent/core/agent/runtime.py:2077` |
| typed diagnostic 与固定用户文案分离，普通异常协议不变 | 是 | `src/agent/core/errors.py:63`, `src/agent/core/runs/registry.py:523`, `src/agent/core/agent/runtime.py:2399` |
| 单条长青 E2E 真正守住工具历史压缩与 restart 连续性 | 否 | `scripts/fixtures/anthropic_sse_compaction_recording.py:200` 的回复不依赖当前 request 上下文 |

架构自洽性：未发现依赖方向、跨机边界或平行机制问题。变更仍在 `agent.core` 内扩展原 session/compaction/run-status seam，Gateway 复用现有 assistant delivery。

### Prototype / Reference Contract

N/A。

## Validation Evidence

- Focused unit/integration suite: `86 passed`.
- Adjacent compaction/contract suite: `26 passed`.
- New compaction E2E + existing fake-LLM #14/#15: `3 passed in 42.71s`.
- Architecture contracts: `5 passed`.
- Ruff: `All checks passed!`.
- Docs integrity: `230 maintained Markdown sources, 67 required routes`.
- `git diff --check`: passed.

## Issues

### CRITICAL（提 PR 前必须修）

- **C1 — 长青 E2E 的 fake LLM 泄露了预期答案，无法证明压缩/restart 后上下文连续。** `scripts/fixtures/anthropic_sse_compaction_recording.py:200-203` 在 `_summary_completed` 后无条件返回 `CONTINUED/RESTARTED + sentinel`，而 `tests/e2e/critical_paths/test_context_compaction_continuity_critical_path.py:102-110` 和 `:146-156` 只检查这个 stub 生成的回复。即使 Gateway 发给模型的压缩后或 restart 后 request 已丢失 summary/sentinel，当前测试仍会绿，因而未满足 M1-C1 和用户要求的长青 E2E 保护。修复时让 fixture 在每个 `post_summary` request 中校验 sentinel（以及必要的 compact-summary marker），缺失时返回 422 或不含 sentinel 的响应；同时在 E2E 重新读取 recording，明确断言压缩后和 Gateway restart 后两个 upstream request 都携带 sentinel。

### WARNING（提 PR 前必须修）

None.

### SUGGESTION（可以修）

None.

# Round 2

> Validation snapshot: `1d0c2cb45b887162912402b0fb489cdf3a1ad9c9 → 2ff5ef8ffd135e7c1a89217b8669d6ec1ac22e62`

## Summary

Mode: targeted-closure

Delta range: `0c46a03ea82fd37b16057c146e2cb5b0cf76c8c4..2ff5ef8ffd135e7c1a89217b8669d6ec1ac22e62`

Focus issues: C1 长青 E2E fixture 无条件回传 sentinel 导致假绿

requires_full_verification: false

| 维度 | 结果 |
|---|---|
| Completeness | C1 1/1 closed |
| Correctness | Required compaction/restart E2E oracle is context-sensitive |
| Coherence | Followed |

All checks passed. Ready for PR.

## Targeted Closure

| Focus issue | Fix evidence | Verification | Status |
|---|---|---|---|
| C1: post-summary fake LLM 泄露 sentinel，上下文丢失仍可能绿 | `scripts/fixtures/anthropic_sse_compaction_recording.py:200-207` 现在从当前 request messages 查找 sentinel，缺失立即返回 422；`tests/e2e/critical_paths/test_context_compaction_continuity_critical_path.py:161-172` 在 Gateway restart 后重读 recording，断言压缩后与 restart 后恰有两个 post-summary request，且两者 messages 都包含 sentinel | 静态检查确认 response 只在 request 自身携带目标时才回传 sentinel；独立真 IM + 真 Gateway + recording LLM 旅程 `1 passed in 27.54s` | closed |

fix delta 只修改上述 fixture 与 E2E 断言，未触及产品实现、架构边界或其他 requirement/scenario；Round 1 的其余结论不受影响，无需升级 full verification。

## Validation Evidence

- Target E2E: `1 passed in 27.54s`.
- Ruff on both delta files: `All checks passed!`.
- `git diff --check` for the fix delta: passed.

## Issues

### CRITICAL（提 PR 前必须修）

None.

### WARNING（提 PR 前必须修）

None.

### SUGGESTION（可以修）

None.

# Round 3

> Validation snapshot: `1d0c2cb45b887162912402b0fb489cdf3a1ad9c9 → 8a01c838fda8b4ef68dd3a741f60c17ad28dc77d`

## Summary

Mode: delta

Delta range: `f50c59d41a29e9bb9892292c30cd952934574ff6..8a01c838fda8b4ef68dd3a741f60c17ad28dc77d`

Focus issues: N/A

requires_full_verification: false

| 维度 | 结果 |
|---|---|
| Completeness | 6/6 code-review substantive closures proven |
| Correctness | Added regressions and affected compaction journey pass |
| Coherence | No new spec/design/architecture deviation |

All checks passed. Ready for PR.

## Delta Verification

| Closure | Implementation evidence | Permanent regression | Status |
|---|---|---|---|
| 格式化后为空的 summary 不得假成功 | `src/agent/core/agent/compaction/summarizer.py:72-90` 对格式化结果再次判空，仅返回有效文本或 `None` | `tests/unit/test_loop_compact.py:634` | closed |
| compaction summary side-chain 不泄露用户可见事件 | `src/agent/core/agent/compaction/summarizer.py:84-88` 不把父 `HookContext` publisher 传入内部 fork；run model override 与 trace ContextVar 路由保持 | `tests/unit/test_loop_compact.py:663` | closed |
| skill reinjection 在 durable active branch 与 restart 后可达 | `src/agent/core/agent/runtime.py:2154-2165` 将 reinjection 的 parent 明确设为 compact summary entry | `tests/unit/agent/test_kernel_manual_compact.py:255` 从真实 JSONL close/reopen 后同时恢复 summary 与 reinjection | closed |
| overflow 恢复后的 retry 若再抛 `CompactionError`，仍先提示再 failed | `src/agent/core/agent/runtime.py:727-773` 在 retry seam 捕获 typed failure 并复用 `_emit_compaction_failure()` | `tests/integration/test_conversation_compaction_integration.py:472` | closed |
| manual 成功后旧 prompt usage 不触发伪 threshold | `src/agent/core/agent/runtime.py:2118-2121` 仅在 durable commit 成功后清空 `last_prompt_tokens` | `tests/integration/test_conversation_compaction_integration.py:378` | closed |
| overflow 成功后旧 prompt usage 不污染 retry | 同一成功 commit seam 清空 prior usage，stale/persistence 失败路径不触达 | `tests/integration/test_conversation_compaction_integration.py:423` | closed |

本 delta 只加深既有 `agent.core` summarizer/runtime seam，没有新增产品入口、JSONL schema、wire event 或 durable owner。格式化后判空仍是 design 决策 2 的“有效文本或未生成”，不是摘要质量启发式；reinjection 父链、成功后的 prompt-window refresh 和 retry 失败提示分别闭合 design 决策 1、3、4。Round 2 已关闭的上下文敏感 E2E oracle 未被改写，真 IM + 真 Gateway 旅程在本 snapshot 仍通过。因此此前 full/targeted-closure 结论可保留，无需升级 full verification。

## Validation Evidence

- Six new substantive regressions: `6 passed in 6.46s`.
- Focused unit/integration compaction suite: `92 passed in 22.67s`.
- Context-sensitive compaction/restart E2E: `1 passed in 27.60s`.
- Core/compaction/replay architecture contracts: `6 passed`.
- Hook integration and test naming/size contracts: `6 passed`.
- Ruff on all changed Python files: `All checks passed!`.
- Docs integrity: `232 maintained Markdown sources, 67 required routes`.
- `git diff --check` for the delta: passed.

## Issues

### CRITICAL（提 PR 前必须修）

None.

### WARNING（提 PR 前必须修）

None.

### SUGGESTION（可以修）

None.

## Corrected Delta Reconciliation

> Validation snapshot: `1d0c2cb45b887162912402b0fb489cdf3a1ad9c9 → 647be9717c83997e10e6372f17f01c4ef7595338`

| Delta item | Implementation evidence | Test evidence | Outcome |
|---|---|---|---|
| MODIFIED Requirement：上下文压缩在长会话中保持可恢复 | `src/agent/core/session/entries.py:92-200`; `src/agent/core/session/transcript.py:171-229`; `src/agent/core/agent/compaction/summarizer.py:57-95`; `src/agent/core/agent/loop.py:1010-1128`; `src/agent/core/agent/runtime.py:684-775,1919-2165` | `tests/unit/test_session_persistence_fidelity.py:349`; focused suite；critical-path E2E | aligned |
| Scenario：手动触发压缩 | `src/agent/sdk/kernel.py:1353-1381`; `src/agent/core/agent/runtime.py:308-327,1949-2137` | `tests/integration/test_conversation_compaction_integration.py:233` | aligned |
| Scenario：focus 指导手动压缩的后续上下文 | `src/agent/core/agent/runtime.py:1995-2003`; `src/agent/core/agent/compaction/prompts.py:124-134` | `tests/unit/test_loop_compact.py:584`; `tests/unit/personal_assistant/test_gateway_stop_command.py:560` | aligned |
| Scenario：手动压缩摘要失败不改变上下文 | `src/agent/core/agent/runtime.py:2011-2025,2086-2117` | `tests/unit/agent/test_kernel_manual_compact.py:67,102,141` | aligned |
| Scenario：自动阈值压缩失败不伪装成功 | `src/agent/core/agent/loop.py:1027-1050,1095-1119` | `tests/unit/test_loop_compact.py:398`; `tests/integration/test_conversation_compaction_integration.py:520` | aligned |
| Scenario：只有 reasoning 的摘要响应视为失败 | `src/agent/core/agent/compaction/summarizer.py:89-95`; `src/agent/core/agent/compaction/prompts.py:137-158` | `tests/unit/test_loop_compact.py:634` | aligned |
| Scenario：摘要生成的内部事件不泄露给消费者 | `src/agent/core/agent/compaction/summarizer.py:72-95` 统一隔离 threshold、overflow、manual 共用 summarizer 的父 publisher | `tests/unit/test_loop_compact.py:663` | aligned |
| Scenario：连续自动压缩失败有界并可诊断 | `src/agent/core/agent/compaction/types.py:9-41`; `src/agent/core/session/conversation.py:182,423-431`; `src/agent/core/agent/loop.py:1010-1050`; `src/agent/core/agent/runtime.py:684-691,1919-1947` | `tests/unit/test_loop_compact.py:398,427`; `tests/unit/agent/session/test_conversation_session.py:244`; `tests/integration/test_conversation_compaction_integration.py:520` | aligned |
| Scenario：overflow 恢复摘要失败保留原错误与历史 | `src/agent/core/agent/runtime.py:692-775,1949-2025`; `src/agent/core/errors.py:63-97`; `src/agent/core/runs/registry.py:523-534` | `tests/integration/test_conversation_compaction_integration.py:586` | aligned |
| Scenario：压缩记录持久化失败不暴露半提交上下文 | `src/agent/core/agent/loop.py:1095-1119`; `src/agent/core/agent/runtime.py:2086-2117` | `tests/unit/agent/test_kernel_manual_compact.py:102`; `tests/integration/test_conversation_compaction_integration.py:660,730` | aligned |
| Scenario：含工具历史的压缩在重启后继续任务 | `src/agent/core/session/entries.py:92-200`; `src/agent/core/session/transcript.py:171-229,688-708`; `src/agent/core/agent/runtime.py:2057-2165` | `tests/unit/test_session_persistence_fidelity.py:349`; `tests/unit/agent/test_kernel_manual_compact.py:256`; `tests/e2e/critical_paths/test_context_compaction_continuity_critical_path.py:71` | aligned |
| Scenario：成功压缩后不沿用压缩前的 token 判定重复压缩 | `src/agent/core/agent/runtime.py:2118-2121`，仅在 durable commit 成功后清空旧 usage | `tests/integration/test_conversation_compaction_integration.py:378,423` | aligned |
| Scenario：自动压缩不继承手动关注点 | `src/agent/core/agent/runtime.py:1995-2003` 只在 manual 分支传 focus；threshold/overflow 调用点不接收 focus | `tests/unit/test_loop_compact.py:584` + call-site inspection | aligned |
| Scenario：相同手动操作 identity 不重复压缩 | `src/agent/core/agent/runtime.py:1962-1972,2087-2100`; `src/agent/core/session/transcript.py:438-470` | `tests/unit/agent/test_kernel_manual_compact.py:167` | aligned |
| Scenario：按当前轮模型的窗口判定压缩 | `src/agent/core/agent/loop.py:934-973`; `src/agent/core/agent/runtime.py:405-409` | `tests/unit/test_loop_compact.py:731` | aligned |
| Scenario：未声明窗口的模型回退默认上限 | `src/agent/core/agent/loop.py:934-973` | `tests/unit/test_loop_compact.py:748` | aligned |
| Scenario：工作区绑定的会话压缩落盘后运行透明继续 | `src/agent/core/agent/runtime.py:1973-2001,2027-2047,2086-2137` | `tests/integration/test_conversation_compaction_integration.py:103,233,294` | aligned |

校准新增的 reasoning-only、summary side-chain 隔离、reinjection 父链与 manual/overflow token freshness 都是 approved design 中“有效摘要或失败”“内部摘要不是用户事件”“durable replacement 可恢复”“成功后刷新 prompt window”的直接消费者投影，没有扩大 JSONL schema、产品入口或跨包协议。持久化异常与 external-epoch stale 继续按 design 分流：前者进入 typed automatic failure，后者保留原上下文并重算或保留原 overflow；delta 没有把 stale 错写为 persistence exception。

验证证据：focused unit/integration compaction suite `92 passed in 22.87s`；上下文敏感真 IM + 真 Gateway compaction/restart E2E `1 passed in 25.77s`；PA `/compact focus` consumer seam `1 passed in 2.63s`。

### Uncovered Observable Behavior

None. 对 `executed_base..validated_at` 的全部生产 diff 反向扫描后，新增/改变的消费者行为均已由本 delta 的 requirement 或 scenario 覆盖；其余改动是对应 carrier、测试、fixture 与 unit evidence。

Outcome: aligned

# Round 4

> Validation snapshot: `1d0c2cb45b887162912402b0fb489cdf3a1ad9c9 → d502ec617512cdf57603d7eba76ff94bea96a108`

## Summary

Mode: targeted-closure

Delta range: `f9db02d958e9972e229a774036eaa40df8d454c4..d502ec617512cdf57603d7eba76ff94bea96a108`

Focus issues: R7/R8 摘要 side-chain 必须保留 workspace hook scope/model routing，同时隔离父会话的 assistant/turn 与 permission 事件

requires_full_verification: false

| 维度 | 结果 |
|---|---|
| Completeness | R7/R8 2/2 target contracts closed |
| Correctness | Derived context preserves routing and fail-closes permission without parent event leakage |
| Coherence | Existing HookContext/workspace scope seams reused; no new abstraction or package boundary |

All checks passed. Ready for PR.

## Targeted Closure

| Target | Implementation evidence | Permanent regression | Status |
|---|---|---|---|
| 恢复 summary fork 的 originating workspace hook scope 与模型路由 | `src/agent/core/agent/compaction/summarizer.py:72-96` 用 `dataclasses.replace()` 派生不可变 `HookContext`，保留 metadata/model caller 等 routing 字段；`model_override` 仍按 shared/dedicated summary model 旧契约传递。`src/agent/core/agent/loop.py:242-267` 仍从 `_workspace_execution_scope` 选择 hook runner | `tests/unit/agent/test_workspace_scope_observer_hooks.py:88-121` 从 public `Kernel.compact()` 证明 `.consumer` workspace `turn_start` hook 确实运行；`tests/unit/test_loop_compact.py:663-704` 同时锁定 metadata 与 run model override | closed |
| 摘要内部 assistant/turn 事件不进入父会话消费流 | 派生 context 只把 `session_event_publisher` 替换为 no-op，不改动 scope 和 model routing | `tests/unit/test_loop_compact.py:663-704` 主动在 summary fork 发布 `assistant_message`/`turn_end`，并断言父 publisher 无事件 | closed |
| summary workspace hook 不能绕过 no-op publisher 打开父 permission 流 | `src/agent/core/agent/compaction/summarizer.py:72-80` 进一步将派生 context 的 `permission_requester=None`；`src/agent/core/hooks/context.py:243-269` 使无 channel 请求按现有契约 fail-closed 为 `deny` | `tests/unit/agent/test_workspace_scope_observer_hooks.py:124-180` 的 public Kernel 回归证明 hook 确实执行并得到 `deny`，父 stream 无 `permission_request`/`permission_resolved`/权限 heartbeat | closed |

R7 中间快照仅替换 direct publisher，会保留一个已捕获父 publisher 的 `permission_requester` 闭包；R8 在同一派生 seam 清除该能力字段，已关闭这个确认过的 P2 泄漏路径。最终 delta 没有改变 JSONL schema、wire event、durable owner 或产品入口；只在现有 `HookContext` 不可变数据面上收窄 side-chain 用户事件与交互权限能力。Round 3 与 corrected-delta 的 full 结论不受影响，无需升级 full verification。

## Validation Evidence

- Three cross-contract regressions: `3 passed in 0.24s`.
- Extended affected compaction/workspace suite: `80 passed in 27.64s`.
- Context-sensitive compaction/restart E2E: `1 passed in 26.41s`.
- Core/package architecture contracts: `7 passed in 0.20s`.
- Ruff on all R7/R8 Python delta files: `All checks passed!`.
- Docs integrity: `232 maintained Markdown sources, 67 required routes`.
- `git diff --check` for the complete R7/R8 delta: passed.

## Issues

### CRITICAL（提 PR 前必须修）

None.

### WARNING（提 PR 前必须修）

None.

### SUGGESTION（可以修）

None.
