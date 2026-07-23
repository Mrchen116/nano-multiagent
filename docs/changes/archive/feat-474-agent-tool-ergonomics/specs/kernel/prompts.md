# kernel / prompts — delta (feat-474)

> 目标 canonical: `docs/specs/kernel/prompts.md`

## ADDED Requirements

### Requirement: 内置子 agent 类型经 PromptSlots 注入专用角色指引

经 `agent` 工具新建的子会话不继承父会话的产品 PromptSlots；按所选内置类型写入该子会话自己的 PromptSlots（身份在 head、角色与只读约束在 body）。`Explore` / `Plan` 的指引表达只读探索/规划职责；`general-purpose` 表达可完成多步实现类任务。类型文案在该子会话配置代次内稳定，不因父会话后续替换运行配置而改变已创建子会话的角色提示。

#### Scenario: Explore / Plan 子会话携带只读角色指引
- **WHEN** 消费者以 `Explore` 或 `Plan` 新建子 agent 并装配其 system prompt
- **THEN** 子会话 PromptSlots 含该类型的只读角色指引，且不含父会话产品身份/行为文案的副本

#### Scenario: general-purpose 子会话携带通用执行指引
- **WHEN** 消费者以缺省或显式 `general-purpose` 新建子 agent 并装配其 system prompt
- **THEN** 子会话 PromptSlots 含通用执行类角色指引，且不含父会话产品 PromptSlots 副本

## MODIFIED Requirements

（无。）

## REMOVED Requirements

（无。）
