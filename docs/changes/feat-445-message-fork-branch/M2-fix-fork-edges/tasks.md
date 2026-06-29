# feat-445-M2: fix-fork-edges — Tasks

> 对齐: ../design.md（M2 行）+ round-1 verification.md / acceptance.md
> 模式: fix-implementation（reviewer 反馈循环，复用 M1 worker 上下文）。每条缺陷配回归红→绿。

## 目标

修 round-1 三道闸 CONFIRMED 的 8 个 fork 边缘缺陷 + 1 防御 + W1/W2 测试 + 群聊源 400 后端测，真栈复跑边缘路径到通。happy-path 已过、不重测。

## 退出标准（= 8 缺陷各修 + 守护）

- [ ] #1 fork up_to 用 `flush_async` 不阻塞事件循环
- [ ] #2 up_to 路径不长持 source_lock（agent 忙时 fork 不超时），附安全性论证
- [ ] #3 长对话(>200)fork 取全量历史：早期 fork 点不报 400、分支展示=记忆
- [ ] #4 新分支会话在 binding 成功前不暴露/不会因回滚吞用户消息（编排重排）
- [ ] #5 递归 fork 复制气泡不再 502（分支 IM 行 kernel_message_id == 分支 JSONL uuid）
- [ ] #6 回滚受保护（不吞原异常、捕 BaseException/CancelledError、不留幽灵会话）
- [ ] #7 fork 按钮 in-flight 禁用、双击不产生两条分支
- [ ] #8 复制气泡保留源 delivery_status（failed 不被改写为 completed）
- [ ] 防御: jsonl_store up_to 命中加 role=='assistant' 守卫
- [ ] W1 tool_calls+thinking 复制单测；W2 fork 登记 e2e-critical-paths.md + 永久 e2e；群聊源→400 后端单测
- [ ] `pytest -m "not e2e"` 全树 + 前端 vitest 不回归；真栈复跑边缘路径通

## 测试策略

- 每缺陷红→绿回归（§FL ⚡ 行为/契约类 fix 不豁免红测）。
- 落层：kernel/IM 进程内单测 tests/unit + tests/im_service；前端 vitest；W2 永久 e2e 落 tests/e2e/critical_paths/（@pytest.mark.e2e 真栈）。
- live：真栈复跑长对话 fork / 递归 fork / agent 忙时 fork / 双击 / 回滚。

## Roadpoints

### R1 — kernel: flush_async(#1) + drop source_lock(#2) + role 守卫(防御)

- 步骤: runtime.fork_session up_to 路径 `flush()`→`await flush_async()`；去掉 up_to 路径的 `async with source_lock`（数据全来自磁盘 load、_fork_locked 只写新 session，锁无正确性意义；附 JSONL append-only + M 处截断 + 行原子 + 先 flush 的安全论证写 progress）；jsonl_store.load up_to 命中加 `role=='assistant'` 守卫（非 assistant 命中显式报错）。
- 验证: 单测——up_to fork 不调同步 flush（断言走 flush_async / 或不阻塞）；source agent 持锁时 up_to fork 仍能完成（不死锁）；up_to 指向非 assistant turn → 报错。

### R2 — 长对话 fork 取全量历史（#3）

- 步骤: MessageRepository 暴露无上限全量时间线读（`list_all_messages` 复用 `_list_message_timeline`，不 `[-200:]`、不 cursor）；fork_conversation 的 fork_index 定位 + 复制改用它。
- 验证: 单测——seed >200 条消息、fork 点在末 200 之外 → fork 成功、分支含 [0..M] 全部、fork 点前后正确。

### R3 — fork_conversation 编排重排 + 递归 fork 映射 + 回滚健壮 + 保留状态（#4/#5/#6/#8 + kernel/gateway map 接线）

- 步骤:
  - #5 map 接线: `_fork_locked`/`runtime.fork_session` 返回 `(Session, old→new uuid map)`；`SessionInfo` 加 `fork_id_map`；`kernel.fork_session` 填入；gateway `_build_session_fork_handler` result 带 `id_map`；`gateway_handler.request_fork_session` 回包透传 `id_map`。
  - #4 重排: create 空会话 → 在线校验已在前 → `request_fork`（先绑 kernel session）→ 成功后再复制展示历史。
  - #5 回写: 复制行 kernel_message_id = `id_map.get(源 kernel_message_id)`（不在 map=compact 掉的前界气泡 → None，分支不可 fork，诚实）。
  - #6 回滚: 抽 `_rollback_fork(new_conv_id, actor)` 受保护 helper（try 包 delete、失败只 log 不覆盖原异常）；异常捕获覆盖 BaseException（含 CancelledError）；去重两段回滚。
  - #8 复制保留源 delivery_status（create_message 加 delivery_status 入参或复制后置位，不强制 completed）。
- 验证: 单测——重排后 binding 前无展示消息广播 + RPC 失败回滚空会话；递归 fork 映射后复制行 kernel_message_id 来自 map；回滚 helper 不吞原异常 + 捕 CancelledError；failed 气泡复制后仍 failed。

### R4 — 前端 fork 按钮 in-flight 禁用（#7）

- 步骤: `message-pane.tsx` fork 按钮 disabled 透传 `forkPending`；`chat-workspace-page.tsx` 把 `forkMutation.isPending` 传下去。
- 验证: vitest——pending 时按钮 disabled、点击不再触发 onFork。

### R5 — 补测试: W1 + W2 + 群聊源 400

- 步骤: W1 `test_fork_conversation` seed 带 tool_calls+thinking 的 agent 消息断言复制；W2 `docs/e2e-critical-paths.md` 加 fork 行 + `tests/e2e/critical_paths/test_message_fork_critical_path.py`(@pytest.mark.e2e 真栈：fork 后新单聊带记忆 + 原会话不变)；群聊源 fork → 400 后端单测。
- 验证: 各测试绿；e2e 真栈跑过。

### R6 — live 真栈边缘路径复跑

- 步骤: e2e-up.sh 起栈；复跑长对话 fork(>200)、递归 fork(分支再 fork 复制气泡)、agent 忙时 fork、双击、RPC 失败回滚。
- 验证: 各边缘路径真栈通过 + 截图/log 证据进 progress；env 撞墙按 §0.11 报 lead 不降级。
