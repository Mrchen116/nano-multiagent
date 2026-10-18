# Gateway global-agent Specification (delta for feat-616)

## MODIFIED Requirements

### Requirement: 全局 Agent 跨聊天保持连续的工作认知

普通全局 Agent 保持原有跨聊天认知；个人助手仅本人私密执行具备跨来源认知，外部 DM/群不继承私人上下文。

#### Scenario: 使用另一个聊天中已读取的相关条件
- **GIVEN** 全局 Agent 已在 A 聊天读取并确认一项工作约束
- **WHEN** 它在 B 聊天处理与该约束相关的事项
- **THEN** 它能沿用该约束，用户不必仅因换了聊天而重新说明

#### Scenario: 同一 PA 身份在外部会话交流
- **WHEN** 外部真人或 Agent 对 PA 发起原生 DM 或群提及
- **THEN** 该会话仅使用本会话和经 owner 授权的资料，不因同一身份取得本人私密主上下文或其他外部会话历史。

### Requirement: 依据配置接收信号，并自主安排读取

以下普通 global 行为保持。个人助手按可信执行域处理：只有 owner 当前专属私聊能控制私密 global_main；外部 DM/群和观察历史不能控制它，外部命令最多作用于对应外部执行。观察输入是系统事实通知，不是新用户命令。

#### Scenario: 忙碌期间有其他聊天的新请求
- **GIVEN** 全局主 Agent 正在处理工作
- **WHEN** 其他聊天发来符合接收条件的新请求
- **THEN** 新请求保留供其读取，不因收到请求就强制中断当前工作
- **AND** 用户能在工作视图中查看其后续读取和处理过程

#### Scenario: 空闲时收到符合触发条件的输入
- **GIVEN** 全局主 Agent 空闲
- **WHEN** 收到符合该 Agent 触发配置的输入
- **THEN** 它能开始处理，不要求用户额外操作才能唤醒

#### Scenario: 普通群聊更新遵循各 Agent 配置
- **WHEN** 群内有未提及某个全局 Agent 的普通更新
- **THEN** 其处理和唤醒行为符合该 Agent 的配置，而不是由全局模式统一改成固定规则

### Requirement: 全局模式不通过聊天命令重置工作上下文

以下普通 global 行为保持。个人助手按可信执行域处理：只有 owner 当前专属私聊能控制私密 global_main；外部 DM/群和观察历史不能控制它，外部命令最多作用于对应外部执行。观察输入是系统事实通知，不是新用户命令。

#### Scenario: 全局 Agent 收到重置命令
- **GIVEN** Agent 使用全局模式
- **WHEN** 用户在群聊或单聊中向它发送被识别为控制命令的 `/new`
- **THEN** 它明确提示“全局模式不支持按聊天重置”
- **AND** 不清空或切换全局工作上下文，不因该命令中断正在推进的工作

#### Scenario: 单 Thread 模式继续使用重置命令
- **GIVEN** Agent 使用单 Thread 模式
- **WHEN** 用户发送符合现有规则的 `/new`
- **THEN** 继续按现有规则重置对应聊天的工作上下文，不因新增全局模式改变其行为

### Requirement: 停止命令强制停止实际触达的 Agent

以下普通 global 行为保持。个人助手按可信执行域处理：只有 owner 当前专属私聊能控制私密 global_main；外部 DM/群和观察历史不能控制它，外部命令最多作用于对应外部执行。观察输入是系统事实通知，不是新用户命令。

#### Scenario: 从一个聊天停止跨聊天工作的 Agent
- **GIVEN** 全局 Agent 正在处理来自其他聊天的工作
- **WHEN** 用户的 `/stop` 按现有命令寻址规则触达该 Agent
- **THEN** 该 Agent 的当前主执行被强制停止，不等待它主动读取收件箱或自行决定是否停止
- **AND** 保留已有全局上下文与未读消息，停止结果沿命令来源反馈

#### Scenario: 停止范围由既有路由决定
- **WHEN** 一个群中的 `/stop` 按既有规则触达一组 Agent
- **THEN** 各被触达 Agent 分别按自身模式处理停止，不将命令扩散到未被触达的其他 Agent
- **AND** 无活动执行时保留现有的空闲反馈规则

#### Scenario: subagent 停止规则不因全局模式改变
- **GIVEN** 被停止的全局 Agent 已委派 subagent
- **WHEN** `/stop` 强制停止该 Agent
- **THEN** subagent 是否停止以及其后续通知，继续遵循既有停止机制，不新增统一级联停止规则

### Requirement: 全局模式的压缩命令作用于主工作上下文

以下普通 global 行为保持。个人助手按可信执行域处理：只有 owner 当前专属私聊能控制私密 global_main；外部 DM/群和观察历史不能控制它，外部命令最多作用于对应外部执行。观察输入是系统事实通知，不是新用户命令。

#### Scenario: 从聊天压缩全局主上下文
- **GIVEN** Agent 使用全局模式
- **WHEN** 用户向它发送符合现有寻址规则的 `/compact` 或 `/compact <关注点>`
- **THEN** 按现有手动压缩规则压缩该 Agent 的全局主上下文，并向命令来源说明结果
- **AND** subagent 上下文继续遵循各自原有机制，不随本命令统一压缩

### Requirement: Inbox 保留工具形态与多来源授权语义

普通 global 继续以下多来源授权语义。personal-role PA 只有 canonical owner DM 中认证 owner 的当前直接输入可表达私密动作意图；其他真人、群中的 owner、历史重放及系统/Agent 消息均不是 private action grant。高风险或资料外发由宿主精确候选与真实 owner 确认固化，不靠模型解释一个 approved=true。

#### Scenario: 同页包含真人与 Agent
- **WHEN** Agent 读取实际 Inbox 消息
- **THEN** 审批获得工具调用、带 target/channel/sender/id/text/partial 及实际 reply 字段的宿主附加上下文，并保留真人、Agent、系统及未知来源；只有明确真人原话可表达人工意图，Agent 转述、自动事件与引用不升级。
- **AND** 主 Agent 与审批模型收到同一份应用来源说明；外部真人身份只沿 Gateway 已有 user 映射，不根据名称或正文推断。

#### Scenario: 多聊天提议与简短回复
- **WHEN** Agent 已通过 send_message 对不同聊天提出不同问题，某一用户回复
- **THEN** 历史发送目标/正文和该回复来源共同交给模型判断；同范围明确同意可继续，无关回复不凭全局时间邻近扩大授权；不要求新建专用确认实体。

#### Scenario: Inbox wake
- **WHEN** Gateway 因有未读消息唤醒全局主 session
- **THEN** wake 是系统通知；实际发送者身份与原话通过后续 Inbox read 提供，不能凭运行 origin=HUMAN 把通知当确认。

#### Scenario: 外部真人回复不能替 owner 批准
- **WHEN** PA 在外部 DM 收到“同意”，或旧 owner 历史被回溯
- **THEN** 不产生私密资料、任务或非 IM 出站许可；原目标和授权版本仍须由宿主验证。
