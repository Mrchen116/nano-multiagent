# IM 会话消息增量契约

### Requirement: 通用草稿采用只填入目标输入框

#### Scenario: 与明确请求区分
- **WHEN** 用户点击 SendToChat 等明确提交请求的动作
- **THEN** 向当前聊天提交实际点击用户的消息和状态快照，保留卡片Agent关注及普通群成员／Agent可见性；与只填输入框的ComposeMessage分开。
- **AND** 新动作和生成指南统一使用SendToChat(message, context?)；旧ToAssistant卡片继续解释，不改写历史。两者均沿现有提交、来源、权限、只读和幂等契约，不能与ComposeMessage组合隐式提交。
