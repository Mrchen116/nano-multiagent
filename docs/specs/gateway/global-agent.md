# gateway (personal_assistant) - Global Agent Specification

> 对齐: feat-552
> 上级: [gateway (personal_assistant) Specification](spec.md)

## Purpose

全局 Agent 跨聊天持续工作、Inbox 摄取、内部委派、显式投递、群聊复核和主上下文控制的 Gateway 契约。

## Requirements

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
- **AND** 续页保持原查询快照；IM 断连导致在线历史暂不可续读时，原游标可在恢复后重试；缓存历史明确标出仅含已接收记录及权限确认时间
- **AND** 普通文件附件按其描述和读取入口摄取，不因误认图片而持续阻塞向来源群回复

#### Scenario: 受限的聊天访问
- **WHEN** Agent 查询它不可访问的聊天，或子 Agent 尝试消费全局主 Inbox
- **THEN** 请求被拒绝，不扩大访问权限或改变消费位置


#### Scenario: 模型读取简洁且可操作的 Inbox 结果
- **WHEN** 全局 Agent 查看或读取 Inbox
- **THEN** 来源摘要提供真实可读名称、待读数量和必要的提及线索；普通 check 在输出预算内列全，超过预算时可继续读取且不遗漏来源
- **AND** read 保留消息与发送者稳定身份、真实名字、秒级 UTC 时间和有序正文／多模态内容；内部回执、分片及重复路由字段不进入模型上下文
- **AND** 只有存在后续页、不完整内容或读取错误时才附相应信息；精简展示不影响持久摄取确认、用户请求的权限识别或人的聊天已读状态

### Requirement: Inbox 与聊天使用同一会话标题

#### Scenario: 私聊被用户改名后读取
- **WHEN** 用户修改私聊会话名后 Agent 再查询或读取该会话
- **THEN** Inbox 显示同一个新标题，身份和回复目标不变

### Requirement: 聊天工具提供连续的查询到发送路径
#### Scenario: 已知群聊查询成员并沟通
- **WHEN** 全局Agent查询指定聊天信息并使用返回身份私信或群内提及
- **THEN** 得到完整成员及可直接使用的身份，消息到达选定对象
#### Scenario: 未读与历史辨认同一发送者
- **WHEN** Agent读取同一聊天的未读和历史
- **THEN** 发送者身份、聊天类型与内容表达一致，历史查询不消费Inbox

#### Scenario: 外部聊天发送者没有 IM 身份映射
- **WHEN** 读取外部来源消息，现有记录未关联真实 IM 用户
- **THEN** 明确显示外部来源身份，不将代记账号作为可私信发送者；平台身份已知时保留该身份，未知历史只保留已知显示名，回复仍发往原聊天

### Requirement: 全局未获准动作由主 Agent 继续处理

#### Scenario: 自动拒绝或审核故障
- **WHEN** 全局消息驱动的主 Agent 或其普通 child 动作未获准
- **THEN** 不弹权限卡片、不挂权限 Future；原因交回主 Agent，由其选择合规替代、普通聊天询问或说明停止；故障不归咎于用户未授权。

#### Scenario: 正常发送询问
- **WHEN** Agent 在发起事项的合适聊天中澄清具体操作
- **THEN** send_message 根据完整目标和正文审核，正常询问适用协作/回复例外；工具整体不免审，结果中的 accepted、held_for_revalidation 或错误按实际状态保留，不把受理或暂缓描述为已送达。

#### Scenario: 主会话创建、恢复与运行配置刷新
- **WHEN** 全局主 session 新建，或既有/恢复主 session 在空闲后继续接收事项、刷新运行配置
- **THEN** 保留未获准动作返回主 Agent 的交互选择；仅读取已有绑定不替换忙碌运行的配置，后续接续在提交前沿共享运行配置入口应用该选择。
- **AND** 该会话被 Heartbeat 复用时仍按实际自动入口的原 fallback 处理，不改变普通 global wake 和普通 child 的返回路由。

### Requirement: Inbox 保留工具形态与多来源授权语义

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

### Requirement: 等待确认可继续独立事项并按原来源恢复

#### Scenario: 其他聊天有工作
- **WHEN** 当前事项在等待用户回复
- **THEN** 待确认动作保持未执行，Agent 可完成独立工作，无事则 idle，回复到来后重新处理原事项。

#### Scenario: 普通跨轮或重启压缩后回复
- **WHEN** 用户回答旧问题
- **THEN** 根据当前可见问答与 CC 实时/恢复规则判断；必要时通过 conversations 查询背景后重述确认，查询旧消息不产生新的 live Inbox 投影，不复认证旧授权，也不要求用户重提完整任务。

#### Scenario: 连续拒绝
- **WHEN** 普通 global wake 或 global child 的拒绝次数达到阈值
- **THEN** 不变成弹窗等待、不因计数放行，后续新动作仍能接受分类；Heartbeat（包括复用全局主 session）和独立 Cron 按各自自动入口继续原有 fallback；普通 global child 仍返回主 Agent，不因 BACKGROUND_TASK 调度值切到该 fallback。
