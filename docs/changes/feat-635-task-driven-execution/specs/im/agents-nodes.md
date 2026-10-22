# im Agents Nodes Specification (delta for feat-635)

## ADDED Requirements

### Requirement: Web 与原生 iOS SHALL 提供默认关闭的 DSH Goal 配置

#### Scenario: 默认及保存反馈
- **WHEN** 用户进入现有或新建 Agent 的能力配置
- **THEN** 未主动开启时 DSH Goal 显示关闭，说明这是独立的原生目标能力且不与 Task 同步。
- **AND** 用户可主动开关并看到真实保存结果，生效时机沿用下一轮整体生效；失败不能展示已生效。
