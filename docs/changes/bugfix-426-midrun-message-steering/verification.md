# Verification Report: bugfix-426

> Round 1 — 2026-06-23

## Summary

| 维度 | 结果 |
|---|---|
| Completeness | 7/7（退出标准全达成；tasks.md 格式未勾选见注） |
| Correctness | 13/13 scenario 全覆盖 |
| Coherence | Followed（4 条关键决策均遵守） |

No critical issues. 1 warning to consider. Ready for PR (with noted improvements).

---

## Completeness

### Tasks 完成情况

M1 / M2 全部 Roadpoints 在 progress.md 标注 DONE，全测试树通过（2759 passed, 0 failed, 1 skipped）。
`tasks.md` 退出标准项目格式为 `- [ ]`（未勾选），但 Roadpoints 状态行均标 `— DONE`，progress.md 也有对应实现证据——属于 worker 未更新 checkbox 的格式问题，不影响实际完成度。

**Tasks: M1(4/4 roadpoints) + M2(2/2 roadpoints) = DONE**

### Spec 覆盖

所有 3 条 Requirement 均有对应实现，见 Correctness 节逐条核对。

---

## Correctness

### Requirement: 运行中消息在当前 run 下一轮被带进上下文

| Scenario | 实现位置 | 测试覆盖 | 状态 |
|---|---|---|---|
| 工具循环中途发消息，下一轮即被消费 | `registry.py:545-570` `inject_pending_message`；`loop.py` 每轮 `drain_pending()` | `test_kernel_sdk_behavior_contract.py:471` `test_submit_steer_active_run_injects_not_new_run`；M1 live IM 旅程① | covered |
| 不掐断正在执行的工具 | `inject_pending_message` 只入 pending 队列不 abort；`abort_event` 仅 `interrupt()` 设置（`run_control.py:54`） | contract 测试已验注入后工具批次跑完；无专项断言但机制清楚 | covered |
| 连发多条，按序全注入 | `run_control.py:48` `SimpleQueue` FIFO；`drain_pending()` 一次性全取；`test_run_control_pending_origin.py:17` `test_enqueue_drain_carries_origin_fifo` | `test_cli_repl_steering.py:178` `test_mid_run_multiple_messages_each_steered_in_order` | covered |
| 空闲时发消息仍开新 run | `kernel.py:913-926` `_try_inject_active_run` 无活跃 run 返回 None → 正常 submit | `test_kernel_sdk_behavior_contract.py:426` `test_submit_steer_idle_session_creates_new_run`；`test_cli_repl_steering.py:156` `test_idle_input_opens_new_run_without_steer`；`test_inbound_pipeline_kernel_sdk.py:409` `test_idle_message_opens_new_run_not_steer` | covered |

### Requirement: 注入能力恢复为 SDK 内核级 affordance，consumer 统一复用

| Scenario | 实现位置 | 测试覆盖 | 状态 |
|---|---|---|---|
| 任一 agent.sdk consumer 复用同一注入能力 | `kernel.py:836` `submit(steer=bool)` 是唯一对外接口；IM 和 CLI 均经此，无 per-product 实现 | IM 和 CLI 单测各自验证同一 SDK 面 | covered |
| 注入消息携带多模态 parts | `kernel.py:916` `render_user_text(parse_input_parts(parts))`：text 保留、image→`[image:placeholder]` | `test_kernel_sdk_behavior_contract.py:506` `test_submit_steer_injects_render_user_text_content` | covered（按 design 决策2 校正：内核 text-only 现实，content=str，图片→placeholder，与 submit 同款） |
| 多条 steer 消息按序全注入（内核层） | `run_control.py:48,77` SimpleQueue FIFO drain | `test_run_control_pending_origin.py` FIFO 顺序断言 | covered |
| run 结束竞态时续跑保留来源与内容 | `registry.py:708-753` `_settle_terminal_pending`：非 user-initiated → auto-continuation + origin 跟随；`interrupt()` 同步 drain → held | `test_runs_registry.py:588` `test_stranded_continuation_follows_injected_origin`；`:726` `test_stranded_continuation_fires_on_non_user_cancel` | covered |

### Requirement: IM 与 CLI 两端均恢复该能力

| Scenario | 实现位置 | 测试覆盖 | 状态 |
|---|---|---|---|
| IM 聊天运行中 steer | `inbound_pipeline.py:242-272` 运行中调 `_try_steer_active_run` → `submit(steer=True)` | `test_inbound_pipeline_kernel_sdk.py:359` `test_steer_injects_into_active_run_not_new_run`；M1 live IM 旅程① | covered |
| 群聊运行中 steer 保留发言人与缓冲上下文 | `inbound_pipeline.py:513-560` `_build_message_parts` 共用 helper；steer 路径与 normal 路径同源 | `test_inbound_pipeline_kernel_sdk.py:428` `test_group_steer_preserves_sender_prefix_and_buffered_context` | covered |
| CLI REPL 运行中 steer | `commands.py:836-868` `_active_run` 有同 session 活跃 run → `submit(steer=True)` | `test_cli_repl_steering.py:136` `test_mid_run_input_routes_through_steer_not_a_new_run`；M2 live CLI 验证 | covered |

---

## Coherence

| design 决策 | 遵守? | 代码证据（file:line） |
|---|---|---|
| 决策1：SDK 注入 affordance = `Kernel.submit(steer=False)` + 返回 `injected`，steer=True 内核原子地 inject-or-new | 是 | `kernel.py:836-887` submit；`dto.py:64` `injected: bool = False`；`kernel.py:889-930` `_try_inject_active_run` |
| 决策2：注入复用 `parse_input_parts + render_user_text`，content=str，图片→placeholder，与 submit 完全同路径 | 是 | `kernel.py:916` `render_user_text(parse_input_parts(parts))`（design Changelog 校正后最终形态） |
| 决策3：终态三档（非用户终止→续跑；用户/stop→挂起 held；B+A 接线修竞态），单点收口 `_settle_terminal_pending` | 是 | `registry.py:508-521` interrupt() 同步 drain→held；`registry.py:708-753` `_settle_terminal_pending`；`kernel.py:844-886` `flush_held` 参数；`inbound_pipeline.py:841-848` /stop 合成 submit `flush_held=False` |
| 决策4：CLI 非阻塞 REPL 输入，run task + executor input future，`asyncio.wait FIRST_COMPLETED`，运行中输入走 steer=True | 是 | `commands.py:673-868` `_run_repl` 重构；M2 R2 删除 `ReplRunQueue` 死代码确认（`runtime/` 目录已不存在） |

### §4.2 代码模式一致性

- 注释密度、Google docstring 均到位（`kernel.py:847-870` `submit` docstring；`registry.py:715-732` `_settle_terminal_pending` docstring）。
- TODO/FIXME 格式：无发现格式违规。
- Commit 格式：`feat/fix/test/refactor/docs(bugfix-426/M1/R1…)` 规范。
- 产品模块边界：`coding_cli` 和 `personal_assistant` 均只 import `agent.sdk`，无直接 import `agent.core`（contract 测试覆盖依赖方向）。

### §4.3 架构自洽性

- 依赖方向：`_try_inject_active_run` 内有 `from agent.core.agent.state import ...`（`kernel.py:906-910` local import）。这是 `agent.sdk` 内部依赖 `agent.core`——符合架构规则（`sdk → core + platform`），不是产品包直接触 core。
- 跨机边界：注入能力完全在进程内（RunsRegistry / RunController / AgentLoop 同一进程），无跨进程假设。
- 复用 vs 平行：复用既有 `inject_pending_message` / `drain_pending` / `_settle_terminal_pending` 机制，无另立平行实现。

---

## Issues

### CRITICAL（提 PR 前必须修）

无。

### WARNING（应该修）

**W1：delta-spec 尚未归并进长青契约层**

delta-spec 位于 `docs/changes/bugfix-426-midrun-message-steering/specs/{kernel,gateway,cli}/spec.md`，但：
- `docs/specs/kernel/spec.md` 无 `steer` / `inject` / `injected` 相关内容
- `docs/specs/gateway/spec.md` 无运行中 steer 相关内容
- `docs/specs/cli/spec.md` 无 REPL 非阻塞输入/steer 相关内容

按 `docs/SPEC_GUIDE.md:143-151`，orchestrator 应在提 PR 前完成收尾归并（校正 delta → 合并进 canonical）。这是 orchestrator 的收尾义务，verifier 仅报告未完成状态。

修复：orchestrator 执行 SPEC_GUIDE 收尾归并 checklist，把三份 delta-spec 中的 ADDED Requirements 合并进对应长青 spec，bump `> 对齐:` 行。

**W2：M1/M2 tasks.md 退出标准 checkbox 未勾选**

`M1-sdk-im-steering/tasks.md:14-20` 和 `M2-cli-steering/tasks.md:11-15` 的退出标准条目全部为 `- [ ]`。progress.md 和 Roadpoints 状态行（`— DONE`）有对应证据，实际均已完成。格式不一致，后续维护时易产生误解。

修复：worker 或 orchestrator 把退出标准勾选状态更新为 `- [x]`。

### SUGGESTION（可以修）

**S1：`_settle_terminal_pending` 中 `is_user_interrupt` 分支事实上不可达（防御性冗余）**

`registry.py:508-520`：`interrupt()` 已在 abort 后**同步**把 controller pending 全 drain 进 held；`_settle_terminal_pending`（`registry.py:735`）再次 `drain_pending()` 时，/stop 路径下 controller 已空 → `if not stranded: return`，永远不到 `if controller.is_user_interrupt:` 分支。

该分支是防御性设计（注释说「后台 _settle_terminal_pending drain 此时为空」）——如果未来有其他代码路径 abort 但不 drain，仍能正确处理。属于有意的防御性冗余，不影响正确性，但值得在注释里显式说明"此分支为防御路径，正常流 interrupt() 已同步 drain"，减少后人困惑。

**S2：CLI 双订阅 stream 为已知 drift，建议独立 refactor unit 跟踪**

`M2-cli-steering/progress.md:37-41` 已记录：`_send_message_async` per-run stream + `_drain_forever` 持久 drain 形成双订阅，属于 feat-338「单常驻 reader」设计的 drift。产品行为当前正确（双订阅无重复渲染），但属于架构欠债。

进度笔记已建议"独立 refactor unit 将 CLI 渲染收敛回单订阅"，建议 orchestrator 提 follow-up issue 追踪，防止遗忘。
