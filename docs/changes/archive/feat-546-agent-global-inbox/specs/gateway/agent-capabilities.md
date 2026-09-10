# gateway/agent-capabilities Specification (delta for feat-546)

> 目标增量；实施校正后归并 current。

## ADDED Requirements

### Requirement: 全局主 Agent 保留默认工具并具备固定基础能力

#### Scenario: 新建全局 Agent 时保留正常执行能力
- **WHEN** 用户新建全局 Agent
- **THEN** 除读取收件箱、查阅聊天、显式发言及委派的固定基础工具外，仍默认拥有现有创建流程提供的工具
- **AND** 不因选择全局模式变成只能统筹、不能正常查询或执行的空工具 Agent

#### Scenario: 固定基础工具与可配置工具区分
- **GIVEN** 用户创建或编辑全局 Agent
- **WHEN** 查看和调整工具配置
- **THEN** `inbox`、`conversations`、`send_message`、`agent` 作为固定基础工具，不可关闭
- **AND** 其他工具继续按现有规则默认选择及配置，单 Thread 模式不因此改变

## MODIFIED Requirements

### Requirement: Agent 工具集由 tool_allowlist 真白名单决定并在执行层强制，能力特性按 requires_tool 联动其工具

本条以下恰等于配置白名单、显式空集和不自动扩宽的规则及 Scenario 适用于 `single_thread`。global 主 Agent 的有效集为配置集合与固定基础四项的并集；其他工具仍按配置限制，能力特性联动规则不变。固定项及创建默认值以本 area 的“全局主 Agent 保留默认工具并具备固定基础能力”为准；子工具继续既有继承和角色限制，不因主工具固定而扩大数据权限。

Gateway 为某 Agent 构建会话工具集时，以该 Agent 配置的 `tool_allowlist` 为白名单单一来源：非空时 Agent 工具集**恰为**列出的这些（列表外的默认工具不提供，即默认文件/web 工具可被用户禁用）；**显式为空时该 Agent 没有任何工具**。会话执行层按同一白名单强制：名单外工具调用（含模型未按声明自由发挥的调用）被拒且不产生副作用，调用方收到含工具名与「未在本会话启用」语义的错误结果。能力特性（如 cron）启用时，其 `requires_tool` 工具经"特性→工具"联动已落在该 Agent 的 `tool_allowlist` 里，Gateway 不在运行时另行注入——Agent 工具集与配置侧存储的 `tool_allowlist` 一致，无分裂。

#### Scenario: 用户禁用某默认工具后该工具不再提供
- **GIVEN** 某 Agent 的 `tool_allowlist` 被设为不含某默认工具（如不含 `read`）的非空显式集
- **WHEN** Gateway 为该 Agent 构建会话
- **THEN** 该 Agent 工具集不含被禁的默认工具（下发给模型的工具列表里没有它）

#### Scenario: 显式空名单的 Agent 会话拒绝一切工具调用
- **GIVEN** 某 Agent 的 `tool_allowlist` 显式为空
- **WHEN** 用户与该 Agent 会话，模型尝试调用工具
- **THEN** 工具不执行，用户在会话中看到含工具名与未启用语义的明确反馈

#### Scenario: 显式工具白名单不被默认集合自动扩宽
- **GIVEN** PA agent 已持久化非空 `tool_allowlist`
- **WHEN** Gateway 为该 agent 创建新 session
- **THEN** session 只启用该白名单列出的工具
- **AND** 若白名单不含 `skill_view`,session 不启用 `skill_view`

#### Scenario: 启用 cron 能力使 cron 工具进入该 Agent 工具集
- **GIVEN** 某 Agent 启用了 cron 能力特性（其 `requires_tool="cron"` 已联动进 `tool_allowlist`）
- **WHEN** Gateway 为该 Agent 构建会话
- **THEN** 该 Agent 工具集包含 `cron` 工具；停用 cron 能力则 `cron` 工具随之移出

#### Scenario: Gateway 上报能力时标记 skill_view 默认开启
- **WHEN** Gateway 向 IM 上报当前节点可配置工具
- **THEN** 工具列表包含 `skill_view`
- **AND** `skill_view` 的 `default_on` 为 true

### Requirement: 主模型因可用性失败时按有序备用链换模型，本轮继续回复

两种模式均保持下述候选链、可重试条件、持久 Session 粘性与配置重置规则。以下按聊天隔离、失败气泡、切换说明自动出站和 `/new` 重置的 Scenario 适用于 `single_thread`；global 的粘性归主 Session，改模型配置可重置，失败/切换记录归工作轮次，正式聊天仍显式发言，`/new` 不改变其状态。

Gateway 在每次新回复开始时先组链：有该 Kernel session 的备用粘性则第一次就用粘性模型，否则以 Agent 保存的 `default_model`（空则产品默认）为链头，再加上有序 `model_fallbacks`。本轮候选因欠费/额度、过载/5xx、超时、限流或认证失败而无法完成时，用户先看到带该模型名的失败提示；若该 run 没有产出非失败气泡的真实正文或工具时间线，Gateway 按列表顺序改用下一个候选并继续本轮，用户不必再发消息。明确不可重试的错误（如无效密钥 / 401）很快投下该提示，不对同一模型空转；网络抖动与限流才按既有预算同模型重试。上下文太长不换模型。没配备用或整条链耗尽时，每个失败候选留下带模型名的失败提示，不改用其它 Agent 的模型，也不把未配置的平台默认塞进备用链。自动切换不写回保存的 `default_model`。切到备用时使用该备用模型自己的默认推理档，不沿用主模型保存的强度，也不沿用会话 `/effort`。

同一 Kernel session 在成功改用备用后粘在该备用上，直到该聊天 `/new` 或用户保存该 Agent 的主模型/备用列表。另一聊天各自从链头试起。首次因切换而成功回复时，先投递一句轻量说明「已改用 {model}，因为主模型不可用。」再投递该备用模型的普通助手正文；粘住后不再每条重复。说明走与压缩控制确认相同的出站形态，正文不进这条控制消息。Web IM 上该正文带 token 用量。

#### Scenario: 欠费或服务不可用时本轮仍收到回复
- **GIVEN** Agent 保存了有序备用列表，且当前聊天尚未因失败粘在备用上
- **WHEN** 用户发一条消息，主模型因欠费、额度、服务挂了或过载、超时、限流或认证失败而无法完成本轮，且尚未投出真实正文或工具时间线
- **THEN** 用户先看到带该主模型名的失败提示
- **AND** 若失败是无效密钥等明确不可重试的原因，该提示很快出现，不对同一模型空转
- **AND** 不必再发消息，本轮按备用列表顺序改用下一个能用的模型，并收到该备用模型的普通助手回复
- **AND** Web IM 上该回复带 token 用量；「已改用」是独立短说明，不是把正文写进说明里

#### Scenario: 上下文太长不换模型
- **GIVEN** Agent 配备用列表
- **WHEN** 本轮失败原因是上下文太长
- **THEN** 不改用备用模型，仍走今天的压缩或失败呈现

#### Scenario: 没配备用时失败呈现与现在一样
- **GIVEN** Agent 没有备用列表
- **WHEN** 主模型本轮失败
- **THEN** 失败呈现与变更前一致，不改用节点平台默认模型顶上，也不借用其他 Agent 的模型

#### Scenario: 整条备用链都失败时按现状失败呈现
- **GIVEN** Agent 配备用列表，且主模型与全部备用都因可用性失败
- **WHEN** 用户发一条消息
- **THEN** 每个失败的候选都留下带该模型名的失败提示
- **AND** 用户收不到伪装成功的回复

#### Scenario: 已有真实回复后再失败则本轮不换
- **GIVEN** 本轮已经向该聊天投出过非失败气泡的 assistant 正文或工具时间线
- **WHEN** 当前候选随后因可用性失败
- **THEN** 本轮按现状失败收口，不删除已可见内容再开新气泡

#### Scenario: 首次切换有轻量说明，粘住后不再每条提示
- **WHEN** 某聊天本轮因主模型不可用改用了备用模型并成功回复
- **THEN** 用户先看到轻量说明：已改用该备用模型，因为主模型不可用
- **AND** 同一轮随后出现备用模型的普通助手正文；Web IM 上该正文带 token 用量
- **AND** 不出现必须确认的弹窗或按钮
- **WHEN** 用户再发下一条普通消息且本轮没有再次换到另一个模型
- **THEN** 回复正常给出，不再重复那句切换说明

#### Scenario: 粘在当前聊天，不改写保存的主模型
- **GIVEN** 某聊天本轮已改用备用模型 B
- **WHEN** 用户在同一聊天接着发消息，且没有 `/new`、也没有改该 Agent 的主模型或备用列表
- **THEN** 新回复继续使用 B
- **AND** Agent 保存的 `default_model` 仍是原来的主模型

#### Scenario: `/new` 或改模型配置后重新从主模型试起
- **GIVEN** 某聊天已粘在备用模型上
- **WHEN** 用户发送 `/new`，或保存对该 Agent 主模型或备用列表的修改
- **THEN** 之后的普通消息重新从保存的主模型试起

#### Scenario: 另一个聊天互不影响
- **GIVEN** 同一 Agent 的聊天甲已粘在备用模型上
- **WHEN** 用户在该 Agent 的另一个尚未切换过的聊天乙发消息
- **THEN** 聊天乙仍先使用保存的主模型
