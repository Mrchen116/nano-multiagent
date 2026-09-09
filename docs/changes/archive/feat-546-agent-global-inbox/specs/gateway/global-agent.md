# gateway/global-agent Specification (delta for feat-546)

> 目标增量；实施校正后归并 current。

## ADDED Requirements

### Requirement: 全局 Agent 跨聊天保持连续的工作认知

#### Scenario: 使用另一个聊天中已读取的相关条件
- **GIVEN** 全局 Agent 已在 A 聊天读取并确认一项工作约束
- **WHEN** 它在 B 聊天处理与该约束相关的事项
- **THEN** 它能沿用该约束，用户不必仅因换了聊天而重新说明

### Requirement: 依据配置接收信号，并自主安排读取

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

### Requirement: 主 Agent 统筹工作，并偏向按需委派执行

主 Agent 与其派生的 subagent 共同构成同一个数字人，内部委派不转移对用户的交付责任。IM 中的其他 Agent 属于外部协作对象；只有用户设定的上下级关系、职责分工或明确任务授权允许时，才能向其派工。

#### Scenario: 委派实质工作并跟进交付
- **WHEN** 用户向全局 Agent 交办适合委派的实质工作
- **THEN** 主 Agent 倾向安排 subagent 执行，能够接收其结果并继续向用户交付
- **AND** 用户可查看委派及执行过程，委派不被当作整个工作的完成

#### Scenario: 保留主 Agent 自行处理的能力
- **WHEN** 主 Agent 判断一个请求适合直接处理
- **THEN** 它可以自行查询、执行或回复，不因全局模式被强制要求创建 subagent

#### Scenario: 多项工作独立推进
- **WHEN** 主 Agent 将可以独立开展的工作交给不同 subagent
- **THEN** 用户能看到这些工作分别推进，并能辨认各自的结果与所属委派

#### Scenario: 外部通信能力不等于派工权限
- **GIVEN** 用户未授予对其他 IM Agent 的任务分配权限
- **WHEN** 用户要求该数字人完成一项工作
- **THEN** 它可自行执行或内部委派，不因能够向其他 IM Agent 发消息就默认将工作分派给对方

### Requirement: 全局模式向目标群发言前复核应处理的新消息

#### Scenario: 没有新消息时正常发言
- **GIVEN** 全局 Agent 准备向内置 Web IM 群发送消息
- **WHEN** 目标群没有它尚未读取、按其配置需要处理的新消息
- **THEN** 可以正常发言，不需要用户批准或额外触发

#### Scenario: 目标群的新更正被考虑
- **GIVEN** 全局 Agent 正准备向内置 Web IM 群回答一项安排
- **WHEN** Gateway 在发言前收到该群按 Agent 配置需要处理的新更正
- **THEN** 旧草稿不先公开，Agent 读取新信息后重新判断再交付
- **AND** 新信息不影响原结论时可保留原文；是否允许静默仍遵循原有规则

#### Scenario: 复核期间又收到适用的新消息
- **GIVEN** 全局 Agent 已因目标群更正开始复核
- **WHEN** Gateway 在其正式发言前再次收到该群按配置需要处理的新更正
- **THEN** 后续发言继续考虑新更正，不把第一次复核当作永久通行证

#### Scenario: 其他群及仅作背景的更新不阻塞发送
- **GIVEN** 全局 Agent 准备向 A 群发送消息
- **WHEN** 只有 B 群的新消息，或 A 群按其配置仅作背景的普通更新
- **THEN** 这些消息不阻塞本次向 A 群发言，也不因复核改变它们原有的处理与唤醒规则

#### Scenario: 草稿和复核归属员工工作视图
- **WHEN** 用户查看全局 Agent 的工作视图
- **THEN** 可以展开查看真实未发送草稿、所涉目标群与复核过程
- **AND** 未发送草稿不作为群内正式发言出现，也不触发其他 Agent 接话

#### Scenario: 单聊和外部聊天不新增复核
- **WHEN** 全局 Agent 向单聊或外部 channel 发言
- **THEN** 不因本项群聊复核能力增加草稿拦截或复核步骤
- **AND** 外部回复经原 Channel 投递，不能仅保存 Web IM 镜像就确认已发送

### Requirement: 全局模式不通过聊天命令重置工作上下文

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

#### Scenario: 从聊天压缩全局主上下文
- **GIVEN** Agent 使用全局模式
- **WHEN** 用户向它发送符合现有寻址规则的 `/compact` 或 `/compact <关注点>`
- **THEN** 按现有手动压缩规则压缩该 Agent 的全局主上下文，并向命令来源说明结果
- **AND** subagent 上下文继续遵循各自原有机制，不随本命令统一压缩

### Requirement: Inbox 读取与聊天历史读取具有不同的消费语义

全局 Agent 可以先查看待读来源摘要，再选择摄取消息；只有完整内容进入可恢复的主上下文才清除对应待读。聊天发现／历史查询不修改 Agent Inbox 或人的聊天已读状态。

#### Scenario: 只查看摘要或历史
- **WHEN** 全局 Agent 查看 Inbox 摘要或回查某聊天历史
- **THEN** 本 Agent 待读数量和人的聊天已读状态不因该查看推进

#### Scenario: 分页、分段及失败
- **WHEN** 一次读取只返回部分内容，或正文持久摄取失败
- **THEN** 未完整摄取的部分仍可重读，不因页面最大序号被跨过
- **AND** 图片与附件来源不被替换成已完整摄取的虚假声明

#### Scenario: 受限的聊天访问
- **WHEN** Agent 查询它不可访问的聊天，或子 Agent 尝试消费全局主 Inbox
- **THEN** 请求被拒绝，不扩大访问权限或改变消费位置
