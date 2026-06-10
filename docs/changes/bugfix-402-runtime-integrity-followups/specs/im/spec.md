# IM Specification (delta for bugfix-402)

## ADDED Requirements

### Requirement: Web IM 身份与会话参与者不依赖全局真人用户目录

Web IM 的当前用户只来自认证会话，Agent 候选来自 `/im/v1/agents`，已有会话中的真人和 Agent
身份来自 conversation `participants`。前端不得请求、创建或兼容 `/im/v1/users`，也不提供全局
真人搜索或新真人会话发现。

#### Scenario: 打开和浏览现有聊天

- **WHEN** 已认证用户打开 Web IM、浏览会话列表或进入 Agent/已有真人会话
- **THEN** 页面使用认证用户和 conversation actors 展示身份，不请求 `/im/v1/users`

#### Scenario: 创建 Agent 直聊

- **WHEN** 用户选择自己可见的 Agent 创建 direct conversation
- **THEN** 前端使用 `/im/v1/agents` 返回的 Agent actor 信息创建会话，不创建 Agent alias user

#### Scenario: 创建 Agent 群聊

- **WHEN** 用户选择多个自己可见的 Agent 创建 group conversation
- **THEN** 候选和 participants 均来自 Agent actor，流程不读取全局真人目录

#### Scenario: 已有真人会话仍可继续

- **GIVEN** 用户已有一个包含其他真人 participant 的 conversation
- **WHEN** 用户打开并继续该会话
- **THEN** 真人身份取自 conversation response；当前版本不据此开放真人搜索或创建入口
