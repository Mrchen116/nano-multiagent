# Gateway agent-capabilities Specification (delta for bugfix-629)

## MODIFIED Requirements

### Requirement: 无摘要换窗的 workspace 支持持续任务与按需恢复

#### Scenario: 多次换窗后继续任务
- **GIVEN** 用户在已启用该能力的 workspace 提供了目标、限制并在后续纠正过要求
- **WHEN** 同一个未完成任务经历多次上下文换窗
- **THEN** Agent 能利用已保存记录与原始历史继续工作，按最新有效要求交付，不要求用户重复提供仍可恢复的信息
- **AND** 不因换窗重复已经完成的外部副作用，不把未完成事项报告为完成

#### Scenario: 新任务已读但尚未保存笔记时强制换窗
- **GIVEN** 旧笔记记录旧事项已完成，而 Agent 已读到新的直接或 Inbox 请求且尚未完成
- **WHEN** 在保存新笔记前发生压力或容量溢出换窗
- **THEN** Agent 能定位并恢复本次工作的原始输入与已完成动作，继续按最新请求交付
- **AND** 不以旧笔记为由把当前请求报告为无任务或已完成

#### Scenario: 恢复原始细节或说明缺口
- **WHEN** 换窗后的任务需要早先消息或较长工具结果中的细节
- **THEN** Agent 可以按需恢复已离开活动上下文的原始记录及来源，并据此继续工作
- **AND** 缺失记录时如实说明具体缺口，不编造已经恢复的信息

#### Scenario: 长任务按需恢复 Skill
- **GIVEN** 会话曾使用多个 Skill 并已发生换窗
- **WHEN** Agent 继续工作或需要此前使用的操作指导
- **THEN** 新窗口根据当前能力重建可用 Skill 目录，不自动重放此前加载的正文或整个会话的已用 Skill 索引
- **AND** Agent 按需通过已获准的 Skill/文件工具读取，或从当前会话 History 恢复此前原始加载记录；无 `skill/read` 工具时也不回退自动正文、不扩大权限
- **AND** 普通工具进展与历史导航不会让未变化的 Skill 正文每步重复进入上下文
- **AND** 显式停用新模式后，旧摘要模式的 Skill 恢复行为保持
