# IM agent-work Specification (delta for feat-616)

## MODIFIED Requirements

### Requirement: 聊天沟通与全局工作轨迹分开呈现

以下空间共享规则适用于普通 Agent；个人助手的主/子、外部/观察及 authorized_task 专业执行 Work 均仅本人可查看，外部会话参与资格不授予 PA Work 访问权。

#### Scenario: Agent 向聊天报告进展或结果
- **WHEN** 主 Agent 选择向某个群聊或单聊发送进展、问题或结果
- **THEN** 消息出现在它明确选择的聊天中
- **AND** 不附带与该聊天无关的整段全局执行轨迹

#### Scenario: 查看员工整体工作
- **WHEN** 对该 Agent 所在空间有访问权的已登录用户进入全局 Agent 的工作视图
- **THEN** 可以查看主 Agent 跨聊天的连续工作轨迹，辨认其读取、执行及委派过程

#### Scenario: 深入查看 subagent 工作
- **GIVEN** 主 Agent 已委派 subagent
- **WHEN** 用户查看这次委派对应的执行过程
- **THEN** 可以查看 subagent 的工作轨迹及当前结果，并辨认其与主 Agent 委派的关联，不要求是 Agent 管理者

#### Scenario: Work 内容完整可见，原聊天仍按会话范围访问
- **GIVEN** 主执行和子执行记录包含查看者未参与的聊天内容
- **WHEN** 有该 Agent 资源空间资格的用户查看 Work，或从中点击来源聊天及受保护附件
- **THEN** Work 的已有内容不按来源聊天过滤或遮盖；原聊天和受保护附件仍按当前会话读取资格判定；有效公司成员可读公开群，私密群与私聊仅成员可读，Work 可见不额外授予来源访问权。

#### Scenario: 非管理者持续查看工作进度
- **GIVEN** 用户打开有权访问的公司全局 Agent Work
- **WHEN** Agent 产生新的过程记录，或用户刷新、恢复可见页
- **THEN** 可继续看到更新后的完整记录；节点离线及尚未知的执行状态可辨认。

#### Scenario: 个人助手的外部联系人查看工作轨迹
- **WHEN** 外部真人或 Agent 已可与 PA 私聊或同群，继而查询 PA Work、子执行、附件或轨迹
- **THEN** 不因可联系或同公司取得私人工作内容、执行 ID 或其他会话信息；本人仍能查看自己的完整 PA 工作。

#### Scenario: 个人助手专业任务仍只对本人投影
- **WHEN** owner 批准 PA 用专业能力运行独立任务
- **THEN** 实际 product actor 仍为 PA，fresh authorized_task 及其轨迹、产物、媒体、WS 和已知 ID 查询仅本人可见；不投递给普通公司共享 Agent 的账号或历史。
- **AND** 广权限结果正文及子执行输出标记来源未知，仅人在私密 Work 查看，不自动回流模型/记忆/审批；本人须明确选择具体内容作为新输入，才可交给 PA，且不恢复旧源持续观察。
