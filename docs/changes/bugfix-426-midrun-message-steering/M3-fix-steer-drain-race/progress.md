<!--
模板说明（定稿后删除本块）

每个 roadpoint 完成后实时追加。一个 roadpoint 一段。
重点记"为什么这么决定"和"凭什么相信改对了"，不重复代码本身。

【硬约束：Pause-on-design-issue】
实现期发现 design 偏差时，禁止悄悄绕过。worker 必须：
1. 立即暂停编码
2. 在本文加一段 [Design 修订] R<n>: X → Y（现状 / 新方案 / 原因）
3. 同步改 ../../design.md 正文；若影响后续 milestone，再追加 design.md 顶部 Changelog
4. 通知人/orchestrator 确认后再继续

phase-locked 不重要，知识同步重要。
-->

# <milestone_id> — Progress

## R1 — steer drain 串行化 + 并发回归单测

- Context: code-review round 1 confirmed correctness bug。`inbound_pipeline.py` 的
  mid-run steer 快路径中，group buffer drain 未串行化：`process` 约 261-262 的
  `_active_runs_lock` 只包廉价的 `has_active_run` 判定即释放；之后 `_try_steer_active_run`
  在锁外执行，其 `_ensure_binding`（await，yield 点）+ `_build_message_parts`→
  `GroupContextStore.drain`（destructive，read-then-delete 全部）不互斥。同 session 两个
  `handle_inbound` 协程都过 has_active_run、都进 steer、在 `_ensure_binding` 的 await 处交错
  调度 → 协程 A drain 走全部 buffered 群聊上下文、协程 B drain 得空，一条 steer 丢失缓冲上下文，
  违反 gateway spec「群聊运行中 steer 保留发言人与缓冲上下文」不变量。正常路径的 drain 在
  `_run_turn` 内、被 `SessionRunQueue` 按 session_key 串行；steer 快路径绕过了该串行化。
- Decision: 在 `InboundPipeline` 引入 per-session drain 锁 `_session_drain_locks`
  （lazily 创建，复用既有 `_active_runs` / `asyncio.Lock` 模式，不另造并发原语）。
  - steer 决策段：把「has_active_run 判定 + `_try_steer_active_run`（含 `_ensure_binding`
    + `_build_message_parts` drain + 原子 `kernel.submit(steer=True)`）」整段纳入
    `async with self._drain_lock_for(session_key)`。fallback（injected=False）的
    `_run_queue.submit` 放在锁**外**——它带 `prebuilt_parts` 不再 drain，且 `_run_turn`
    会重入同一把锁，留在锁内会自死锁。
  - normal 路径：`_run_turn` 的 `_build_message_parts` drain 调用（仅 prebuilt_parts is None
    时）也纳入同一把 `_drain_lock_for(session_key)`。这样 steer-vs-steer、steer-vs-normal
    都互斥；normal-vs-normal 本就被 run_queue 串行。
- Rationale: 不能把整个 steer 决策塞进 `_run_queue`——那会排到活跃 run 之后，丧失 steer
  「注入当前 run」的本意。per-session 锁只串行「廉价的 gate + 一次性 drain 决策」，活跃 run 仍
  正常收到注入的 steer。无死锁：steer 锁内只调 sync 非阻塞的 `kernel.submit`，不 await
  run_queue；normal 路径在 run_queue 串行域内持 drain 锁，不构成循环等待。
- Evidence:
  - Tests: `pytest tests/unit/personal_assistant/test_inbound_pipeline_kernel_sdk.py`
    7 passed（原 6 + 新增 1）。新增并发回归
    `test_concurrent_group_steer_drain_is_serial_not_interleaved`：插桩 `_build_message_parts`
    （drain 记录点）+ `_ensure_binding`（注入 `await asyncio.sleep(0)` 复现真实 await yield
    窗口），断言事件序中两个 bind 之间必有 drain（即每个协程 bind+drain 相邻、串行）。
    修前红：`['bind:A', 'bind:B', 'drain:A', 'drain:B']`（两 bind 相邻、drain 交错瓜分）；
    修后绿：`['bind:A', 'drain:A', 'bind:B', 'drain:B']`（严格串行）。修前红经 `git stash`
    实现实测确认。
  - Entry: gateway 后端并发缺陷，真实入口 = 进程内 InboundPipeline 并发 `handle_inbound`。
    回归测试用真实 `InboundPipeline` + `SessionRunQueue` + `GroupContextStore`（真 SQLite
    drain），仅 stub `Kernel`（FakeKernel）——drain 串行语义全在真实 gateway 代码里跑通，
    非 mock 断言。
  - Frontend State Matrix: N/A（纯 gateway 后端并发修复）。
  - Browser QA: N/A（无 UI 变更）。
  - E2E/Regression: 回归用例
    `tests/unit/personal_assistant/test_inbound_pipeline_kernel_sdk.py::test_concurrent_group_steer_drain_is_serial_not_interleaved`，
    `pytest <该用例>` 修后绿、`git stash` 实现后红。永久保留。
  - Visual/Interaction: N/A。
- Rollback: 单 commit `git revert`（C2 实现 commit）即回到 stash 前竞态态。
- Commits: C1=ee90b399, C2=82b5155f, C3=<本提交>

## [评估] kernel.py `_try_inject_active_run` 三步非原子窄竞态（不修，建议 follow-up issue）

- 派发包要求评估的 PLAUSIBLE：`src/agent/sdk/kernel.py:889-930` `_try_inject_active_run`
  三步 `get_active_run_id` → `inject_pending_message` → `get(active_run_id)` 非原子。
  inject 持锁成功（`registry.py:564-570` 锁内查 `controller.is_aborted` 后 enqueue）返回 True
  后，若 run 在 `get(active_run_id)` 前转 terminal，`_settle_terminal_pending`（决策3 backstop）
  把 pending 移到续跑 run，而 `get(active_run_id)` 仍返回旧 terminal run record（`_runs` 永不删），
  返回 `injected=True` + 旧 terminal run_id → gateway steer 路径监听错事件流（非双执行）。
- 结论：**不廉价，不一并修**。
  - 不能「inject 后复检 run 仍活跃则返回 None」：inject 已成功（消息已入 pending 队列），返回 None
    会让 caller 走 fallback 新 run → 消息**双执行**，比现状更糟。
  - 返回「真正执行该消息的 run_id」需查 `_settle_terminal_pending` 续跑的新 run_id，而该续跑由
    异步 backstop 创建，`_try_inject_active_run` 同步拿不到 → 跨 inject/settle 协调，非廉价。
  - 影响有界：reviewer 实跑未触发；非双执行；`_runs` 永不删故不降级，仅该条 steer 的 reply 可能
    不在原 SSE 流冒出（消息仍正确执行）。
- 建议：orchestrator 据此立 follow-up issue（kernel 层 inject-or-settle 原子化），不在本 fix 范围。
