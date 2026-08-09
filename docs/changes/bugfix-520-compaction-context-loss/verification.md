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
