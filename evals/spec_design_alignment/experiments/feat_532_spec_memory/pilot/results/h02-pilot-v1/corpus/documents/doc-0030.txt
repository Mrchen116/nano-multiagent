# refactor-477: 建立 CLI 单一会话事件流所有者

> 状态：v4（2026-07-25）

## Relations

- Depends on: 无
- Blocks: 无
- Related: refactor-476、refactor-479

## 原始诉求

> 再看看当前代码仓中有多少巨石代码
>
> 我希望你能明确当前所有的重要的架构问题，如果和CC有类似的概念则和CC的源码的架构做对比，然后用change-spec-author，change-design-author skill（不需要跟我逐个进行对齐），帮我创建独立的几个unit。我要逐个进行重构，完善架构。我最终做一次确认后，再开始按可并行性开始做各个unit的实现。
>
> 中途你全程负责。我只做最终的确认。

## 澄清记录

- Q1: 是否逐个对齐？
  A: “中途你全程负责。我只做最终的确认。”
- Q2: 是否按 `commands.py` 行数做机械拆分？
  A: 否；只处理两个订阅者并行消费同一 session stream、而预期 pipeline 未成为生产所有者的事实。

## 现状痛点

REPL 经 `/new`、`/use` 或首次懒创建激活 session 后建立一个持久
`kernel.stream(session_id)`，每次前台发送又建立第二个订阅；初始
`--resume` 反而漏起持久 drain。`EventStreamHub` 会向每个订阅者重放历史并广播同一批
实时事件，因此同一次用户运行可能同时进入前台渲染与后台处理。后台处理器遇到
`origin=user` 后直接返回，却保留此前缓冲事件。

与此同时，`event_pipeline.py` 已定义 normalizer、去重窗口、phase machine 和 consumer，但生产链路
大部分绕开它；结构测试只能证明 helper 存在，不能证明单一消费所有权成立。

第二条更深的约束是：SDK 的 replay 来源只是进程内有界 journal，而不是无限 durable log。当前
`stream(after_sequence=...)` 在 cursor 已落出窗口时会静默从仍保留的最旧事件开始，且
`current_event_sequence()` 虽已存在于代码中，却尚未进入 canonical SDK 方法契约。若 CLI 把一个
scalar cursor 当成“永远可完整补齐”的日志位置，长时间离开 session 或 subscriber failure 后仍会静默
漏事件。

## 目标状态

一个 REPL 进程只有一个 session event owner，任一时刻只订阅当前 active session；发送与 steer 只经
该 owner 调用 Kernel/Registry 拥有的原子 USER admission；创建期先以 reservation 线性化，异常终态
产生的 USER/BACKGROUND/USER successor 按原 origin/FIFO 形成一条有序 lineage，任一时刻只有一个
明确的 USER admission target。不再用 event watermark 猜 active/continuation 状态，也不再由
`commands.py` 维护另一份“当前 user run”事实。普通 submit、Kernel 自动创建的 USER continuation、
后台 run、session-level event、中断和终态都由同一 owner 归属；所有 session event
view/notice/terminal summary 再经一个有界、按序、带 ack 的 delivery arbiter 投影。

owner 为每个访问过的 session 保存**已连续提交**的 replay cursor。SDK 为有界 journal 提供严格
replay 模式：窗口内从 cursor 精确补齐且不重复；cursor 已落出窗口时，在产出任何“看似完整”的 replay
前返回 typed gap；strict subscription 必须在 gap 检查、subscriber 注册和 replay snapshot 已完成后
才返回 ready。Registry 为任意已知 run 的终态、stranded-input/continuation 决策提供可晚到查询的
settlement barrier。CLI 的 Ctrl-C 携带 owner 当前 USER run 的 expected id 走精确中断 seam，不能因
session active-map 漂移中断 background run。
CLI 对 gap 或 stream source failure 必须先关闭输入 admission、收口仍活着的 USER flow，再一次性
向用户显示失败；不得静默越过缺口，也不得在旧 run 仍活时接受下一轮。

TTY/stdout 与 history append 不是跨副作用事务。若 renderer 本身在一次投影中途失败，CLI 不声称能把
部分输出 exactly-once 补完：该 session 在本进程内 fail-stop，不自动 replay/重试未 ack event；先精确
收口 USER lineage，再只允许切换安全 session 或退出。这样可能留下明确不完整的本次显示，但不会把一次
未知的部分写入伪装成可安全重放。

本 unit 不改变 CLI 命令、正常输出语义、快捷键、后台运行能力或 SDK event dict schema。为使上述
保证可证明，本 unit 会把现有 `current_event_sequence()` 纳入 SDK canonical，增加 SDK-owned
ready subscription、原子 USER admission 与 settlement barrier，并保留 `stream()` 的既有兼容
行为；新增精确 `interrupt_user(expected_run_id)`，既有 `interrupt(session_id)` 语义不变。未启用
新接口的既有消费者保持原行为。replay gap/session 阻断与 renderer fail-stop 是新增的稳定 CLI 故障
契约，由本 unit 的 CLI delta 明确记录。

## 用户侧验收标准（正常行为不变，缺口不再静默）

用户继续在同一个 REPL 中发送消息、看到流式回答和工具事件、切换到后台运行并收到完成通知，也可中断
当前运行。正常重放窗口内不新增重复消息、不丢后台通知；若事件已超出 SDK 有界 journal，CLI 明确报错并
阻止旧 run 与下一轮混流，而不是伪装成完整恢复。

### Requirement: 前台会话输出保持

#### Scenario: 发送一轮普通消息
- **WHEN** 用户在 REPL 发送消息并等待回答完成
- **THEN** 流式文本、工具展示和终态与变更前一致，且每个事件只呈现一次

#### Scenario: 在 journal 窗口内切回会话
- **WHEN** 用户从会话 A 切到 B，A 在离开期间产生事件，随后用户在这些事件仍可重放时切回 A
- **THEN** A 离开期间的事件按原顺序补齐，每个事件只呈现一次

### Requirement: 后台运行通知保持

#### Scenario: 后台运行与前台运行交错
- **WHEN** session 中存在后台运行，同时用户继续前台对话
- **THEN** 两类事件仍被正确归属，后台完成通知和前台输出与变更前一致
- **AND** 用户 Ctrl-C 只中断 owner 指定的当前 USER run，不中断同时存在的 background run

### Requirement: USER continuation 的输入归属保持

#### Scenario: Kernel 自动续接后再次输入
- **GIVEN** 前一条 USER run 异常终止，Kernel 为尚未消费的 steer 创建了 USER continuation
- **WHEN** continuation 仍在 queued/running 时用户再次输入
- **THEN** 输入只尝试 steer 到该 continuation，不新建并行 USER run，也不误注入 background run

### Requirement: 中断和恢复保持

#### Scenario: 中断当前生成后继续输入
- **WHEN** 用户中断当前运行并发起下一轮输入
- **THEN** Ctrl-C 对应的 run 被标记为 benign user interrupt、旧运行被正确排空，下一轮不混入旧事件
- **AND** 中断目标由 CLI 当前 USER run 的精确 id 决定，不因同 session background/queued run
  更新 active-map 而漂移

#### Scenario: stream source 在 USER run 中途失败
- **WHEN** CLI 的唯一 session stream 在 USER run 仍未终态时异常退出
- **THEN** CLI 暂停新输入，终止并收口该 USER run 后只显示一次可执行错误，再恢复或明确阻断该 session
- **AND** 不把仍活的旧 run 留给下一轮继续输出或接受 steer

#### Scenario: replay cursor 已落出有界 journal
- **WHEN** 用户切回会话或 owner 恢复订阅，而已提交 cursor 之后的某个该会话事件已被 journal 淘汰
- **THEN** CLI 明确显示 replay gap，绝不把不完整事件流当成成功 catch-up
- **AND** 在无法证明旧 USER run 已收口前，不接受该 session 的下一轮输入

#### Scenario: renderer 在一次投影中途失败
- **GIVEN** terminal/history/stdout 投影不是一个可回滚事务
- **WHEN** renderer 在某个 event 的一次或多次可见副作用之间抛错
- **THEN** CLI 不自动 replay 或重试该未 ack event，也不宣称部分输出已完整呈现
- **AND** 该 session 在本进程内保持阻断，USER lineage 收口后只允许 `/new`、`/use <其他安全
  session>` 或 `/exit`

## 影响范围

- `src/coding_cli/commands.py`
- `src/coding_cli/events/` 下 owner、route、projection 与后台通知相关模块
- `src/agent/core/events/hub.py` 的有界 journal replay watermark
- `src/agent/core/runs/registry.py` 的 USER admission reservation、有序 lineage、run-settlement 原子 seam
- `src/agent/core/background_tasks/foreground_registry.py` 与 foreground tool wiring 的 run-scoped stop
  identity（只服务精确 USER interrupt）
- `src/agent/sdk/kernel.py`、SDK-owned replay gap 类型与 `agent.sdk` 导出面
- Kernel SDK contract、CLI 产品装配及事件相关测试
- CLI canonical 的 unsafe stream source/gap 阻断 delta
- 不改变 kernel event dict schema、IM、Gateway 或其他产品的 stream ownership

## 迁移与回滚策略

先添加“单订阅覆盖前台、adopted USER、后台、重放、终态、中断、source failure”的接口级测试，以及
SDK strict replay 的窗口内/gap contract 测试；再把发送与 steer admission 改为单一 owner，随后删除
第二订阅与无生产价值的浅结构。

SDK strict replay 通过 opt-in 参数引入，既有调用方默认语义不变。CLI owner、SDK strict replay 与
对应 contract 作为单个 M1 原子切换；失败时整体回滚该切换。禁止长期保留新旧 consumer 并行、通过内容
fingerprint 掩盖重复订阅，或把 typed replay gap 降级成静默 best-effort。
