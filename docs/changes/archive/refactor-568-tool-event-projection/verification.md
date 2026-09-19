# Verification Report: refactor-568-tool-event-projection

> Validation snapshot: `4394ad4246b2ec3324e2c8aa219212dc0ec2ff75 → 151928fed7d894114b89c851cce8b621872e64d7`

## Round 1

- reviewer: `/root/static_review`，未参与受审实现；caller 明确合并派发静态 code review 与 verifier，两份报告分别给出结论。
- verification_mode: `full`
- verdict: **pass — 0 CRITICAL / 0 WARNING / 0 SUGGESTION**
- requires_full_verification: `false`
- 范围：完整 frozen diff、M1 退出标准、motivation/design、相关 current specs 与测试证据；no spec delta。只写报告，不启动服务或改动被审对象。

## Summary

| 维度 | 结果 |
|---|---|
| Completeness | M1 的静态实现、回归保护和 no-spec-delta 检查完整 |
| Correctness | 3/3 不变性场景有实现与直接测试/代码证据 |
| Coherence | 4/4 design 决策遵守 |

## Completeness

- M1 实现把 start/end 解析、in-flight 状态、正常 `finish` 与异常 `reconcile` 收敛到 `tool_projection.py`；observer 保留 shadow 写入顺序、门控、Workflow binding、任务命名和调度。
- `implementation.md` 的基线 89 项既有回归及新增 4 项目的地投影证据可复用；本次独立复跑的 21 项覆盖新增文件、reconcile input/presentation 和 presenter 字段透传。
- diff 仅含 runtime_delivery 内部职责迁移、测试及 unit 记录；不含 `docs/specs/`、协议、存储、Kernel、IM 或 UI 修改，因此 `no spec delta` 成立。Prototype / Reference：N/A。
- design 要求的真实产品观察（实际 IM/Gateway/LLM 路径与持久化工具历史）由 caller 同时派发的独立 product reviewer 验收；本静态 verifier 未将该未完成的独立职责声称为已执行。

## Correctness

| Requirement / Scenario | 实现位置 | 测试覆盖 | 状态 |
|---|---|---|---|
| 正常与失败工具的名称、参数、detail、emoji、完成/失败和 verdict 保持 | `tool_projection.py:26-86`; `observer.py:788-799, 1674-1754` | `test_tool_delivery_projections.py:89-131`; `test_tool_end_detail_passthrough.py` | covered |
| 中断中工具关闭且保留原参数/展示，已完成工具不改写 | `tool_projection.py:116-163`; `observer.py:733-734, 843-859, 1971-2003` | `test_reconcile_preserves_tool_input.py:66-303` | covered |
| IM 离线时 shadow 恢复语义和实时/历史字段省略规则不变 | `observer.py:723-799, 951-962`; `tool_projection.py:78-114` | `test_tool_delivery_projections.py:134-181`; implementation.md 的 shadow 回归记录 | covered |

## Coherence

| design 决策 | 遵守? | 代码证据 |
|---|---|---|
| 一个状态 owner，保留两种历史 wire schema | 是 | `tool_projection.py:12-17, 78-89` 明确返回 shadow/live 两份 payload；`observer.py:788-799, 1690-1745` 分别写入/发送。 |
| 每个 admitted 事件最多一次状态转换；未走 shadow 者在既有 live gate 后投影 | 是 | `observer.py:788-792` 将 shadow 投影放进 scope；`observer.py:1690, 1734` 只在缺少 scope 投影时调用 project；离线分支在 `951-962` 前不再调用 live handler。 |
| 保持 shadow-before-live 和 live-only revalidation | 是 | `observer.py:735-859` 先持久化，`1674-1710` 后发送；`tool_projection.py:92-114` 仅在 live path 更新 pending detail。 |
| 保持工厂注入接口和异常 bare-name fallback | 是 | `observer.py:172, 245-247`; `tool_projection.py:127-153`。 |

## Issues

### CRITICAL

无。

### WARNING

无。

### SUGGESTION

无。

## Corrected Delta Reconciliation

**no spec delta**：完整 diff 未引入未被 current specs 覆盖的可观察行为；两份历史 schema、顺序与 gate 均保留。无 uncovered observable behavior。

独立验证命令：

```sh
PYTHONPATH=src /Users/czj/Repos/nano-multiagent/.venv/bin/python -m pytest -q \
  tests/unit/personal_assistant/test_tool_delivery_projections.py \
  tests/unit/personal_assistant/test_reconcile_preserves_tool_input.py \
  tests/unit/personal_assistant/test_tool_end_detail_passthrough.py
PYTHONPATH=src /Users/czj/Repos/nano-multiagent/.venv/bin/python -m ruff check \
  src/personal_assistant/gateway/runtime_delivery/observer.py \
  src/personal_assistant/gateway/runtime_delivery/tool_projection.py \
  tests/unit/personal_assistant/test_tool_delivery_projections.py
git diff --check 4394ad424..151928fed7d894114b89c851cce8b621872e64d7
```

结果：`21 passed in 1.38s`；Ruff 通过；diff check 通过。

caller 提供并在同一 `validated_at` 上执行的可复用验证：`PYTHONPATH=src pytest -m 'not e2e' -n 4 --dist worksteal` 为 **3992 passed / 178.84s**（`/tmp/refactor568-pytest.log`）；frontend 的 `npm ci`、`npm audit --audit-level=critical`、`npm test -- --maxWorkers=2` 全部通过，结果为 **83 files / 770 tests / 125.46s**（`/tmp/refactor568-frontend.log`）；`docs-check` 为 **242 maintained Markdown sources / 73 routes**，`ruff check .` 与 format check（1082 files）通过。我已读取两份日志末尾确认上述两个测试汇总；其余命令结果按 caller 提供证据复用。独立 product reviewer 的真实用户旅程结论仍应由其专属报告给出，未被表述为本 verifier 的执行结果。

## Round 2

- reviewer: `/root/static_review`，未参与 A1 实现；caller 明确派发 patch code review 与 delta verification。
- verification_mode: `delta`
- executed_base: `4394ad4246b2ec3324e2c8aa219212dc0ec2ff75`
- validated_at: `34ff1a2cedfac2224ec88661bc19b54d4dded4c0`
- fix_delta_range: `151928fed7d894114b89c851cce8b621872e64d7..34ff1a2cedfac2224ec88661bc19b54d4dded4c0`
- verdict: **fail — 0 CRITICAL / 1 WARNING / 0 SUGGESTION**
- requires_full_verification: `false`；该测试接线缺口修复后只需 targeted closure。

### Delta 对齐

| A1 contract | 实际证据 | 状态 |
|---|---|---|
| 明确 user stop 授权，cancelled 保留同次授权 | `context.py:406-429`; `session_run_coordinator.py:1319-1322,3109-3111` | 实现 aligned；回归保护不足，见 R2-W1 |
| reset/generation revoke 不能恢复 cleanup | `context.py:353-361,417-425`; `test_im_reply_image_delivery.py:156-185` 的 reset 参数分支 | covered：revoked+false 与旧 generation 都不能重新授权 |
| revoked observer 仅继续 reconcile | `observer.py:696-699` | covered：正文和 tool_end 仍被 gate 丢弃 |
| 已有 bubble 的 failed tool/bodyless completion 可收口，无正文/新 bubble | `image_connection.py:92-104`; `test_im_reply_image_delivery.py:188-203` | covered |

### Issues

### CRITICAL

无。

### WARNING

- **R2-W1 — 实现 A1 核心 coordinator 传播没有可观察回归保护。** `tests/unit/personal_assistant/test_im_reply_image_delivery.py:128-203` 的六个新增 case 手动调用 `RunDeliveryContextStore.suppress(..., terminal_cleanup=True)`，没有执行 `SessionRunCoordinator.stop` 或其 cancelled 分支。`tests/unit/personal_assistant/test_session_run_coordinator_terminal.py:175-206` 真实驱动 stop/cancelled/reconcile，却未注入 `delivery_context_store`，所以也不会执行新授权契约。若 `session_run_coordinator.py:1319-1322` 或 `3109-3111` 回退为普通 suppress，现有新旧测试仍可通过，真实 `/stop` 会重新吞掉 reconcile，正是设计 R2-W1 曾发现的生产链。建议扩展该 coordinator terminal 测试，接入真实 context store、observer 和 writer，验证 stop→cancelled→reconcile 的原 bubble 收口；并加入 reset/generation advance 后迟到 cancelled 的拒绝路径。此问题直接由 diff 和测试构造确认，无需追加核验。

### SUGGESTION

无。

### Corrected Delta Reconciliation

**no spec delta**：A1 修复 current `tool-timeline` 已有的中断收口约束，未增加协议字段、网络接口、存储或新的可观察权限。唯一 delta-mismatch 是 R2-W1 的自动化接线证据缺口，不是通过修改 spec 可以消除的实现偏离。

独立执行：`PYTHONPATH=src /Users/czj/Repos/nano-multiagent/.venv/bin/python -m pytest -q tests/unit/personal_assistant/test_im_reply_image_delivery.py tests/unit/personal_assistant/test_reconcile_preserves_tool_input.py tests/unit/personal_assistant/test_tool_delivery_projections.py`，结果 **19 passed**；A1 涉及源文件和测试的 Ruff 通过，`git diff --check` 通过。caller 的窄套件 60 passed 和正在运行的全量 Python CI 可在修正测试后继续复用，但当前不能替代 R2-W1 要求的生命周期接线断言。

## Round 3

- reviewer: `/root/static_review`，未参与修正实现。
- verification_mode: `targeted-closure`
- executed_base: `4394ad4246b2ec3324e2c8aa219212dc0ec2ff75`
- validated_at: `a2a86e7308b746638bf987d4fc4c69434a379336`
- fix_delta_range: `34ff1a2cedfac2224ec88661bc19b54d4dded4c0..a2a86e7308b746638bf987d4fc4c69434a379336`
- focus_issues: R2-W1。
- verdict: **fail — 0 CRITICAL / 1 WARNING / 0 SUGGESTION**
- requires_full_verification: `false`；一条 reset 负断言即可 targeted closure。

### R2-W1 reconciliation

| Focus issue | Evidence | Outcome |
|---|---|---|
| coordinator stop→cancelled→reconcile must preserve cleanup to original bubble | `test_session_run_coordinator_terminal.py:190-271` injects ContextStore, observer and ImageReplyConnection; starts a tool, calls real `coordinator.stop`, delivers cancelled, and asserts failed tool plus `message_completed` | closed for non-reset |
| stop→reset/generation advance→late cancelled must not publish any terminal | reset branch at `test_session_run_coordinator_terminal.py:259-267` advances generation and sees cancelled, but only asserts no `tool_call_completed` | still_open |

### Issues

### CRITICAL

无。

### WARNING

- **R3-W1 — reset 反例漏断言 `message_completed`。** 当前测试将 frames 中的 `tool_call_completed` 单独筛出并在 reset 分支断言空，却没有检查 `message_completed`。A1 的 reset 契约禁止旧 bubble 的整个 cleanup terminal，不只禁止工具 terminal；错误地放行 bodyless bubble completion 仍会改变已 reset 的历史，而该测试会通过。建议在 reset 分支断言两类 terminal 均不存在或完整 frame kinds 仅为起始 `tool_call_upserted`。

### SUGGESTION

无。

`test_session_run_coordinator_terminal.py` 独立结果为 **11 passed**；该文件 Ruff 与 fix-delta `git diff --check` 均通过。产品 Round 2 和 34ff1 的全量 CI 是未变化实现的有效证据，但不覆盖本次新测试遗漏的负断言。

## Round 4

- reviewer: `/root/static_review`，未参与修正实现。
- verification_mode: `targeted-closure`
- executed_base: `4394ad4246b2ec3324e2c8aa219212dc0ec2ff75`
- validated_at: `995f6724b43fe640c5f47e381ab20b7a42509d85`
- fix_delta_range: `a2a86e7308b746638bf987d4fc4c69434a379336..995f6724b43fe640c5f47e381ab20b7a42509d85`
- focus_issues: R2-W1, R3-W1.
- verdict: **pass — 0 CRITICAL / 0 WARNING / 0 SUGGESTION**
- requires_full_verification: `false`；本冻结版本仅补强已审 lifecycle 回归断言，无产品或实现变化。

### Closure reconciliation

| Focus issue | Evidence | Outcome |
|---|---|---|
| R2-W1 coordinator stop→cancelled lifecycle propagation | The existing parameterized test drives the actual coordinator with ContextStore, observer and ImageReplyConnection, and the non-reset case observes failed `tool_call_completed` plus `message_completed` on the existing bubble | closed |
| R3-W1 reset must reject every terminal frame | After actual `stop → advance_generation → cancelled`, the reset case asserts full frame kinds equal only `["tool_call_upserted"]`; this excludes both tool completion and bubble completion | closed |

### Issues

### CRITICAL

无。

### WARNING

无。

### SUGGESTION

无。

**no spec delta**：此次仅把测试的负断言从单类 tool terminal 扩展为完整 frame 序列，恢复并保护既有 current `/stop` 收口规定，不新增可观察行为或接口。独立执行 `PYTHONPATH=src /Users/czj/Repos/nano-multiagent/.venv/bin/python -m pytest -q tests/unit/personal_assistant/test_session_run_coordinator_terminal.py` 得到 **11 passed in 0.58s**；该文件 Ruff 和 `git diff --check` 均通过。34ff1 的 3998 项 Python 全量、格式/文档检查，以及产品 Round 2 pass 为未变化实现保留的调用方证据；本次冻结只增加上述断言。
