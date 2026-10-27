# Gateway Agent Capabilities Specification (delta for feat-667)

## ADDED Requirements

### Requirement: 默认原生委派允许两层执行者

#### Scenario: 执行者再委派独立子工作
- **GIVEN** 使用 Nano 默认原生委派深度，主 Agent 深度为 0
- **WHEN** 深度为 1 的执行者创建下级执行者
- **THEN** 允许深度为 2 的执行者执行并按原生机制回传结果；普通与 PA 使用同一默认深度。

#### Scenario: 默认深度不无限扩展
- **GIVEN** 使用默认深度且未显式覆盖普通 spawn/fork 的深度配置
- **WHEN** 深度为 2 的执行者继续尝试创建第三级
- **THEN** 按原生深度上限拒绝；增加一层不改变并发上限、工具选择或授权范围。
