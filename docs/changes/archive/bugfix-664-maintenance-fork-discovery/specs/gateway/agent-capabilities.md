## ADDED Requirements

### Requirement: 系统知识维护不进入模型的子 Agent 管理目录

系统启动的 Memory、Skill、combined 和 F4 维护 SHALL 保留继承上下文与独立执行历史，但不发布为模型通过 `list_agents` 管理的子 Agent。模型正常委派的 Agent 发现、续接与取消能力保持。

#### Scenario: 长期 Agent 查询受管理的执行者

- **GIVEN** 同一 Agent 已完成多次系统知识维护
- **WHEN** 模型查询直接子 Agent 或递归查询后代 Agent
- **THEN** 新维护运行不在管理目录中，查询不进入这些维护分支；维护不会因历史积累扩大受管理 Agent 集合。
- **AND** 正常模型委派的运行按既有规则列出。

#### Scenario: 维护执行失败或取消

- **WHEN** 系统维护发生模型失败、步骤上限或取消
- **THEN** 保留真实终结状态和此前成功事实，未完成工作不推进维护周期，执行结束后释放运行资源。
