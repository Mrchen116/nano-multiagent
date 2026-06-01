# feat-393: heartbeat/cron 结果真正回发到 IM 会话 — 技术方案

> 对齐: spec.md v1

> Unit branch: `unit/feat-393` (will be created by orchestrator)

## Changelog

## 现状分析

### 涉及范围

- `src/personal_assistant/scheduler/heartbeat_scheduler.py` — `HeartbeatScheduler.tick` 评估 `HEARTBEAT.md`、`_submit_run` 现在**每 tick 现造一个 fresh kernel session** 并 fire-and-forget（提交完返回 `HeartbeatRunRecord`，不等终态、不取回复、不投递）。本 unit 改：在 agent 专属稳定 session 上跑、等终态、把结果接入流式投递。删除 fresh-session 旁路。
- `src/personal_assistant/main.py` —
  - `PollingHeartbeatRunner`（~757-820）后台 tick 循环 + `request_tick`；
  - `_KernelClientShim`（~1237）把 Kernel 适配成 scheduler 的 `kernel_client`（`create_session` / `submit_message` / `append_message`）；
  - `run_context_store: dict[run_id → {conversation_id, message_id, agent_id, kernel_session_id}]`（~1433）是流式桥的运行上下文；
  - `_build_relay_lifecycle_callback`（~1810）在 `accepted` 阶段用 `message.external_chat_id` **播种** `run_context_store`——但**仅对带 `relay_task_id` 的 relay 消息生效**；
  - `_build_kernel_event_observer`（~1909）读 `run_context_store[run_id]` 把 kernel 事件翻成 `node.streaming_delta`（`turn_start`→建占位消息 / `message_delta` / `message_completed` / `tool_call_*`）。
- `src/personal_assistant/gateway/inbound_pipeline.py` — `_await_terminal_run_async`（~639）消费 `kernel.stream` 直到终态、取 `assistant_message` 内容 + 调 `_kernel_event_observer`。heartbeat 要复用这套消费逻辑。
- `src/IM/ws/gateway_handler.py` — `_handle_streaming_delta`（~732）：`turn_start` 当前**必须给 `conversation_id`**（`_require_text`），调 `EventBridge.on_turn_start` 建占位消息、回传 `message_id`；`resolve_send_message_target` / `_find_or_create_direct_conversation` / `_find_canonical_direct_conversation`（~1364-1508）已能把 `to=user_id` 解析成 (owner,agent) 的 **canonical（最旧）直聊**，没有就建。
- `src/IM/application/event_bridge.py` — `on_turn_start` / `on_message_delta` / `on_message_completed` 落库 + 向 owner 扇出。

### 既有约束

- 产品包（`personal_assistant`）只能 import `agent.sdk`，不得碰 `agent.core` / `agent.platform` 内部（AGENTS.md 依赖方向硬规则）。
- IM 不依赖 `agent`，只与用户和 `personal_assistant` 交互。heartbeat 投递必须经 gateway↔IM 既有 WS 协议，不能让 IM 反向调内核。
- IM `events` 表外键硬引用 `messages` 表——任何"上报"必须基于真实 message 行（这正是 M138 `node.report` 旁路崩溃的根因，已被 refactor-387 删除）。
- 对 `web_relay`，`OutboundRouter.send_text` → `WebRelayAdapter.send` 是 **no-op**（只 append 本地 `self.sent`）；IM 里用户可见的 agent 消息**完全由流式 `node.streaming_delta` 创建**。所以"让汇报出现在会话"＝走 `node.streaming_delta`。

### 可复用能力

- **流式桥**（`run_context_store` + `_build_kernel_event_observer` + IM `_handle_streaming_delta`）——普通聊天的消息创建机制，heartbeat 走同一条，**用**（heartbeat 侧加 origin 门控）。
- **`_await_terminal_run_async`** 的事件消费循环——**抽出/复用**，避免 heartbeat 重写一套流式消费。
- **IM `_find_canonical_direct_conversation`**（`to=user_id`→最旧直聊，无则建）——canonical 直聊解析的服务端逻辑，`turn_start` 扩展时**复用**。
- `RunOrigin.HEARTBEAT`（`_KernelClientShim.submit_message` 已映射）+ `auto_mode_gate` 对无人值守的处理——**用**。

### 相关历史

- **M138**（commit 79eda8b2）：立意做 heartbeat→IM 汇报，但自造 `node.report`→events 旁路，payload 缺 `node_id` + 合成 FK，真实 IM 上从未生效；集成测试用不强制外键的桩给了假绿。本 unit 的**硬约束**：测试必须打真实 FK 强制的 message 路径。
- **refactor-387**（`fix-heartbeat-im-report-progress.md`）：删除畸形 `node.report` heartbeat 桥 + 双侧健壮性加固（IM `_handle_report` 不再因畸形 payload 关连接；gateway 收 `type=error` 帧不再 raise 触发重连），并把"真正做对回发"单列为本 unit。heartbeat run 的 async 提交路径已修好、scheduler 能正常提交 run。

## 架构总览

核心思路一句话：**heartbeat run 走与普通聊天完全相同的流式消息创建路径（`node.streaming_delta`），但消息气泡惰性创建——只在产生真实内容时才建，NO_REPLY/空则零痕迹；目标会话为 (owner,agent) 的 canonical 直聊，惰性解析/创建。**

Before（坏）：

```
scheduler.tick → _submit_run(fresh session) → submit → 返回 run_id  ❌ 不等结果
   M138 曾试图: 结果 → node.report(合成 conv/msg id) → IM events 表 FK 崩 → 从未生效
```

After（本 unit）：

```
scheduler.tick (due)
  └─ 在 agent 专属稳定 :heartbeat session 上 submit(origin=heartbeat)
       └─ 复用 _await_terminal_run_async 消费 kernel.stream
            └─ 事件 → 共享 kernel_event_observer（heartbeat 门控）
                 ├─ 首条真实内容前：不发 turn_start（无 IM 痕迹）
                 ├─ NO_REPLY/空：永不发 turn_start → 静默
                 └─ 有真实内容：
                      turn_start{to_user_id=owner}  ──ws──▶ IM
                        IM: 解析/惰性创建 canonical 直聊
                            EventBridge.on_turn_start → 建真实 message 行
                            ack{conversation_id, message_id}  ◀──
                      message_delta / message_completed (复用普通流式) ──▶ IM 扇出给 owner
```

普通聊天路径**完全不动**（仍 eager 占位气泡）。heartbeat 与普通聊天的差异仅在"有内容才建气泡"——这是 heartbeat 可静默的本质决定的；真实汇报的流式呈现与普通消息逐字一致。

## 关键决策

### 决策 1: 汇报走共享流式路径（node.streaming_delta），不另起投递通道

- **选择**: heartbeat run 的事件经与普通聊天相同的 `kernel_event_observer` → `node.streaming_delta` → IM `EventBridge`，由 IM 创建真实 message 行。
- **理由**: 对 web_relay，流式就是消息创建机制本身；走同一条 = "平时的对话怎么样就是怎么样"，且天然基于真实 message 行（无 FK 问题）。
- **拒绝**: ①M138 的 `node.report`→events 旁路（合成 FK，必崩，已删）；②`send_agent_message`/`/internal/dispatch` dispatch 路径——它建的是"完整消息、无逐字流式"，且 `_sync_direct_session` 会把 canonical 直聊回绑到 heartbeat 的 origin session，劫持普通聊天的会话绑定。
- **风险**: heartbeat 复用普通流式 observer，需保证不污染普通聊天行为（靠 origin 门控隔离）。

### 决策 2: 消息气泡惰性创建（有真实内容才发 turn_start），仅作用于 heartbeat

- **选择**: heartbeat（`origin=heartbeat`）的 observer 推迟 `turn_start` 到第一条非空、非 `NO_REPLY` 的 assistant 内容到达；普通聊天保持 eager 占位不变。
- **理由**: heartbeat 常态是"无事可报"，eager 建气泡会每个空 tick 冒空泡再撤，最吵；惰性建泡让静默 tick 零 IM 痕迹。普通直聊总会回复、且 eager 占位兼作 `/sync` "running 未完成"标记，不动它可把改动面和回归风险收窄（用户已确认只改 heartbeat）。
- **拒绝**: 把惰性建泡套到普通聊天——会动 `/sync` 语义 + 需补普通聊天回归，风险/改动面更大。
- **风险**: heartbeat 流式首块延迟（要等内容判定）；NO_REPLY 检测需在建泡前完成（见决策 5）。

### 决策 3: 目标会话 = (owner,agent) canonical 直聊，由 turn_start 惰性解析/创建

- **选择**: 扩展 IM `_handle_streaming_delta` 的 `turn_start`：除现有 `conversation_id` 模式外，新增接受 `to_user_id`（owner）模式——服务端复用 `_find_or_create_direct_conversation` 解析 canonical（最旧）直聊、没有则建，回传 `conversation_id` + `message_id`。gateway 据回传更新 `run_context_store`，后续 `message_delta`/`completed` 用之。owner 取 `config.node.user_id`。
- **理由**: 惰性建泡意味着"首条内容到达那一刻才需要会话 id"——此刻一并解析/创建，既满足"无事不创建空会话"、又满足"首次有事自动新建直聊"。复用服务端既有 canonical 解析逻辑，gateway 不预解析、不加额外 round-trip。
- **拒绝**: ①gateway 预解析（需在 run 前拿 id，与"静默 tick 不建会话"冲突）；②新增独立 resolve 帧（多一次往返，turn_start 已是首个必发帧，顺带解析最省）。
- **风险**: `config.node.user_id` 未绑定（node 未 bind owner）时无 owner 可投——此时 heartbeat run 仍执行但不投递（记日志，见决策 6）。

### 决策 4: heartbeat run 跑在 agent 专属稳定 `:heartbeat` 隔离 session

- **选择**: 每个 agent 一条稳定复用的 `:heartbeat` kernel session（跨 tick 复用，承载 standing-task 上下文连续性），不再每 tick 现造。
- **理由**: 隔离 session 不需要预解析 canonical 会话即可起跑（配合决策 3 惰性解析投递目标）；与普通聊天的用户会话 session 解耦，heartbeat 的触发 prompt/历史不混入用户任务单聊的 kernel 上下文。
- **拒绝**: ①每 tick fresh session（现状，无上下文连续性、且 M138 据此走了死胡同）；②跑在 canonical 直聊的 session 上（需预解析会话 id，与"静默不建会话"冲突，且把 heartbeat 触发 prompt 混进用户任务单聊上下文）。
- **风险**: canonical 直聊的 kernel session 不持有 heartbeat 汇报历史——用户在该直聊追问"你刚那条汇报"时，agent 上下文里没有该 turn（已知限制，记入风险段）。

### 决策 5: NO_REPLY / 空内容静默，复用既有 NO_REPLY 约定

- **选择**: 沿用现有 `InboundPipeline._is_no_reply_token`（`NO_REPLY`）+ 空内容判定。observer 在发 `turn_start` 前检查首条 assistant 内容：是 `NO_REPLY` 或空 → 不建泡、不投递；否则正常流式。
- **理由**: HEARTBEAT.md prompt 已含"无事可报就闭嘴"，agent 产 `NO_REPLY` 即沉默信号；复用既有约定不造新词。
- **拒绝**: 新增 heartbeat 专属哨兵——重复造轮子。
- **风险**: 需保证 NO_REPLY 在建泡前可判定（kernel `assistant_message` 事件 content 为完整文本，可在首个该事件处判定，可行）。

### 决策 6: 投递行为继承普通流式路径，不单造重试/持久化

- **选择**: heartbeat 投递走与普通聊天相同的 `node.streaming_delta`/ack 路径，送达/失败/重连行为完全继承；run 执行失败与投递失败分开记日志，不做持久化失败队列/离线补投。
- **理由**: 用户原话"平时的对话怎么样就是怎么样"。可靠通知是另一种语义，不压给周期心跳；下个 due tick 基于最新状态重评、该报再报。
- **拒绝**: 持久化失败队列 + 重连补投（更大工程，spec 已列为非目标）。
- **风险**: 断线期间产生的汇报会丢这一条（可接受，周期机制自然补位）。

## 接口与数据流

**gateway → IM 协议扩展（`node.streaming_delta` / `turn_start`）**：
- 现有：`{kind:"turn_start", conversation_id, agent_id, agent_user_id?}` → ack `{message_id}`。
- 新增模式：`{kind:"turn_start", to_user_id:<owner>, agent_id}`（无 `conversation_id`）→ IM 复用 `_find_or_create_direct_conversation(owner, agent, "user-agent")` 解析 canonical/建会话 → `EventBridge.on_turn_start` → ack `{conversation_id, message_id}`。
- 两模式互斥：给 `conversation_id` 走旧路（普通聊天不变）；给 `to_user_id` 走新路（heartbeat）。

**heartbeat run 上下文播种（gateway 侧）**：
- heartbeat run 提交后，在 `run_context_store[run_id]` 写入 `{to_user_id:<owner>, agent_id, conversation_id:"", message_id:""}`（heartbeat 变体：先无 conversation_id）。
- `kernel_event_observer` 对 heartbeat run：
  - 收到首条真实内容（非 NO_REPLY/非空）才发 `turn_start{to_user_id}`；用 ack 回传的 `conversation_id`/`message_id` 回填 store；
  - 后续 `message_delta`/`message_completed`/`tool_call_*` 与普通流式一致；
  - run 终态前从未产生真实内容 → 不发任何 `node.streaming_delta` → 静默。

**scheduler / runner（gateway 侧）**：
- `HeartbeatScheduler` 持有 agent→稳定 `:heartbeat` session 的解析（首次创建、之后复用）。
- `tick` 对每个 due agent：submit(origin=heartbeat) → 复用 `_await_terminal_run_async` 等价的消费逻辑驱动 observer → 终态返回。`HeartbeatTickSummary`/`HeartbeatRunRecord` 保留用于可观测。
- owner 来源：`config.node.user_id`；为空则跳过投递（run 仍执行，记日志）。

**数据结构**：`run_context_store` 值新增可选 `to_user_id` 字段；其余沿用。

## 风险与回退

- **NO_REPLY 判定时机**：若 kernel 流式把真实内容拆成多个 delta 且首块无法判定 NO_REPLY，可能误建泡。缓解：以 `assistant_message` 事件的完整 content 为判定点（现有事件即完整文本），在该点之前不发 turn_start。
- **canonical 直聊语义漂移**：`_find_canonical_direct_conversation` 取最旧；若 owner 删了最旧直聊，canonical 会变。属既有 IM 行为，本 unit 不改，接受。
- **canonical 会话 kernel 上下文不含 heartbeat 汇报历史**（决策 4 风险）：已知限制；如需可后续 unit 把汇报 append 回 canonical session。本 unit 接受。
- **owner 未绑定**：`node.user_id` 为空 → 不投递、记日志，run 不报错。
- **普通聊天回归**：决策 2/3 要求普通聊天路径零行为变化。缓解：observer 的 heartbeat 门控以 `origin=heartbeat` 为唯一开关；补普通聊天流式不回归的断言。
- **回滚**：本 unit 改动集中在 heartbeat 提交/消费 + observer 的 origin 分支 + IM turn_start 的 to_user_id 分支。`git revert` unit 分支即恢复到 refactor-387 收口态（heartbeat 正常执行、不投递、连接健康）。

## Runbook for Reviewer

| 服务 | 停止命令 | 启动命令 | 健康检查 |
|---|---|---|---|
| IM 服务 | `kill "$(cat .im.pid)" 2>/dev/null; rm -f .im.pid` | `IM_JWT_SECRET="demo-jwt-secret-for-feat340-testing" PYTHONPATH=src python -m uvicorn IM.app:app --host 127.0.0.1 --port "$IM_PORT" > .im.log 2>&1 & echo $! > .im.pid` | `curl -s http://127.0.0.1:$IM_PORT/ ` 返回 200；WS `/im/ws/gateway` 可连 |
| Gateway（个人助手） | `kill "$(cat .gateway.pid)" 2>/dev/null; rm -f .gateway.pid`（须 `--foreground` 起） | `PYTHONPATH=src python -m personal_assistant.main --config "$WT_CFG" --im-service-url "http://127.0.0.1:$IM_PORT" --foreground --auto-bind > .gateway.log 2>&1 & echo $! > .gateway.pid` | `.gateway.log` 出现 `auto-bound to IM`；heartbeat tick 后 IM 直聊出现汇报消息 |

> 验收建议：在某 agent 的 `workspace_root/HEARTBEAT.md` 写 `interval: 10s` + 一条明确会产出的指令（如"报告当前时间"）验"有内容→直聊出现汇报"；再写一条恒静默指令验"无事→无新消息"。worktree e2e 用 `scripts/e2e-up.sh` 自动分配端口/隔离 config/auto-bind。

## Milestones

单 M1：本 unit 是一个内聚的垂直切片——heartbeat 提交/消费（scheduler+runner）、流式 observer 的 origin 门控、IM `turn_start` 的 `to_user_id` 解析三处强耦合（gateway 发新 turn_start 形状，IM 必须能解析），无法真并行；改动量预估 < 800 行。不满足任一拆分硬触发条件，默认单 M1。

| ID | 标题 | 依赖 | 并行组 | 范围 | 退出标准 |
|---|---|---|---|---|---|
| feat-393-M1 | heartbeat-im-delivery | — | A | `src/personal_assistant/scheduler/heartbeat_scheduler.py`、`src/personal_assistant/main.py`（runner/observer/run_context_store 播种）、`src/IM/ws/gateway_handler.py`（turn_start 的 to_user_id 分支）、`src/IM/application/event_bridge.py`（如需）、相关 tests | `[reviewer]` heartbeat 有内容时直聊出现 agent 汇报消息（Req-定时结果以 agent 消息出现 / 全部 Scenario）；`[reviewer]` 无事可报时直聊无新消息（Req-本轮无内容则静默）；`[reviewer]` 多单聊时落最旧那条、其它不受污染 + 首次无直聊自动新建（Req-canonical 直聊 / 两 Scenario）；`[reviewer]` 用户只见汇报、不见内部触发指令（Req-触发指令不可见）；`[worker]` 集成测试打**真实 FK 强制**的 IM message 路径，断言 heartbeat 有内容时建真实 message 行、静默 tick 零 message（不得用不强制外键的桩）；`[worker]` 普通聊天流式路径无回归（eager 占位/`/sync` 行为不变）的断言通过；`[worker]` `pytest -m "not e2e"` 全绿（含 IM_service）；`[worker]` fresh-session 旁路已删、`origin=heartbeat` 门控为唯一开关 |
