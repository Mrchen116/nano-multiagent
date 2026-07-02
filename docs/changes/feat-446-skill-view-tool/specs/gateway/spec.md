# Gateway delta-spec: feat-446 skills_usage WS RPC provider

## ADDED Requirements

### Requirement: Skills 使用统计 WS RPC

#### Scenario: IM 前端通过 gateway 读取 skill 使用统计
- **WHEN** gateway 收到 WS RPC `skills_usage_request`（含 agentId）
- **THEN** 读取该 agent workspace 的 `.usage.json`，聚合后返回 `skills_usage_response`

#### Scenario: workspace 不存在或 .usage.json 缺失
- **WHEN** agent workspace 不存在或 `.usage.json` 文件缺失
- **THEN** 返回空 skill 列表（不报错）

## MODIFIED Requirements

### Requirement: PA agent 默认工具集合

本条修改 canonical Gateway/PA agent 配置契约：PA 产品默认工具集合新增 `skill_view`。该默认只在 agent 未显式配置工具白名单时生效；已有显式白名单仍是精确白名单。

#### Scenario: 未显式配置工具白名单的 agent 默认启用 skill_view
- **GIVEN** PA agent 没有持久化非空 `tool_allowlist`
- **WHEN** Gateway 为该 agent 创建新 session
- **THEN** session 启用 PA 默认工具集合
- **AND** 默认工具集合包含 `skill_view`

#### Scenario: 显式工具白名单不被默认集合自动扩宽
- **GIVEN** PA agent 已持久化非空 `tool_allowlist`
- **WHEN** Gateway 为该 agent 创建新 session
- **THEN** session 只启用该白名单列出的工具
- **AND** 若白名单不含 `skill_view`，session 不启用 `skill_view`

#### Scenario: Gateway 上报能力时标记 skill_view 默认开启
- **WHEN** Gateway 向 IM 上报当前节点可配置工具
- **THEN** 工具列表包含 `skill_view`
- **AND** `skill_view` 的 `default_on` 为 true

## REMOVED Requirements

（无）
