# bugfix-426: 运行中发送的用户消息无法 steer 进当前 run

## Relations

- Related:

## 原始报告

> http://127.0.0.1:54213/chat/b3a4228fd4444b189d719eaf7328bfec 为啥我给他发了新消息，但是它还是继续不停进行了多轮工具调用，用户消息不是在下一轮工具调用就带进去了吗

补充追问：

> 之前有unit修这个问题吧？是没修好？

## 澄清记录

- Q1: 运行中发消息"被带进下一轮"的边界——A 只在当前工具批次跑完、下一次 LLM 调用前注入（不掐断正在跑的工具）；B 注入并中断当前轮剩余工具。
  A(原话): A
  Agent 解读: 目标行为 = round-boundary 注入（复用内核已有 drain_pending 通道）。"中断正在跑的工具"属于 abort 语义（现有 /stop / priority=now），不在本 unit 范围。
- Q2: 修复范围覆盖哪些产品入口——只 IM，还是 IM+CLI 都恢复？
  A(原话): IM+CLI
  Agent 解读: 两条路径同源——refactor-387 删 SDK `priority` 参数 + HTTP API 时，IM(Gateway inbound) 和 CLI(repl_runtime) 的 priority=next 注入双双被架空，现 `inject_pending_message` 仅 background_tasks 在用。本 unit 同时恢复两端。
- Q3: 当前 run 未结束时连发多条消息，期望按序全注入还是只取最新一条？
  A(原话): 按序全注入
  Agent 解读: FIFO 一条不丢、不乱序（内核 pending 队列即 SimpleQueue，drain_pending 一次性按序全取，语义天然匹配）。
- Q4: 这能力定位为 SDK 内核级能力（任何 consumer 复用），以后新增产品也能直接用，对吧？
  A(原话): 这个能力是sdk内核能力对吧，以后新增产品也能用
  Agent 解读: 是。机制本就在 agent.core（RunController/AgentLoop/RunsRegistry），bug 是消费侧接线丢失。修复点定在 `agent.sdk` 对外面——把注入意图暴露成干净的内核级 affordance，IM/CLI 及未来 consumer 统一复用，禁止 per-product 私有实现。IM/CLI 仅作为本 unit 的两个验证 consumer。

## 现象与复现

用户在 agent 一个 run 正进行多轮工具调用期间发送新消息，期望该消息在当前 run 的下一轮 LLM 调用前被带进上下文（CC 式 steering），从而调整 agent 行为。实际：新消息被晾在队列里，直到当前 run 完全跑完才作为**新的一个 run** 被处理——agent 对运行中发来的消息视而不见，继续跑完所有工具轮次。

**真实复现时间线**（session `sess_b098243cf95daddd`，IM 会话 `b3a4228f…`，证据见 `~/Repos/LLM_PROXY/logs/session/2026-06-23_09-21-19_167_sess_b098243cf95daddd/` 与 IM 库 `messages` 表）：

| 时间(UTC) | 事件 |
|---|---|
| 01:21:19 | user「上网搜下田园之歌」→ run1 启动，web_search ×3 全部超时 |
| 01:23:19 | run1 放弃，回「网络搜索一直超时」（finish=stop，run1 结束）|
| 01:28:05 | user「再试试ddgs」→ run2 启动，bash ddgs + web_fetch 循环约 30 轮 |
| **01:28:52** | **user「不是，我想让你直接用web_search工具」**（run2 正在跑工具中途发出）|
| 01:28:52–01:35 | run2 对该消息视而不见，继续 ddgs/web_fetch 循环约 6 分钟 |
| **01:35:34** | 该消息**首次进入 LLM 上下文**（run3 第一轮请求才出现），比发出晚 **6 分 43 秒** |
| 01:35:35 | run3 回「好的，我直接用 web_search 再试一次」 |

复现步骤：对接入 IM 的 agent 发一条会触发长工具链（如多次 web_search/web_fetch）的消息；在其工具循环执行期间再发一条新消息；观察新消息在当前 run 结束前是否进入上下文。期望：下一轮 LLM 调用前注入；实际：等到下一个 run 才处理。

## 影响范围

- **受影响产品**：个人助手 Gateway（IM 聊天，所有 agent 会话）+ Coding CLI（REPL 运行中输入）。两者均无法在运行中 steer agent。
- **严重度**：功能性缺陷，非数据损坏。用户在 agent 跑长任务/卡在慢工具/方向跑偏时，无法及时干预纠偏，只能干等当前 run（含所有慢工具与超时重试）整个结束——上例等待达 6 分 43 秒。
- **无数据损坏**：消息不丢失，只是延迟到下一个 run 才被消费（FIFO 队列保序）。

## 根因分析（RCA）

**直接原因**：消费侧链路断裂。运行中用户消息从未被喂进内核已有的 round-boundary 注入通道：

- 内核侧机制完好：`RunController` 持 pending `SimpleQueue`；`AgentLoop` 每轮 LLM 调用前 `drain_pending()` 注入；`RunsRegistry` 暴露 `inject_pending_message` / `get_active_run_id` / `interrupt`（`src/agent/core/agent/loop.py`、`run_control.py`、`src/agent/core/runs/registry.py`）。
- 但 `inject_pending_message` 当前全仓**仅 1 个调用方**：`src/agent/platform/background_tasks/wiring.py`（后台任务完成通知，先判 `get_active_run_id` 有活跃 run 才注入——这正是缺失的正确范式）。
- Gateway `src/personal_assistant/gateway/inbound_pipeline.py` 记着 `_active_runs[session]`，但只用于 `/stop`（abort），**从不调 `get_active_run_id` + `inject_pending_message`**；用户消息一律走 `run_queue.submit()` 进 per-session FIFO + `asyncio.Lock` 串行，只能等当前 run 跑完才开新 run。
- CLI `src/coding_cli/runtime/repl_runtime.py` 同样不再有注入路径；SDK 的 `priority` 参数已不存在。

**为什么这种错能进来（原始设计意图追溯）**：

- steering 能力本是齐的。commit `ecdb21b9 feat(agent): parallel tool execution and round-boundary message injection` 引入 `inject_pending_message` / `interrupt` / `get_active_run_id`，并**接在 HTTP API 上**：`priority='next'` 注入活跃 run、`priority='now'` 中断。commit `244c73f8 feat(cli): priority='next' injection` 给 CLI input loop 也接了 priority=next。即「运行中发消息 steer 进下一轮」当时**可用**。
- 回归引入点：commit `bc12a628 feat(refactor-387/M4/R3): 删除 agent/platform/http_api/ 整目录`（unit refactor-387，内核由独立 HTTP server 改为进程内库）。该重构删 HTTP API + SDK `priority` 参数时，把「用户消息 → `inject_pending_message`」的**唯一两个消费者（HTTP priority=next、CLI priority=next）一并删除**，而新的进程内投递路径（Gateway inbound / CLI repl_runtime）未重新接线。`background_tasks` 因走独立通道幸存，掩盖了用户侧链路已断。
- **必须保住的不变量**：注入只发生在 run 活跃时（`get_active_run_id` 非空）；run 空闲时仍走正常 submit 新 run；注入消息 FIFO 保序；不破坏现有 `/stop`（abort）语义。
- **防再发着力点**：恢复后补端到端测试覆盖「运行中发消息 → 下一轮注入」，防止后续重构再次悄悄断链（本次正是缺这层 e2e 守护，HTTP 删除时无测试报红）。

## 目标行为与验收

> 用户可观察口径。下游 reviewer 逐条走查；design 阶段投影为对内核/Gateway/CLI 契约层的 delta-spec。

### Requirement: 运行中发送的消息在当前 run 的下一轮被带进上下文

#### Scenario: 工具循环中途发消息，下一轮即被消费
- **GIVEN** agent 正在一个 run 内连续执行多轮工具调用
- **WHEN** 用户在该 run 仍在执行时发送一条新消息
- **THEN** 该消息在当前 run 的**下一次 LLM 调用前**被带进上下文，agent 的后续回应据其调整方向
- **AND** 无需等待当前 run 整体结束、也不另起一个新 run 才理睬

#### Scenario: 不掐断正在执行的工具
- **GIVEN** 当前轮有工具正在执行（含慢工具/超时重试）
- **WHEN** 用户在此期间发送新消息
- **THEN** 正在执行的工具批次照常跑完，不被强行中断；消息在该批次结束后的下一轮 LLM 调用前注入

#### Scenario: 一个 run 内连发多条，按序全注入
- **GIVEN** 当前 run 正在执行
- **WHEN** 用户在 run 结束前连续发送多条消息
- **THEN** 这些消息按发送顺序全部进入上下文，一条不丢、不乱序

#### Scenario: 空闲时发消息仍正常开新 run
- **GIVEN** 当前没有活跃 run
- **WHEN** 用户发送一条消息
- **THEN** 照常作为新 run 处理，行为与现状一致（注入路径不影响空闲态）

### Requirement: 注入能力恢复为 SDK 内核级 affordance，consumer 统一复用

#### Scenario: 任一 agent.sdk consumer 复用同一注入能力
- **GIVEN** 一个产品通过 `agent.sdk` 接入内核
- **WHEN** 它需要在 run 运行中投递用户消息
- **THEN** 经由 SDK 对外暴露的注入能力即可获得「下一轮注入」行为，无需自行实现注入逻辑（IM 与 CLI 均走同一能力，未来新增产品同理）

### Requirement: IM 与 CLI 两端均恢复该能力

#### Scenario: IM 聊天运行中 steer
- **WHEN** 用户在 IM 会话里于 agent 运行中发送消息
- **THEN** 表现符合上述「下一轮被带进上下文」

#### Scenario: CLI REPL 运行中 steer
- **WHEN** 用户在 Coding CLI 中于 run 执行期间输入并提交一条消息
- **THEN** 该消息在当前 run 下一轮被注入，而非排到队尾等当前 run 结束

## 范围与非目标

- **非目标**：中断/掐断正在执行的工具（abort 语义，归现有 `/stop` / `priority='now'`，本 unit 不动）。
- **非目标**："只取最新一条/后发覆盖先发"语义——已定为 FIFO 按序全注入。
- **非目标**：群聊特有的 @ 路由/多 agent 投递行为变更——本 unit 只恢复"运行中消息进当前 run 下一轮"的通用注入链路。
- **非目标**：注入消息的前端"已接收待处理"特殊 UI 提示——消息照现状即时显示在会话即可。

## 修复方向

> 高层方向，行级实现在 milestone 内。

把「用户消息 → 内核 round-boundary 注入通道」恢复为 `agent.sdk` 对外暴露的内核级 affordance（机制本就在 `agent.core`，只需在 SDK 面重新接出），让 IM/CLI 及未来 consumer 统一复用；复用内核既有 `get_active_run_id` + `inject_pending_message`（沿用 `background_tasks/wiring.py` 已验证的范式：有活跃 run 则注入、否则 submit 新 run）：

- **Gateway**（`inbound_pipeline.py`）：投递用户消息前先 `get_active_run_id(session)`，活跃则 `inject_pending_message` 并直接返回，不再无脑 `run_queue.submit`。
- **CLI**（`repl_runtime.py` / SDK 面）：恢复运行中输入的注入路径（等价旧 `priority='next'`），SDK 对外面按 design 决定如何重新暴露该意图（参数/独立方法）。
- **测试守护**：补 IM 与 CLI 的端到端测试，覆盖「运行中发消息 → 下一轮注入 / 连发保序 / 空闲态开新 run / 不掐工具」，防回归再发。
- 实现层选型（SDK 面如何暴露注入意图、Gateway 注入与 run 生命周期的并发时序、CLI 输入循环改造）留给 `change-design-author`。
