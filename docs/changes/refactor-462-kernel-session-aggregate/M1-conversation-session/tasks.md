# refactor-462-M1 — conversation-session

## 目标

把现有由 `SessionManager` / `SessionService` / 多 session `AgentRuntime` / `RunsRegistry` / `RuntimeRunner` 共同持有的会话事务，收敛为 `SessionDirectory + ConversationSession × N + private JsonlTranscript + KernelExecutor`。公开 SDK、DTO、错误语义、事件以及 JSONL entry/path 保持不变。

## 退出标准

- motivation.md 的 CLI/Gateway 多轮与重启、两类同步 append、cancel/interrupt 后继续、三类 compaction、两类 fork、PromptSlots/file window 场景从真实产品入口保持不变。
- 新建 session 的 PromptSlots seed 经 reserved metadata 重启恢复；旧档案无 seed 时为空；任何 SDK metadata projection 不暴露 `__nano_internal_*`。
- `/stop` 返回前同步 park pending；cancel 同步返回 CANCELLED；同 session 后续 run 不永久阻塞。
- foreground 超时转 background、fire-and-forget subagent 后立即 `aclose` 均在有限时间完成且无残留 target。
- 一个 Kernel 生命周期内同一 session id 只对应一个稳定 `ConversationSession`；正常路径是 Directory open → `submit_turn`。
- production 删除 `SessionManager` / `SessionService`、多 session runtime maps、`.store/.writer` 穿透、高层 JsonlSessionStore、RuntimeRunner 裸 loop/coroutine、public lease/generic executor。
- Transcript 统一 taxonomy/tail/write path，并覆盖 fresh-first-append、active append 交错、recovery control 不推进 tail、append-vs-close 双顺序、cancel worker drain、binding mismatch、parent-scoped find、close/shutdown。
- RunsRegistry 是 RunInfo 唯一 writer；Executor 只拥有 Task/TargetToken/cleanup ack；public cancel terminal 与 internal cleanup 分开测试。
- ConversationSession interface、真实 Kernel 集成、contract、`pytest -m "not e2e"`、`ruff check .`、`ruff format --check .` 全绿；旧 private-map/manager 测试删除或改成最终 interface 行为测试。

## 测试策略

- 被测行为(来自退出标准):
  - stable identity、binding mismatch、PromptSlotSeed reserved metadata strip/rehydrate、parent-scoped find。
  - Transcript 首次 append tail、control taxonomy、active append ordering、append/close 线性化、compaction/fork materialize。
  - ConversationSession normal turn/compact/fork/close、cancel recovery、prompt/file window。
  - Executor bind-before-schedule、top-level/auxiliary/lifecycle cleanup；RunsRegistry semantic status 与 cleanup ack 分域。
  - Kernel SDK/DTO/JSONL/path 不变；CLI/Gateway 真入口多轮、重启、append、cancel、compact、fork、subagent close。
- 已有测试在: `tests/unit/test_jsonl_store_dag_recovery.py`、`tests/unit/test_session_persistence_fidelity.py`、`tests/unit/test_agent_runtime.py`、`tests/unit/test_fork_session.py`、`tests/unit/test_runs_registry.py`、`tests/unit/test_run_cancel.py`、`tests/integration/test_session_store_persistence_integration.py`、`tests/integration/test_compaction_runtime_integration.py`、`tests/e2e/critical_paths/`；按最终 interface 改写。新建 `tests/unit/agent/session/test_conversation_session.py`、`test_session_directory.py`、`test_jsonl_transcript.py` 与 `tests/unit/agent/runs/test_kernel_executor.py`，因为最终 aggregate/executor 没有合适的既有目标文件。
- 落层/目录/marker: 纯 session/executor 行为在 `tests/unit/`，真实 Kernel 跨模块行为在 `tests/integration/`，依赖/禁旧 seam 在 `tests/contract/`，真进程/真 LLM 旅程在 `tests/e2e/` 且 marker `e2e`。
- 可选依赖 importorskip: 真入口若依赖 Playwright 使用现有 e2e fixture/importorskip；本 unit 无新增可选依赖。
- 本 milestone 产生的一次性验收证据(收尾删除,不进套件): 隔离 worktree 的 CLI/Gateway 真栈命令输出与服务日志摘要，结果写入 progress.md；不提交临时脚本。

## Frontend Implementation Plan

N/A：本 milestone 不修改 UI、前端状态或视觉资源。

## Roadpoints

### R1 — Transcript、Directory 与核心 session 数据模型

- 状态: TODO
- 步骤:
  - 定义 `SessionRef` / `NewSession` / `TurnRequest` / `ExternalMessage` / `PromptSlotSeed` 及内部 lifecycle errors。
  - 把 JSONL 高层 materialize/repair/taxonomy/tail/append/compaction/fork 语义收进绑定单 session 的 private `JsonlTranscript`；下层仅保留 raw address/read/enumerate 与 writer raw enqueue/barrier。
  - 实现短 registry guard 的 `SessionDirectory` stable intern、binding mismatch、create/open/get/list/find/close_all；reserved metadata encode/decode/strip。
  - 把 memory/file context state 迁到 session 所属模块。
- 验证: 新 interface 红测转绿；fresh-first-append、recovery-control tail、parent scope、reserved metadata、binding mismatch、append/close admission 行为覆盖。

### R2 — ConversationSession 接管 turn/compact/fork transaction

- 状态: TODO
- 步骤:
  - 将 `AgentRuntime` 的单会话算法迁入长期存活的 `ConversationSession` 字段，移除所有 session-id keyed live-state maps。
  - 每个 session 持有自己的 `AgentLoop` / state / prompt seed / transcript / lifecycle permit；normal turn、sync append、manual/threshold/overflow compact、whole/as-of fork、recovery、close 均经高层事务。
  - AgentLoop 改为 per-conversation scalar state，不再穿透 SessionManager 或 store。
- 验证: ConversationSession interface 行为、active append epoch、compact stale commit、fork 独立性、prompt/file window 与 cancel worker drain 红测转绿。

### R3 — KernelExecutor、RunsRegistry 与 subagent 控制面

- 状态: TODO
- 步骤:
  - 新增 typed `KernelExecutor`，唯一拥有 owner loop、top-level/auxiliary/lifecycle Task、TargetToken 与 cleanup ack；禁止 generic coroutine/event-loop getter。
  - RunsRegistry 只保留 RunRecord/controller/steer/held-pending，保持 `/stop` 同步 park 与 cancel 同步 semantic terminal，并用 Executor token 做资源清理。
  - RuntimeRunner/AgentTool 改为 Directory/Executor 的窄 subagent control；parent scope、foreground/auto-background/fire-and-forget/shutdown 走 typed target。
- 验证: bind-before-schedule、admission/shutdown、cancel terminal vs cleanup、same-session resubmit、foreground/background subagent immediate close 红测转绿。

### R4 — SDK composition cutover、旧 seam 删除与真实入口签收

- 状态: TODO
- 步骤:
  - `build_kernel`/Kernel façade 全量切到 Engine + Directory + Executor + Registry；create/submit/append/compact/fork/get/close 公共形态不变。
  - 删除 SessionManager/SessionService/多 session AgentRuntime/高层 JsonlSessionStore 以及旧 private-map/manager tests；添加 contract 守卫防回流。
  - 更新 `SPEC.md` 与 `docs/specs/kernel/context-persistence.md` grounding；不写 delta-spec。
  - 跑窄测、contract/integration、全量非 e2e、ruff，并按 reviewer runbook 启动隔离 CLI/Gateway 真栈覆盖全部用户场景。
- 验证: 所有退出标准有 durable evidence；unit 分支只保留最终单 owner 架构且本地 CI 等价全绿。
