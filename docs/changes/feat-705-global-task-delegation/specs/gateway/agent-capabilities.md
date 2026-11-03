# gateway agent-capabilities Specification (delta for feat-705)

> 目标：`docs/specs/gateway/agent-capabilities.md`。

## ADDED Requirements

### Requirement: Global 的一级执行者获得独立工作能力，二级沿用原生子 agent

#### Scenario: 主会话工具选择不缩减完整事项执行能力
- **GIVEN** Global／PA 主会话的工具选择满足其日常和协调需要
- **WHEN** 主会话把完整事项交给一级 subagent
- **THEN** 一级以 DSH 默认工作能力为基础执行，可使用原生 fork、子 agent 及内部通信，不因主会话未勾选普通工作工具而失去这些能力。
- **AND** 主会话自身仍按其有效选择执行；一级工作能力不反向开启主会话未选择的工具，也不恢复运行时未装载的能力。

#### Scenario: 二级无额外产品身份
- **WHEN** 一级创建普通二级 subagent
- **THEN** 二级使用 DSH 原生子 agent 上下文与父级交办的子目标，不额外注入 Nano 身份或完整事项负责者职责，不自动复制父级历史。
- **AND** fork 继续使用原生父上下文继承，不因该规则裁改其前缀；各级来源、审批、深度、workspace 与宿主产品权限限制仍有效，用户沟通逐级经过 Global。

#### Scenario: 更新与恢复保持角色边界
- **WHEN** 修改主会话工具选择，或恢复已有一级／二级会话
- **THEN** 按该层职责恢复实际工作能力与上下文，原执行者身份和已有工作保留；主会话 fork 开关不撤销一级的原生 fork 能力。
- **AND** 共享 Feature、Skill 与扩展的选择、撤回和权限继续生效；不将其他特定范围的子任务自动升级为完整工作执行者。

### Requirement: 主会话 fork 默认关闭，可按现有工具规则开启

#### Scenario: 新建和无显式工具选择
- **WHEN** 新建 Global、PA 或 SingleThread 主 Agent，或主会话配置没有显式工具名单
- **THEN** subagent_fork 默认不启用，仍可在现有工具目录发现并选择；普通 subagent 和 Global 固定基础能力不因此关闭。
- **AND** 此主会话默认值不套用到 Global／PA 一级执行者的 DSH 工作工具。

#### Scenario: 显式选择与撤回
- **WHEN** 用户选中或取消主会话 fork 并保存
- **THEN** 采用现有工具配置及生效规则，模型可调用能力和预览与有效设置一致；开启只增加原生工具，不增加专门身份提示、清理流程或新开关。
- **AND** Goal 三工具仍各自选择、默认关闭，不因启用 fork 而启用 Goal 或注入 Goal 专属指导。

#### Scenario: 保留已有选择
- **WHEN** 已保存工具名单的 Agent 升级或恢复
- **THEN** 名单保持，显式启用的 fork 仍可用，不按新默认值覆盖已有选择；原生返回和继承语义保持。
