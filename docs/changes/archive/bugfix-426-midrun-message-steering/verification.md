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

---

# Round 2 — 2026-06-24

> 本轮新增 M4（#140 修复）后的完整验证。M4 引入：决策5（loop 末轮 re-drain 续同一 run、commit_terminal 原子化，正常 steer 不再分裂 run_id）、决策6（kernel 在 drain 消费点发 injection_consumed 信号 → gateway observer 收尾旧气泡 A、开排在 steer 之后的新气泡 B）、决策3 收窄（continuation 仅兜异常终止）。

## Summary

| 维度 | 结果 |
|---|---|
| Completeness | M1–M4 全 Roadpoints DONE；M3 退出标准 3/3 [x]；M4 退出标准 0/7 [x]（格式问题，实现有据）；**一条退出标准（e2e marker 测试）以 unit 层回归替代** |
| Correctness | M4 新增 5 条 Requirement/Scenario 全覆盖（6 个新增测试 + kernel contract 测试）；全 not-e2e 树 2804 passed |
| Coherence | 决策5/6/3收窄均遵守；依赖方向 / 跨机边界 / 平行实现无违规 |

No critical issues. 3 warnings to consider. Ready for PR (with noted improvements).

---

## Completeness

### Tasks 完成情况

- **M1 M2**：已在 Round 1 核验，全部 DONE。
- **M3**：`M3-fix-steer-drain-race/tasks.md` 退出标准 3/3 全勾 `[x]`；Roadpoints 标 `— DONE`；新增并发回归测试 `test_concurrent_group_steer_drain_is_serial_not_interleaved`。
- **M4**：`M4-fix-steer-reply-relay/tasks.md` 退出标准 7 条全为 `- [ ]`，但 progress.md R1–R4 全标 `[DONE]`，有测试与 live 证据。属格式问题（同 Round 1 W2 模式），不影响完成度——但其中 `新增 e2e 复现 #140（marker e2e）` 的落层与 tasks 策略不符，见 W3。

**Tasks: M1(4/4)+M2(2/2)+M3(1/1 R)+M4(4/4 R) = DONE**

### Spec 覆盖

M4 新增 2 条 Requirement：
1. `steer 进活跃 run 的消息，其后续事件始终归属同一个 run`（delta-spec kernel/spec.md 行 43）— 实现见 Correctness。
2. `对插话的回复出现在插话下方，并随 Agent 做事逐步显示`（delta-spec gateway/spec.md 行 37）— 实现见 Correctness。

---

## Correctness

### M4 新增 Requirement：steer 事件归属同一 run（决策5）

| Scenario | 实现位置 | 测试覆盖 | 状态 |
|---|---|---|---|
| steer 的后续事件都出现在该 run 的事件流上 | `loop.py:459-478` 末轮 `try_commit_terminal()` 非空→ append + continue 同 run；`run_control.py:97-116` `try_commit_terminal` 持 terminal_lock | `test_run_control_terminal_commit.py`: 4 测试（非空不 commit / 空 commit / commit 后 enqueue=False / 200轮并发）；`test_agent_loop.py:575` `test_loop_redrains_at_terminal_and_continues_same_run`；`test_kernel_sdk_behavior_contract.py:594` `test_terminal_window_steer_continues_same_run_no_continuation` | covered |
| 活跃 run 已结束无法接续时退化为新建 | `run_control.py:91-95` `enqueue_message` 已 commit → return False；`registry.py:567` 透传 bool → Kernel fallback 新 run | `test_run_control_terminal_commit.py:54` `test_enqueue_after_commit_is_rejected` | covered |
| 事件流标出 steer 消息进入上下文的位置（injection_consumed 信号） | `loop.py:272-274` mid-loop 消费点发 `pending_injection_consumed`；`loop.py:475-477` 末轮 re-drain 消费点同发；`realtime_stream.py:137-189` 转发为 `injection_consumed` session 事件 | `test_agent_loop.py:606` `test_loop_emits_injection_consumed_signal_at_consume_point`；`test_realtime_stream_events.py:193` `test_pending_injection_consumed_emits_injection_consumed`；`:221` `test_pending_injection_consumed_without_run_id_is_skipped` | covered |
| 决策3 收窄：正常完成不再产生 continuation | `registry.py:712-757` `_settle_terminal_pending` drain 为空→自然 no-op（决策5 loop 末轮已消费或 commit 后 inject=False）；异常终止仍走 continuation 分支 | `test_runs_registry.py:599` 引用 `test_terminal_window_steer_continues_same_run_no_continuation`（确认正常路径 runs_before==runs_after）；`test_runs_registry.py:726` `test_stranded_continuation_fires_on_non_user_cancel`（异常路径仍 continuation） | covered |

### M4 新增 Requirement：气泡滚动（决策6）

| Scenario | 实现位置 | 测试覆盖 | 状态 |
|---|---|---|---|
| 对插话的回复排在插话下方并随做事流式显示 | `main.py:3732-3793` `injection_consumed` 分支：message_completed(A,completed) + turn_start(B) + 切 message_id；`main.py:3043-3047` accepted 守卫不覆盖活跃 run 上下文 | `test_steer_bubble_roll.py:55` `test_injection_consumed_closes_bubble_a_completed_then_opens_b`；`test_steer_bubble_roll.py:93` `test_injection_consumed_noop_without_bubble`；`test_steer_reply_relay_regression.py:63` `test_collapse_window_steer_streams_reply_in_new_bubble_no_timeout`（真 InboundPipeline relay + 真 observer + 脚本化 kernel 流：同 run_id post-steer 事件不丢、A completed、steer 工具落 B）；`test_inbound_pipeline_streaming.py:115` `test_accepted_phase_preserves_existing_run_context_for_injected_steer`（#140 根因红测：accepted 不覆盖活跃 run 上下文，修前红修后绿） | covered |

---

## Coherence

### M4 关键决策遵守情况

| design 决策 | 遵守? | 代码证据（file:line） |
|---|---|---|
| 决策5：loop 终止决策与 inject 原子化，`try_commit_terminal` 持锁，非空续跑同 run（不分裂 run_id） | 是 | `run_control.py:97-116` `try_commit_terminal`；`loop.py:462-478` 终止决策处持锁 re-drain |
| 决策6：kernel 在 `drain_pending` 消费点发 `pending_injection_consumed` observe 事件；relay 收 `injection_consumed` → close A + open B | 是 | `loop.py:266-274`（mid-loop）+ `loop.py:475-477`（末轮 re-drain）发信号；`realtime_stream.py:137-189` 注册+转发；`main.py:3732-3793` observer 消费 |
| 决策3 收窄：continuation 仅兜异常终止，正常完成不再产生新 run_id | 是 | `registry.py:712-757` `_settle_terminal_pending`：drain 为空→ return，正常路径自然 no-op（无新 continuation 分支代码，结果源自决策5 的前置消费） |
| 依赖方向 / 跨机边界 / 平行实现（同 Round 1） | 是（无变化） | `tests/contract/` 依赖方向继续通过；所有 M4 新增实现仍在进程内；复用既有 `_close_old_and_restart` 同款序列（无平行气泡路径） |

### §4.2 代码模式一致性

- M4 新增代码注释符合 COMMENTING_GUIDE：`loop.py:459-477` 有 Why 注释和决策编号；`run_control.py:50-116` 有锁纪律说明；`main.py:3733-3743` 有气泡滚动决策说明。
- `hook_types.py` 新枚举 `PENDING_INJECTION_CONSUMED` 命名一致（全大写蛇形，与既有枚举一致）。
- Commit 格式：`fix/test/refactor/docs(bugfix-426/M4/R*)` 规范。

---

## Issues（Round 2 更新）

### CRITICAL（提 PR 前必须修）

无。

### WARNING（应该修）

**W1（延续，状态更新）：M4 delta-spec 尚未归并进长青契约层；`> 对齐:` 行未 bump**

Round 1 报告时 kernel/cli/gateway spec 均无 steer 内容。目前状态：
- `docs/specs/kernel/spec.md`：已有 M1 steer requirement（line 150），但 **M4 追加的 Requirement**（`steer 进活跃 run 的消息，其后续事件始终归属同一个 run` 含 3 个 Scenario）未归并；对齐行仍为 `feat-425`。
- `docs/specs/gateway/spec.md`：已有 M1/M3 steer requirement（line 112），但 **M4 追加的 Requirement**（`对插话的回复出现在插话下方，并随 Agent 做事逐步显示` 含 1 个 Scenario）未归并；对齐行仍为 `bugfix-417`。
- `docs/specs/cli/spec.md`：已有 M2 REPL steer requirement（line 91），内容完整；对齐行仍为 `feat-392`（未 bump 到 bugfix-426）。

修复：orchestrator 执行 SPEC_GUIDE 收尾归并 checklist：
1. 把 `docs/changes/bugfix-426-midrun-message-steering/specs/kernel/spec.md` 中「ADDED Requirements (M4，修 #140)」段（共 3 个 Scenario）追加进 `docs/specs/kernel/spec.md` steer 相关 Requirement 之后。
2. 把 `docs/changes/bugfix-426-midrun-message-steering/specs/gateway/spec.md` 中「Requirement: 对插话的回复出现在插话下方」及其 Scenario 追加进 `docs/specs/gateway/spec.md` steer Requirement 之后。
3. 三份长青 spec 的 `> 对齐:` 行 bump 到 `bugfix-426`。

**W2（延续）：M4 tasks.md 退出标准 7 条全未勾选**

`M4-fix-steer-reply-relay/tasks.md:13-19` 全为 `- [ ]`，但 progress.md R1–R4 均标 `[DONE]`，测试通过。格式不一致。

修复：orchestrator 把 M4 tasks.md 所有退出标准从 `- [ ]` 更新为 `- [x]`。

**W3（新）：M4 #140 回归测试落 unit 层而非 tasks 策略要求的 e2e 层**

`M4-fix-steer-reply-relay/tasks.md:36` 测试策略写 `落层：tests/e2e/（#140 复现，marker e2e）`，退出标准 `新增 e2e 复现 #140` 也指向 pytest e2e 套件。实际产出：
- 3 个 unit 层回归测试（`test_steer_bubble_roll.py`、`test_steer_reply_relay_regression.py`、`test_inbound_pipeline_streaming.py:115`）覆盖了 #140 的关键代码路径；
- `test_steer_reply_relay_regression.py` 使用真 InboundPipeline relay + 真 observer + 脚本化 kernel 流，覆盖度接近 e2e；
- live 手动验证（真 Gateway 进程 + 真 LLM，scratchpad/e2e_run*.log）作为 Entry 证据，但不在 pytest 套件。
- `tests/e2e/` 目录下无 #140 专项测试。

修复：tasks.md 策略说明与实际产出不一致。根据 TESTING_GUIDE §6 判据（"半年后还该每次 CI 跑"），需真 Gateway 进程 + 真 LLM 的 e2e 测试不适合日常 CI；unit 层回归覆盖了根因路径，接受当前状态。建议 orchestrator 更新 tasks.md 测试策略，把 `落层：tests/e2e/` 改为 `落层：tests/unit/`，标注 live 证据路径，防止后续混淆。替代方案：若认为有价值，可补写不依赖真 LLM 的 gateway-level e2e 测试（mock LLM + 真 Gateway 进程），落 `tests/e2e/`，marker e2e，importorskip gateway 进程依赖。

### SUGGESTION（可以修）

**S1（延续）：`_settle_terminal_pending` `is_user_interrupt` 分支为防御性冗余，建议补注释**

`registry.py:742` `is_user_interrupt` 分支（`interrupt()` 已同步 drain）在正常流中永不到达（`registry.py:517` 的同步 drain 在先）。建议在 `_settle_terminal_pending` docstring 或 `:742` 前加注：「interrupt() 在 abort 前已同步 drain，此分支为防御路径，正常流不到达——兜 abort-without-drain 的未来变更」。

**S2（延续）：CLI 双订阅 stream 架构欠债，建议独立 unit 跟踪**

同 Round 1 S2，无变化。

**S3（新）：`docs/specs/cli/spec.md` `> 对齐:` 行未 bump（内容已归并，标记遗漏）**

`docs/specs/cli/spec.md:3` 写 `> 对齐: feat-392`，但 M2 的 REPL steer requirement 已归并（line 91+）。标记与内容不一致，阅读时易产生「这份 spec 不含 bugfix-426 改动」的误判。

修复：`docs/specs/cli/spec.md:3` `feat-392` → `bugfix-426`（与 W1 修复一并执行）。

---

# Round 3 — 2026-06-24

> 本轮对象：fix delta `git diff 941fb6ca 60e4a3da`。核对 V1（三处硬停 commit_terminal）、V2（`_roll_bubble` 原语抽取保真）、V3（`rolling` 守卫语义）、abort×held-buffer 无回归、M1-M3 无回归。

## Summary

| 维度 | 结果 |
|---|---|
| Completeness | V1/V2/V3 全实现；新增 6 个测试；全 not-e2e 树 2810 passed（较 Round 2 多 6） |
| Correctness | 三硬停出口全覆盖、abort 测试有 2/3 出口（max_turns/tool_unavailable）；`rolling` 守卫在串行 observer 流中不产生误拦；V2 行为保真；M1-M3 无回归 |
| Coherence | 决策5 扩展（三硬停 commit_terminal）逻辑自洽；`_roll_bubble` 共享原语实现一致；`_extract_ack_message_id` 防御两种 ack 格式 |

No critical issues. 1 warning to consider. Ready for PR (with noted improvements).

---

## V1：三硬停出口全面 commit_terminal

**核对：决策5 现在覆盖所有终止出口**

| 出口 | 位置 | commit_terminal 调用 | None 守卫 |
|---|---|---|---|
| `max_turns` | `loop.py:~235` | `if controller is not None: controller.commit_terminal()` | 有（controller 可 None） |
| `abort`（cooperative） | `loop.py:~286` | `controller.commit_terminal()`（无 None 守卫） | 无（此分支 drain 在先，controller 已知非 None） |
| `tool_unavailable` | `loop.py:~515` | `if controller is not None: controller.commit_terminal()` | 有 |
| 正常完成（`not iteration_tool_calls`） | `loop.py:~471-482` | `try_commit_terminal()`（软提交，已在 Round 2 验证） | — |

`commit_terminal()` 新方法（`run_control.py:+20`）：持 `_terminal_lock` 无条件 `_terminal_committed.set()`，幂等。与 `enqueue_message` 互斥——commit 后到达的 inject 返回 False，触发 fallback 新 run（不再 stranded）。

**测试覆盖：**
- `test_commit_terminal_is_hard_and_rejects_later_inject`（`run_control_terminal_commit.py`）：commit → enqueue 返回 False。
- `test_commit_terminal_idempotent`：多次 commit 幂等。
- `test_loop_commits_terminal_at_max_turns_exit_with_pending_steer`：max_turns 出口 steer 被拒 → fallback。
- `test_loop_commits_terminal_at_tool_unavailable_exit_with_pending_steer`：tool_unavailable 出口同理。
- **缺口**：abort 出口（`is_aborted` 分支）无专项 loop 级测试。abort 路径的 commit_terminal 语义正确（代码审查确认），但测试不对称。

**WARNING（Round 3 新）：abort 出口缺专项 loop 级测试**

`loop.py:~286` abort 分支 `commit_terminal()` 无对应 `test_loop_commits_terminal_at_abort_exit_*` 测试，与 max_turns / tool_unavailable 的测试模式不对称。abort 路径的正确性靠代码阅读和 `test_commit_terminal_is_hard_and_rejects_later_inject` 的 API 级测试兜底，缺直接的行为断言。

修复建议：参照 `test_loop_commits_terminal_at_max_turns_exit_with_pending_steer`，在 `tests/unit/test_agent_loop.py` 新增 `test_loop_commits_terminal_at_abort_exit_with_pending_steer`：使用 `_SteerThenAbortClient`（在 steer enqueue 后触发 abort_event），断言 steer 被拒/fallback 新 run。

---

## V3：`rolling` 守卫不产生误拦

**核对 code-review 疑点：`_close_old_and_restart` 与 `_roll_bubble_on_steer` 是否因共享 rolling 标志而互斥？**

observer（`main.py:1131`）被 **串行 await**（`obs_result = observer(event); if asyncio.iscoroutine(obs_result): await obs_result`）——同一 SSE 事件流中相邻两个事件顺序处理，不并发。因此：

- `injection_consumed` 事件触发 `_roll_bubble_on_steer()` → await → `_roll_bubble` 全程完成（rolling 在 finally 清除）→ 下一个事件才处理。
- `assistant_message` 事件触发 `_close_old_and_restart()` → await → `_roll_bubble`（此时 rolling 已清，正常执行）。

两条路径不存在真并发（均通过 `return coroutine + await obs_result` 串行化），`rolling` 守卫在此场景下只起防御作用，实际不会触发。

**真并发场景（`loop.create_task`）**：检查了代码，`_close_old_and_restart` 和 `_roll_bubble_on_steer` 均无 `loop.create_task` 包裹。rolling 守卫保护的是未来可能出现的并发调用（防御性设计）。

**结论：rolling 守卫无误拦风险，代码正确。**

---

## V2：`_roll_bubble` 行为保真

**`delivery_status` 字段**

旧内联 `_close_old_and_restart` 的 message_completed 帧**无 `delivery_status`**；新 `_roll_bubble` 有 `delivery_status: "completed"`。这是 V2 引入的差异。

影响评估：前端 `chat-stream-reducer.ts:140` 处理 `message.completed` 时直接硬编码 `delivery_status: "completed"`，不读事件载荷的 `delivery_status` 字段。新增字段对前端无影响，属于帧内容更完整（改进）。

**空 message_id 行为（V3 gate 变化）**

旧 injection_consumed 守卫：`if conversation_id and agent_id and message_id:` → 空 message_id 时 return，不发任何帧，steer 回复无气泡。

新守卫：`if conversation_id and agent_id:` → 空 message_id 时跳过 message_completed（`_roll_bubble` 里 `if old_message_id:` 守卫），但仍发 turn_start 开 bubble B，steer 回复有去处。

`test_injection_consumed_opens_b_even_when_message_id_empty` 直接覆盖此路径，断言发出 `["turn_start"]`（非空列表）。

**ack message_id 提取**

新 `_extract_ack_message_id()` 处理两种 ack 格式：`{"payload": {"message_id": ...}}` 和 `{"message_id": ...}`。旧路径各处各自手写 `.get("payload") / .get("message_id")`，现在统一。逻辑等价，覆盖更全。

---

## abort × /stop held-buffer 语义无回归

abort 出口（`is_aborted` 分支）只在 **cooperative abort**（`abort_event.is_set()` 被检测到）时触发，这对应用户主动 /stop 路径。

时序：`interrupt()`（registry.py）→ 同步 drain pending → held_pending → 设 abort_event → loop 下轮检测到 is_aborted → `drain_pending()` 此时取空 → `commit_terminal()`。

`commit_terminal()` 在 `interrupt()` 的 drain 已经完成之后调用，held_pending 已 populated。commit_terminal 只阻止未来的 `enqueue_message`，不影响已在 held_pending 的消息。/stop 的 held-buffer 语义无回归。

**CancelledError（force-cancel）路径**：`CancelledError` 是 `BaseException`，不经过 loop 的 `except Exception` 块及 `is_aborted` 出口，直接 unwind，由 registry 的 `_run_worker_async.finally` 进入 `_settle_terminal_pending`。此路径 controller pending 未被 loop drain，`_settle_terminal_pending` 正常续跑。不受 V1 影响。

---

## M1-M3 无回归

全 not-e2e 树（commit 60e4a3da）：**2810 passed, 0 failed, 1 skipped**（Round 2 为 2804，增量 6 = 新增 6 个测试）。所有 M1-M3 路径测试通过，无回归。

---

## Issues（Round 3）

### CRITICAL

无。

### WARNING

**W4（Round 3 新）：abort 出口缺专项 loop 级 commit_terminal 测试**

`loop.py:~286` abort 分支调用 `commit_terminal()`，但 max_turns 和 tool_unavailable 各有一个专项 loop 级测试，abort 出口没有。测试不对称，代码正确性依赖代码审查和间接覆盖。

修复：在 `tests/unit/test_agent_loop.py` 新增 `test_loop_commits_terminal_at_abort_exit_with_pending_steer`，参照已有 max_turns 测试模式，验证 abort 出口后 steer 被拒/fallback。

### SUGGESTION

Round 1/2 的 S1/S2/S3 建议不变，本轮无新增 SUGGESTION。

---

No critical issues. 1 warning to consider (W4: abort exit test gap). Ready for PR (with noted improvements).
