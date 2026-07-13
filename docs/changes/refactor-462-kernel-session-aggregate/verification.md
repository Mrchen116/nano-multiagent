# Verification Report: refactor-462

## Summary

| 维度 | 结果 |
|---|---|
| Completeness | 4/4 roadpoints 已落地，但 3 个退出标准行为未满足 |
| Correctness | 6/8 用户场景保持；另有 1 个公开 SDK 兼容回归 |
| Coherence | Partially followed（决策 2 / 5 / 8 存在偏离） |

**Verdict: FAIL. 3 critical issues found. Fix before PR.**

## Scope and Evidence

- Verification mode: `full`
- Review round: `1`
- Verified commit: `226a33c02ac856ab710cdf6cd75922eb0cc6a095`
- Narrow final-aggregate tests: `38 passed in 1.41s`
- Full regression: `pytest -m 'not e2e'` → `3305 passed, 1 skipped, 20 deselected in 278.43s`
- Quality gates: `ruff check .` → passed；`ruff format --check .` → `758 files already formatted`；`git diff --check origin/main...HEAD` → passed
- Read-only behavior probes independently reproduced all three CRITICAL findings below. Their absence from the green suite is a coverage gap, not evidence that the behaviors are correct.

## Completeness

- Tasks: 4/4 roadpoints are marked `DONE` and the structural cutover is present.
- Exit criteria are not actually complete:
  - `tasks.md:9` requires all motivation scenarios, including active append/cancel recovery and prompt refresh at every compaction boundary; CRITICAL-2 and CRITICAL-3 violate those behaviors.
  - `tasks.md:15` requires active append interleaving coverage; the current test stops the fake engine before it emits any residual turn write, so it does not cover the required race.
  - `tasks.md:17` requires final-interface behavior coverage after removing private-map/manager tests; manual/threshold/overflow compaction, restart prompt-seed use, and prompt/file-window refresh no longer have equivalent permanent coverage.
- Spec coverage: stable identity, cold first append, between-turn append, ordinary multi-turn replay, simple as-of fork, typed executor ownership, and old-seam deletion are implemented. Active append reconciliation, manual-compaction prompt refresh, and the documented string `workspace_root` SDK contract are incomplete.
- Prototype / Reference coverage: N/A（本 unit 无前端原型或视觉 reference contract）。

## Correctness

| Requirement / Scenario | 实现位置 | 测试覆盖 | 状态 |
|---|---|---|---|
| CLI 多轮对话与恢复 | `src/agent/sdk/kernel.py:849`, `src/agent/core/session/conversation.py:194`, `src/agent/core/agent/runtime.py:321` | `tests/unit/agent/session/test_conversation_session.py:164` | covered |
| IM/Gateway 多轮对话与重启恢复 | `src/agent/sdk/kernel.py:1012`, `src/agent/core/runs/registry.py:168`, `src/agent/core/session/conversation.py:194` | `tests/unit/personal_assistant/test_session_reuse_regression.py:152`, `tests/e2e/critical_paths/test_restart_session_continuity_critical_path.py:65` | covered |
| 带外追加进入下一轮上下文 | `src/agent/sdk/kernel.py:1503`, `src/agent/core/session/conversation.py:207`, `src/agent/core/session/transcript.py:226` | `tests/contract/test_kernel_sdk_behavior_contract.py:303` | covered（仅两轮之间） |
| 重启后首次操作就是带外追加 | `src/agent/core/session/transcript.py:226`（UNKNOWN tail 从 durable turn 初始化） | `tests/unit/agent/session/test_jsonl_transcript.py:27` | covered |
| 中断或取消后继续会话 | `src/agent/core/session/conversation.py:194`, `src/agent/core/agent/runtime.py:321`, `src/agent/core/agent/runtime.py:593` | `tests/unit/agent/session/test_conversation_session.py:111` 未覆盖 residual write | **deviates — CRITICAL-2** |
| 上下文压缩后透明继续 | `src/agent/core/session/conversation.py:227`, `src/agent/core/agent/runtime.py:1727`, `src/agent/core/agent/loop.py:874` | 只有 planner/loop 与 stale-epoch 片段测试，无最终 aggregate / SDK 三类压缩测试 | covered in code, insufficient durable coverage（WARNING-1） |
| 从指定消息 fork 会话 | `src/agent/core/session/conversation.py:236`, `src/agent/core/session/directory.py:177` | `tests/unit/agent/session/test_conversation_session.py:207` + R4 真栈记录 | covered（边界覆盖不足，见 WARNING-1） |
| 会话内提示稳定且在压缩边界刷新 | `src/agent/core/agent/runtime.py:1715`, `src/agent/core/agent/runtime.py:1727`, `src/agent/core/agent/loop.py:969` | 无 manual compact 后重新读取 AGENTS.md 的永久测试 | **deviates — CRITICAL-3** |

## Coherence

| design 决策 | 遵守? | 代码证据 |
|---|---|---|
| 1. 每 session 一个长期存活 ConversationSession | 是 | `src/agent/core/session/directory.py:35`, `src/agent/core/session/directory.py:88` |
| 2. 五个高层事务隐藏 ordering | 部分 | interface 位于 `src/agent/core/session/conversation.py:194`；active append 未完成 live-state reconciliation（CRITICAL-2） |
| 3. ConversationSession 接管 turn state，旧多 session runtime maps 退役 | 是 | `src/agent/core/session/conversation.py:24`, `tests/contract/test_session_aggregate_architecture.py:42` |
| 4. 私有 Transcript + lifecycle permit | 是 | `src/agent/core/session/conversation.py:80`, `src/agent/core/session/transcript.py:40` |
| 5. 三类 compaction 共用 commit 并统一 reset 窗口 | 否 | threshold 路径在 `src/agent/core/agent/loop.py:969` 失效快照，manual 路径 `src/agent/core/agent/runtime.py:1727` 成功提交后未执行同一 reset（CRITICAL-3） |
| 6. KernelExecutor 只拥有 loop / Task / TargetToken | 是 | `src/agent/core/runs/executor.py:139`, `src/agent/core/runs/registry.py:108` |
| 7. SessionService / SessionManager 退役 | 是 | `tests/contract/test_session_aggregate_architecture.py:12` |
| 8. SDK / consumer behavior 无增量 | 否 | `Kernel.submit(workspace_root: str | Path)` 接受 `str`，但未归一化（CRITICAL-1） |

### Prototype / Reference Contract

N/A：`design.md` 没有前端原型或 must-match 视觉 reference。

## Issues

### CRITICAL（提 PR 前必须修）

- **CRITICAL-1 — `Kernel.submit()` 破坏公开的 `str | Path` workspace contract。** `src/agent/sdk/kernel.py:1012-1019` 明确接受 `workspace_root: str | Path | None`，但 `src/agent/sdk/kernel.py:1055-1066` 直接把字符串传给 Registry；`src/agent/core/runs/registry.py:199` 构造 `SessionRef` 后，`src/agent/core/session/types.py:39-48` 对字符串调用 `.expanduser()`，同步抛出 `AttributeError: 'str' object has no attribute 'expanduser'`。这与 progress 中“所有 SDK 会话入口已归一化”的记录（`M1-conversation-session/progress.md:77-82`）及 design 决策 8 的 no-SDK-delta 合约冲突。**修复建议：**在 `Kernel.submit` 与其它 path-taking SDK 方法一样，先执行 `Path(workspace_root or self._repo_root).expanduser().resolve()`；增加真实 `build_kernel` 回归，以 `str(root)` create/submit，等待 run terminal 并断言第二轮历史连续，而不是只检查签名或 mock 调用。

- **CRITICAL-2 — active external append 会让当前进程的 live history 永久漏掉随后已持久化的 assistant/tool/recovery，下一轮上下文不完整。** `AgentEngine._run_locked` 在 `src/agent/core/agent/runtime.py:321-322` 捕获 `state.history` 的旧 list；模型 await 期间，`ConversationSession.append_external` 在 `src/agent/core/session/conversation.py:207-216` 重载 transcript 后用新 list 替换 `self._state.history`；active engine 随后仍在 `src/agent/core/agent/runtime.py:593-615` 向旧 list 追加并把这些条目写入 transcript。独立 probe 得到 durable history=`[external, late assistant]`，但 `history_snapshot()` 和下一 turn 所见均只有 `[external]`，直至进程重启才恢复。现有测试 `tests/unit/agent/session/test_conversation_session.py:111-136` 的 blocking engine 在 append 后不写任何 residual message，反而把只剩 external 的错误形态固化为期望。该行为直接违背 design 的 active append epoch protocol（`design.md:326-343`）及 cancel/interrupt continuation 场景。**修复建议：**不要从 foreign thread 在 active turn 中替换 engine 已捕获的 list；在 ConversationSession 内记录 turn 开始时的 external epoch，append 只提交 durable mutation并标记 loaded state stale，turn/recovery 完成后若 epoch 变化则在 owner loop 上卸载/重载完整 reachable history，再释放 turn gate。新增永久回归：active turn 在 external append 后继续持久化 assistant + tool/recovery，下一次真实 submit 的 LLM context 同时包含 external 与所有 residual entries。

- **CRITICAL-3 — manual compaction 成功后不失效 memory/AGENTS.md prompt snapshot，违反“压缩边界刷新”。** `_invalidate_memory_snapshot` 在 `src/agent/core/agent/runtime.py:1715-1725` 才会清 memory snapshot 与 AGENTS.md dedup；threshold/overflow loop 路径在 `src/agent/core/agent/loop.py:969-972` 调用它，但 public `Kernel.compact()` 进入的 manual 路径 `src/agent/core/agent/runtime.py:1727-1858` 成功 commit 后只替换 `file_state`，没有清 `memory_snapshot`。独立真实 SDK probe：首轮读取 `AGENTS.md=MARKER_OLD`，磁盘改为 `MARKER_NEW`，manual compact 成功后下一轮 system prompt 仍含 OLD 且不含 NEW。该实现还证明 design 决策 5 所要求的“三类 compaction 共用一条 commit + window reset”没有真正收口。**修复建议：**把 successful compaction 的 history replacement、memory/file/prompt reset 收口为一个 ConversationSession/engine commit-finalization helper，让 manual/threshold/overflow 都走同一调用点；仅在 durable commit 成功后失效 snapshot。增加真实 Kernel 测试：同一窗口 prompt 冻结，修改 AGENTS.md 后 manual compact，下一轮读取新内容；同时覆盖 threshold 与 overflow，并验证 restart replay。

### WARNING（应该修）

- **WARNING-1 — 删除旧 private-seam 测试后，关键退出场景没有被最终 interface 的永久测试等价接回。** `tasks.md:21-30` 要求 ConversationSession/真实 Kernel 覆盖 manual/threshold/overflow compact、whole/as-of fork、restart PromptSlotSeed、prompt/file window、active residual append；但当前 aggregate 测试只有简单两轮（`tests/unit/agent/session/test_conversation_session.py:164`）、无 residual write 的 active append（`:111`）、简单 as-of fork（`:207`）和 transcript stale epoch（`tests/unit/agent/session/test_jsonl_transcript.py:138`）。`progress.md:81-85` 的 6 个 selected e2e 也没有 compaction/prompt-window 旅程。全量 3305 项通过却未捕获本报告三个 probe，已经实际证明该缺口。**修复建议：**按 `tasks.md` 测试策略，在最低 final-interface 层补齐 durable matrix：三类 compaction + restart、active append residual/recovery、whole/as-of fork 穿越 compaction boundary、两个 Kernel 实例恢复 PromptSlots 并进入真实 system prompt、legacy archive 无 reserved key 的 empty fallback、manual/automatic compaction 后 memory/AGENTS/file-window refresh；临时 e2e 记录不能替代这些回归。

### SUGGESTION（可以修）

- **SUGGESTION-1 — 退役 owner 的注释仍残留，容易误导后续维护。** `src/agent/core/session/jsonl_writer.py:18-19` 仍称 `_session_histories` 无上限，`src/agent/platform/tools/builtins/agent.py:542-547` 仍描述 `_active_run_models`；两者已被本 unit 删除。**建议：**按 `COMMENTING_GUIDE.md` 改为当前 ConversationSession / current-run model owner 的事实，或删除不再提供约束价值的历史注释。

# Round 2

## Summary

- **Mode:** full
- **Verdict:** **FAIL**
- **Scope:** `origin/main...c83acaa9b66d20d9c3e45cebc141654015ebd08c`
- **Roadpoints:** 4/4 标记 DONE；但 2 个实现/生命周期阻断使 milestone 退出标准未达成。
- **Issues:** 2 CRITICAL，3 WARNING。
- **Prior round:** CRITICAL-1（string workspace）、CRITICAL-2（active append residual history）、CRITICAL-3（manual compact window refresh）均已关闭；WARNING-1 仅部分关闭；SUGGESTION-1 的生产注释已清理。

## Verification Evidence

- 聚焦回归：72 passed（SDK contract、ConversationSession/Transcript/Directory、compaction、Executor/Registry、RuntimeRunner/ForegroundRegistry、architecture/wiring）。
- 全量非 e2e：`pytest -m "not e2e"` → **3319 passed, 1 skipped, 20 deselected**。
- `ruff check .` → passed。
- `ruff format --check .` → failed，3 files would be reformatted。
- `git diff --check origin/main...HEAD` → failed，`acceptance.md:3-5` trailing whitespace。
- 独立 interrupt 竞态 probe：provider await 被释放紧跟 `kernel.interrupt()`；输出 `interrupt run_...` 后 `terminal completed`。
- 独立 lifecycle probe：build Kernel 创建 `JsonlWriter` 与 `nano-kernel-executor` 两个线程；`kernel.close()` 后 executor 已退出，`Thread-1 (_run)` 仍 alive。
- 独立 partial-result probe：active turn 先有 partial assistant；同步 external append 前 `partial_turn_result() is not None`，append 后返回 `None`。

## Prior Round Closure

| Round 1 issue | Round 2 result | Evidence |
|---|---|---|
| CRITICAL-1 string workspace | closed | `src/agent/sdk/kernel.py:1080-1095`; `tests/contract/test_kernel_sdk_behavior_contract.py:335-349` |
| CRITICAL-2 active append residual history | closed | `src/agent/core/session/conversation.py:225-239`; `tests/contract/test_kernel_sdk_behavior_contract.py:433-492` proves external + late assistant both reach next model context |
| CRITICAL-3 manual compact prompt refresh | closed | `src/agent/core/agent/runtime.py:1707-1717,1832-1843`; `tests/integration/test_conversation_compaction_integration.py:182-240` |
| WARNING-1 durable scenario matrix | partially closed | threshold replacement/stale epoch/manual AGENTS refresh and active late assistant are now permanent tests; restart compaction, compaction-crossing forks, active tool/recovery residuals and real restart PromptSlots remain absent |
| SUGGESTION-1 stale production comments | closed | cited `_session_histories` / `_active_run_models` comments are gone |

## Completeness

| User scenario / exit concern | Result | Evidence |
|---|---|---|
| CLI/Gateway multi-turn and restart continuity | covered | full suite plus existing product/e2e regression tests |
| Between-turn and cold-first external append | covered | `tests/contract/test_kernel_sdk_behavior_contract.py:370-430`; `tests/unit/agent/session/test_jsonl_transcript.py:28-51` |
| Interrupt/cancel continuation | **deviates** | fast provider completion wins the 100ms cancellation grace; CRITICAL-4 |
| Compaction transparent continuation | implemented; durable matrix incomplete | `tests/integration/test_conversation_compaction_integration.py:52-240`; WARNING-2 |
| Whole/as-of fork independence | implemented; compaction boundary matrix incomplete | `src/agent/core/session/directory.py:204-244`; `tests/unit/agent/session/test_conversation_session.py:207-244`; WARNING-2 |
| Prompt/file window stability and refresh | manual path covered; restart/automatic matrix incomplete | `tests/integration/test_conversation_compaction_integration.py:182-240`; WARNING-2 |
| Stable aggregate / bounded loaded payload | covered | `tests/unit/agent/session/test_session_directory.py:143-203`; `src/agent/core/session/directory.py:119-195` |
| Shared engine/provider ownership | covered | one shared engine at `src/agent/sdk/kernel.py:545-565`; owned clients close at `:588-601`; contracts at `tests/contract/test_session_aggregate_architecture.py:78-108` and `tests/contract/test_sdk_kernel_wiring.py:211-243` |
| Auxiliary cleanup / partial result | partially covered | typed stop, foreground reap and ordinary raw-cancel partial result tests pass, but active append invalidates the observable partial state; WARNING-3 |

## Coherence

The final aggregate shape is substantially aligned: stable per-session objects, header-only Directory reads, bounded loaded-payload LRU, private Transcript, shared session-stateless engine/provider graph, typed Executor ownership, and retired legacy managers are all present. Two lifecycle edges remain incoherent with the approved final architecture: accepted user interrupt can still finish successfully, and the Kernel-owned JSONL writer has no shutdown path.

## Issues

### CRITICAL（提 PR 前必须修）

- **CRITICAL-4 — `interrupt()` 存在 100ms 竞态：已向用户确认 stop 的 run 仍可输出并终态为 COMPLETED。** `RunsRegistry.interrupt()` 在 `src/agent/core/runs/registry.py:283-332` 仅当 foreground stopper 返回 true 时同步把 RunRecord 置为 CANCELLED；普通 provider await 只调用非 force cancel。`KernelExecutor` 在 `src/agent/core/runs/executor.py:385-402` 等待 100ms 才取消 carrier。与此同时 `AgentLoop` 只在下一轮 model call 前检查 abort（`src/agent/core/agent/loop.py:320-351`），provider 在 grace 内返回后，terminal 分支 `:535-572` 不再检查 abort并提交 completed。独立真实 SDK probe 稳定得到 `kernel.interrupt(session_id)` 返回目标 run_id，紧接释放 provider，最终 `get_run(run_id).status == "completed"`。现有回归 `tests/contract/test_kernel_sdk_behavior_contract.py:217-263` 只让 provider 永久阻塞，因此没有覆盖该竞态。**修复方向：**把 user interrupt 的语义终态在同步返回前线性化为 CANCELLED，并保证 carrier 不能在该线性化点后发布 late assistant/completed；可对 user interrupt 一律 force-cancel，或在 model stream/terminal commit 前加入 abort-aware suppression，但不能依赖 grace 定时器。新增真实 SDK 回归：provider 在 `interrupt()` 返回后立即完成，断言目标 run 为 cancelled、late assistant 不对用户发布，随后同 session 新 turn 正常完成。

- **CRITICAL-5 — Kernel close 泄漏每个实例的 `JsonlWriter` daemon thread，未兑现 final architecture 的 deterministic close。** `JsonlWriter.__init__` 在 `src/agent/core/session/jsonl_writer.py:24-27` 启动线程，`_run()` 在 `:54-94` 永久 `while True`，类没有 close/sentinel。Kernel finalizer `src/agent/sdk/kernel.py:588-601` 只关闭 conversations 与 owned provider clients。独立 probe 在 `kernel.close()` 后观察 executor thread 已结束，但 `Thread-1 (_run)` 仍 alive。该行为违背 design 的 deterministic close 要求（`design.md:116`）、共享 writer ownership（`:148`）及 shutdown 顺序（`:182`），反复 build/close 会无界累积线程。**修复方向：**为 JsonlWriter 增加幂等 `close()`（先 durable drain，再 sentinel，join 并传播写入错误），由 Kernel finalizer 在 Directory close 后调用；补永久 contract：重复 build/close 后 writer/executor threads 均退出，close/aclose 幂等，最后一批数据已 durable。

### WARNING（应该修）

- **WARNING-2 — milestone 要求的最终接口永久测试矩阵仍不完整。** `M1-conversation-session/tasks.md:9-17,21-30` 明确要求三类 compaction、两类 fork、restart PromptSlots/file window、active append tool/recovery与真产品入口。Round 2 已补 threshold、manual、stale epoch 和 late assistant，但仍没有 overflow + restart、whole/as-of fork 穿越 compact boundary、active append 后 late tool result/recovery、两个 Kernel 实例把 PromptSlots seed 注入真实 system prompt、legacy empty fallback及 automatic compaction refresh 的永久回归。**修复方向：**在最低 final-interface 层补齐这些组合，不以 progress/临时 e2e 记录替代。

- **WARNING-3 — active external append 会让 raw-cancel auxiliary 丢失 partial result。** `ConversationSession.append_external()` 在 `src/agent/core/session/conversation.py:225-239` 将 `self._state=None`；`partial_turn_result()` 在 `:249-267` 只读取该槽位。若 active engine 已累计 partial assistant/tool/usage，append 后再被 raw cancel，`RuntimeRunner` 的 cancellation 分支 `src/agent/platform/background_tasks/runtime_runner.py:80-92` 得到 `None`。独立 probe 已复现 append 前有 partial、append 后为 None；现有 `tests/unit/agent/background_tasks/test_runtime_runner_foreground.py:157-194` 使用 fake session，未覆盖真实 aggregate。**修复方向：**把 active state 的可取消 progress 保留到 turn cleanup，或为 stale payload 保存独立 active-turn partial handle；补 real ConversationSession + auxiliary + external append + force cancel 回归，断言 text/usage/tool count 保留。

- **WARNING-4 — 当前分支未通过 milestone 自己声明的格式/差异门禁。** `ruff format --check .` 报 `src/agent/core/session/conversation.py`、`src/agent/sdk/kernel.py`、`tests/contract/test_kernel_sdk_behavior_contract.py` 需格式化；`git diff --check origin/main...HEAD` 报 `acceptance.md:3-5` trailing whitespace。`M1-conversation-session/tasks.md:17` 要求这些门禁全绿。**修复方向：**运行 formatter、移除 trailing whitespace，并重跑两项检查。

2 critical issue(s) found. Fix before PR.

# Round 3

## Summary

- **Mode:** targeted-closure
- **Delta range:** `0d96d5573774c9886aee7110da585f9f8192bbf8..d4c611438a9e75d0fec876ae12d4c4f6836cb8dd`
- **Focus issues:** Round 2 CRITICAL-4、CRITICAL-5、WARNING-3、WARNING-4，以及 code-review 的 cold append / metadata lookup 两项遗留。
- **Verdict:** **PASS**
- **requires_full_verification:** `false`
- **Issues:** 0 CRITICAL，0 WARNING，0 SUGGESTION（限本轮 targeted scope）。

| 维度 | 结果 |
|---|---|
| Completeness | 6/6 focus issues / review concerns closed |
| Correctness | 6/6 targeted behaviors reproduced as fixed |
| Coherence | Followed（interrupt semantic terminal、writer ownership、active payload ownership、cold-read boundary 均与 design 对齐） |

Round 2 WARNING-2（更完整的最终接口永久测试矩阵）不在本轮 orchestrator 的 targeted focus 中，本轮没有重新判定或计入 issue 数；其历史记录保留在 Round 2。

## Verification Evidence

- 受影响窄测：`pytest -q` 覆盖 Kernel interrupt/active append、Kernel wiring、ConversationSession、JsonlWriter、JsonlTranscript、SessionDirectory、RuntimeRunner、KernelExecutor、RunsRegistry 与 architecture contract → **66 passed in 1.98s**。
- Round 2 full 基线复用：`pytest -m "not e2e"` → **3319 passed, 1 skipped, 20 deselected**；本轮 delta 只触及上述 focus 路径，定向测试与独立 probes 足以核销，不要求升级 full。
- 独立 interrupt grace probe：连续 30 次让 provider 在 `interrupt()` 返回后立即产出 late assistant；30/30 RunInfo 保持 `cancelled`，0 条 late provider output 进入 JSONL，30/30 同 session 后续 turn 完成。
- 独立 writer lifecycle probe：连续 build/close 20 个 Kernel，交替调用 `close()` / `aclose()` 并重复关闭；20/20 writer thread 退出，20/20 close 前 enqueue 的最后一条 entry durable。
- 独立 active-append partial probe：真实 `ConversationSession + KernelExecutor + RuntimeRunner` 中先记录 assistant/tool/usage partial，再同步 append external 并 raw-cancel auxiliary；kill callback 保留 `partial-real`、18 tokens、1 tool，target 与 writer 均完成 cleanup。
- `ruff check .` → passed；`ruff format --check .` → **760 files already formatted**；`git diff --check origin/main...HEAD` → passed。

## Targeted Closure

| Focus issue / concern | Round 3 result | Implementation evidence | Permanent regression evidence |
|---|---|---|---|
| CRITICAL-4 interrupt grace race | **closed** | `src/agent/core/runs/registry.py:283-332` 在返回前线性化 `CANCELLED` 并请求 carrier cancel；`src/agent/core/agent/loop.py:394-401,548-562` 在 stream 与 terminal commit 两处阻止 abort 后的 late completed/output | `tests/contract/test_kernel_sdk_behavior_contract.py:266-318`；另有 30 次独立 race probe |
| CRITICAL-5 JsonlWriter thread leak | **closed** | `src/agent/core/session/jsonl_writer.py:28-78,80-107` 以 lifecycle guard + FIFO sentinel flush/join；`src/agent/sdk/kernel.py:589-603` 在 Directory close 后由 Kernel finalizer 关闭 writer | `tests/unit/agent/session/test_jsonl_writer.py:12-23`、`tests/contract/test_sdk_kernel_wiring.py:246-254`；另有 20 次独立 lifecycle probe |
| WARNING-3 active append 后 partial result 丢失 | **closed** | `src/agent/core/session/conversation.py:226-271` 用 `_payload_stale` 保留 active state，下一次 stateful operation 才 reload；`partial_turn_result()` 仍可读取 active progress | `tests/unit/agent/session/test_conversation_session.py:157-184` + `tests/unit/agent/background_tasks/test_runtime_runner_foreground.py:157-194`；另有真实 aggregate/auxiliary 组合 probe |
| WARNING-4 format / diff gate | **closed** | Round 2 的 3 个 formatter drift 与 `acceptance.md` trailing whitespace 均已清理 | 本轮 `ruff check .`、`ruff format --check .`、`git diff --check origin/main...HEAD` 全绿 |
| code-review: cold append 不应 materialize Message history | **closed** | `src/agent/core/session/transcript.py:432-451,521-573` 直接从 raw turn entries 解 reachable tail，不再调用 `_materialize()` / `_to_message()` | `tests/unit/agent/session/test_jsonl_transcript.py:53-76` 令 `_materialize` 抛错并证明 cold append 仍接到既有 tail |
| code-review: `find_by_metadata` 应 header-only | **closed** | `src/agent/core/session/directory.py:152-174` 只调用 `initial_metadata()`；`src/agent/core/session/transcript.py:141-149` 以 `limit=1` 只读 creation header | `tests/unit/agent/session/test_session_directory.py:169-197` 记录读取 limit 并断言只有 `[1]` |

## Issues

### CRITICAL（提 PR 前必须修）

N/A。

### WARNING（应该修）

N/A（限本轮 targeted scope）。

### SUGGESTION（可以修）

N/A。

All checks passed. Ready for PR.

# Round 4

## Summary

- **Mode:** targeted-closure
- **Delta range:** `aa6f7ee0fd5ebdec46f2471e8006d329449fb5ca..99b4a71ca77f7fe6eab8e2a21ca02909e03ac3e2`
- **Focus issues:** fix-r3 的 hook-await interrupt publication race、cleanup failure resource drain、cold-load/external-append publication race；并回归 Round 3 已通过范围。
- **Verdict:** **PASS**
- **requires_full_verification:** `false`
- **Issues:** 0 CRITICAL，0 WARNING，0 SUGGESTION（限本轮 targeted scope）。

| 维度 | 结果 |
|---|---|
| Completeness | 3/3 fix-r3 focus issues closed；Round 3 scope regression preserved |
| Correctness | 3/3 race/failure behaviors independently reproduced as fixed |
| Coherence | Followed（hard interrupt boundary、best-effort cleanup with error propagation、epoch-gated cache publication 均符合 design） |

Round 2 WARNING-2 仍不在本轮 targeted focus 中，本轮没有重新判定或计入 issue 数；其历史记录继续保留。

## Verification Evidence

- 受影响回归：`pytest -q` 覆盖 Kernel interrupt/active append、Kernel wiring、ConversationSession、JsonlWriter、JsonlTranscript、SessionDirectory、RuntimeRunner、KernelExecutor、RunsRegistry 与 architecture contract → **69 passed in 2.19s**。这包含 Round 3 的全部受影响测试文件及 fix-r3 新增回归。
- 独立 hook-await interrupt probe：连续 30 次在 assistant `message_start` hook 内暂停，`interrupt()` 返回后释放 hook；30/30 run 保持 `cancelled`，首 run 的 public `assistant_message` 为 0，late content 写入 JSONL 为 0，下一轮 model context 污染为 0。
- 独立 cleanup failure probe：分别注入 conversation flush failure 与 `Directory.close_all()` failure，各 10 次；20/20 原始 `OSError` 向 `aclose()` 调用方传播，同时 writer thread、owned provider client 与 executor thread 全部关闭，close 前 pending JSONL entry 全部 durable。
- 独立 cold-load publication probe：连续 50 次在 Transcript materialize 完成、ConversationState 发布前同步 append external；50/50 下一 serialized turn 重新加载并看到该消息，0 次被刚发布的旧缓存吞掉。
- `ruff check .` → passed；`ruff format --check .` → **760 files already formatted**；`git diff --check origin/main...HEAD` → passed。

## Targeted Closure

| Focus issue | Round 4 result | Implementation evidence | Permanent regression evidence |
|---|---|---|---|
| message hook await 中 interrupt 后 late publication / persistence / context contamination | **closed** | `src/agent/core/runs/registry.py:273-322` 将每次 accepted interrupt 变成 hard carrier cancel；`src/agent/core/agent/loop.py:428-440,652-710` 在 hook dispatch 前后检查 controller，未完整发布的 assistant 不再 yield 给 runtime | `tests/contract/test_kernel_sdk_behavior_contract.py:320-380`；另有 30 次独立 public-event + JSONL + next-context probe |
| directory/flush failure 仍须关闭 writer/client/executor 并传播错误 | **closed** | `src/agent/sdk/kernel.py:589-615` 逐阶段收集错误并继续 writer/client cleanup，最终抛首个错误；`src/agent/core/runs/executor.py:255-295` 即使 finalizer 抛错也先停止 owner loop、join executor，再传播异常 | `tests/contract/test_sdk_kernel_wiring.py:256-274` 联同 `:211-253` 的 owned-client/writer 生命周期测试；另有 20 次两类 failure injection probe |
| cold load 与 external append 交错时旧缓存发布吞消息 | **closed** | `src/agent/core/session/transcript.py:39-46,120-132` 把 mutex 内捕获的 `external_epoch` 随 load 返回；`src/agent/core/session/conversation.py:226-234,325-352` 只在 loaded epoch 等于 current epoch 时复用 state，竞态发布的旧 state 下一次必 reload | `tests/unit/agent/session/test_conversation_session.py:183-216`；另有 50 次 materialize→append→publish 精确窗口 probe |
| Round 3 interrupt/writer/partial/cold-read/header-only closure | **preserved** | fix-r3 没有恢复旧 manager/runtime seam；新的 hard interrupt、finalizer 与 epoch token 沿用同一 owner 边界 | 本轮 69 项受影响回归全绿，Round 3 的 66 项测试范围全部包含在内 |

## Issues

### CRITICAL（提 PR 前必须修）

N/A。

### WARNING（应该修）

N/A（限本轮 targeted scope）。

### SUGGESTION（可以修）

N/A。

All checks passed. Ready for PR.
