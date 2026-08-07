# Gateway Agent Capabilities Specification (delta for refactor-483)

## MODIFIED Requirements

### Requirement: Agent 工具集由 tool_allowlist 真白名单决定并在执行层强制，能力特性按 requires_tool 联动其工具

Gateway 为某 Agent 构建会话工具集时，以该 Agent 配置的 `tool_allowlist` 为白名单单一来源：非空时
Agent 工具集**恰为**列出的这些（列表外的默认工具不提供，即默认文件/web 工具可被用户禁用）；**显式
为空时该 Agent 没有任何工具**。会话执行层按同一白名单强制：名单外工具调用（含模型未按声明自由发挥
的调用）被拒且不产生副作用，调用方收到含工具名与「未在本会话启用」语义的错误结果。能力特性（如
cron）启用时，其 `requires_tool` 工具经“特性→工具”联动已落在该 Agent 的 `tool_allowlist` 里；
停用特性不自动删除仍可独立使用的工具，显式移除工具则同步停用依赖它的特性。Gateway不在运行时另行
注入工具——Agent工具集与配置侧存储的 `tool_allowlist` 一致，无分裂。

#### Scenario: 用户禁用某默认工具后该工具不再提供
- **GIVEN** 某 Agent 的 `tool_allowlist` 被设为不含某默认工具（如不含 `read`）的非空显式集
- **WHEN** Gateway 为某 Agent 构建会话
- **THEN** 该 Agent 工具集不含被禁的默认工具（下发给模型的工具列表里没有它）

#### Scenario: 显式空名单的 Agent 会话拒绝一切工具调用
- **GIVEN** 某 Agent 的 `tool_allowlist` 显式为空
- **WHEN** 用户与该 Agent 会话，模型尝试调用工具
- **THEN** 工具不执行，用户在会话中看到含工具名与未启用语义的明确反馈

#### Scenario: 显式工具白名单不被默认集合自动扩宽
- **GIVEN** PA agent 已持久化非空 `tool_allowlist`
- **WHEN** Gateway 为该 agent 创建新 session
- **THEN** session 只启用该白名单列出的工具
- **AND** 若白名单不含 `skill_view`，session不启用 `skill_view`

#### Scenario: 启用 cron 能力使 cron 工具进入该 Agent 工具集
- **GIVEN** 某 Agent 启用了 cron 能力特性（其 `requires_tool="cron"` 已联动进 `tool_allowlist`）
- **WHEN** Gateway 为该 Agent 构建会话
- **THEN** 该 Agent 工具集包含 `cron` 工具

#### Scenario: 停用 feature 不自动删除仍在白名单中的工具
- **GIVEN** 某 Agent 的 cron feature与 `cron` tool均已启用
- **WHEN** 用户只停用 cron feature并保存
- **THEN** `cron` tool仍保留在该Agent的显式白名单中，Gateway继续按该白名单构建工具集

#### Scenario: 显式移除工具会停用依赖 feature
- **GIVEN** 某 Agent 启用了一个声明 `requires_tool="cron"` 的feature
- **WHEN** 用户从tool allowlist显式移除 `cron` 并保存
- **THEN** 该feature同时变为停用，Gateway不会在运行时把`cron`重新注入

#### Scenario: Gateway 上报能力时标记 skill_view 默认开启
- **WHEN** Gateway 向 IM 上报当前节点可配置工具
- **THEN** 工具列表包含 `skill_view`
- **AND** `skill_view` 的 `default_on` 为 true
