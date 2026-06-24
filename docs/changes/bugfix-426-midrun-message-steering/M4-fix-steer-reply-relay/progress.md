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

## R4 — 决策6 气泡滚动 + #140 e2e
