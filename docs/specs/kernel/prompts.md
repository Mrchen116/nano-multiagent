# kernel (agent) - Prompts Specification

> 对齐: bugfix-471
> 上级: [kernel (agent) Specification](spec.md)
>
> 写法纪律见 [`../../SPEC_GUIDE.md`](../../SPEC_GUIDE.md)「给库/内核写契约的额外纪律」。本目录只收 **消费者经 `agent.sdk` 真正依赖的对外行为**(CDC 裁剪);内部如何装配/实现不在此层(那在代码 + 归档 design)。

## Purpose

产品专属 prompt 条件、PromptSlots 和系统提示组装的内核契约。

## Requirements

### Requirement: feature 内核只留通用项，产品专属条件 prompt 经 PromptSlots 持久归属会话配置

内核 feature 目录只含配内核内置工具的通用项；产品专属条件 prompt 全由消费者经 `PromptSlots` 提供。消费者在创建会话时提供初始值，也可经明确的完整运行配置替换更新既有会话；产品不通过普通 per-turn 参数或 hook 临时注入系统提示。

#### Scenario: 通用 feature 由会话开关与工具在场门控
- **GIVEN** 会话运行配置启用某通用 feature 且其所需工具在 enabled tools 中
- **WHEN** 装配该会话 system prompt
- **THEN** 对应 guidance 出现；feature 未开或工具不在场时不渲染

#### Scenario: 产品 prompt 只经会话配置改变
- **GIVEN** 一个已创建会话
- **WHEN** 消费者没有显式替换其运行配置而连续提交多轮
- **THEN** PromptSlots 产品内容保持稳定，普通 per-turn 参数和 hook 不能改写系统提示

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
