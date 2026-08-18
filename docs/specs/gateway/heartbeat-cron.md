# gateway (personal_assistant) - Heartbeat and Cron Specification

> 对齐: feat-541
> 上级: [gateway (personal_assistant) Specification](spec.md)
>
> 写法纪律见 [`../CONTRIBUTING.md`](../CONTRIBUTING.md)。本目录只收 Gateway **对外可观察的行为**:消费者是在外部 IM / 内置 Web IM 上收发消息的终端用户、与 Gateway 双向通信的 IM 服务、敲启停命令的运维者。

## Purpose

heartbeat 与 cron 两套本地主动机制的 per-agent 开关、调度和错过周期语义契约。

## Requirements

### Requirement: Heartbeat 与 Cron 是两套独立的本地主动机制,各由 per-agent 开关启停

Gateway 提供两套**相互独立**的本地主动行为机制,均完全在本地调度(IM 服务不作调度源),各自由 IM 配置页上一个 per-agent 开关启停(配置经 IM→Gateway 同步生效):

- **Heartbeat**:周期性"带上下文"唤醒。携带该 Agent 与 owner 的 canonical 直聊上下文。**顶层节律 (多久唤醒一次)来自 agent 配置 `heartbeat.every`(未配置默认 30m),不来自 HEARTBEAT.md**; `<workspace_root>/.nanoassistant/HEARTBEAT.md`(Agent 可经对话自管写入)承载任务内容:freeform 任务清单 + 可选 `tasks:` 块的 per-task 独立频率子节律。活跃时段(activeHours)限制来自配置;无可冒泡内容时回 `HEARTBEAT_OK` 静默、不打扰用户。
- **Cron**:无上下文的定时任务。可挂多条,各在隔离 session 执行(不带对话上下文),由 Agent 经 cron 工具自管 (注册/查看/删除)。结果文本回发 owner 的 canonical 直聊;用户可就该结果追问,Agent 记得自己汇报过什么。

两套机制**均不补跑积压**:停机/空闲错过多个周期后,恢复只推进到最近一次边界触发一次(不刷屏回填); 已过期的一次性(`at`)任务恢复后不补跑。

Cron 的定时触发和 Agent 手动触发具有同一执行语义:同样的 Kernel 提交、IM 投递、运行历史和 canonical-session awareness;手动触发只改变触发时机并立即返回入队确认。手动触发请求按发起请求的 Agent 身份路由——多 Agent 并存、Agent 在运行期新建、或请求来自 heartbeat / cron 隔离会话时均路由到正确 Agent,互不串扰。运行历史必须区分 trigger,记录 accepted/running/terminal 状态、Kernel run、目标会话、结果或错误;仅有最近一次调度时间不构成运行历史。Gateway 关闭时已入队的 cron 投递在 IM 连接关闭前完成收拢。

#### Scenario: 未启用的 Agent 两套机制都不跑
- **GIVEN** 某 Agent 的 heartbeat 与 cron 开关均关闭
- **WHEN** 调度器周期 tick 或工具运行发生
- **THEN** 不为该 Agent 创建任何 heartbeat / cron 运行,cron 工具不获得可用手动运行能力

#### Scenario: 手动运行已有 cron 任务立即入队
- **GIVEN** 某 Agent 已启用 cron,且 workspace 中存在目标 job
- **WHEN** Agent 的 cron 工具请求立即运行该 job
- **THEN** Gateway 校验后接管请求,工具立即返回 accepted 与请求标识,不等待模型任务执行完成

#### Scenario: 手动 cron 与定时 cron 使用同一执行语义
- **WHEN** 手动入队的 cron job 执行完成
- **THEN** 结果按该 job 原规则投递到目标会话、记录运行历史,并写入 canonical session awareness, 后续用户追问可引用该结果

#### Scenario: 查询 cron 运行历史
- **WHEN** Agent 查询某 job 的运行历史
- **THEN** Gateway 返回手动和定时触发的最新结构化记录,包含触发来源、状态、时间、结果或错误, 不只返回 scheduler 的 `last_due_at`

#### Scenario: 手动运行未知或不可运行任务
- **WHEN** cron 工具请求不存在或未启用的 job
- **THEN** Gateway 在创建 isolated session 前拒绝请求并返回明确错误,不执行其他任务

#### Scenario: Heartbeat 有内容时带上下文主动冒泡
- **GIVEN** 某 Agent 的 heartbeat 已启用,且当前 tick 有可冒泡内容
- **WHEN** 调度器到点触发该 Agent 的 heartbeat
- **THEN** 在该 Agent 与 owner 的 canonical 直聊里像普通 Agent 消息一样发出,且能引用此前的对话上下文

#### Scenario: Heartbeat 无可行动任务时安静跳过
- **GIVEN** 某 Agent 的 `HEARTBEAT.md` 当前 tick 无可冒泡内容
- **WHEN** 调度器到点触发该 Agent 的 heartbeat
- **THEN** 不发任何用户可见消息(回 `HEARTBEAT_OK` 静默)

#### Scenario: 活跃时段外不唤醒
- **GIVEN** 某 Agent 的 heartbeat 配了 activeHours,当前时刻落在窗口外
- **WHEN** 调度器周期 tick
- **THEN** 不触发该 Agent 的 heartbeat,不打扰用户

#### Scenario: 同一 Agent 多条 cron 任务各自按时触发
- **GIVEN** 某 Agent 挂了多条不同节律的 cron 任务
- **WHEN** 各任务到点
- **THEN** 每条任务独立触发并把各自结果发回 canonical 直聊,互不干扰

#### Scenario: 周期任务错过多个周期不刷屏回填
- **GIVEN** 一个固定间隔的 heartbeat/cron 在 Gateway 停机或空闲期间错过了多个周期
- **WHEN** 调度器恢复
- **THEN** 只在最近一次边界触发一次,不为每个错过的周期各补跑一次

#### Scenario: 过期的一次性任务不补跑
- **GIVEN** 一个一次性(`at`)cron/heartbeat 的触发时刻在 Gateway 停机期间已过
- **WHEN** Gateway 重启后调度器恢复
- **THEN** 该任务被视为错过窗口、不补跑(已执行过的同样不重复)

#### Scenario: Cron 汇报后用户追问,Agent 记得汇报内容
- **GIVEN** 某 Agent 的 cron 任务已执行并把结果发回 canonical 直聊
- **WHEN** 用户在该直聊就此结果追问
- **THEN** Agent 的回复能引用刚发出的 cron 汇报内容(该结果对后续对话轮次可见)

#### Scenario: Heartbeat 顶层节律由配置决定,忽略 HEARTBEAT.md 顶层 every
- **GIVEN** 某 Agent 配置 `heartbeat.every=10m`,其 HEARTBEAT.md 顶层又写了 `every: 15s`
- **WHEN** 调度器评估该 Agent 的 heartbeat 顶层节律
- **THEN** 按 10m 触发;HEARTBEAT.md 顶层 `every:` 不生效(未配置则按默认 30m)

#### Scenario: Agent 配置变更在活连接即时生效,无需重启 Gateway
- **GIVEN** Gateway 与 IM 活连接,owner 在配置页关闭某 Agent 的 heartbeat
- **WHEN** 该变更经 IM→Gateway 同步到达
- **THEN** Gateway 无需重启,数个 tick 内停止该 Agent 的 heartbeat(enable/cadence 等配置变更同理即时生效)

#### Scenario: 断连期间的配置变更在重连对账时收敛
- **GIVEN** Gateway 断连期间 owner 改了某 Agent 的 enable / cadence(增量同步未送达)
- **WHEN** Gateway 重连 IM 并完成全量对账
- **THEN** 该 Agent 的调度行为收敛到 IM 当前真值

### Requirement: 心跳与 cron 走该 Agent 同一条模型备用链

Heartbeat tick 与 cron 执行使用与人工聊天相同的主模型 + 有序备用链及粘性规则。复用已有 Kernel session（含心跳优先使用的 canonical 直聊）时，第一次 admit 与随后经 `submit_message` 打进内核的 model 都必须是该 session 的 `candidates[0]`（有粘性就是备用）；不得省略、也不得再把保存的主模型当 explicit 打进去。主模型因可用性失败且该 run 尚未投出真实正文或工具时间线时，先投下带模型名的失败提示（若该路径对用户可见），再按备用链改用能用的模型并完成本次 tick/任务。成功切换且向用户发出可见内容时，内容前带与聊天相同的轻量切换说明。没配备用或整链耗尽时，每个失败候选留下带模型名的失败提示，没有伪装成功。

#### Scenario: 心跳在主模型不可用时仍能完成 tick
- **GIVEN** Agent 配备用列表
- **WHEN** 一次心跳 tick 时主模型因可用性失败，且尚未投出真实正文或工具时间线
- **THEN** 用户若能看见该次失败，失败提示带该模型名
- **AND** 该 tick 按备用链改用能用的模型并完成
- **AND** 若这次心跳向用户发出了成功可见内容，内容旁带与聊天相同的轻量切换说明

#### Scenario: 心跳复用已粘备用的直聊时仍用备用
- **GIVEN** 某 Agent 的 canonical 直聊已粘在备用模型 B
- **WHEN** 下一次心跳 tick 复用该 Kernel session
- **THEN** 该 tick 第一次就用 B，入队显式传入 B，不因传入保存的主模型或省略 model 而被内核拒
- **AND** 不先再撞已经失败的主模型

#### Scenario: 定时任务在主模型不可用时仍能跑完
- **GIVEN** Agent 配备用列表
- **WHEN** 一次 cron 任务执行时主模型因可用性失败，且尚未投出真实正文或工具时间线
- **THEN** 用户若能看见该次失败，失败提示带该模型名
- **AND** 该次执行按备用链改用能用的模型并完成
- **AND** 若这次任务向用户发出了成功可见内容，内容旁带与聊天相同的轻量切换说明
