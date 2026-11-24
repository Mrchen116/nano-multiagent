# Agent 目录状态摘要

## ADDED Requirements

### Requirement: Agent 目录提供已确认停用状态

已授权 Agent 联系人条目提供 `lifecycle_disabled` 布尔值，表示当前停用意图已由节点在同一代次确认。列表与导航可用此字段显示已有徽标。

#### Scenario: 停用确认及重新启用
- **WHEN** 停用仍在进行、已确认，随后用户重新启用 Agent
- **THEN** 目录摘要依次为 false、true、false；仅可查看该联系人的用户能读取该摘要。
