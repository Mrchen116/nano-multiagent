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

（无）

## REMOVED Requirements

（无）
