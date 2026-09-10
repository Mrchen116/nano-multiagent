# IM Conversations and Messages delta — feat-551

## ADDED Requirements

### Requirement: Agent 新托管图片按会话保护且稳定可回看

IM MUST 将新托管 Agent 图片作为对应会话的受保护资源。访问遵循会话 owner 权限；历史回看不依赖 Agent 原文件或节点在线。此规则不追溯迁移旧公开上传附件。

#### Scenario: 已交付图片持久回看
- **GIVEN** 会话已有新托管的 Agent 图片
- **WHEN** 原文件删除或覆盖、Gateway 重启或离线，用户刷新或重新登录
- **THEN** 有权用户仍看到交付时的同一图片。

#### Scenario: 地址不授予访问权限
- **WHEN** 未登录或其他 owner 用户请求新托管图片
- **THEN** 分别返回 401 或 404，不返回图片；有权用户正常读取。

#### Scenario: 会话 fork 保留图片
- **WHEN** 用户 fork 含图片的消息历史并随后删除原会话
- **THEN** fork 中仍可查看已复制消息的图片，且访问遵循目标会话权限。
