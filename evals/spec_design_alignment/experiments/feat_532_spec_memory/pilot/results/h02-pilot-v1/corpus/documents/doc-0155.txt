# bugfix-417: 一个超时/卡死工具永久锁死整个会话（bash 孤儿 × watchdog 误杀 × session 锁泄漏）

## Relations

- Closes: #110
- Related: bugfix-416

## 原始报告

报告人 @Mrchen116，GitHub Issue #110：<https://github.com/Mrchen116/nano-multiagent/issues/110>

> **一个超时或卡死的工具,会永久锁死它所在的整个会话**:该会话之后每一轮用户消息都只会回 `relay idle for 120s with no new event`,**在重启 Gateway 之前不可恢复**。其他会话不受影响(锁是 per-session 的),但被波及的会话彻底报废。
>
> 这不是单点 bug,是**三层缺陷叠成的一条事故链**:
>
> ```
> C. bash 子进程无进程组隔离 → 超时杀不净、孤儿孙进程 → 静默/挂死
>         ↓ 触发
> B. watchdog 用「输出事件静默」判卡死 → 误杀「活着但安静」的长工具
>         ↓ 误杀后
> A. 合作式 cancel 停不下已 parked 的 run → session 锁永不释放 → 会话报废
> ```
>
> 三层都要修才闭环;但 **A 即使 B 修好也必须单独修**——真·死锁(非误杀)时,cancel 仍须能释放锁。

完整事故链、复现实录、三层各自的代码定位与修法方向、不变量，见 issue #110 原文（内容详尽，此处不复述）。

## 澄清记录

- Q1: 本单元目标——三层(A/B/C)一次全修闭环，还是分阶段交付（先 A 保命，B/C 后续）？
  A(原话): 全部闭环。
  Agent 解读: 本单元覆盖 A/B/C 三层，目标状态是事故链整体闭环；milestone 拆分仍可让 A（P0 锁泄漏）独立可验证。

- Q2: 工具"超时(跑太久)"和"卡死(不再前进)"在用户侧要不要呈现成两种不同的失败态？
  A(原话): 当然需要区分。
  Agent 解读: max-duration 超时与 watchdog idle 判定要落成两种用户可观察失败态（文案/语义分开），作为 B 重设计的可验证投影。

- Q3: 除了工具自身 deadline，本期要不要再加一个 run 级硬上限兜底？
  A(原话): 对，只要它一直还是有信号的，我觉得问题都不大。
  Agent 解读: 本期 max-duration 只靠工具自身 deadline（核心是 bash timeout 可靠生效 + 进程组回收）；run 级硬上限为非目标。只要工具持续发 liveness 心跳就视为正常，不收。

- Q4: run 被强制取消/收掉后，被波及的那条用户消息在 IM 里要留下什么？
  A(原话): 对
  Agent 解读: 失败要留明确气泡（按 Q2 区分"耗时过长"/"已中断"），不静默消失、不永久转圈；且下一条新消息无需重启 Gateway 即可正常处理（自愈的可观察证据）。

## 现象与复现

**用户侧现象**：某会话里 agent 跑了一个超时或卡死的工具（实战是 `npm run build`，工具 `timeout=180`）后，**该会话彻底报废**——之后每一轮用户消息都只在气泡转圈、最终回 `relay idle for 120s with no new event`，**重启 Gateway 之前无法恢复**。其他会话不受影响。

**复现实录**（issue #110 原始事故）：

- 会话 `135156…`（direct，default-agent），kernel session `sess_5c47b30b`。
- agent 跑 `npm run build` 排查分支：`01:38:01` 起、`01:40:04` 被 reconcile 成 `timed_out`、`01:42:07` `relay.failed`。
- 同轮**前一个** bash「Run full frontend test suite」`duration=121637ms` 却 `completed`——比 120s 线只晚 0.2s 险过；build 没那么走运被斩。
- 之后「继续」「hi」以及手发的 probe **三次全部**：`message.created running` 后零事件，精确 120s 被 reap。
- 对照实验：给**另一个**会话（同 default-agent）发消息 → 秒回 completed。⇒ 卡的是这一个 session，不是 agent/gateway 全局。
- `py-spy dump`：所有线程 idle、无阻塞栈 ⇒ 协程在等 `asyncio.Lock`，非线程死锁。
- wedged session 的 JSONL **干净**（6 条正常 user/assistant，无悬空 tool_use）⇒ 不是磁盘历史损坏，是内存锁态。
- **重启 Gateway 后**：`135156` 立刻复活，正常跑完一轮含多个 bash 的多工具任务 ⇒ 坐实是内存里泄漏的 session 锁。

**期望 vs 实际**：期望——超时/卡死工具失败后会话能自愈，下一条消息正常处理；长静默命令（tsc build）不被误杀。实际——会话永久报废、长命令险过或被斩。

## 影响范围

- **谁受影响**：任何会话里跑了静默长命令、或工具真卡死的用户；个人助手（Gateway）与 IM relay 两条通路同源（`inbound_pipeline.py` / `relay_watchdog.py` 镜像逻辑）。
- **严重度**：被波及会话**彻底不可用**且 Gateway 重启前不可恢复；属 P0（A 层）。波及范围 per-session（锁是 per-session 的），不蔓延到其他会话或 agent。
- **数据损坏**：无。session JSONL 干净，纯内存锁态泄漏；重启即恢复。

## 根因分析（RCA）

三层独立缺陷叠成一条事故链：`C 触发 → B 误杀 → A 锁死`。三层定位均已对照当前代码核实。

### A. session 锁永久泄漏 → 会话报废（P0）

- 代码：`src/agent/core/agent/runtime.py:278-289`，整轮在 `async with lock` 内执行（锁要等 `_run_locked` return/raise 才释放）。
- 链路：build 轮拿锁进 `_run_locked` → gateway 120s idle 抛 TimeoutError + `kernel.cancel(run_id)` → 但 `kernel.cancel`（`src/agent/core/runs/registry.py:463`）是**合作式**的，只 `controller.cancel()` 翻标志，靠 AgentLoop 自查检查点；承载该 run 的协程没被打断 → 僵尸继续跑、最终停在一个 `blocked_by_hook=True` 的 parked 状态（等一个永不到来的权限确认）→ `_run_locked` 既不 return 也不 raise → `async with lock` 永不退出 → **锁被永久攥住**。
- **为什么能进来**：per-session 锁在 `F-330`（JSONL session storage）引入，用于串行化同会话的 run；当时假定"run 总会终止"，没有"run 可能 parked 在 hook/permission 等待里永不返回"的失效模型。`kernel.cancel` 设计成合作式（适合 AgentLoop 自查），但**强制取消承载 Task 的能力其实已存在**——`runs/registry.py:126` 的 `_owned_tasks` + `drain_async()` 的 `task.cancel()`（`bugfix-402` 引入），只在 Gateway 关停时用，**没接进普通 `cancel(run_id)` 路径**。缺的是把已有的强制取消能力接到 per-run cancel + 连带取消它正等的 permission/hook broker。

### B. watchdog 用「输出事件静默」判卡死 → 误杀活着但安静的工具

- 代码：`src/personal_assistant/gateway/inbound_pipeline.py:856`（及镜像 `src/IM/application/relay_watchdog.py:91`）用 `asyncio.wait_for(anext(stream), timeout=120s)` 判超时——判据挂在"业务输出事件静默"上。
- "无输出事件"混淆了**真卡死**（deadlock/crash/断连/死循环，该收）与**活着但安静**（跑静默长命令 tsc build、等 LLM 首 token、等人点权限，不该收）。
- 心跳其实已存在但看不见：bash 层 `src/agent/platform/tools/builtins/bash_runner.py:142-157` 在 selector 循环里**实时**发 `phase:running` liveness 心跳；但被困在 `src/agent/core/tools/registry.py:202-250` —— `_emit_execution_update`（:204-207）只 `append` 到 `_pending_updates`，`await asyncio.to_thread(tool.run,...)`（:234）阻塞整个 bash 时长，跑完才循环 flush（:247-250）。⇒ bash 全程心跳一个都到不了 watchdog，这就是"全量测试 121.6s 仅差 0.2s 幸存、build 被斩"的直接原因。
- **为什么能进来**：registry 的缓冲式 flush 在 `feat-335`（Streaming Tool Executor）引入。watchdog 的"输出静默=卡死"定义从一开始就把 liveness 与 max-duration 混为一谈；`awaiting_permission` 豁免（`inbound_pipeline.py:845-853`，`bugfix-410/M2` #98 加）已经承认"等人≠卡死"，但只补了"等人"一种特例，漏了"跑工具""等 LLM"。历史上 `bugfix-361/383` 都在此区域打过补丁——逐特例缝补而非重定义，是反复踩坑的根。

### C. bash 子进程无进程组隔离 → 孤儿 + 阻塞 read

- 代码：`src/agent/platform/tools/builtins/bash_runner.py:80` `subprocess.Popen(["bash","-c",command],...)` **无 `start_new_session`**；超时时 `process.kill()`（:117/:161）**只 SIGKILL 直接子 bash**，`npm run build` 的 node/vite/tsc/esbuild 孙进程被孤儿化、继续持有 stdout 写端；收尾 `process.stdout.read()`（:166）是**阻塞读**，等一个永不到来的 EOF → 承载 `tool.run()` 的线程挂死（本次事故中 A 的最初锁持有者）。
- **为什么能进来**：bash_runner 自建 selector 读循环时未起独立进程组，杀进程只针对直接子进程；阻塞 drain 假定 EOF 一定到来，没考虑孤儿持写端的场景。

### 必须保住的不变量（修复不能阉割原功能）

- per-session 锁的**原意图**是串行化同会话 run，防止并发 run 互踩历史——修 A 不能去掉串行化，只能保证锁总能释放。
- watchdog 的**原意图**是收掉不再前进的 run（防永久转圈、防占锁占资源）——修 B 不能去掉收尸能力，只能把判据从"输出静默"换成"liveness 静默"，真卡死仍要被收。
- bash 的**原意图**是流式回显 + 自身 timeout——修 C 不能改回显语义，只能让 timeout 杀整棵进程树、drain 不挂死。

## 目标状态与验收标准

> 用户可观察验收。issue 三条不变量的用户侧投影。

### Requirement A: 任何单条 run 都不能让 session 锁永久不可释放

#### Scenario: 工具超时后会话自愈
- **GIVEN** 某会话刚有一条工具因超时/被取消而结束的 run
- **WHEN** 用户在同一会话发下一条消息
- **THEN** 不重启 Gateway 即可正常处理并正常回复，不再每轮零事件、不再永久回 `relay idle for 120s`

#### Scenario: 真卡死的 run 被收掉后会话恢复
- **GIVEN** 某会话一条 run 真卡死（不再前进）
- **WHEN** watchdog 判定并收掉它
- **THEN** 该会话下一条消息正常处理，会话不报废

### Requirement B: watchdog 只收「不再前进」的 run，活着但安静的不被误杀

#### Scenario: 静默长命令不被误杀
- **GIVEN** agent 在跑一个耗时远超 120s 的静默命令（如 `tsc` / `npm run build`），其间持续在执行但无业务输出
- **WHEN** 命令仍在前进（仍发 liveness 心跳）
- **THEN** run 不被中断，命令跑完，结果正常返回

#### Scenario: 等 LLM 首 token 慢不被误杀
- **GIVEN** 一条 run 在等 LLM 返回，长时间未吐首 token 但连接活着
- **WHEN** 等待时间超过 120s
- **THEN** run 不被误判卡死、不被收

#### Scenario: 等权限确认不被误杀
- **GIVEN** 一条 run parked 在等用户点权限确认
- **WHEN** 用户迟迟未确认
- **THEN** run 不被 reap，权限确认后仍能继续

#### Scenario: 真卡死被收
- **GIVEN** 一条 run 不再发出任何 liveness 心跳
- **WHEN** liveness 静默超过阈值
- **THEN** 该 run 被判"不再前进"并收掉

### Requirement C: 超时与卡死在用户侧是两种不同失败态，且失败不静默

#### Scenario: 工具自身超时报「耗时过长」
- **WHEN** 一个工具（如 bash 命令）到达自身 deadline（`timeout`）被掐
- **THEN** 气泡报"耗时过长 / 工具执行超时"，而非"卡死 / 中断"

#### Scenario: 真卡死报「已中断」
- **WHEN** watchdog 收掉一条不再前进的 run
- **THEN** 气泡报"已中断 / 卡死"，与"耗时过长"语义区分

#### Scenario: 失败不静默
- **WHEN** 任一 run 因超时或卡死结束
- **THEN** 该轮消息留下明确失败气泡，不静默消失、不永久转圈

### Requirement D: 工具子进程超时连同进程树一起回收，会话可继续

#### Scenario: 会派生子进程的命令超时能干净收尾
- **GIVEN** agent 跑一个会派生子进程的命令（如 `npm run build`）且设了 `timeout`
- **WHEN** 命令到达 `timeout`
- **THEN** 该轮在 `timeout` 附近及时以"耗时过长"失败，会话能继续下一轮，不卡死、不因孤儿进程而无限等待

## 范围与非目标

**本期做**：

- A：把已有的强制取消 Task 能力接进 `kernel.cancel(run_id)`，并连带取消该 run 正等的 permission/hook broker，保证锁经异常路径释放。
- B：watchdog 重定义为 liveness 心跳驱动；让 bash `phase:running` 心跳在 `tool.run()` 执行期间实时 dispatch（不缓冲到结束）；给"等 LLM 返回""agent loop 步骤间"补 liveness tick；把 `awaiting_permission` 豁免一般化为"活着但安静皆维持存活"；idle 与 max-duration 拆开，分别报"中断"与"耗时过长"。
- C：bash `Popen(..., start_new_session=True)` 起独立进程组；超时改 `os.killpg` 杀整组；阻塞 drain 换成带超时/非阻塞 drain。
- 修复需保住"必须保住的不变量"三条（不阉割串行化、不去掉收尸能力、不改回显语义）。

**本期不做（非目标）**：

- **run 级 max-duration 硬上限/run 预算机制**：只靠工具自身 deadline。只要工具持续发 liveness 心跳即视为正常，不收（Q3 确认）。一个"无 deadline 又持续吐心跳的死循环工具"属边缘，用户可自行在命令里加 `timeout`。
- 不改其他工具（非 bash）的现有执行语义，除"给等 LLM/loop 步骤间补 liveness tick"这一最小改动。
- 不引入新的权限确认 UI；A 层只负责"放弃某 run 时取消它正等的 broker"。

## 修复方向

> 高层方案，行级实现在 design/milestone 阶段拍板。issue #110 给出的方向已验证可行：

- **A（锁释放）**：`cancel(run_id)` 复用 `_owned_tasks` 对承载 run 的 asyncio Task 做强制 `task.cancel()`，让 `async with lock` 走异常路径退出；同时取消该 run 等待中的 permission/hook broker。核心不变量：没有任何单条 run 能让一把 session 锁永久不可释放。
- **B（watchdog 重设计）**：落地前先出一份设计——心跳从哪几层发（bash 工具层 / 等 LLM 层 / agent loop 步骤间）、经哪条通路实时汇到 watchdog（重点拆 `registry.py` 的缓冲 flush）、idle(liveness) 与 max-duration 如何分离、两种失败态如何分别呈现。`inbound_pipeline.py` 与 `relay_watchdog.py` 两处镜像逻辑同步改。
- **C（进程组隔离）**：`start_new_session=True` + `os.killpg(os.getpgid(pid), SIGKILL)` 杀整棵进程树 + 非阻塞/带超时 drain，杜绝孤儿管道挂死执行线程。

> 实现层选型（心跳事件结构、tick 注入点、broker 取消接口形态、drain 超时取值等）留给 `change-design-author`。
