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

---

## MODIFIED Requirements（2026-06-08 验收修订：决策 E）

### Requirement: Heartbeat 顶层节律来自 agent 配置，HEARTBEAT.md 承载任务内容

> 修订上文「Heartbeat … 由 `HEARTBEAT.md` 驱动 … 支持单一节律与多子节律」中"顶层节律由文件驱动"的部分。

Heartbeat 的**顶层节律**（多久唤醒一次）来自 agent 配置 `heartbeat.every`（经 IM `AgentProfile` 同步），
未配置时默认 **30m**。HEARTBEAT.md 承载任务内容：freeform 任务清单 + 可选 `tasks:` 块的 per-task
`interval:` 子节律（子节律读自文件）。

#### Scenario: 顶层节律由配置决定
- **GIVEN** 某 Agent 配置 `heartbeat.every=10m`
- **WHEN** 调度器评估该 Agent 的 heartbeat 顶层节律
- **THEN** 按 10m 触发

#### Scenario: 未配置 every 时默认 30m
- **GIVEN** 某 Agent 未配置 `heartbeat.every`
- **WHEN** 调度器评估其顶层节律
- **THEN** 按默认 30m 触发

## ADDED Requirements（2026-06-08 验收修订：决策 F）

### Requirement: Gateway 连接/重连 IM 后做全量配置对账

Gateway 与 IM 建立连接并完成 bind 后（含断线重连），对本 node 下所有 agent 拉取 IM 权威配置做一次全量对账，
使本地配置（heartbeat enable / cadence / active_hours 等同步字段）收敛到 IM 当前真值；与增量推送并存时以
`profile_version` 较大者为准。

#### Scenario: 关闭 heartbeat 后无需重启即停
- **GIVEN** owner 在 IM 关闭某 Agent 的 heartbeat（即使该次增量推送未送达 Gateway）
- **WHEN** Gateway 下次连接/重连 IM 完成对账
- **THEN** 该 Agent 的 heartbeat 停止触发，无需重启 Gateway

#### Scenario: 重连后配置收敛到 IM 真值
- **GIVEN** Gateway 断连期间 owner 改了某 Agent 的 cadence 或 enable
- **WHEN** Gateway 重连并对账
- **THEN** 该 Agent 的调度行为与 IM 当前真值一致

## ADDED Requirements（2026-06-08 验收修订：决策 G）

### Requirement: Gateway 应 IM 请求返回自身 workspace 的 per-agent 运行态

IM 不直读 gateway 侧 workspace 文件；gateway 通过 IM↔gateway 通道响应 IM 的请求，读自己机器上的
workspace 文件并回传：HEARTBEAT.md 全文（只读预览用）、cron jobs 列表、cron job 删除。这保证 IM 与
gateway 跨机部署时这些视图/操作仍正确（数据来自 agent 实际所在 node）。

#### Scenario: 返回 HEARTBEAT.md 全文供预览
- **GIVEN** IM 请求某 agent 的 HEARTBEAT.md 内容
- **WHEN** 该 agent 所在 node 的 gateway 在线
- **THEN** gateway 读自己 `<workspace>/HEARTBEAT.md` 并回传全文（不存在/空则回空）

#### Scenario: cron 列表/删除作用于 gateway 自身的 jobs 文件
- **GIVEN** IM 请求某 agent 的 cron jobs 列表或删除某 job
- **WHEN** 该 agent 所在 node 的 gateway 在线
- **THEN** gateway 读/改自己 `<workspace>/.nanoassistant/cron/jobs.json` 并回传结果

#### Scenario: node 离线时优雅降级
- **GIVEN** 某 agent 所在 node 的 gateway 不在线
- **WHEN** IM 请求其 HEARTBEAT.md 预览或 cron jobs
- **THEN** 返回空 + "node 不在线"语义，不报错（沿用 prompt-preview 的 timeout 降级）
