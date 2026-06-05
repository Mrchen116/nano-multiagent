# gateway (personal_assistant) Specification (delta for feat-394)

> 本单元对 canonical `docs/specs/gateway/spec.md` 的增量。收尾归并已合并进 canonical（§7.0）。

## ADDED Requirements

### Requirement: Agent 工具集由 tool_allowlist 真白名单决定，能力特性按 requires_tool 联动其工具

> post-acceptance 决策 D：纠正原实现把 `tool_allowlist` 当"默认集 + 加项"（默认工具无法禁用）、且把
> cron 工具靠 gateway 运行时注入 allowlist（导致 IM 侧存储与运行时分裂）。

Gateway 为某 Agent 构建会话工具集时，以该 Agent 配置的 `tool_allowlist` 为**白名单单一来源**：

- `tool_allowlist` **非空** → Agent 工具集**恰为**列出的这些；列表外的默认工具**不**提供（默认文件/web 工具
  **可被用户禁用**）。
- `tool_allowlist` **为空** → 取产品默认工具集（未配置语义）。
- 能力特性（如 cron）启用时，其 `requires_tool` 工具经"特性→工具"联动**已落在该 Agent 的 `tool_allowlist`
  里**，Gateway 不在运行时另行注入；Agent 工具集与 IM 侧存储的 `tool_allowlist` 一致（无分裂）。

#### Scenario: 用户禁用某默认工具后该工具不再提供
- **GIVEN** 某 Agent 的 `tool_allowlist` 被设为不含某默认工具（如不含 `read`）的非空显式集
- **WHEN** Gateway 为该 Agent 构建会话
- **THEN** 该 Agent 工具集不含被禁的默认工具（下发给模型的工具列表里没有它）

#### Scenario: 未配置 allowlist 的 Agent 拿到产品默认工具集
- **GIVEN** 某 Agent 的 `tool_allowlist` 为空
- **WHEN** Gateway 为该 Agent 构建会话
- **THEN** 该 Agent 工具集 = 产品默认工具集

#### Scenario: 启用 cron 能力使 cron 工具进入该 Agent 工具集
- **GIVEN** 某 Agent 启用了 cron 能力特性（其 `requires_tool="cron"` 已联动进 `tool_allowlist`）
- **WHEN** Gateway 为该 Agent 构建会话
- **THEN** 该 Agent 工具集包含 `cron` 工具；停用 cron 能力则 `cron` 工具随之移出

## MODIFIED Requirements

### Requirement: Heartbeat 与 Cron 是两套独立的本地主动机制,各由 per-agent 开关启停

> 取代旧 Requirement「Heartbeat 调度完全在本地,无有效任务时安静跳过」。旧契约把 heartbeat 与 cron
> 揉成"一次性/固定间隔/Cron 三种模式"，且声明"进程重启后**补跑**错过的到期任务"——与 feat-394 的
> no-catchup 决策直接矛盾。本单元改为两套独立机制 + per-agent 开关 + **不补跑**。

Gateway 提供两套**相互独立**的本地主动行为机制,均完全在本地调度(IM 服务不作调度源),各自由 IM 配置页上
一个 per-agent 开关启停(配置经 IM→Gateway 同步生效):

- **Heartbeat**:周期性"带上下文"唤醒。携带该 Agent 与 owner 的 canonical 直聊上下文,由 Agent 工作区的
  `HEARTBEAT.md` 驱动(Agent 可经对话自管写入)。支持单一节律与多子节律(`tasks:` 各自独立频率)、活跃时段
  (activeHours)限制;无可冒泡内容时回 `HEARTBEAT_OK` 静默、不打扰用户。
- **Cron**:无上下文的定时任务。可挂多条,各在隔离 session 执行(不带对话上下文),由 Agent 经 cron 工具自管
  (注册/查看/删除)。结果文本回发 owner 的 canonical 直聊;用户可就该结果追问,Agent 记得自己汇报过什么。

两套机制**均不补跑积压**:停机/空闲错过多个周期后,恢复只推进到最近一次边界触发一次(不刷屏回填);
已过期的一次性(`at`)任务恢复后不补跑。

#### Scenario: 未启用的 Agent 两套机制都不跑
- **GIVEN** 某 Agent 的 heartbeat 与 cron 开关均关闭
- **WHEN** 调度器周期 tick
- **THEN** 不为该 Agent 创建任何 heartbeat / cron 运行

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
