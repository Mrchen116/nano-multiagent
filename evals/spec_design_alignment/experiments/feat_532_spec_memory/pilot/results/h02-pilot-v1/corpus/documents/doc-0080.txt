# bugfix-418: subagent(agent 工具)跨事件循环崩溃且异常拖垮整个 Gateway

## Relations

- Closes: #117
- Refs: #119（结构性「关键路径真 LLM e2e 套件 + 清单」拆为独立后续 unit 另立项，本 unit 只随 bug 加一条 subagent 回归 e2e）
- Related: feat-337-cc-background-subagents（引入 subagent 执行模型的原始 unit）

## 原始报告

> ## 现象
>
> IM 上让 agent 调用 `agent` 工具派生 subagent（例：description="Tell a joke" + subagent_type="default..."），subagent 启动即失败，工具结果返回：
>
> ```
> Agent failed.
>
> Error: <asyncio.locks.Event object at 0x... [unset]> is bound to a different event loop
>
> agent_id: ae85548875650f8e5
> ```
>
> 子 agent 功能当前**完全不可用**。
>
> ## 复现
>
> 1. 起 IM + Gateway（worktree e2e 或主仓均可）
> 2. 前端发消息让 agent 派一个 subagent（前台 `agent` 工具调用）
> 3. 工具卡返回上述 event-loop 错误
>
> 实测 session：`sess_05d743275831dab9`，proxy log `2026-06-21_19-50-16_696-req`。
> （附带：第一次调用若漏传 `subagent_type` 会先报 `either category or subagent_type is required for new agent`——那是入参校验，补上 subagent_type 后才暴露本 event-loop bug。）
>
> ## 根因（已确证部分 + 待定位部分）
>
> **执行模型冲突（已确证）**：`agent` 工具的前台 subagent 经
> `src/agent/platform/tools/builtins/agent.py:_run_subagent_turn_sync`（约 :623）在
> `ThreadPoolExecutor` 工作线程里用 `asyncio.run(runtime.run(...))` **起一个全新事件循环**执行，
> 但传入的 `runtime` 是**与主 agent 共享的同一实例**。于是 subagent 新循环里 await 到某个
> **绑定在 kernel 主循环上创建的 asyncio 原语**（Event/Lock/Queue），触发
> `bound to a different event loop`。
>
> **具体那个 Event 待定位**：排查中已**排除** `StreamingToolExecutor._sibling_event`
> （`core/agent/tool_executor.py:71`）——它是 per-run 在 subagent 自己的循环内新建、且只 `.set()`
> 从不 `.wait()`，不跨循环。强嫌疑指向 kernel 级单例持有的循环绑定对象，候选：
> - `core/runs/registry.py:158` `self._async_loop = asyncio.new_event_loop()`（RunsRegistry 专用循环）
> - `core/agent/runtime.py:166` `self._session_locks`（按首次使用的循环 lazy 建 Lock）
> - `platform/permissions/broker.py:148` `asyncio.get_event_loop()`
> 需用最小复现脚本逐一坐实哪个 Event 真正在 subagent START 阶段被 await。
>
> ## 影响范围 / 与 bugfix-417 的关系
>
> - **pre-existing，与 bugfix-417 (#110, PR #116) 无关**：`agent.py` 在 `main` 与 `unit/bugfix-417`
>   **逐字相同**，PR #116 既未引入也未触碰 subagent 执行路径。
> - bugfix-417 的验收聚焦 bash 前台/后台双通道，**未覆盖 subagent 工具**——本 bug 从该盲区漏出。
>
> ## 升级证据：subagent 异常会连带拖垮整个 Gateway
>
> - 触发那次 subagent event-loop 报错（19:50:13）后，Gateway **进程仍存活**（pid 仍在、STAT=S、未崩溃），但 gateway.log 自该时刻起**再无任何输出**。
> - IM 侧查 node 状态（`GET /im/v1/nodes`）：`status: offline`、`last_error: heartbeat_timeout`、`last_heartbeat_at` 此后心跳停发。
> - 即 subagent 的跨循环异常**没有被隔离在该工具调用内**，而是冒泡停掉了 Gateway 的 heartbeat（极可能连同 channel relay）协程——进程在、对外彻底失联，前端显示 Gateway 离线，需重启才能恢复。
>
> ## Suggested Severity
>
> major → 视为接近 blocking（单次子 agent 调用即可使节点离线、需重启恢复）。

（完整原始报告见 GitHub issue #117，含测试覆盖缺口分析与结构性 e2e 建议。）

## 澄清记录

- Q1: 本 unit 的范围边界怎么定？issue 提了三件事——①修 event-loop 根因让 subagent 可用；②修故障隔离（工具异常绝不冒泡打挂 Gateway 的 heartbeat/relay）；③建「关键路径真 LLM e2e 套件 + 清单」。
  A(原话): "①+②+本bug一条e2e回归"
  Agent 解读: 本 unit = 修两个根因（执行模型 + 故障隔离）+ 随本 bug 加一条「派 subagent 跑通一轮」的真 LLM e2e 回归守卫；③整套关键路径 e2e 套件（发消息/bash前台后台/subagent/stop/cron/heartbeat 各一条经 Gateway 的 e2e）拆为独立后续 unit 另立项，本 unit 不做。

## 现象与复现

**环境**：IM + Gateway（worktree e2e 或主仓均可），真 LLM provider（本地代理 `127.0.0.1:4000`）。前台 `agent` 工具调用路径。

**步骤**：
1. 起 IM + Gateway。
2. 前端发消息让某 agent 调用 `agent` 工具派一个**前台**（`run_in_background=false`，默认）subagent，传齐 `description` + `subagent_type`。
3. 工具卡返回 `Agent failed. Error: <asyncio.locks.Event object ...> is bound to a different event loop`。

**期望**：subagent 正常启动、跑完一轮、把结果作为工具结果返回给父 agent；子 agent 失败时也只在工具边界内返回失败，不影响 Gateway 存活与在线。

**实际**：subagent 启动即崩；且该次崩溃后 Gateway 的 heartbeat 停发，节点对外离线（`status: offline` / `last_error: heartbeat_timeout`），需重启 Gateway 才能恢复。

## 影响范围

- **谁受影响**：所有通过 IM/Gateway 使用 agent 的用户，只要触发 `agent` 工具派 subagent。
- **严重度**：子 agent 能力**完全不可用**（前台路径 100% 崩）；更严重的是单次失败即让整个常驻 Gateway 节点离线、对外失联，需人工重启——接近 blocking。
- **数据损坏**：无已知数据损坏；故障表现为进程存活但失联（heartbeat / relay 协程停摆）。
- **不影响**：主 agent 对话回复、bash 工具前台/后台路径（issue 已确认这些路径不走本崩溃点）。

## 根因分析（RCA）

### 缺陷一：subagent 前台执行模型跨事件循环（已确证）

`agent.py:235` 前台路径把**与主 agent 共享的同一个 `runtime` 实例**提交到 `ThreadPoolExecutor` 工作线程，工作函数 `_run_subagent_turn_sync`（:611-631）对它执行 `asyncio.run(runtime.run(...))`——这会**新建一个临时事件循环**跑。而 `runtime.run`（`runtime.py:278`）入口第一步就 `async with self._session_locks.setdefault(session_id, asyncio.Lock())`，且 runtime / RunsRegistry / permission broker 等 kernel 级单例持有大量**在主循环上创建并绑定**的 asyncio 原语（`registry.py:158` 专用 loop、`runtime.py:158` 按首用循环 lazy 建的 session Lock、`broker.py:148` `get_event_loop()` 上 create_future 等）。subagent 的新循环一旦 await 到这些**绑定主循环的原语**，Python asyncio 抛 `... is bound to a different event loop`。

**具体那个 Event 待 design/实施阶段用最小复现脚本逐一坐实**（候选见原始报告；已排除 `tool_executor.py:71` 的 per-run `_sibling_event`）。spec 不拍板修法。

### 缺陷二：工具异常未被隔离，冒泡拖垮 Gateway 常驻协程

前台路径虽有 `except Exception`（:271-276）把异常收成 `status: failed` 返回，用户也确实看到 "Agent failed" 工具卡——但实测同一时刻 Gateway 的 heartbeat 停发、节点离线。这说明崩溃的副作用**没有被收敛在工具调用边界内**：强嫌疑是 `asyncio.run` 起的临时子循环在运行中**触碰并污染了某个跨循环共享的 kernel 单例**（如 RunsRegistry 的专用 loop / 共享 Queue），子循环结束 close 后，主循环上的 heartbeat / relay 协程下次再操作该单例即抛异常、协程死掉，进程存活但对外失联。**精确污染链待 design/实施用复现脚本坐实**。

### 为什么这种错能进来（防再发）

- **执行模型从设计上就把「共享 runtime」交给「独立新循环」跑**——`feat-337-cc-background-subagents` 引入 subagent 执行模型时，前台路径直接用 `asyncio.run` 在 executor 线程跑共享 runtime，没有保证「跑 subagent 的循环 == 创建 runtime 内 asyncio 原语的循环」。这是结构性前提错误，不是某一行笔误。
- **测试盲区**：默认每次跑的 2707 个单测/集成多用 stub/fixture LLM，不真正起子 agent 的完整 turn；`tests/e2e/` 真 LLM 套件没有任何一条测 `agent` 工具派 subagent。于是「子 agent 完全不可用」无任何自动化拦截。
- **验收 scope 缝隙**：每个 unit 的 reviewer 只验本 unit 旅程，没人对「subagent 是否还能用」这条跨 unit 的关键路径负责——本 bug 从缝里漏出。

### 原始设计意图追溯（修复必须保住的不变量）

subagent 执行模型由 `feat-337-cc-background-subagents` 引入，本意：让父 agent 通过 `agent` 工具派生**自治子 agent**，支持前台（等结果，超 budget 自动转后台）/ 后台（立即返 agent_id）/ continuation（按 agent_id 续跑）三种模式，子 agent 复用父进程的 kernel/runtime 与 session 存储。**修复不得为消症状而砍掉前台 subagent 能力**——前台「等结果并把子 agent 输出作为工具结果返回」是核心特性，必须保活；后台与 continuation 路径同样不能回归。

## 修复方向

供 design 阶段拍板（spec 不选型）：

1. **修执行模型（缺陷一）**：subagent 不应在 executor 线程用裸 `asyncio.run` 起独立循环跑**共享**的 runtime/loop 组件。issue 给出两条候选——(a) 把 subagent 协程提交到 kernel 主循环执行（`run_coroutine_threadsafe`），与 bash 前台心跳的跨线程桥一致；(b) subagent 用**完全独立**的 runtime/loop 实例，不共享任何主循环绑定的 async 原语。design 阶段用最小复现脚本坐实具体被 await 的原语后定方案。
2. **修故障隔离（缺陷二）**：保证 subagent（及任意工具）的异常被收敛在工具边界内，**绝不冒泡终止 Gateway 的 heartbeat / relay 等常驻协程**；常驻协程对工具层异常/子循环污染要有防护，单个工具失败不得使节点离线。
3. **回归守卫**：随本 bug 加一条真 LLM e2e——派 subagent 跑通一轮（`@pytest.mark.e2e`，默认不跑），作为本 bug 的回归守卫。

**非目标（本 unit 不做）**：issue 建议的结构性「关键路径真 LLM e2e 套件 + 清单」（发消息回复 / bash 前台超时 / bash 后台通知 / subagent / /stop / cron / heartbeat 各一条经 Gateway 的真 LLM e2e + 统一 marker/开关 + 关键路径清单与归属）——拆为独立后续 unit 另立项。
