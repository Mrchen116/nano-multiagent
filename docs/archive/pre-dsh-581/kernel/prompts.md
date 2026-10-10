# kernel (agent) - Prompts Specification

> 对齐: feat-530
> 上级: [kernel (agent) Specification](spec.md)
>
> 写法纪律见 [`../CONTRIBUTING.md`](../CONTRIBUTING.md)「给库/内核写契约的额外纪律」。本目录只收 **消费者经 `agent.sdk` 真正依赖的对外行为**(CDC 裁剪);内部如何装配/实现不在此层(那在代码 + 归档 design)。

## Purpose

产品专属 prompt 条件、PromptSlots 和系统提示组装的内核契约。

## Requirements

### Requirement: feature 内核只留通用项，产品专属条件 prompt 经 PromptSlots 持久归属会话配置

内核 feature 目录只含产品无关的通用 guidance 或 runtime policy；其中需要内核工具的 guidance 同时受 feature 开关与 required tool 在场门控，不需要工具的通用 policy 可声明 `requires_tool=None`。产品专属条件 prompt 全文由消费者经 `PromptSlots` 提供。消费者在创建会话时提供初始值，也可经明确的完整运行配置替换更新既有会话；产品不通过普通 per-turn 参数或 hook 临时注入系统提示。

#### Scenario: 工具相关通用 feature 由会话开关与工具在场门控
- **GIVEN** 会话运行配置启用某个声明 required tool 的通用 feature
- **WHEN** required tool 在 enabled tools 中
- **THEN** 对应 guidance 出现；feature 未开或工具不在场时不渲染

#### Scenario: 无工具通用 policy 继承默认值并接受显式布尔覆盖
- **GIVEN** 一个声明 `default_on` 且 `requires_tool=None` 的通用 runtime policy
- **WHEN** 会话完整运行配置省略该 key，或显式提供 `True`/`False` override
- **THEN** 省略时 Kernel 继承 registry default，显式提供时按该布尔值应用或省略对应 runtime 行为
- **AND** Kernel 不从产品 PromptText 或 routing metadata 猜测 override

#### Scenario: 产品 prompt 只经会话配置改变
- **GIVEN** 一个已创建会话
- **WHEN** 消费者没有显式替换其运行配置而连续提交多轮
- **THEN** PromptSlots 产品内容保持稳定，普通 per-turn 参数和 hook 不能改写系统提示

### Requirement: session 创建时间由完整运行配置显式控制

Kernel 通过 product-neutral feature `include_session_created_datetime` 控制 runtime footer 是否包含 session 创建时间。该 feature 默认 `True`，保持既有 `Current date and time` 与 current working directory；消费者显式设为 `False` 时只保留 current working directory。稳定 timezone 等产品文案仍由消费者经普通 PromptSlots 提供，Kernel 不根据 PromptText name、workspace 或 routing metadata 猜测产品。该 policy 不改变消息的提交、消费、持久化或恢复生命周期。

#### Scenario: 显式关闭 session 创建时间
- **GIVEN** 一个 session 的完整运行配置将 `include_session_created_datetime` 设为 `False`，且 PromptSlots 提供稳定 timezone
- **WHEN** Kernel 为该 session 装配 system prompt
- **THEN** prompt 包含消费者提供的稳定 timezone 与 current working directory
- **AND** 不把 session 创建时刻渲染为 `Current date and time`

#### Scenario: 默认或显式开启时保持 runtime footer bytes
- **GIVEN** 一个 session 省略 `include_session_created_datetime` override 或显式设为 `True`
- **WHEN** Kernel 为该 session 装配 system prompt
- **THEN** runtime footer 继续按既有顺序渲染 session-created current datetime 与 current working directory

#### Scenario: PromptText name 不改变 Kernel policy
- **WHEN** 消费者增加、删除或重命名一个 PromptText，但没有改变完整运行配置中的 `include_session_created_datetime`
- **THEN** Kernel runtime footer policy 不因 PromptText name 变化

### Requirement: 系统提示由内核模板与 PromptSlots 四槽组装，并在显式配置替换边界更新

内核拥有固定模板骨架；消费者以 `PromptSlots(head/body/custom/tail)` 提供产品文案。产品内容在一次运行配置代次内稳定。消费者成功替换会话完整运行配置后，下一新 turn 使用新的四槽内容；已开始的 turn 仍使用开始时的旧内容。内核自管的工作区 AGENTS.md 与易变尾部继续遵循各自刷新规则。`PromptSection`、`PromptContext` 与 `RenderMode` 不在公共表面。

#### Scenario: 同一配置代次内产品内容稳定
- **GIVEN** 一个已创建且未发生运行配置替换的会话
- **WHEN** 同一会话多回合运行
- **THEN** PromptSlots 四槽逐回合不变，只有内核自管内容按其契约变化

#### Scenario: 显式替换后下一 turn 使用新 PromptSlots
- **GIVEN** 会话已用 PromptSlots A 形成历史
- **WHEN** 消费者成功把完整运行配置替换为 PromptSlots B 并提交下一 turn
- **THEN** 下一 turn 的系统提示使用 B，同时模型上下文保留 A 代次形成的历史

#### Scenario: 活跃 turn 不在中途切换 prompt
- **GIVEN** 一个 turn 已用 PromptSlots A 开始执行
- **WHEN** 消费者请求替换为 PromptSlots B
- **THEN** 当前 turn 完整使用 A，B 从随后新开始的 turn 生效

#### Scenario: prompt preview 与真实装配同源
- **WHEN** 消费者用与创建或替换会话相同的 PromptSlots、features、enabled tools 和 workspace 请求预览
- **THEN** 预览与该运行配置的真实 system prompt 装配一致，内核易变内容按既有占位语义展示

### Requirement: 内置子 agent 类型经 PromptSlots 注入专用角色指引

经 `agent` 工具新建的子会话不继承父会话的产品 PromptSlots；按所选内置类型写入该子会话自己的 PromptSlots（身份在 head、角色与只读约束在 body）。`Explore` / `Plan` 的指引表达只读探索/规划职责；`general-purpose` 表达可完成多步实现类任务。类型文案在该子会话配置代次内稳定，不因父会话后续替换运行配置而改变已创建子会话的角色提示。

#### Scenario: Explore / Plan 子会话携带只读角色指引
- **WHEN** 消费者以 `Explore` 或 `Plan` 新建子 agent 并装配其 system prompt
- **THEN** 子会话 PromptSlots 含该类型的只读角色指引，且不含父会话产品身份/行为文案的副本

#### Scenario: general-purpose 子会话携带通用执行指引
- **WHEN** 消费者以缺省或显式 `general-purpose` 新建子 agent 并装配其 system prompt
- **THEN** 子会话 PromptSlots 含通用执行类角色指引，且不含父会话产品 PromptSlots 副本
