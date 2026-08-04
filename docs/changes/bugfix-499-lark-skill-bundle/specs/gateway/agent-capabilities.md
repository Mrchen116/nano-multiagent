# gateway (personal_assistant) - Agent Capabilities Specification (delta for bugfix-499)

## ADDED Requirements

### Requirement: 飞书绑定 agent 获得完整 Lark skill bundle

Gateway 随包提供当前产品定义的完整 Lark skill bundle。绑定飞书 channel 的
agent 能发现该 bundle 并使用其中与用户请求匹配的 Lark 能力；能力默认沿用
Gateway 所在机器已登录的 Lark 用户身份，只有各 skill 已有规则明确要求时才
使用其他身份。

#### Scenario: 新安装的飞书 agent 发现完整 Lark 能力
- **GIVEN** 用户本机尚未安装任一同名的 Lark skill
- **WHEN** Gateway 启动并为 agent 启用飞书 channel
- **THEN** agent 的 capabilities 和会话可发现产品随包的完整 Lark skill bundle
- **AND** 用户可从飞书要求该 agent 操作文档、云盘、表格、日程、任务、审批、邮件、知识库、会议或其他由 bundle 覆盖的 Lark 资源

#### Scenario: 显式 skill allowlist 的飞书 agent 获得完整 bundle
- **GIVEN** 飞书绑定 agent 的本地 skills allowlist 非空且缺少一个或多个 Lark skill
- **WHEN** Gateway 启动静态 `config.channels` 中的该飞书 channel，或调和 IM 托管的该飞书 channel
- **THEN** Gateway 保留已有条目并将完整 Lark skill bundle 加入 allowlist
- **AND** 重复调和不会重复写入或重复列出 bundle skill

#### Scenario: 空 skill allowlist 保持默认发现语义
- **GIVEN** 飞书绑定 agent 的本地 skills allowlist 为空
- **WHEN** Gateway 启动或调和该飞书 channel
- **THEN** Gateway 不将完整 bundle 物化写入该 allowlist
- **AND** 该 agent 仍按默认全局 skill discovery 发现 Lark bundle

#### Scenario: 静态 Feishu agent 的 IM profile ingress 保留完整 bundle
- **GIVEN** Gateway 的静态 `config.channels` 绑定了一个 skills allowlist 非空的 Feishu agent
- **AND** IM 中该 agent 已存在一个尚未包含完整 Lark skill bundle 的 mirror profile
- **WHEN** Gateway 连接、重连 IM，或接收该 agent 的 `config.sync` profile 更新
- **THEN** Gateway 将完整 Lark skill bundle 补齐到该 agent 的显式 profile 后再应用到本地运行态
- **AND** 该 agent 后续会话仍可发现完整 Lark skill bundle

#### Scenario: 用户明确请求独立 Lark 事件监听
- **WHEN** 用户要求飞书绑定 agent 监听并处理一种 Lark 事件
- **THEN** agent 可使用 bundle 中的 Lark event 能力按其既有身份、授权和生命周期规则建立独立监听
- **AND** 该监听不取代 Gateway 对普通飞书对话的消息接收和回复

## MODIFIED Requirements

## REMOVED Requirements

### Requirement: 内置 skills 启动自举
