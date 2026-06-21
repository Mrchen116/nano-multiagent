# kernel (agent) Specification (delta for bugfix-417)

> 主语 = 经 `agent.sdk` 调用内核的消费者（`coding_cli` / `personal_assistant`）或 `tests/contract/`。
> 本 delta 对既有 canonical 做 diff：MODIFIED 强化既有 cancel 契约（原仅断言 status/幂等，未保证强制终止 parked run 与释放 session 锁）；ADDED liveness 事件为净新增；MODIFIED「后台任务完成通知」契约补全前台不发通知的负向不变量（C 升级 / M7：消除前台 bash 同步返回结果又额外发 `<task-notification>` 的双通道）。

## MODIFIED Requirements

### Requirement: 运行可被中断与取消

消费者可中断某会话当前活动运行(`interrupt`),或按 `run_id` 取消排队/运行中的运行(`cancel`);两者对不存在的目标安全无害。`cancel` 必须**强制终止**承载该 run 的执行（不依赖被取消代码合作式自查），使该 run 即使 parked 在工具执行、LLM 等待或权限决策上也能终止；终止后该 run 占用的 session 串行锁必须释放，同一 session 后续 `submit` 不被此前 run 永久阻塞。取消同时取消该 run 仍在等待的权限请求（resolve 为拒绝）。中断/取消还必须**终止该 run 正在执行的工具派生的子进程（树）**，不留孤儿；该工具的在飞 tool_call 收口为「已中断」终态（既非成功、也非工具自身超时）。

#### Scenario: 取消运行中的运行,二次取消幂等
- **GIVEN** 一个运行中的运行
- **WHEN** 消费者 `kernel.cancel(run_id)`
- **THEN** 返回的记录 `status == "cancelled"`;再次 `cancel(同一 run_id)` 仍返回 `cancelled`(幂等)

#### Scenario: 取消未知运行返回 None 而非抛错
- **WHEN** 消费者 `kernel.cancel("<不存在的 run_id>")`
- **THEN** 返回 `None`(不抛异常)

#### Scenario: interrupt 无活动运行的会话不抛错
- **WHEN** 消费者对一个无活动运行的会话调 `kernel.interrupt(session_id)`
- **THEN** 返回 `None` 或被中断的 run_id,均不抛异常

#### Scenario: 取消一条 parked 的 run 后同 session 可继续
- **GIVEN** 某 session 有一条 run 卡在工具执行 / LLM 等待 / 等待权限决策且不再前进
- **WHEN** 消费者对该 run 调 `kernel.cancel(run_id)`，随后对同一 session `submit` 一条新 run
- **THEN** 被取消的 run 到达取消终态（`get_run` 可见 `status == "cancelled"`）
- **AND** 新 run 正常开始执行并能到达终态，无需重建内核（此前的 parked run 不会永久阻塞同 session）

#### Scenario: 取消会连带取消该 run 待决的权限请求
- **GIVEN** 某 run parked 在等待用户权限决策（broker 有该 run 的待决请求）
- **WHEN** 消费者 `kernel.cancel(run_id)`
- **THEN** 该 run 的待决权限请求被取消（resolve 为拒绝），不残留 pending 请求

#### Scenario: 中断正在执行长命令的 run 后子进程被回收、tool_call 收口为已中断
- **GIVEN** 某 session 的活动 run 正在执行一个长时间运行、派生了子进程的工具（如长 shell 命令）
- **WHEN** 消费者对该 session 调 `kernel.interrupt`（或对该 run 调 `kernel.cancel`）
- **THEN** 该工具派生的子进程（树）被终止，不留存活的孤儿进程
- **AND** 该工具的在飞 tool_call 在 session 事件流中收口为「已中断」终态（不停留运行中、不标成功、不标工具自身超时），同一 session 后续 `submit` 正常推进
- **AND** 该工具回填到 transcript 的 tool result content 明确归因为用户中断（`[Request interrupted by user for tool use]`），使下一轮模型据此知道是用户主动停止（区别于系统看门狗收尸/崩溃的中断）

### Requirement: 后台任务完成后发起 session 收到结果通知，跨 workspace 可靠

后台 bash / subagent 任务完成（无论成功、失败或被终止）后，发起它的 session 在下一轮输入中收到一条 `<task-notification>` 消息，内含任务结果——消费者无需轮询即可感知。该通知在任意 workspace_root 下均可靠送达，不因 session 绑定非默认工作区而丢失。**反之，同步前台工具（前台 bash 在预算内完成/失败/超时/被中断）的结果只经该工具的 tool result 同步返回，绝不再额外发 `<task-notification>`——一次执行只走一条结果通路。** 仅当前台命令超出前台预算、真正转为后台任务（auto-background）后，其后续完成才发一次 `<task-notification>`（此后它就是后台任务）。

#### Scenario: 非默认 workspace 下后台任务完成通知送达
- **GIVEN** 一个绑定非默认 workspace_root 的 session 启动了后台任务
- **WHEN** 任务完成
- **THEN** 该 session 下一轮输入含一条带任务结果的 `<task-notification>` 消息

#### Scenario: 前台命令完成只走 tool result，不发通知
- **GIVEN** 某 session 执行一条前台 bash 命令（未声明 `run_in_background`），且在前台预算内完成、失败或自身超时
- **WHEN** 消费者消费该 run 的结果
- **THEN** 该命令的结果只经其 tool result 同步返回（含成功输出 / 失败 / 超时归因）
- **AND** 该 session 后续输入中**不含**针对该命令的 `<task-notification>`（不出现"既返回结果又异步通知"的双通道）

#### Scenario: 前台命令超预算转后台后仍发一次完成通知
- **GIVEN** 某 session 执行一条前台 bash 命令，运行时长超出前台预算被 auto-background（其 tool result 返回 `async_launched` + task_id）
- **WHEN** 该命令稍后在后台完成
- **THEN** 该 session 下一轮输入含一条带结果的 `<task-notification>`（转后台后按后台任务发一次通知，不重复、不遗漏）

## ADDED Requirements

### Requirement: alive-but-quiet 窗口经 stream 持续发出 liveness 事件

当一条 run 处于"活着但暂无业务输出"的窗口（执行**任意**静默长工具、等待 LLM 返回、parked 等待用户权限决策）时，内核必须经 `kernel.stream` 周期性发出 liveness 事件（携带 run_id），间隔显著小于消费者侧的存活判定窗口。该事件仅表征"该 run 仍存活"，消费者可据其判定存活而不误判为卡死。三类窗口走同一事件通路，消费者无需按窗口类型分别豁免；执行期 liveness 是**工具无关**的（不限于某一类工具），任意长耗时工具执行期间都产出。

#### Scenario: 执行任意静默长工具期间 stream 仍有事件
- **GIVEN** 某 run 正在执行一个长时间无业务输出的工具（长命令、或其它长耗时工具如网络抓取）
- **WHEN** 消费者消费 `kernel.stream(session_id)`
- **THEN** 在工具执行全程内，stream 周期性产出携带该 run_id 的 liveness 事件（不必等工具结束才出现，且不限工具类型）

#### Scenario: 等待 LLM 返回期间 stream 仍有事件
- **GIVEN** 某 run 正在等待 LLM 返回且长时间未产出业务事件
- **WHEN** 消费者消费 `kernel.stream(session_id)`
- **THEN** 等待期间 stream 周期性产出携带该 run_id 的 liveness 事件

#### Scenario: parked 等待权限决策期间 stream 仍有事件
- **GIVEN** 某 run parked 在等待用户权限决策、长时间未产出业务事件
- **WHEN** 消费者消费 `kernel.stream(session_id)`
- **THEN** 等待期间 stream 周期性产出携带该 run_id 的 liveness 事件（与工具/LLM 等待同一事件通路），消费者据此判存活，无需 permission 专用豁免
