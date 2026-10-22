# gateway Agent Capabilities Specification (delta for feat-635)

## ADDED Requirements

### Requirement: DSH Goal SHALL 默认关闭并独立于 Task

#### Scenario: 现有及新建 Agent
- **WHEN** Agent 没有用户明确开启 dsh_goal 的配置
- **THEN** 原生 Goal 管理工具及专属引导默认关闭，既有工具白名单包含其名称不视为主动开启。
- **AND** Task 持续执行独立生效，不转换、双写或同步两套状态，不进行历史 Goal 迁移或清理。

#### Scenario: 用户显式开启和关闭
- **WHEN** 用户在配置页开启或关闭 DSH Goal
- **THEN** 下一轮按配置整体更新其原生工具及自动接线，开启保留原生工具语义与授权，关闭不影响 Task 的执行责任。
