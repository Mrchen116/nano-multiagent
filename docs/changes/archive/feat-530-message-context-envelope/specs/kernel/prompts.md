# kernel / prompts — delta (feat-530)

> Target canonical: `docs/specs/kernel/prompts.md`

## ADDED Requirements

### Requirement: session 创建时间由完整运行配置显式控制

Kernel通过product-neutral feature `include_session_created_datetime`控制runtime footer是否包含session创建时间。该feature默认`True`，保持既有`Current date and time`与current working directory；消费者显式设为`False`时只保留current working directory。稳定timezone等产品文案仍由消费者经普通PromptSlots提供，Kernel不根据PromptText name、workspace或routing metadata猜测产品。该policy不改变消息的提交、消费、持久化或恢复生命周期。

#### Scenario: 显式关闭 session 创建时间
- **GIVEN** 一个session的完整运行配置将`include_session_created_datetime`设为`False`，且PromptSlots提供稳定timezone
- **WHEN** Kernel 为该 session 装配 system prompt
- **THEN** prompt 包含消费者提供的稳定 timezone与 current working directory
- **AND** 不把 session 创建时刻渲染为 `Current date and time`

#### Scenario: 默认或显式开启时保持 runtime footer bytes
- **GIVEN** 一个session省略`include_session_created_datetime` override或显式设为`True`
- **WHEN** Kernel 为该 session 装配 system prompt
- **THEN** runtime footer继续按既有顺序渲染 session-created current datetime与 current working directory

#### Scenario: PromptText name 不改变 Kernel policy
- **WHEN** 消费者增加、删除或重命名一个PromptText，但没有改变完整运行配置中的`include_session_created_datetime`
- **THEN** Kernel runtime footer policy不因 PromptText name变化

## MODIFIED Requirements

### Requirement: feature 内核只留通用项，产品专属条件 prompt 经 PromptSlots 持久归属会话配置

内核 feature目录只含产品无关的通用 guidance或 runtime policy；其中需要内核工具的 guidance同时受 feature开关与 required tool在场门控，不需要工具的通用 policy可声明 `requires_tool=None`。产品专属条件 prompt全文由消费者经 `PromptSlots` 提供。消费者在创建会话时提供初始值，也可经明确的完整运行配置替换更新既有会话；产品不通过普通 per-turn参数或 hook临时注入系统提示。

#### Scenario: 工具相关通用 feature由会话开关与工具在场门控
- **GIVEN** 会话运行配置启用某个声明 required tool的通用 feature
- **WHEN** required tool在 enabled tools中
- **THEN** 对应 guidance出现；feature未开或工具不在场时不渲染

#### Scenario: 无工具通用 policy继承默认值并接受显式布尔覆盖
- **GIVEN** 一个声明`default_on`且`requires_tool=None`的通用runtime policy
- **WHEN** 会话完整运行配置省略该key，或显式提供`True`/`False` override
- **THEN** 省略时Kernel继承registry default，显式提供时按该布尔值应用或省略对应runtime行为
- **AND** Kernel不从产品PromptText或routing metadata猜测override

#### Scenario: 产品 prompt只经会话配置改变
- **GIVEN** 一个已创建会话
- **WHEN** 消费者没有显式替换其运行配置而连续提交多轮
- **THEN** PromptSlots产品内容保持稳定，普通 per-turn参数和 hook不能改写系统提示

## REMOVED Requirements

（无。）
