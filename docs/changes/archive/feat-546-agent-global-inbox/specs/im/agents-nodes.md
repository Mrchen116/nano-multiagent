# im/agents-nodes Specification (delta for feat-546)

> 目标增量；实施校正后归并 current。

## ADDED Requirements

### Requirement: 新建时选择工作模式，已有 Agent 保持原行为

#### Scenario: 新建全局 Agent
- **WHEN** 用户创建 Agent 并选择全局模式
- **THEN** 创建结果保留该选择，后续跨聊天工作按全局方式进行

#### Scenario: 保留单 Thread 方式
- **WHEN** 用户使用已有 Agent，或新建时选择单 Thread 模式
- **THEN** 继续使用当前各聊天独立工作的行为

#### Scenario: 不提供模式切换
- **WHEN** 用户查看或编辑一个已创建 Agent 的配置
- **THEN** 可以辨认其模式，但不能将其改成另一种模式
