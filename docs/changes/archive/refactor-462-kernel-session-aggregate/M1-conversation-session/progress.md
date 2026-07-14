# refactor-462-M1 — Progress

## Baseline

- Context: M1 是一次性 session ownership cutover；必须先证明 main 基线稳定，避免把既有失败误归因到重构。
- Decision: 使用仓库共享 `.venv` 跑完整非 e2e 测试与 ruff 格式门禁。
- Rationale: 与项目 CI 的 Python job 一致，同时避免新建环境造成依赖漂移。
- Evidence:
  - Tests: `PATH=/Users/czj/Repos/nano-multiagent/.venv/bin:$PATH /Users/czj/Repos/nano-multiagent/.venv/bin/python -m pytest -m 'not e2e'` → `3496 passed, 1 skipped, 23 deselected`。
  - Entry: N/A（实现前基线）。
  - Frontend State Matrix: N/A。
  - Browser QA: N/A。
  - E2E/Regression: N/A（实现前基线）。
  - Visual/Interaction: N/A。
  - Prototype Comparison: N/A。
- Rollback: N/A（尚未修改产品代码）。
- Commits: plan commit 待提交。
- Next: R1 C1 为 Transcript/Directory/Prompt seed/lifecycle 写最终 interface 红测。

## R1 — Transcript、Directory 与核心 session 数据模型

- Status: DONE
- Context: 旧 JSONL store 同时拥有 raw I/O 与会话语义，Runtime 又另存 tail/history/context maps；PromptSlots 只在进程内保存，重启后无法重建。
- Decision: 引入绑定 `SessionRef` 的 private `JsonlTranscript`、raw `JsonlSessionFiles`、stable-identity `SessionDirectory` 与 core-owned request/seed/context types；writer 收窄为 raw enqueue + durability barrier，旧入口暂留到 R4 cutover。
- Rationale: tail、repair、materialize、idempotency 与持久化 prompt seed 只有一个 per-conversation owner；Directory 的短 guard 只负责 identity intern，不承载 I/O 或事务。
- Evidence:
  - Tests: `python -m pytest -q tests/unit/agent/session/test_jsonl_transcript.py tests/unit/agent/session/test_session_directory.py tests/unit/test_session_file_state.py tests/unit/test_agents_md_runtime_snapshot.py` → `28 passed`。
  - Entry: `JsonlTranscript.create/load/append_external/prepare_for_run` 与 `SessionDirectory.create/open/get/find_by_metadata/close_all` 的真实 temp-dir 测试。
  - Frontend State Matrix: N/A（纯内核重构）。
  - Browser QA: N/A（纯内核重构）。
  - E2E/Regression: baseline 非 e2e 套件已通过；最终真实入口签收在 R4。
  - Visual/Interaction: N/A。
  - Prototype Comparison: N/A。
- Rollback: 回退 `15c9ee5e` 及其 C1 `01ee0172`；旧 manager/store/runtime 路径在 R4 前仍可工作。
- Commits: `01ee0172`（C1），`15c9ee5e`（C2）。
- Next: R2 以 `ConversationSession` interface 红测锁定 lifecycle permit、active external append、compact stale commit 与 fork snapshot。

## R2 — ConversationSession 接管 turn/compact/fork transaction

- Status: DONE
- Context: 旧 `AgentRuntime` 以多张 session-id map 同时管理 history/config/path/lock/file/memory/prompt/model，turn、append、compact 与 fork 分别操作不同 owner。
- Decision: 将 runtime 收敛为无 session live-state 的 `AgentEngine`，每个 `ConversationSession` 持有稳定 state、private Transcript、单 turn gate 与统一 lifecycle permit；AgentLoop 的 prompt-token 状态改成 per-conversation scalar，compact/fork 经 session 高层事务。
- Rationale: async turn/compact/fork 和同步 append 共用 admission，只有短 Transcript mutex 保护 JSONL mutation；close 能线性化拒绝新操作并 drain 已接纳 worker，带外 append 不需要失效全局 cache。
- Evidence:
  - Tests: `python -m pytest -q tests/unit/agent/session/test_conversation_session.py tests/unit/agent/session/test_jsonl_transcript.py tests/unit/agent/session/test_session_directory.py tests/unit/test_session_file_state.py` → `27 passed`。
  - Entry: 真实 `AgentEngine + ConversationSession + JsonlTranscript` 两轮 replay；active turn 并发 durable append；close drain；as-of fork re-stamp/PromptSlotSeed；stale external epoch 拒绝 compaction commit。
  - Frontend State Matrix: N/A（纯内核重构）。
  - Browser QA: N/A（纯内核重构）。
  - E2E/Regression: SDK composition 尚待 R4 切换；最终从 CLI/Gateway 入口签收。
  - Visual/Interaction: N/A。
  - Prototype Comparison: N/A。
- Rollback: 回退 `8072fd47` 与红测 `67da031d` 可恢复旧 multi-session runtime；R4 前 unit 分支不作为可运行交付。
- Commits: `67da031d`（C1），`8072fd47`（C2）。
- Next: R3 将 owner loop/task/token/cleanup 从 RunsRegistry 与 RuntimeRunner 收进 typed KernelExecutor，并把 `/stop` park 与 cleanup ack 分域。

## R3 — KernelExecutor、RunsRegistry 与 subagent 控制面

- Status: DONE
- Context: 旧 RunsRegistry 同时持 event loop、Task 与 RunRecord，RuntimeRunner 暴露 loop getter/bare coroutine；cancel 的 public terminal 与 carrier cleanup 混在同一状态域。
- Decision: 新建 typed `KernelExecutor`，以 `TargetToken` 统一 top-level/auxiliary/lifecycle carrier ownership；RunsRegistry 只写 RunRecord/controller/held pending，并通过 completion sink 完成 bind-before-schedule 与 cleanup ack；subagent runner 改成 typed auxiliary API。
- Rationale: Executor 不发布 RunStatus，Registry 不接触 Task/loop；cancel 可同步写 CANCELLED 后异步清理 target，同一 session 的后续 run 由 ConversationSession permit/gate 等待旧事务退出。
- Evidence:
  - Tests: `python -m pytest -xvs tests/unit/agent/runs/test_kernel_executor.py tests/unit/agent/runs/test_runs_registry_executor.py` → `5 passed`。
  - Entry: top-level bind→start 顺序、blocked target cancel→cleanup ack→同 executor resubmit、auxiliary shutdown、late admission reject、Registry completion、model threading、`interrupt()` 返回前 held-pending park。
  - Frontend State Matrix: N/A（执行控制面重构）。
  - Browser QA: N/A（执行控制面重构）。
  - E2E/Regression: AgentTool 已不再向 runner 传 bare coroutine；完整 subagent 真入口在 R4 签收。
  - Visual/Interaction: N/A。
  - Prototype Comparison: N/A。
- Rollback: 回退 `6dfc0f9f` 与红测 `3a87ff73` 可恢复 Registry-owned loop；R4 前 unit 分支不作为可运行交付。
- Commits: `3a87ff73`（C1），`6dfc0f9f`（C2）。
- Next: R4 切换 build_kernel/Kernel/AgentTool 到 Directory+Executor，删除 manager/service/store/旧测试 seam，跑全量与真实入口。

## R4 — SDK composition cutover、旧 seam 删除与真实入口签收

- Status: DONE
- Context: SDK、Gateway、CLI、AgentTool 与后台任务仍经旧 manager/runtime seam 装配；最终切换还必须证明 interrupt recovery、字符串 workspace binding、重启与 fork 在真 Gateway 进程中保持兼容。
- Decision: `build_kernel` 最终装配 `SessionDirectory + ConversationSession × N + AgentEngine + KernelExecutor + RunsRegistry`；删除 SessionManager/SessionService/高层 JsonlSessionStore 与 session file adapter，SDK 的 create/get/append/compact/fork/close 直接经最终 aggregate；foreground interrupt 对 carrier 使用强制取消，普通 cancel/auxiliary 保留 cooperative grace；所有 SDK 会话入口将 `str | Path` workspace binding 归一化成绝对 `Path`。
- Rationale: 真栈第一次 interrupt 验收显示 100ms cooperative grace 会让已收到 SIGTERM 的 Bash 正常返回“interrupted”工具结果，因而不会写 orphan recovery；强制 interrupt 必须绕过 grace。第二次 Gateway 验收显示 inbound pipeline 传入字符串 workspace root，而新 SDK 直接调用 `.expanduser()`；统一在 SDK 边界归一化可保持既有消费者契约且覆盖全部同源入口。
- Evidence:
  - Tests: `pytest -q` 覆盖最终接口/SDK/Gateway/后台任务的窄测 → `62 passed`；`pytest -m 'not e2e'` → `3305 passed, 1 skipped, 20 deselected`（143.05s）。
  - Entry: 真实 `build_kernel` 两轮、同步 append、compact/fork、interrupt recovery、string workspace binding；architecture contract 证明 production 无 `SessionManager` / `SessionService` / `JsonlSessionStore` / `AgentRuntime` 及旧 writer/store 穿透。
  - Frontend State Matrix: N/A（无前端状态或 UI 改动）。
  - Browser QA: N/A（产品验收走 IM HTTP/WebSocket + 真 Gateway 进程，不涉及视觉变更）。
  - E2E/Regression: `PATH=/Users/czj/Repos/nano-multiagent/.venv/bin:$PATH ./scripts/e2e-critical.sh -q -m 'not slow' -k '<selected>'` 在隔离端口/config 的真 IM + Gateway + LLM 栈通过工具调用回复、foreground subagent、subagent failure isolation、`/stop`、Gateway restart continuity、message fork → `6 passed, 11 deselected`（104.69s）；`tests/integration/test_foreground_interrupt_reap.py` 单独证明 interrupt 后 recovery 闭合。
  - Visual/Interaction: N/A。
  - Prototype Comparison: N/A。
  - Quality: `ruff check src tests` → all checks passed；`ruff format --check src tests` → `742 files already formatted`；`git diff --check` 通过。
- Rollback: 回退 R4 的 composition/contract/normalization commits 可恢复旧装配，但不能只回退 manager 文件删除的一部分；R1-R3 与 R4 是一次性 cutover，需整体回退 milestone。
- Commits: `1c9a32bf`（C1 contract），`c50f9293`（C2 cutover），`bf984c91`（format），`613467b7`（string binding 红测），`691c2294`（binding fix）；本节 C3 文档提交待生成。
- Next: 合并 milestone 到 unit 集成分支，派发独立 verifier、产品 reviewer 与 code review 三道验收闸。

## Unit gate closure

- Status: DONE
- Context: milestone 合入后，独立 verifier、产品验收与代码审查先后暴露 active append reconciliation、compaction window、interrupt terminal、writer/client shutdown、cold-load publication 与 hook event publication 的边界问题；Round 2 还保留了最终接口永久回归矩阵缺口。
- Decision: 所有 implementation fix 由 orchestrator 亲自按 impl-worker 的 C1/C2/C3 纪律完成；每轮先提交可复现测试，再修实现并复验。Verifier、产品 reviewer 与两路 code review 均由独立 agent 执行，旧 PASS 在后续 blocker 出现后不继承。
- Rationale: `interrupt()` 的用户可见终态、assistant event 发布、JSONL durable history 与资源清理是不同线性化边界；分别以确定性排队 probe、失败注入与 final-interface 行为测试守住，避免依赖时序运气。测试矩阵按合约原子行为收口，不扩张成未约定的笛卡尔组合。
- Evidence:
  - Fix rounds: fix-r1 修复 string workspace、active append residual、manual compaction refresh、bounded ownership、interrupt/client lifecycle；fix-r2 修复 fast-provider interrupt、writer close、partial state、cold raw read/header-only；fix-r3 修复 hook-await late persistence、cleanup failure drain 与 cold-load publish race；fix-r4 将 assistant 发布与 `/stop` 放入同一短锁线性化边界；fix-r5 补齐 overflow/restart、whole fork、PromptSlots/legacy、memory/file window、late tool/recovery 永久回归。
  - Full Python: `pytest -m 'not e2e' -n 4 --dist worksteal` → `3336 passed, 1 skipped`（fix-r5 final shape）。
  - Targeted verification Round 5: 新场景 `8 passed`、受影响回归 `82 passed`、queued-wakeup stress `20/20 passed`；0 CRITICAL / 0 WARNING / 0 SUGGESTION。
  - Product acceptance Round 2: CLI resume、Gateway restart、cold/active append、manual compact + restart、PromptSlots restart、as-of fork、string workspace 与真 IM/Gateway `/stop` 全部通过；`/stop` 后 8 秒无 late assistant，下一轮 3.245 秒完成。
  - Code review closure: finalizer failure、cold-load epoch、hook wakeup-before-cancel 与历史 WARNING-2 全部关闭；legacy fallback mutation probe 输出 `MUTATION_KILLED`。
  - Quality: `ruff check .`、`ruff format --check .`、test naming/size contract、`git diff --check` 全绿。
  - Frontend State Matrix / Browser QA / Visual / Prototype: N/A（无前端产品代码变化）；产品验收使用真实 CLI 与隔离 IM/Gateway 公共入口。
- Rollback: fix commits 与 milestone 属于同一 session-owner cutover；若需回退，应整体回退 refactor-462 unit，JSONL schema 未迁移，旧代码仍可读取既有档案。
- Commits: `956c59b8`..`fbd2a9f8`（fix-r1），`cf30691e`..`7444060a`（fix-r2），`12ad3215` / `ca72d9d4`（fix-r3），`2d52613f` / `d37c711f`（fix-r4），`55b2cb85` / `3c53b9f1` / `4fa748af`（fix-r5）。
- Next: rebase `origin/main`，运行精确 CI 等价命令，归档 unit 并创建 PR。
