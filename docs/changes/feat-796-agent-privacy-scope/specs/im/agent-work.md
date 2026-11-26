# im/agent-work.md (delta for feat-796)

## MODIFIED Requirements

### Requirement: 聊天沟通与全局工作轨迹分开呈现

#### Scenario: Agent 向聊天报告进展或结果
- **WHEN** 主 Agent 选择向某个群聊或单聊发送进展、问题或结果
- **THEN** 消息出现在它明确选择的聊天中
- **AND** 不附带与该聊天无关的整段全局执行轨迹

#### Scenario: 查看员工整体工作
- **WHEN** 全局 Agent 的管理者本人，或（当该全局普通 Agent 处于「团队公开」且其管理者为有效团队成员时）其他有效团队成员进入该全局 Agent 的工作视图
- **THEN** 可以查看主 Agent 跨聊天的连续工作轨迹，辨认其读取、执行及委派过程（无论管理者是否启用了个人空间）
- **AND** 若该全局 Agent 处于「私有」（`owner_only`）或属于个人助手（PA），非管理者访问其 Work 相关接口返回 404 且不接收其实时 `agent.work.updated` 事件。

#### Scenario: 深入查看 subagent 工作
- **GIVEN** 主 Agent 已委派 subagent 且查看者具备该主 Agent 的 Work 查看资格
- **WHEN** 用户查看这次委派对应的执行过程
- **THEN** 可以查看 subagent 的工作轨迹及当前结果，并辨认其与主 Agent 委派的关联，不要求是 Agent 管理者

#### Scenario: Work 内容完整可见，原聊天仍按会话范围访问
- **GIVEN** 主执行和子执行记录包含查看者未参与的聊天内容
- **WHEN** 有该 Agent Work 查看资格的用户查看 Work，或从中点击来源聊天及受保护附件
- **THEN** Work 的已有内容不按来源聊天过滤或遮盖；打开原聊天和受保护附件仍按[当前会话读取资格](auth-tenancy.md#requirement-数据面按登录身份聊天成员与资源管理归属确定访问)单独判定，Work 可见不额外授予来源访问权。

#### Scenario: 非管理者持续查看工作进度
- **GIVEN** 有效团队成员打开有权访问的「团队公开」全局普通 Agent Work
- **WHEN** Agent 产生新的过程记录，或用户刷新、恢复可见页
- **THEN** 可继续看到更新后的完整记录；节点离线及尚未知的执行状态可辨认。
