# feat-445-M2 — Progress

fix-implementation（reviewer 反馈循环，复用 M1 worker 上下文）。round-1 三道闸的 8 个
CONFIRMED fork 边缘缺陷 + 防御 + W1/W2 + 群聊400。每条配回归红→绿，真栈复跑边缘路径。

### R1 — kernel: flush_async(#1) + drop source_lock(#2) + role 守卫(防御)

- Decision: ① runtime.fork_session up_to 路径 `flush()`→`await flush_async()`；② 去掉 up_to 路径的 `async with source_lock`；③ jsonl_store.load up_to 命中加 `role=='assistant'` 守卫。
- #2 安全性论证（已核实）：up_to 路径数据全部来自 `manager.load`（磁盘 boundary-aware materialize，锁外已完成），`_fork_locked` 只 enqueue 写**新** session 的 JSONL、从不读源内存历史。源 JSONL append-only：并发 run 只会在当前 tail（即 M）之后追加，而 up_to 在 M 处截断、M 之后条目本就丢弃；行写入原子 + 路径首已 `flush_async`，故 as-of-M 切片一致，无需锁。原来在此持源锁 → 源 agent 活跃 run 持同一把锁数分钟 → fork 阻塞 → gateway 10s 超时 → 502（#2 根因）。非 up_to 路径保留锁（复制内存缓存、需防 compact 并发）。
- Evidence:
  - Tests: `tests/unit/test_fork_session.py` 13 passed——`test_fork_up_to_uses_async_flush_not_blocking`(loop 线程上无阻塞 flush)、`test_fork_up_to_does_not_block_on_busy_source_lock`(源持锁时 fork 3s 内完成)、`test_fork_up_to_non_assistant_message_rejected`(防御)。
  - Entry: 内核进程内真实 JSONL。
  - E2E/Regression: `pytest tests/unit/ tests/contract/` 2623 passed/1 skipped。
- Rollback: revert C2；非 up_to 路径不变。
- Commits: C1=test, C2=fix, C3=docs。
- Next: R2 长对话 fork 全量历史读。

### R2 — 长对话 fork 取全量历史（#3）

- Decision: 加 `MessageRepository.list_all_messages(conversation_id)`（复用 `_list_message_timeline` 全量，无 `[-200:]`、无 cursor）；fork_conversation 的 fork_index 定位 + 复制改用它。根因：`list_messages` 是 UI 分页读（`min(limit,200)` + `[-200:]`），fork 误用它 → fork 点在末 200 外找不到(400)、或分支只复制末段(展示<记忆)。
- Evidence:
  - Tests: `test_fork_conversation.py` 9 passed——`test_fork_point_outside_last_200_is_found`(260 条、fork 早期点 → 分支精确 [0..M])、`test_fork_at_end_of_long_conversation_copies_full_history`(fork 末尾 → 分支 260 条全量、含最早 u0)。
  - E2E/Regression: 真栈 >200 复跑见 R6。
- Rollback: revert C2。
- Commits: C1=test, C2=fix, C3=docs。
- Next: R3 fork_conversation 编排重排 + 递归 fork 映射 + 回滚 + 保留状态。

### R3 — fork_conversation 重排 + 递归映射 + 回滚健壮 + 保留状态（#4/#5/#6/#8 + map 接线）

- Decision:
  - #5 map 接线: `_fork_locked`/`runtime.fork_session` 返回 `(Session, old→new uuid map)`（runtime 调用点 + test 解包）；`SessionInfo` 加 `fork_id_map`；`kernel.fork_session` 经 `replace()` 填入；gateway `_build_session_fork_handler` result 带 `id_map`；`request_fork_session`/`_handle_session_fork_result` 回包本就透传全部 key，id_map 自动流到 IM。
  - #4 重排: 建**空**会话 → request_fork（先绑 kernel session）→ 成功后才复制展示历史。binding 前无 message.created 广播，RPC 失败回滚的是空会话。
  - #5 回写: 复制行 kernel_message_id = `id_map.get(源 km)`；不在 map（compact 掉的前界气泡）→ None（分支不可再 fork 它，诚实）。
  - #6 回滚: `_rollback_fork` 受保护 helper（try 包 delete、失败只 log 不覆盖原异常）；request_fork 异常捕获 `except BaseException`（含 CancelledError）。
  - #8: repo `create_message` 加 `delivery_status` 入参；复制时传源 delivery_status（failed 不被改写成 completed）。
- Rationale: 复用 `_fork_locked` 已有的 `old_to_new_uuid`（无需新算）；id_map 经 SessionInfo（SDK 边界 DTO）类型化承载，不污染 metadata。重排让「binding 早于广播」，从根上消除 RPC 窗口内用户消息被回滚吞掉。受保护回滚 + BaseException 覆盖根治幽灵会话 + 500 误码。
- Evidence:
  - Tests: `test_fork_conversation.py`(7) + `test_fork_conversation_edges.py`(R2+R3，含 #4 binding 前空会话、#5 映射回写 + 不在 map→None、#6 回滚不吞原异常 + 捕 CancelledError、#8 failed 保留)、`test_session_fork_handler.py`(id_map 透传)、`test_fork_session.py`(返回 tuple 解包) 全绿。拆 edges 文件守 400 行上限（contract 绿）。
  - E2E/Regression: `pytest tests/im_service/ tests/unit/ tests/contract/` 2999 passed/2 skipped；ruff check+format 干净。
  - 残余: request_fork 成功后复制循环若失败（本地 sqlite 写，极端）不回滚（避免 gateway binding 悬挂，无 unbind RPC）——属既有「回滚本身失败」极端边缘。
- Rollback: revert C2。
- Commits: C1=test, C2=fix, C3=docs。
- Next: R4 前端 fork 按钮 in-flight 禁用。

### R4 — 前端 fork 按钮 in-flight 禁用（#7）

- Decision: MessagePane/MessageBubble 加 `forkPending` prop；fork 按钮 `disabled={!agentOnline || forkPending}` + onClick `if (agentOnline && !forkPending)`；chat-workspace 传 `forkMutation.isPending`。前端守卫足够（后端去重可选，未做）。
- Evidence:
  - Tests: `message-pane-fork.test.tsx` 7 passed（新 `disables fork while a fork is in flight` — pending 时 disabled + 点击不触发 onFork）；全前端 vitest 550 passed；tsc 干净。
  - Browser QA: 真栈双击复跑见 R6。
- Rollback: revert C2；prop 默认 false 向后兼容。
- Commits: C1=test, C2=fix, C3=docs。
- Next: R5 补测试 W1 + W2 + 群聊源 400。

### R5 — 补测试 W1 + W2 + 群聊源 400

- Decision: W1 `test_fork_conversation_edges.py::test_fork_copies_tool_calls_and_thinking`（源 agent 气泡带 tool_calls + thinking，fork 后分支复制都在）；W2 加 `IMClient.fork_conversation` + `tests/e2e/critical_paths/test_message_fork_critical_path.py`(@pytest.mark.e2e 真栈：分支带记忆追问答对 + 排除 fork 点后消息 + 原会话不变) + `docs/e2e-critical-paths.md` v1 表登记第 12 行（10→11 条）；群聊源 `test_fork_conversation.py::test_fork_group_conversation_rejected`(direct_kind!=user-agent → ForkValidationError 400)。
- Evidence:
  - Tests: 两 fork unit 文件 16 passed；e2e 测试 `--collect-only` 通过（真跑在 R6）。ruff check+format 干净；两测试文件均 <400 行。
  - E2E/Regression: e2e 真跑见 R6（scripts/e2e-critical.sh 按目录 glob 自动纳入新测试）。
- Rollback: revert C-test。
- Commits: 单 commit（test + e2e + doc）。
- Next: R6 live 真栈边缘路径复跑。

<!-- 每个 roadpoint 完成后实时追加 -->
