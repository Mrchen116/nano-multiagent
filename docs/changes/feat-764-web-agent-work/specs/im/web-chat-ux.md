# IM Web Chat UX Specification (delta for feat-764)

## ADDED Requirements

### Requirement: Web 聊天可从 Agent 头像查看工作状态

#### Scenario: 私聊和群聊查看同一个 Agent
- **GIVEN** 用户可以查看该 Agent 的 Work
- **WHEN** 在私聊或群聊点击 Agent 头像
- **THEN** 在头像旁查看主 Agent 状态、正在执行的主轮次最近工具，以及正在运行、待授权的子 Agent 数量；关闭后原聊天位置和草稿仍可继续使用。
- **AND** 可以展开一、二级等活跃子执行并打开相应 Work，配置入口仅在具备编辑资格时显示。

#### Scenario: 执行状态暂不能确认
- **WHEN** 工作记录正在补齐、节点离线或活跃状态不能确认
- **THEN** 显示对应同步或不确定状态，不把尚未确认的执行数显示为零。


### Requirement: 单条 Agent 回复的执行记录从消息操作打开

#### Scenario: 在桌面与触屏追溯一条回复
- **GIVEN** 消息满足已有 Work 入口的可见性条件
- **WHEN** 用户使用桌面悬停或键盘工具条、右键菜单、触屏长按或更多操作
- **THEN** 可选择查看这条回复的执行记录，直达真实发信轮次，消息下方不重复显示常驻入口。
- **AND** 仅交互卡或附件的符合资格回复同样可用；不可用、尚未同步和已删除的记录仍遵守现有访问规则及反馈。
