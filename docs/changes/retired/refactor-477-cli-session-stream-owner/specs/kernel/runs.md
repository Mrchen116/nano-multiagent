# kernel (agent) - Runs Specification (delta for refactor-477)

## MODIFIED Requirements

### Requirement: 创建会话必须绑定 workspace_root

消费者创建会话时绑定一个 `workspace_root`;该路径绑定到会话生命周期,后续该会话内工具执行的
`cwd` / 安全沙箱边界、以及工具/hook/skill 的工作区层扫描均以此为根。

#### Scenario: 创建会话返回绑定工作区的 SessionInfo
- **WHEN** 消费者 `await kernel.create_session(workspace_root=<path>)`
- **THEN** 返回一个 SDK-owned `SessionInfo`,其工作区根固定为该 `workspace_root`,会话内后续工具执行均在此根下进行

### Requirement: submit 非阻塞调度一轮运行,事件经 stream 异步消费

`submit()` 把一轮(turn)调度到内核后台事件循环并立即返回一个 SDK-owned `RunInfo`(初始状态
QUEUED);消费者经 `stream()` 异步迭代该会话的事件,跨自己的事件循环也能收到。

#### Scenario: 提交后从 stream 收到运行状态事件
- **GIVEN** 一个已创建的会话
- **WHEN** 消费者 `kernel.submit(session_id, parts=[{type:text,...}], workspace_root=...)` 后
  `async for ev in kernel.stream(session_id, after_sequence=0)`
- **THEN** 收到扁平化事件 dict(含 `event` / `session_id` / `sequence_num` + payload 字段),
  其中出现 `run_status` 事件,运行完成时其 `status` 为 `completed`(或失败时 `failed`)

#### Scenario: 同步提交完成后运行记录可查
- **WHEN** 提交一轮并轮询 `kernel.get_run(run_id)`
- **THEN** SDK-owned `RunInfo` 到达终态后 `status == "completed"` 且 `turn_id` 非空

### Requirement: 运行可被中断与取消

消费者可中断某会话当前活动运行(`interrupt`),可携带自己拥有的 USER run identity 精确中断
(`interrupt_user(session_id, expected_run_id)`),或按 `run_id` 取消排队/运行中的运行(`cancel`)。
`interrupt_user` 只在 expected id 仍是该 session 的 nonterminal USER run 时接受；不以 session 当前
background/其他 run 替换目标。既有 `interrupt(session_id)` 的 session-current 选择与返回形态保持兼容。

三者对不存在的目标安全无害。`cancel` 与被接受的精确 USER interrupt 必须**强制终止**承载目标 run 的
执行(不依赖被取消代码合作式自查),使该 run 即使 parked 在工具执行、LLM 等待或权限决策上也能终止；
终止后该 run 占用的 session 串行锁必须释放，同一 session 后续 `submit` 不被此前 run 永久阻塞。取消
同时取消目标 run 仍在等待的权限请求(resolve 为拒绝)。

#### Scenario: 取消运行中的运行,二次取消幂等
- **GIVEN** 一个运行中的运行
- **WHEN** 消费者 `kernel.cancel(run_id)`
- **THEN** 返回的记录 `status == "cancelled"`;再次 `cancel(同一 run_id)` 仍返回 `cancelled`(幂等)

#### Scenario: 取消 lineage 中尚未 bind 的 queued continuation
- **GIVEN** 一个 continuation 已有可查询 `RunInfo(status="queued")`,但因 FIFO 前驱尚未 terminal 而未 bind executor
- **WHEN** 消费者 `kernel.cancel(run_id)`
- **THEN** 该 run 到达 cancelled 并完成 settlement,后续 scheduler 跳过它
- **AND** 不因它尚无 executor token 返回 None 或让它稍后重新开始

#### Scenario: 取消未知运行返回 None 而非抛错
- **WHEN** 消费者 `kernel.cancel("<不存在的 run_id>")`
- **THEN** 返回 `None`(不抛异常)

#### Scenario: interrupt 无活动运行的会话不抛错
- **WHEN** 消费者对一个无活动运行的会话调 `kernel.interrupt(session_id)`
- **THEN** 返回 `None` 或被中断的 run_id,均不抛异常

#### Scenario: 取消一条 parked 的 run 后同 session 可继续
- **GIVEN** 某 session 有一条 run 卡在工具执行 / LLM 等待 / 等待权限决策且不再前进
- **WHEN** 消费者对该 run 调 `kernel.cancel(run_id)`,随后对同一 session `submit` 一条新 run
- **THEN** 被取消的 run 到达取消终态(`get_run` 可见 `status == "cancelled"`)
- **AND** 新 run 正常开始执行并能到达终态,无需重建内核(此前的 parked run 不会永久阻塞同 session)

#### Scenario: 取消会连带取消该 run 待决的权限请求
- **GIVEN** 某 run parked 在等待用户权限决策(broker 有该 run 的待决请求)
- **WHEN** 消费者 `kernel.cancel(run_id)`
- **THEN** 该 run 的待决权限请求被取消(resolve 为拒绝),不残留 pending 请求

#### Scenario: expected USER id 精确中断且不影响 background
- **GIVEN** 同一 session 有消费者持有的 nonterminal USER run U,并同时存在 background run B
- **WHEN** 即使 B 是 session-current map 的最后写入者,消费者调用
  `kernel.interrupt_user(session_id, expected_run_id=U)`
- **THEN** 返回 U,U 到达 cancelled 且 U 的权限/前台工具等待被解除
- **AND** B 不被取消、其权限/子进程/完成事件仍可继续

#### Scenario: stale、非 USER 或错 session expected id 零副作用拒绝
- **WHEN** 消费者调用 `interrupt_user`，但 expected id 已 terminal、属于 background 或属于另一 session
- **THEN** 返回 `None`,不取消任何 run、权限请求或 foreground execution
- **AND** 既有 `interrupt(session_id)` 调用方行为不因新增精确方法改变

## ADDED Requirements

### Requirement: 消费者可建立已 ready 的有界事件订阅,窗口缺口必须在返回前显式失败

`Kernel.current_event_sequence(session_id=None)` 为消费者提供事件序列 anchor:无参返回整个 Kernel
当前最新 `sequence_num`;传 `session_id` 时返回该会话最新已发布 `sequence_num`,即使对应事件已从有界 journal
淘汰也保持该 watermark。`await Kernel.open_event_subscription(..., require_replay=True)` 只在消费者
请求的 `after_sequence` 之后没有该会话已淘汰事件时返回 SDK-owned
`SessionEventSubscription`;否则在返回对象、交付任何 event 前抛出 SDK-owned
`EventReplayGapError`。该错误携带 `session_id`、`requested_after_sequence`、
`evicted_through_sequence` 与 `latest_sequence`,使消费者能区分“没有新事件”与“新事件已经不可重放”。

open 成功返回即代表 strict gap check、subscriber registration 与 replay snapshot 已在同一线性化
边界完成;调用方无需先迭代一次来激活 subscription。`require_replay=False` 仍先注册再返回,但只承诺
future-only/best-effort，不宣称 cursor 之前完整。既有 lazy `stream()` 行为保持兼容。journal 容量与
内部存储结构不是对外常量;消费者只能依赖 strict open 的“窗口内完整、窗口外显式 gap”语义。

#### Scenario: 会话 sequence_num anchor 不受其他会话事件干扰
- **GIVEN** 会话 A 与 B 的事件在同一个 Kernel 内交错发布
- **WHEN** 消费者调用 `current_event_sequence(A)`
- **THEN** 返回 A 最新事件的 `sequence_num`;若 A 从未发布事件则返回 0
- **AND** 无参 `current_event_sequence()` 仍返回整个 Kernel 最新事件的 `sequence_num`

#### Scenario: cursor 仍在 journal 窗口内时精确续读
- **GIVEN** 消费者已处理会话 A 到 `sequence_num=C`,且 A 在 C 之后发布的事件都仍可重放
- **WHEN** 消费者 await `open_event_subscription(A, after_sequence=C, require_replay=True)`
- **THEN** 返回的 subscription 已 ready,迭代时先按发布顺序收到 A 中所有 `sequence_num > C` 的
  可重放事件,随后继续收到 live event
- **AND** replay snapshot 与 live subscription 注册之间没有丢事件窗口,即使尚未调用 `__anext__`

#### Scenario: 该会话存在已淘汰的未读事件时 open 直接报 gap
- **GIVEN** 会话 A 在 cursor C 之后至少一个事件已从有界 journal 淘汰
- **WHEN** 消费者 await `open_event_subscription(A, after_sequence=C, require_replay=True)`
- **THEN** 在返回 subscription 或产出任何 replay/live event 前抛 `EventReplayGapError`
- **AND** 错误字段表明请求 cursor、A 已淘汰到的 watermark 与 A 当前最新 `sequence_num`

#### Scenario: 其他会话的淘汰不制造假 gap
- **GIVEN** journal 淘汰了会话 B 的事件,但会话 A 在 cursor C 之后没有任何事件被淘汰
- **WHEN** 消费者 strict-open 会话 A
- **THEN** 不因全局 `sequence_num` 数字空洞报 gap,A 的 replay + live stream 正常建立

#### Scenario: ready handshake 防止 cleanup 跑在 subscriber registration 之前
- **GIVEN** 消费者需要先订阅,再触发会发布 terminal/continuation 的 cleanup
- **WHEN** `open_event_subscription()` 已返回但 subscription 尚未开始迭代
- **THEN** subscriber 已注册,随后发布的 event 必须进入该 subscription

#### Scenario: 既有 lazy stream 保持调用方行为
- **WHEN** 既有消费者继续调用 `stream()` 而不使用新 open 接口
- **THEN** 保持原 best-effort replay + live lazy iterator 行为,不因新增 strict 契约改变控制流

### Requirement: USER admission 在创建 reservation 与有序 successor lineage 上线性化

`await Kernel.admit_user_input(...)` 是需要“加入当前 USER flow，否则创建”的消费者接口。它在 session
真正 idle 时先建立一个创建期 reservation；reservation 完成前，其他 caller 等待后重新判断，不能收到
指向未 bind run 的成功结果。创建/bind 失败时该调用不得留下 live USER run 或消费其他 caller 的输入，
且不得让任何 caller 收到 false `steered`。

一个 USER flow 的异常 terminal 可按原始 FIFO/origin 产生多个 continuation；它们形成 ordered lineage，
其中 background node 保留顺序但永远不接收 USER 输入。任一时刻只有 lineage 尾部一个 USER node 是
admission target：没有更早 pending successor 时可注入当前 USER controller；已有 successor 时，输入
追加到尾部 planned USER node，或排在 background 尾后新建 planned USER node。只有真正 idle 创建新
lineage 返回 `action="started"`；加入既有 lineage 返回 `action="steered"`。

#### Scenario: 两个 idle caller 在首次 bind 前不会双 create 或 false steer
- **GIVEN** session 真正 idle,caller A 的 USER 创建已 reserved 但 executor 尚未完成 bind
- **WHEN** caller B 同时 await `admit_user_input(...)`
- **THEN** B 等 reservation 完成后重新判断,bind 前不返回 `steered`
- **AND** A 成功时只有一个新 USER lineage,A 返回 `started`,B 只加入该 lineage

#### Scenario: 首次创建失败会 rollback reservation 且保全所有输入
- **GIVEN** caller A 持有 idle-session reservation,caller B 正等待,而 A 的 executor bind/admission 失败
- **WHEN** reservation 完成
- **THEN** A 收到创建失败且没有 live/orphan USER run；B 重新竞争而不是收到指向失败 run 的成功
- **AND** A、B 各自输入都没有因 reservation 失败被静默消费

#### Scenario: active USER lineage 存在时不注入 background
- **GIVEN** session 有一个 nonterminal USER lineage,同时可能存在 unrelated background run
- **WHEN** 消费者 await `admit_user_input(...)`
- **THEN** 返回 `action="steered"`,输入只加入该 lineage 的唯一 USER admission target
- **AND** 不创建并行 fallback,也不注入 background run

#### Scenario: USER-BACKGROUND-USER successor 保持 FIFO 与唯一 admission target
- **GIVEN** 前驱 terminal 的 stranded 输入按 origin 为 USER1、BACKGROUND、USER2
- **WHEN** settlement 建立 successor,并在 USER1 或 BACKGROUND 阶段再次 admission
- **THEN** successor 按 `USER1 → BACKGROUND → USER2` 执行,不覆盖任一 USER identity
- **AND** 新输入只追加到 lineage 尾部 USER target,不得越过更早 batch、并行 fallback 或注入 BACKGROUND

#### Scenario: terminal 已发布但 lineage settlement 未完成时不得 fallback
- **GIVEN** 前驱 USER run 的 terminal status 已发布,但其 stranded input 尚未完成 ordered lineage 决策
- **WHEN** 消费者在该窗口 await `admit_user_input(...)`
- **THEN** 调用等待 settlement 并重新原子判断
- **AND** 若产生 USER successor,输入加入该 lineage；不得并行创建 fallback USER run

#### Scenario: 多个 admission caller 从 settlement 同时醒来仍只有一个 lineage
- **GIVEN** 多个 caller 在同一 settlement 上等待,最终没有 continuation
- **WHEN** barrier 完成
- **THEN** 至多一个 caller建立新的 USER lineage
- **AND** 后续 caller 只加入该 lineage,不会建立第二个 USER flow

#### Scenario: legacy 并行 USER run 冲突显式失败
- **GIVEN** 兼容 `submit()` 在同一 session 留下两个无 predecessor 关系的 live USER run
- **WHEN** 消费者调用 `admit_user_input(...)`
- **THEN** 抛 SDK-owned `UserAdmissionConflictError`,零注入、零 fallback
- **AND** 不以 session active-map 的最后写入者作为猜测目标

### Requirement: 任意已知 run 的 settlement 可在 terminal 前后稳定查询

`await Kernel.wait_run_settlement(run_id)` 返回 SDK-owned `RunSettlement`。它对所有 `RunOrigin` 的已知
run 有效；返回前保证该 run 的 carrier cleanup、terminal status publication、未消费消息的
hold/continuation 决策，以及本次新建 continuation 的 queued `run_status` publication均完成。

结果携带按 FIFO 排列的 `continuations: tuple[RunContinuationInfo, ...]`、
`held_for_next_input` 与 `published_through_sequence_num`；每个 continuation 同时给出 SDK-owned
`RunInfo` 和 `RunOrigin`。immutable result 与可查询 run record 同生命周期，consumer 在 settlement
完成后首次调用仍得到相同结果。未知或已清除 id 抛 SDK-owned `RunSettlementNotFoundError`。

#### Scenario: terminal 前 waiter 等到 cleanup、successor publication 与 watermark
- **GIVEN** run U 异常终止,未消费消息被转交一个或多个混合-origin continuation
- **WHEN** 消费者在 settlement 完成前 await `wait_run_settlement(U)`
- **THEN** 返回前 U carrier 已 cleanup,continuation 决策已完成且各 queued status 已发布
- **AND** `continuations` 按 FIFO 精确给出 run/origin,
  `published_through_sequence_num` 不早于这些 publication

#### Scenario: terminal 和 settlement 完成后的 late waiter 得到同一结果
- **GIVEN** run U 的 settlement 已完成且 U 的 run record 仍可查询
- **WHEN** 一个此前未等待的消费者首次 await `wait_run_settlement(U)`
- **THEN** 立即得到与早期 waiter 相同的 immutable continuation/held/watermark 结果
- **AND** 不因内部 future 已 resolve/清理而报“barrier 不存在”

#### Scenario: background 中间 node 也可等待 settlement
- **GIVEN** USER lineage 中存在 `USER1 → BACKGROUND → USER2`
- **WHEN** 消费者 cancel background node 并 await `wait_run_settlement(<background run id>)`
- **THEN** 返回前该 background carrier 与其 continuation 决策已完成
- **AND** 消费者可按结果继续收口 USER2,无需用临时 active-map 推断

#### Scenario: 没有 stranded input 明确返回空 continuation
- **GIVEN** 已知 run 到达终态且没有未消费消息
- **WHEN** 消费者 await `wait_run_settlement(run_id)`
- **THEN** 返回 `continuations=()` 与覆盖 terminal publication 的 watermark

#### Scenario: 未知或已清除 run id 返回 typed error
- **WHEN** 消费者 await `wait_run_settlement("<未知或已清除 id>")`
- **THEN** 抛 SDK-owned `RunSettlementNotFoundError`,而非无限等待或返回含糊空结果
