# IM delta-spec: feat-446 skill 使用统计面板 + F2 session 选择

## ADDED Requirements

### Requirement: Skill 使用统计 API

#### Scenario: 查询 agent 的 skill 使用统计
- **WHEN** 浏览器前端请求 `GET /im/v1/agents/:agentId/skills/usage`
- **THEN** 返回该 agent 的所有 skill 使用数据（name、source、state、use_count、last_used_at、session_refs）

#### Scenario: agent 离线时查询 skill 统计
- **WHEN** agent 不在线（gateway 无法到达）
- **THEN** 返回 503 或空数据，前端显示离线提示

### Requirement: F2 session 选择入口

#### Scenario: 用户在 IM 左侧面板选择 session 发起蒸馏
- **WHEN** 用户在 IM 左侧 session 列表面板中选择若干已结束 session
- **THEN** 提供"生成 skill"操作入口，点击后跳转到新对话并预填 session IDs

## MODIFIED Requirements

（无）

## REMOVED Requirements

（无）
