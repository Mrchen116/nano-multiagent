# gateway relay-protocol Specification (delta for feat-563)

## ADDED Requirements

### Requirement: Gateway 从已认证 IM 注册结果获得用户访问入口

#### Scenario: 注册与后续配置
- **WHEN** Gateway 完成向 IM 的认证注册
- **THEN** 获得 IM 部署明确配置的用户访问入口，用于 PA 运行背景；节点不得把内部连接 URL 或自行提交的值冒充用户入口。

#### Scenario: 部署缺少必需入口
- **WHEN** IM 没有配置用户入口，或 Gateway 对端版本无法提供它
- **THEN** 产生明确的部署配置或协议错误，不向 Agent 注入猜测的入口。
