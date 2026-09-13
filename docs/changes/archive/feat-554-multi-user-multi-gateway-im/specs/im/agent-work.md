# feat-554 — im/agent-work

> 目标: docs/specs/im/agent-work.md
> 归并时仅替换下列同名条目；REMOVED + ADDED 表达标题及访问规则变更，原有情形在新条目中承接。

## Purpose

多人协作与既有体验承接的目标契约，实施验收后归并。

## MODIFIED Requirements

### Requirement: 聊天沟通与全局工作轨迹分开呈现

#### Scenario: Agent 向聊天报告进展或结果
- **WHEN** 主 Agent 选择向某个群聊或单聊发送进展、问题或结果
- **THEN** 消息出现在它明确选择的聊天中
- **AND** 不附带与该聊天无关的整段全局执行轨迹

#### Scenario: 查看员工整体工作
- **WHEN** 已登录用户进入全局 Agent 的工作视图
- **THEN** 可以查看主 Agent 跨聊天的连续工作轨迹，辨认其读取、执行及委派过程

#### Scenario: 深入查看 subagent 工作
- **GIVEN** 主 Agent 已委派 subagent
- **WHEN** 用户查看这次委派对应的执行过程
- **THEN** 可以查看 subagent 的工作轨迹及当前结果，并辨认其与主 Agent 委派的关联，不要求是 Agent 管理者

#### Scenario: Work 内容完整可见，原聊天仍按成员访问
- **GIVEN** 主执行和子执行记录包含查看者未参与的聊天内容
- **WHEN** 登录用户查看 Work，或从中点击来源聊天及受保护附件
- **THEN** Work 的已有内容不按来源聊天过滤或遮盖；原聊天和受保护附件仍按成员关系判定，非成员无法读取。

#### Scenario: 非管理者持续查看工作进度
- **GIVEN** 用户打开他人的全局 Agent Work
- **WHEN** Agent 产生新的过程记录，或用户刷新、恢复可见页
- **THEN** 可继续看到更新后的完整记录；节点离线及尚未知的执行状态可辨认。
