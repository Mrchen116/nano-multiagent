# feat-445-M1 — Progress

## Decision: 决策1 实现路径取轻法 (b)，非 CC 式 raw-clone (a)

- Context: design.md v2.5 决策1 写「CC 式 raw-clone」（复制源 JSONL 原始条目含 compact_boundary/summary、re-stamp UUID 及内部引用、截断到 M、新 session boundary-aware load 派生视图）；design.md:110 同时显式注明等价轻法 (b)（对源 raw 前缀 [0..M] 做 boundary-aware materialize 得 as-of-M 的 Message 列表 → 交现成已测的 `_fork_locked` 写新 session，完全避开 boundary/summary 内部引用 re-stamp）。design-review.md 留 1 条非阻断 WARNING 推荐 (b)。orchestrator 指示由 worker 在 design 自承等价的两法里知情取舍。
- Decision: **取轻法 (b)**。
- Rationale:
  1. 两法模型行为完全相同（design 自承、review 复核确认），都满足 spec「分支≡源在 M 体验一致」——差别只在最后一步实现与风险。
  2. §0.1（复用/扩展现有架构，别新写平行物）：(b) 复用现有 `store.load` boundary-aware materialize（只加 `up_to` 截断参数）+ 现成已测 `runtime._fork_locked`（Message 侧 re-stamp）。(a) 经第一手核对**无法复用 `_fork_locked`**（它遍历 materialized Message、看不到也无法 re-stamp compact_boundary 标记），是一条**新增 raw-entry 克隆路径**，与 design「可复用能力段」自承的「整体复用 _fork_locked」自相矛盾。
  3. (a) 必须正确一致 re-stamp `compact_boundary.summary_uuid` / summary turn `uuid`/`parent_uuid=first_kept_event_id`（design 自标的「头号易错点①」），且与 compact 条目 schema 长期耦合；换来的 kernel-side scrollback 在 nano **无消费者**——kernel JSONL 不是展示面（展示由 IM 展示副本承担，决策3），compact 后 `store.load:224` 永久跳过 boundary 前 turn，克隆进分支是 write-only 死重。无任何 nano 端现在/近期特性消费它。
  4. **关键正确性论证（为何 (b) 的 as-of-M 视图精确等于源在 M 的视图）**：当 agent 产出消息 M 时，源 JSONL 文件状态 = [0..M]。`store.load` 对 [0..M] 前缀的 boundary-aware materialize = 源当时（产出 M 之后那一 turn）实际加载的工作上下文。轻法 (b) 用 `up_to=M` 截断 raw_lines 到 M 行（含）后跑**同一段** store.load 逻辑 = 复现源在 M 的历史文件状态 → 视图逐字一致。无需任何新「无损读」语义。
- Grounding（第一手核对，非二手）:
  - `store.load` boundary-skip: jsonl_store.py:198-231（有 boundary 只留其后 turn + summary；无 boundary 取全部 turn）。
  - `_fork_locked` 操作 materialized Message、`replace()` 保 reasoning/工具: runtime.py:1312-1385。
  - **linchpin 确认**：relay 事件 `message_id`（realtime_stream.py:54）= loop 的 `assistant_msg_id`（loop.py:407 → message_end 事件 message_id loop.py:653）= 持久化 JSONL turn 的 `uuid`（runtime.py `_message_to_entry`:2251 `"uuid": msg.message_id`）。三处同一 id → fork `up_to=message_id` 按 turn uuid 截断精确落在 IM 气泡所标的那条 assistant 消息。
  - relay 多气泡 roll: 每 IM 气泡 ↔ 一个 kernel message_id，`_roll_bubble`（main.py:3218）切换；`message_completed`（turn_end main.py:3700 / roll main.py:3252）是每气泡恰一次的终结点，token_usage 即在此持久化（precedent）。
  - 无生产调用方依赖现有 `runtime.fork_session` 签名（grep 全 src 仅 kernel stub 与测试）；现有 5 个 test_fork_session.py 用例全走 `up_to=None` 路径，保留 cache-first 不破。
- Impact: 仅本 milestone 实现路径；design 决策1 的「等价轻法 (b)」分支被选中，不改 design 任何决策方向（design 已框定两法等价）。可复用能力段措辞按 review Recommendation 已如实（(b) 即「整体复用 _fork_locked + store.load，只加截断」，与 design:49-50 一致）。

---

### R1 — relay 落逐气泡 kernel message_id 到 IM 消息行（决策 4 地基）

- Context: fork 两侧对齐键必须逐气泡唯一。一个 run 可产出多条 assistant_message = 多个 IM 气泡（textA→工具→textB），每个气泡须标上「产出它的那条 assistant 消息」的 kernel message_id。现状 IM 消息行不存任何 kernel id（`domain/models.py` Message 无字段），gateway observer 虽在 `main.py:3414` 拿到 kernel message_id 但只用于多气泡 roll 边界判定、不发给 IM。
- Decision: 用 `message_completed` 帧作 kernel message_id 的载体（每气泡恰一次的终结点，与 token_usage 同款「气泡终结元数据」precedent，沿用而非另造）。gateway 两处发 message_completed——turn_end（最终气泡，`main.py` ctx.kernel_message_id）+ `_roll_bubble`（被关闭的旧气泡，进入时捕获 ctx 旧 kernel id，在被新气泡覆盖前 stamp）。IM 加 `kernel_message_id` 列（迁移，nullable）+ Message 模型字段 + repo create/update 读写 + `_message_from_row` 读 + on_message_completed 透传 + gateway_handler 取出。
- Rationale: message_delta 是流式高频载体，kernel id 是气泡常量元数据，挂 message_completed 一次写定最干净；roll 旧气泡 + turn_end 最终气泡两路覆盖所有气泡。**linchpin 已第一手核实**：relay 事件 message_id（realtime_stream:54）= loop assistant Message.message_id（loop:407→message_end:653）= JSONL turn uuid（runtime `_message_to_entry`:2251）三处同一 id，故落到 IM 行的就是「源 session 日志中那条 assistant 消息的 uuid」，fork up_to 据此精确截断。
- Evidence:
  - Tests: 新 `tests/unit/personal_assistant/test_relay_kernel_message_id.py`（多气泡 roll → 每 message_completed 帧带各自气泡 kernel id；单气泡 turn_end 带 kernel id）；扩 `test_message_runtime_state.py::test_kernel_message_id_round_trip`（create_message/update_runtime_state 往返 + 无关 patch 不清值）；扩 `test_event_bridge.py::test_on_message_completed_persists_kernel_message_id`。R1 相关 25 passed。
  - Entry: 进程内 gateway observer 真实事件序列驱动（非 mock 内部函数），断言发往 IM 的真实 streaming_delta 帧。完整 live 端到端在 R6。
  - Frontend State Matrix: N/A（R1 后端）
  - Browser QA: N/A
  - E2E/Regression: `pytest tests/im_service/ tests/unit/test_inbound_pipeline_streaming.py tests/unit/personal_assistant/` 1023 passed, 2 skipped（无回归）。
  - Visual/Interaction: N/A
- Rollback: revert C2 commit；schema 迁移幂等（列存在则跳过），回退安全。
- Commits: C1=test 红测, C2=feat 实现, C3=docs 本段。
- Next: R2 kernel fork_session(up_to) — store.load 截断 + 复用 _fork_locked + 三组守护测试。

### R2 — kernel fork_session(up_to=M)：as-of-M 截断 + 复用 _fork_locked（轻法 b）

- Context: 决策1 取轻法 (b)（见顶部 Decision）。需让 fork 出的会话带「源在 fork 点 M 的上下文视图」（含源当时压缩态），与源逐字一致，且复用现有架构、避开 boundary/summary 内部引用 re-stamp。
- Decision: ① `jsonl_store.load` 加 `up_to: str|None`——读完 raw_lines 后定位 `type==turn and uuid==up_to` 的行，截断 `raw_lines[:cut+1]`，找不到 raise `SessionNotFoundError`（§0.2 不静默回落），再跑**原样**的 boundary-skip + chain 逻辑。② `manager.load` 透传。③ `runtime.fork_session` 加 `up_to`：有值时 `store.writer.flush()` + `manager.load(up_to=)` 从当前 JSONL 重 materialize（**不读** `_session_histories` 缓存——compact 后它只剩摘要尾、给不出历史 M）→ 交现成已测 `_fork_locked` 复制。无 up_to 时保留 cache-first（5 个现有测试不破）。④ `kernel.fork_session` 替换 stub，委托 `runtime.fork_session(up_to=)`。
- Rationale: 关键正确性——agent 产出 M 时源 JSONL 文件状态 = [0..M]，故对 [0..M] 前缀跑**同一段** store.load = 复现源在 M 的历史文件状态 → as-of-M 视图逐字等于源在 M 的视图。三种压缩态由「截断后 boundary_idx = M 之前最后一个 boundary」自然导出，无需特判：M 在 boundary 后→summary+boundary..M；M 在 boundary 前→该 boundary 被截掉、只应用更早 boundary；未压缩→到 M 全部 turn。
- Evidence:
  - Tests: `tests/unit/test_fork_session.py` 10 passed——三组守护（uncompacted / after-boundary=summary+kept / before-boundary 忽略后续 boundary）+ up_to 未知 message_id raise + up_to fork 独立性/re-stamp/保真 + 原有 5 个 up_to=None 用例不破。
  - Entry: 内核进程内真实 JSONL（manager append + compaction 真写盘 → flush → fork 真读盘截断）。kernel→gateway→IM 完整链在 R3/R6。
  - Frontend State Matrix / Browser QA / Visual: N/A（R2 内核）
  - E2E/Regression: `pytest tests/unit/ tests/contract/` 2616 passed, 1 skipped（store.load/runtime/kernel 改动无回归）。
- Rollback: revert C2；up_to=None 路径完全不变，回退零影响。
- Commits: C1=test 三组守护红测, C2=feat 实现, C3=docs 本段。
- Next: R3 gateway fork RPC handler（binding 定位源 session → kernel.fork_session(up_to) → bind 新会话）。

### R3 — gateway fork RPC handler（session.fork.request → result）

- Context: 决策2——session fork 只能由 gateway 执行（conversation↔session binding 只在 gateway 侧），IM 经一次 WS RPC 委托。需新增 gateway 侧 fork RPC handler。
- Decision: ① `im_connection.py` 加 `SessionForkHandler` 类型 + `session_fork_handler` 注入 + `session.fork.request` dispatch（仿 agent.create / capabilities.resolve；handler 缺失时 raise，避免 IM waiter 永久阻塞）→ 回 `session.fork.result{request_id, node_id, ok, new_session_id?/error?}`。② `main.py` `_build_session_fork_handler(kernel, session_store, agents_getter, channel_name)`：用 `build_conversation_session_key(web_relay, source_conv, agent)` 经 `session_store.get` 定位源 kernel session → `kernel.fork_session(source, up_to=message_id, workspace_root=agent.workspace_root)` → `bind_conversation_session(new_conv → new_session)`。失败回 `{ok:False, error}` 交 IM 回滚（决策5）。channel_name 用 `WebRelayAdapter.name`，agents_getter 指向 live `pipeline._agents`。
- Rationale: 复用既有 WS RPC request-response 模式 + session_keys binding helper（§0.1）。handler 与 binding 定位都在 gateway 层（IM 不直读 gateway 日志，决策约束）。fork handler 的 try/except 不是兜底吞错——是把 fork 失败显式转成 `{ok:False,error}` 经 RPC 上报 IM（决策5 要求 IM 回滚），错误对用户大声可见，非静默。
- Evidence:
  - Tests: 新 `tests/unit/personal_assistant/test_session_fork_handler.py`（定位源→fork(up_to)→bind 新会话 + 入参断言；源缺 binding → ok:False；kernel 抛错 → ok:False 且不建新 binding）；扩 `test_gateway_im_connection_behavior.py::test_im_connection_dispatches_session_fork_request`（真 frame 进 dispatch → session.fork.result 回包带 request_id/ok/new_session_id）。R3 相关 21 passed。
  - Entry: 真 PersistentSessionBindingStore（tmp sqlite）+ 真 WS dispatch（_listen_once 消真 frame）。完整跨进程 live 在 R6。
  - Frontend / Browser / Visual: N/A
  - E2E/Regression: `pytest tests/unit/personal_assistant/ tests/contract/` 776 passed, 1 skipped。
- Rollback: revert C2；新增 dispatch 分支 + 注入参数均向后兼容（handler 为 None 时旧行为不变）。
- Commits: C1=test, C2=feat, C3=docs 本段。
- Next: R4 IM fork 编排（service fork_conversation + route + request_fork_session WS RPC + 在线校验 + 回滚）。

### R4 — IM fork 编排（service + 路由 + WS RPC + 在线校验 + 回滚）

- Context: 决策2/5——IM 同步编排 fork：建会话 + 复制展示历史在 IM 本地，session fork 经一次 WS RPC 委托 gateway；在线校验前置 + 失败原子回滚（绝不留无记忆空壳）。
- Decision: ① `WebIMService.fork_conversation`（async）做编排，gateway 触达用注入的两个 async 委托 `check_agent_online(agent_id)` / `request_fork(...)`——使 service 不依赖 WS/node、可纯单测。流程：get_conversation_for_owner（None→ForkNotFoundError 404）→ direct_kind=="user-agent"（否则 ForkValidationError 400）→ 定位 fork_message_id（须 sender_type=agent + completed + 有 kernel_message_id，否则 400）→ check_agent_online（否则 AgentOfflineError 409，**建会话前**）→ create_conversation(title=agent名, [user,agent]) → 复制 history[0..M]（content+attachments+tool_calls+token_usage+kernel_message_id 经 repo create_message，thinking 经 append_thinking_segment 逐段）→ request_fork 委托 → 失败/None→delete_conversation 回滚 + ForkDelegationError 502。定义 4 个 ForkError 子类映射 404/400/409/502。② `gateway_handler.request_fork_session`（仿 request_agent_capabilities：waiter + push session.fork.request + wait_for）+ `_handle_session_fork_result`（resolve waiter）+ dispatch + waiter dict。③ 路由 `POST /conversations/{id}/fork`（async，注入 online-check=is_connected(profile.node_id) + request_fork=request_fork_session(profile.node_id)，异常映射状态码）。
- Rationale: 复用 create_conversation/delete_conversation(级联删消息)/list_messages/append_thinking_segment/WS RPC 模式（§0.1）。online 校验前置 + RPC 失败回滚满足决策5「绝不空壳」。委托回调注入让 service 与 WS 解耦、可单测全部分支（含回滚）。service 的 except→rollback→raise 不是吞错，是清理后大声重抛。
- Evidence:
  - Tests: `tests/im_service/unit/test_fork_conversation.py` 7 passed（复制到 M+委托入参；离线不建会话；RPC ok:False 回滚；超时 None 回滚；旧气泡无 kernel id 拒；用户消息拒；跨租 404）；`tests/im_service/integration/test_fork_api.py`（路由 404 + auth）；`test_gateway_handler.py` 不回归。R4 相关 52 passed。
  - Entry: HTTP route（真 TestClient，404/auth）+ service 真 sqlite repos。完整 live（在线 fork→真栈带记忆 + 离线 409）在 R6。
  - Frontend / Browser / Visual: N/A（R4 后端）
  - E2E/Regression: `pytest tests/im_service/ tests/contract/` 499 passed, 1 skipped。
- Rollback: revert C2；新增端点/方法/RPC 均新增，向后兼容。
- Commits: C1=test, C2=feat, C3=docs 本段。
- Next: R5 前端 fork 按钮 + mutation + toast + 跳转（vitest + 真实浏览器验收）。

