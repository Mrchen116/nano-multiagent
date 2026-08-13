# Verification Report: bugfix-536

> Validation snapshot: `84b386b42 → 5d8a6dea3`

## Summary

Mode: full  
Delta range: N/A  
Focus issues: N/A  
requires_full_verification: false

| 维度 | 结果 |
|---|---|
| Completeness | 4/5 |
| Correctness | 24/25 |
| Coherence | 有偏离 |

1 critical issue(s), 0 warning(s) found. Fix before PR.

## Completeness

- Tasks: 4/5 实际满足。`tasks.md` 的 5 项均勾选，但第 3 项要求 Gateway recovery ledger 覆盖失败收口；已认领 successor 自身失败且没有新 suffix 时，active marker 没有释放，见 CRITICAL-1。
- Spec 覆盖：parent compaction liveness、opaque pending identity、continuation descriptor/settlement、正常 recovery adoption、一次最终投递、no-ACK adoption、显式控制与共用 Gateway 入口均已有实现；recovery successor 的终态失败收口不完整。
- Milestone evidence：复跑 M1 聚合测试为 `159 passed in 10.76s`；全量 contract tests 为 `154 passed in 8.73s`；scoped Ruff、`scripts/docs_check.py`（220 maintained sources / 70 routes）和 `git diff --check 84b386b42..5d8a6dea3` 均通过。另以现有 controlled Kernel 只读复现 successor 失败分支，结果为 `RecoveryHandoffError`、`busy=True`、active=`run-2`。
- Prototype / Reference 覆盖：N/A；design 无前端原型或 reference artifact。

## Correctness

| Requirement / Scenario | 实现位置（file:line） | 测试覆盖 | 状态 |
|---|---|---|---|
| Incident：自动压缩期间追加消息 | `src/agent/core/agent/loop.py:1058`; `src/agent/core/agent/compaction/summarizer.py:72` | `tests/unit/test_loop_compact.py:201`; `tests/unit/test_loop_compact.py:724` | covered：父 run 发 `source=compaction` 心跳，sidechain publisher 仍为 no-op；正常 same-run steer 走既有 admission seam |
| Incident：中断前已接收补充消息 | `src/agent/core/runs/registry.py:627`; `src/personal_assistant/gateway/session_run_coordinator.py:2174` | `tests/integration/test_session_run_coordinator_recovery.py:60` | covered：真实 Kernel descriptor/settlement 被 common Gateway 接管并只回一次 |
| Incident：中断后的下一条正常消息 | `src/personal_assistant/gateway/session_run_coordinator.py:413`; `src/personal_assistant/gateway/session_run_coordinator.py:2334` | 正常/成功恢复路径有既有 admission 与 `tests/unit/personal_assistant/test_recovery_handoff_coordinator.py:184`；缺 successor 失败后继续消息回归 | 缺实现：successor 失败无 suffix 时恢复流程未释放 logical active marker，不能声称所有恢复收口后的下一条消息都从干净状态继续 |
| Incident：飞书、Web IM 与其他 Gateway 入口一致 | `src/personal_assistant/gateway/session_run_coordinator.py:413`; `src/personal_assistant/gateway/runtime_delivery/lifecycle.py:31` | Web/common integration `tests/integration/test_session_run_coordinator_recovery.py:60`; Feishu lifecycle `tests/unit/personal_assistant/test_gateway_relay_lifecycle.py:376` | covered：无 Feishu 专用 recovery 分支，入口共用 coordinator/lifecycle owner |
| Kernel delta：pending identity 关联 continuation batch | `src/agent/core/agent/run_control.py:121`; `src/agent/core/runs/registry.py:640`; `src/agent/sdk/kernel.py:1805` | `tests/contract/test_kernel_sdk_behavior_contract.py:1051` | covered：Kernel-owned id、direct predecessor、batch index/origin/exact ids 均从 SDK stream 暴露 |
| Kernel delta：recovery settlement 恰好一次收口 | `src/agent/core/runs/registry.py:627`; `src/agent/core/runs/registry.py:948` | `tests/contract/test_kernel_sdk_behavior_contract.py:1051`; `tests/unit/personal_assistant/test_recovery_handoff.py:43` | covered：old terminal 在先，successor descriptors 在 settlement 前；Gateway 对 duplicate/late settlement 无副作用 |
| Kernel/Gateway/IM delta：静默长工具、主模型、自动压缩、权限等待四类 liveness | `src/agent/core/agent/loop.py:1058`; `src/agent/core/agent/liveness.py:76`; `src/personal_assistant/gateway/session_run_coordinator.py:2076` | 新增 compaction call-site 测试 `tests/unit/test_loop_compact.py:201`；其余窗口由既有 liveness/watchdog tests 覆盖 | covered：四类均走既有 `run_heartbeat` stream 路径；真实无心跳仍由原 idle timeout 回收 |
| Gateway delta：valid recovery exact suffix、prefix/suffix、multi-origin、duplicate/late/corrupt | `src/personal_assistant/gateway/session_run_coordinator.py:154`; `src/personal_assistant/gateway/session_run_coordinator.py:2195` | `tests/unit/personal_assistant/test_recovery_handoff.py:43`; `tests/unit/personal_assistant/test_recovery_handoff_coordinator.py:100` | covered：只认领 user origin 的 exact pending-id prefix，并以 settlement successor 全集校验 |
| Gateway delta：无法验证/无法恢复时失败并释放会话 | `src/personal_assistant/gateway/session_run_coordinator.py:2311`; `src/personal_assistant/gateway/session_run_coordinator.py:2574` | corrupt/unavailable 有覆盖；successor terminal failure 无覆盖 | 缺实现：corrupt/unavailable 会 fail closed，但已认领 successor 失败且无新 suffix 时遗留 active marker（CRITICAL-1） |
| Gateway delta：`/stop`、`/new`、shutdown 收口且不泄漏恢复输出 | `src/personal_assistant/gateway/session_run_coordinator.py:579`; `src/personal_assistant/gateway/session_run_coordinator.py:920`; `src/personal_assistant/gateway/session_run_coordinator.py:2497` | `tests/unit/personal_assistant/test_recovery_handoff_coordinator.py:226`; `tests/unit/personal_assistant/test_recovery_handoff_coordinator.py:269` | covered |
| Gateway delta：`recovery_adopted` 不重复 ACK/`sent` receipt，final 由 anchor 一次发送、各 follower 一次 terminal | `src/personal_assistant/gateway/runtime_delivery/lifecycle.py:44`; `src/personal_assistant/gateway/session_run_coordinator.py:2248`; `src/personal_assistant/gateway/session_run_coordinator.py:2458` | `tests/unit/personal_assistant/test_gateway_relay_lifecycle.py:376`; `tests/unit/personal_assistant/test_recovery_handoff_coordinator.py:100` | covered |
| Gateway 既有路由、FIFO/并行、真实 stall、工具/LLM/权限 liveness 场景 | 既有 coordinator、run queue 与 runtime delivery seams；本 diff 未另造路径 | M1 聚合中相关 admission/terminal/real-kernel tests 全绿 | covered；本 unit 沿用既有 owner |
| IM delta：四类 heartbeat 刷新、真静默 stale 回收 | `src/IM/ws/gateway/execution.py:353`; `src/IM/ws/gateway/sessions.py:436`（既有消费 seam） | 既有 IM watchdog/liveness contract；新增 Kernel compaction producer 测试 | covered；本 diff 不改变 IM 协议或反向调用 Kernel |

## Coherence

| design 决策 | 遵守? | 代码证据（file:line） |
|---|---|---|
| 决策 1：parent compaction await 发 liveness，sidechain 保持静默 | 是 | `src/agent/core/agent/loop.py:1058`; `src/agent/core/agent/compaction/summarizer.py:72` |
| 决策 2：Kernel 暴露 opaque pending id、完整 descriptor 与一次 settlement | 是 | `src/agent/core/agent/run_control.py:121`; `src/agent/core/runs/registry.py:640`; `src/agent/core/runs/registry.py:948`; `src/agent/sdk/dto.py:61` |
| 决策 3：Gateway ledger 精确交接 suffix，并在成功或失败后释放 logical owner | 否 | `src/personal_assistant/gateway/session_run_coordinator.py:2311` 的 successor failure 分支未执行 `claim.run_id` 的 active cleanup；外层异常清理仍只以原 predecessor `run_id` 调用 `_close_active_run()`（`:1521`） |
| 决策 4：typed `recovery_adopted` 只 seed context，不复制 channel ACK/receipt | 是 | `src/personal_assistant/gateway/inbound_models.py:197`; `src/personal_assistant/gateway/runtime_delivery/lifecycle.py:33` |
| 架构自洽：产品包只依赖 `agent.sdk`，IM 不调用 Kernel，各 channel 复用 Gateway owner | 是 | `src/personal_assistant/gateway/session_run_coordinator.py:15`; `src/personal_assistant/gateway/runtime_delivery/lifecycle.py:21`; changed-file import scan 与 contract tests 均通过 |

### Prototype / Reference Contract

N/A。

## Issues

### CRITICAL（提 PR 前必须修）

- **CRITICAL-1 — recovery successor 失败且没有新 suffix 时不会释放 active marker。** `src/personal_assistant/gateway/session_run_coordinator.py:2311-2334` 在 successor 非 `completed` 后尝试 nested handoff；nested 因无 suffix 返回 `None` 时直接抛错，只有 completed 分支才在 `:2336` 调 `_close_active_run(... claim.run_id)`。随后外层异常处理 `src/personal_assistant/gateway/session_run_coordinator.py:1521-1525` 仍用原 predecessor id 清理，因此无法移除当前 active successor。可复现结果是 follower 已 failed，但 `is_session_busy()` 仍为 true、active 仍指向失败 run。修复时在 nested 返回 `None` 的失败路径原子关闭 `claim.run_id`（或让异常清理跟踪当前 logical owner），并在 `tests/unit/personal_assistant/test_recovery_handoff_coordinator.py` 增加“adopted successor failed、无后续 pending”回归：断言 root/follower 各一次 terminal、session 不 busy、active marker 清空，随后一条普通消息可正常提交和回复。

### WARNING（提 PR 前必须修）

None.

### SUGGESTION（可以修）

- `src/agent/core/agent/liveness.py:1-18` 仍写“three windows / two ... produce no business events”，`src/agent/core/agent/liveness.py:94` 的 source 示例也只有 `llm` / `permission`。本 unit 已加入第四个 `compaction` await，建议同步更新模块/API docstring，避免长期契约注释继续描述旧窗口集合。

# Round 2

## Verification Report: bugfix-536

### Summary

Mode: targeted-closure
Delta range: `dc3173750ccbb329003fe3110ff838819e6b36e6..17994ef0fb69f4425a62a29fd039e9047d195efb`
Focus issues: CRITICAL-1 recovery successor failure without a new suffix leaves the session busy; Round 1 product issue exact `/new` does not isolate the old conversation transcript
requires_full_verification: false

> The supplied pre-fix SHA had one extra trailing character; this round normalized it to the actual first parent `dc3173750ccbb329003fe3110ff838819e6b36e6` of `17994ef0f`.

| 维度 | 结果 |
|---|---|
| Completeness | 2/2 |
| Correctness | 2/2 |
| Coherence | Followed |

All checks passed. Ready for PR.

## Targeted Closure

| Focus issue | Implementation / contract evidence | Test / scenario evidence | Status |
|---|---|---|---|
| CRITICAL-1: failed adopted successor with no new suffix leaves the logical active marker busy | `src/personal_assistant/gateway/session_run_coordinator.py:2311-2341` now closes `claim.run_id` after nested handoff proves that no suffix was adopted. The cleanup remains inside the recovery owner that knows the successor identity and leaves the existing suffix re-handoff path unchanged. | `tests/unit/personal_assistant/test_recovery_handoff_coordinator.py:184-220` asserts root and follower each fail once, `is_session_busy()` becomes false, and a later ordinary message submits and replies. Focused rerun passed. | closed |
| Round 1 product issue: exact `/new` must isolate the old conversation transcript | Existing production code already creates a fresh Kernel session in `GatewaySessionBinder.prepare_reset()` (`src/personal_assistant/gateway/session_binder.py:318-330`), atomically publishes that new binding from `SessionRunCoordinator.new_session()` (`src/personal_assistant/gateway/session_run_coordinator.py:491-585`), and dispatch resolves the published binding. The M2 delta correctly makes no speculative reset-source change because no current reuse path was found. | `tests/integration/test_session_run_coordinator_reset.py:64-123` uses the real Kernel and inspects the actual second model request: session id changes, the following turn uses the published new id, and the old sentinel is absent. Existing parser/control coverage plus the recorded isolated Web IM public-relay journey in `M2-fix-recovery-closure/progress.md:53-65` confirms exact `/new`, distinct fresh JSONL, and `UNKNOWN`, while non-exact `/new ...` retains the old context. Focused rerun passed. | closed |

The Round 1 live result and Round 2 result differ despite no reset-source delta. That does not leave a current implementation route open: the deterministic request-level regression proves the old transcript is absent at the model boundary, and the independent public Web IM journey proves the same property through the user ingress. A source change made only to satisfy the earlier report would be unsupported by the current route evidence.

## Relevant Contract and Scenario Evidence

- Incident control boundary: `incident.md:38-40,84-88` requires exact `/new` to reopen without old context while non-exact text remains ordinary input. The real-Kernel regression and Web IM journey cover both sides.
- Design recovery closure: `design.md:81-105` requires the logical active marker and FIFO to release after a failed successor with no further suffix. The new cleanup and regression match this owner/state transition.
- Gateway delta failure closure: `specs/gateway/routing-delivery.md:13-18` requires unrecoverable followers to fail once and release the session. The new regression observes terminal lifecycle and subsequent admission.
- No architecture drift was introduced: the only source delta stays in the shared `personal_assistant` coordinator, adds no `agent.core` import, creates no Feishu-specific path, and preserves the existing Kernel SDK / Gateway / IM dependency direction.

## Validation

- Focused closure and exact-control suite: `9 passed, 15 deselected in 2.69s`.
- M1+M2 aggregate: `160 passed, 1 failed in 11.97s`; the sole failure was the pre-existing thread-gated structured-image steer test, outside this delta. Its immediate isolated rerun passed, then it passed again alongside both closure tests (`3 passed in 2.35s`), so it is not evidence of a stable regression from this patch.
- Changed-source Ruff: passed.
- `git diff --check dc3173750..17994ef0f`: passed.

## Issues

### CRITICAL

None.

### WARNING

None.

### SUGGESTION

None in the targeted delta. Round 1's non-blocking liveness-docstring suggestion was outside this round's focus and remains recorded above.
