# bugfix-426-M4 — Progress

> #140 修复：决策5（同 run 续轮，消除 continuation 新 run_id）+ 决策6（消费点滚动气泡）+ 决策3 收窄。

## 启动澄清

- 派发包指向 design.md 的 M4 行 + 决策5/6，但主仓 cwd 的 design.md 是旧版（只有 M1/M2）；
  权威版本在 unit/bugfix-426 分支（commit de317913 `docs(bugfix-426/M4): 新增 #140 修复方案`）。
  M4 worktree 从 origin/unit/bugfix-426 创建，读到完整 M4 决策 + delta-spec。无需问 leader。
- venv：worktree 无法 editable install（pyproject 非 setuptools editable）；用 main 仓 .venv 的 pytest +
  `PYTHONPATH=src` 跑，已确认 `agent` import 解析到 worktree src。

## R1 — 决策5：loop 末轮 re-drain 续同一 run + commit_terminal 原子化

- Context: #140 根因 = steer 落在 loop 末轮已决定退出（drain 不再执行）的窗口 → stranded →
  registry `_settle_terminal_pending` 起 continuation 新 run_id → relay 锚旧 run_id 丢全部事件。
  根因在「终止决策」与「inject 入队」之间没有原子性。
- Decision:
  - `RunController` 加 `_terminal_lock` + `_terminal_committed`；`try_commit_terminal()` 持锁 re-drain：
    非空→返回待消费消息且**不** commit（run 续活）；空→set committed 返回 []。`enqueue_message` 改返
    bool：持同锁，已 commit→False 不入队。
  - `loop.py` 终止决策处（原 `if not iteration_tool_calls` 直接 break）：先 `try_commit_terminal()`，
    非空则 append 进 llm_messages + `continue`（续跑同一 run，run_id 不分裂）；空才 break。
  - 决策6 钩子：loop 在 round-start drain 与终止 re-drain 两个**消费点**都发
    `pending_injection_consumed` observe 事件（带 run_id）。realtime_stream 转发 + 事件类型注册留 R3。
  - `registry.inject_pending_message` 透传 `enqueue_message` 的 bool（lost-race→False→Gateway fallback 新 run）。
- Rationale: 在 loop 终止决策处原子「还有 pending 就再跑一轮」从源头消除 continuation 新 run_id
  （= CC 单 queryLoop「轮边界检查队列、非空继续」的等价，但保留 run_id 给多 run 源 demux）。锁让
  inject vs commit 无第三态：要么 inject 赢（续同 run），要么 commit 赢（inject=False、Gateway 开新 run + 新气泡）。
- Evidence:
  - Tests: `tests/unit/agent/runs/test_run_control_terminal_commit.py`（4 例：非空不 commit / 空 commit /
    commit 后 enqueue=False / 200 轮并发 inject-vs-commit 不变式）+ `test_agent_loop.py::test_loop_redrains_at_terminal_and_continues_same_run`（终态前 inject → 2 round 同 run 续跑、终态 answer-to-steer）。
    全绿；广测 118 passed（loop/runs/registry/runtime/cancel/contract）+ background_tasks 88 passed（enqueue 签名改动无回归）。
  - Entry: N/A（R1 内核纯逻辑；真端到端 #140 旅程在 R4 e2e + reviewer 轨）。
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: 决策5 续同 run 的端到端验证延到 R4（需 gateway 气泡滚动一起才有用户可见结果）。
  - Visual/Interaction: N/A
- Rollback: `git revert` R1 C2 回排队/stranded-continuation 旧行为；纯加法，无数据迁移。
- Commits: C1=红测, C2=决策5 实现, C3=本次 docs。

## R2 — 决策3 收窄：continuation 仅兜异常终止  [DONE]

- Context: 决策3 收窄要求「正常完成不再产生 continuation」。
- Decision/Rationale: 收窄是决策5 的**自然结果**，非新代码分支——正常完成时 loop 的终止 re-drain
  已消费 steer（同 run 续轮）或 inject 被拒（never enqueue），到 `_settle_terminal_pending` 时
  controller 队列必空 → 自然 no-op；该 chokepoint 仅在异常终止（loop 未达终止决策即被 cancel/timeout/crash
  unwind）才有 stranded 可续。故 `_settle_terminal_pending` **无须改**。
- Evidence:
  - Tests: 新增 kernel contract `test_terminal_window_steer_continues_same_run_no_continuation`——
    真 kernel+loop，终态窗口 inject → 同 run 续轮（2 个 LLM round、steer 进第二轮上下文）、injected=True、
    `runs_after == runs_before`（无 continuation 新 run_id）。这是 #140 的内核级端到端回归证据。30 passed。
  - 旧测试审计：`test_stranded_continuation_follows_injected_origin` docstring 厘清为 registry-isolation
    测 chokepoint origin 机制（stub runtime 是到达机制的载体），正常完成不再走此路径；异常路径由
    `test_stranded_continuation_fires_on_non_user_cancel` 在真实 strand 路径覆盖。
  - Entry / Browser / E2E / Visual: N/A（同 R1，真旅程在 R4）。
- Rollback: revert R2 commit（test-only）。
- Commits: 单 commit（§FL ② 轻量化：自包含 verify+审计，无独立实现 commit）。

## R3 — 决策6 信号：消费点发 pending_injection_consumed → injection_consumed  [DONE]

- Context: 决策6 需要 kernel 在「真正消费注入消息」的轮边界发信号，relay 据此滚动气泡。
  R1 已让 loop 在两个消费点（mid-loop drain + 末轮 re-drain）发 `pending_injection_consumed` observe 事件，
  但该事件未注册（dispatch fail-open 警告）、realtime_stream 未转发到 kernel.stream。
- Decision:
  - `HookEventType` 加 `PENDING_INJECTION_CONSUMED`（自动进 OBSERVE_EVENTS / ALL_HOOK_EVENTS）。
  - `realtime_stream.setup` 注册 `on_pending_injection_consumed` → `publish_session_event("injection_consumed", {run_id, turn_id})`。
    无 run_id 则跳过（无从 scope 气泡）。命名 kernel 内部事件 `pending_injection_consumed`、
    对外 session 事件 `injection_consumed`（与既有 turn_end/assistant_message 同款 observe→session 转发模式）。
- Rationale: 复用既有 realtime_stream「observe 事件 → session 事件」转发机制（turn_end 同款），
  零新基础设施；gateway observer 经 kernel.stream 收 `injection_consumed`（R4 消费）。
- Evidence:
  - Tests: `test_realtime_stream_events.py`（2 例：转发带 run_id / 无 run_id 跳过）+
    `test_agent_loop.py::test_loop_emits_injection_consumed_signal_at_consume_point`（loop 消费点发 1 次、带 run_id）。
    11 passed（含 contract #140 回归，不再有 unknown-hook-event 警告）；
    hook 覆盖测试 `test_hook_event_coverage`/`test_hooks_contract` 4 passed（新枚举无破坏）。
  - Entry/Browser/E2E/Visual: N/A（信号到 session 流即止；用户可见气泡滚动在 R4）。
- Rollback: revert R3 C2（枚举 + handler）；loop 仍发事件但 fail-open 无副作用。
- Commits: C1 红测, C2 实现, C3 docs（含 C1 测试 1 行 format 折叠）。

## R4 — 决策6 气泡滚动 + #140 e2e  [DONE]

- Context: 决策6 让 gateway observer 在收到 injection_consumed 时收尾旧气泡 A（完成态）+ 开新气泡 B
  （排在 steer 之后），后续事件流入 B。并新增 #140 真端到端复现。
- Decision:
  - `main.py` observer 加 `injection_consumed` 分支：message_completed(A,completed) + turn_start(B,await ack)
    + 切 run_context_store[run_id].message_id 到 B + 清 kernel_message_id（复用 _close_old_and_restart 同款序列，
    锚在 kernel 明确消费信号而非推断 kernel_message_id 变化）。
  - **live e2e 暴露 #140 根因（决策5/6 接通后仍残留）**：steer 注入活跃 run 后，`_try_steer_active_run`
    发 `phase=accepted` lifecycle 带**同一** run_id；lifecycle 回调无条件 `run_context_store[run_id] = {message_id:""}`
    把气泡 A 的 message_id 抹空 → observer 后续所有事件 message_id 为空 → 无法收尾 A → A 卡 running →
    120s relay-idle watchdog 判 `relay.failed`（#140 黑屏残留）。**修**：accepted 仅 seed 全新 run（run_id 不在 store），
    绝不 clobber 正在流式的活跃 run 上下文。
- Rationale: observer 单线程读共享 ctx.message_id，气泡创建走异步 task；accepted re-seed 是为新 run 设计、
  对注入 steer（复用 run_id）是破坏性的。根因在「注入 steer 不该重置 run 的 IM 气泡上下文」这一层治本，
  非在 observer 端贴补丁绕过空 message_id。
- Evidence:
  - Tests:
    - `test_steer_bubble_roll.py`（observer injection_consumed 收尾 A completed + 开 B + 切 message_id；无气泡跳过）
    - `test_steer_reply_relay_regression.py`（真 InboundPipeline relay + 真 observer + 脚本化 kernel 流：同 run_id
      post-steer 事件不丢、A completed、steer 工具卡落 B 非 A；修前红[去 observer 分支]修后绿）
    - `test_inbound_pipeline_streaming.py::...preserves_existing_run_context_for_injected_steer`（#140 根因红测：
      accepted 对已存在 run_context 保留 message_id；修前红修后绿）
    - 全 not-e2e 树通过（见末尾）。
  - Entry（真端到端 live，DONE 硬证据）: scripts/e2e-up.sh 隔离栈（ephemeral IM:62963+，真 Gateway 进程，真 LLM K2.6）。
    驱动 docs/changes/.../verification 记录的 #140 旅程（发长工具链消息→收尾窗口 steer）。
    **修前**（去 accepted 守卫）：气泡 A `relay.failed: relay idle for 120s`，B completed（A 黑屏卡死）。
    **修后**（两次不同 steer 时点 8s/12s）：A、B **双 completed**，无 `relay.failed`，
    steer 回复落新气泡 B 排在 steer 消息之后、A 的 in-flight 4 工具留在 A、A 干净收尾。
    事件账：`message.completed:2`、`relay.failed:0`。证据日志：scratchpad/e2e_run*.log。
  - Browser QA: N/A（无前端代码改动；气泡 A/B 行为由 gateway→IM 协议帧驱动，前端复用既有 message_completed/turn_start/delta 渲染）。
  - E2E/Regression: 上述 3 个 regression 测试 + live 真栈复现（修前红修后绿，跨 8s/12s 两个 steer 时点稳定）。
  - Visual/Interaction: N/A（reviewer 轨可在真 IM 浏览器观察气泡时序作补充视觉证据）。
- Rollback: revert R4 fix commit（accepted 守卫）退回 #140 残留；revert R4 feat（observer 分支）退回无气泡滚动。
- Commits: C1 红测（test_steer_bubble_roll）, C2 observer 分支, R4 #140 regression 测试, R4 根因 fix（accepted 守卫）, C3 docs。
- 全 not-e2e 树：2803 passed, 2 skipped（R1-R4 无回归；较 R3 基线 +4 = 本 milestone 新增测试）。

## Fix 轮（reviewer/verifier/code-review 反馈，off origin/unit 941fb6ca）

三闸验收后 code-review 逮到一条 confirmed correctness（V1）+ verifier/cleanup（V2/V3/W2/W3/S1）。

### V1（必修 correctness）— 决策5 终态提交覆盖全部终止出口
- Context: 决策5 原只在『正常完成』出口（`if not iteration_tool_calls`）调 `try_commit_terminal()`。
  另两条硬停出口 `max_turns_reached`(loop top `return`)、`tool_registry_unavailable`(`break`) **绕过**它 →
  `_terminal_committed` 永不 set → steer 落这些窗仍被 enqueue 接受、但 loop 已退出不消费 → stranded →
  `_settle_terminal_pending` continuation 新 run_id → relay 锚旧 run_id 丢事件（#140 在这两路径原样复现）。
  3 个 code-review finder（角度 A/B/C）独立命中。abort 出口 finder 自查碰巧安全（inject 也查 is_aborted），但不该靠隐式互斥。
- Decision（架构正确位置，非两处各补一行）: `RunController` 加 `commit_terminal()`——硬停**无条件** commit（区别于
  `try_commit_terminal` 的 re-drain-or-commit）。所有硬停出口（max_turns / tool_unavailable / abort）调它，使
  任何终止出口后到达的 inject 一律返 False → 调用方 fallback **干净新 run**（injected=False，relay 正常锚），绝不 continuation。
  语义：硬停=run 真结束、steer 是新请求开新 run（非 #140 的同 run 收尾窗错误分裂）；commit 前已入队的极窄竞态 steer
  仍由 registry chokepoint 兜（与决策3 收窄一致）。为何硬停不能套「续同 run」：max_turns 续跑会回 loop top 在调 LLM 前 return、
  steer 进 llm_messages 却永不发模型 → 真丢；tool_unavailable 无 registry 续跑无意义。（语义方向已与 leader 对齐采 (A) commit-then-fallback。）
- Evidence:
  - Tests: `test_run_control_terminal_commit.py`（+commit_terminal 硬停拒后续 inject / 幂等）+
    `test_agent_loop.py`（steer 落 max_turns 窗 / tool_unavailable 窗 → `is_terminal_committed=True`、后续 enqueue 返 False）。
    确定性单测，修前红（去 3 处 commit_terminal 调用→terminal 不提交）修后绿。
  - Entry: N/A（这两条出口 live 难触发：max_turns run 参数主路径恒 None、仅 fork 用；tool_unavailable 罕见。leader 确认确定性单测即可）。
  - 全 not-e2e 树 2809 passed 2 skipped（较前轮 +6 = V1/V3 新测试）。

### V2（cleanup）— roll_bubble 原语 + ack helper
- 抽 `_roll_bubble()`（message_completed→turn_start→ack→repoint run_context_store）+ `_extract_ack_message_id()`，
  `_close_old_and_restart` / `_roll_bubble_on_steer` / `_turn_start_then_delta` 三处复用，消 ~25 行平行重复 + 3 处 ack 双 isinstance 拷贝。
  IM 改 turn_start ack 格式只需改一处。

### V3（守卫，折进 V2 原语）
- ① 重入：`_roll_bubble` 加 per-run `rolling` 守卫——连发两 steer（两个 injection_consumed）安全（A 只 completed 一次、不建两 B、无僵尸 running）。
- ② 空 message_id 窄窗（turn_start ack 未回）：injection_consumed 不再 gate message_id，仍开 B（无 A 可关时只 turn_start），steer 回复不丢气泡。
- Tests: `test_steer_bubble_roll.py` 加 3 例（空 msgid 开 B / 连发两 steer 各自干净滚 / 并发重入守卫丢重复）。

### 杂项
- W2: tasks.md 7 条退出标准 `- [ ]`→`- [x]` + 补 V1 行。W3: tasks.md 测试策略补 #140 落 unit 层 + live 证据落 progress 的落层说明。
- S1: registry `_settle_terminal_pending` 的 `is_user_interrupt` 分支补注释（held-pending vs 续跑分流 + interrupt 同步 drain 后此为兜底）。
- 不归本轮：delta-spec 归并长青契约层（W1/S3，leader 收尾）；CLI 双订阅债（S2=out-of-unit #139）。
