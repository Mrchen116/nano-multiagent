# Gateway Agent Capabilities Specification (delta for refactor-679)

## ADDED Requirements

### Requirement: Agent Context SHALL 保留完整信息并区分稳定指导与本轮输入

#### Scenario: 首次处理请求与能力更新
- WHEN PA 或普通 Agent 首次处理请求，或有效环境／Skill 选择发生变化
- THEN 模型在决策前获得有效身份、边界、环境和可用 Skill 入口，环境／能力信息与触发本轮的消息可区分且保留来源，不因顺序改变获得真人授权资格。
- AND Nano 自有固定指导和动态行动提示使用英文；用户自定义指导、任务原文与历史消息保留，Feature 关闭和工具选择继续遵循现有契约。

#### Scenario: 去重与按需读取
- WHEN 同义指导被合并或详情改为按需读取
- THEN 独有事实、权限约束、来源语义和必要行动规则仍在消费时可获得，详情有可发现且有权限的入口；普通输入和内部对象重建不重复追加无变化信息。
- AND 新 PA 使用更新后的默认指导，既有已保存自定义指导不自动回填。

### Requirement: 用户删除 Schedule 后 SHALL 通知所属 Agent

#### Scenario: 用户删除独立或 Task 关联的 Schedule
- WHEN 用户通过设置页成功删除一个 Schedule
- THEN 所属 Agent 获得明确的 Schedule 删除 reminder，包含可识别标题、唯一 ID 及删除事实；即使没有关联 Task 也要通知。
- AND 如果仍有 waiting Task 失去有效关联安排，另外按 Task 契约提醒具体任务；两类事实不能相互替代。

#### Scenario: 重试、恢复和停止边界
- WHEN 删除结果或通知投递在重试／重启后恢复，或 Agent 当前处于停止／禁用边界
- THEN 仅确认成功后表述删除，尚未消费的通知可恢复，同一删除不重复呈现已消费提醒；通知不解除停止、恢复 paused 或增加行动权限。

