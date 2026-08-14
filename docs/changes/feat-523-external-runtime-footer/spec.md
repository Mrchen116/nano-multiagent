# feat-523: External runtime footer

## 原始需求

> 我觉得没必要，你帮我仿照他的机制，让我的外部channel也能show 模型和context_pct。设计上要所有外部channel都支持，虽然现在只有飞书channel

## 澄清记录

- Q1: 外部 channel 的模型 / context 页脚应默认开启，还是默认关闭、配置开启？
  A(原话): 「我觉得没必要，你帮我仿照他的机制，让我的外部channel也能show 模型和context_pct。设计上要所有外部channel都支持，虽然现在只有飞书channel」「我问你，Hermes是这样的吗」
  Agent 解读: 以已核实的 Hermes 语义为准：默认关闭；可全局开启，并允许单一外部 channel 覆盖；开启后只显示该轮最终回复的运行信息。用户要求 Nano 只显示 `model` 与 `context_pct`，不包含 Hermes 支持的 `cwd`。

- Q2: 运行信息不完整时应如何显示？
  A(原话): 「仿照他的机制」
  Agent 解读: 沿用 Hermes 的可见语义：缺少某一项时静默省略该项；若两项均不可用，则不增加空白页脚或占位符。

## 用户场景

用户在飞书等外部 IM 与自己的 Agent 对话时，希望在一轮回答真正结束后，一眼确认这轮实际使用的模型和上下文占用，而不是从中间进度、工具过程或内部 Web IM 中猜测运行状态。当前只有飞书接入，但这个能力应属于 Gateway 的外部 channel 体验：未来新增的外部 channel 在启用后也获得同样的最终回复页脚，而不需要各自重新实现。

用户或运维者可以选择是否暴露该运行信息。默认对外保持简洁；全局启用后，各外部 channel 的最终回复显示简洁的一行，例如 `gpt-5.4 · 42%`。若某个 channel 不适合显示，单独关闭它即可。用户看到多条过程性消息时，只有这一轮的普通最终回答携带页脚；不把工具进度、审批卡、控制确认或空回复误标成最终运行结果。

## 验收标准

### Requirement: 外部 channel 的最终回复可显示运行信息

#### Scenario: 已启用时显示模型和上下文占用
- **GIVEN** 外部 channel 的运行信息页脚已启用，且本轮 Agent 最终回复具有模型名与上下文占用数据
- **WHEN** 用户从飞书或另一已接入的外部 channel 发起一轮普通对话并收到最终回复
- **THEN** 最终回复下方显示模型名与上下文占用百分比，例如 `gpt-5.4 · 42%`

#### Scenario: 中间消息不显示页脚
- **GIVEN** 已启用外部 channel 的运行信息页脚
- **WHEN** 同一轮处理先产生过程性文字、工具进度、审批卡或控制确认，再产生普通最终回复
- **THEN** 只有普通最终回复显示运行信息页脚
- **AND** 过程性文字、工具进度、审批卡和控制确认不显示该页脚

#### Scenario: 运行信息不完整时不显示虚假占位
- **GIVEN** 外部 channel 的运行信息页脚已启用
- **WHEN** 最终回复只能取得模型名或上下文占用中的一项
- **THEN** 页脚只显示可取得的一项，不显示空字段或未知占位符
- **WHEN** 两项均不可取得
- **THEN** 最终回复不增加空白页脚

### Requirement: 页脚按外部 channel 配置控制

#### Scenario: 默认不暴露运行信息
- **GIVEN** Gateway 未显式启用外部 channel 的运行信息页脚
- **WHEN** 用户从任一外部 channel 收到普通最终回复
- **THEN** 回复不显示模型名或上下文占用页脚

#### Scenario: 全局开启覆盖所有外部 channel
- **GIVEN** Gateway 已全局启用运行信息页脚
- **WHEN** 用户从飞书或未来接入的任一外部 channel 收到普通最终回复
- **THEN** 该外部 channel 的最终回复都显示页脚

#### Scenario: 单一外部 channel 可以覆盖全局设置
- **GIVEN** Gateway 已全局启用运行信息页脚
- **WHEN** 某一外部 channel 被单独关闭该功能
- **THEN** 该 channel 的最终回复不显示页脚
- **AND** 未单独关闭的外部 channel 继续显示页脚

### Requirement: 内部 Web IM 保持原有消息体验

#### Scenario: 内部 Web IM 不显示外部页脚
- **GIVEN** Gateway 已为外部 channel 启用运行信息页脚
- **WHEN** 用户在内部 Web IM 发起一轮对话并收到回复
- **THEN** 内部 Web IM 回复不显示该外部 channel 页脚

## 范围与非目标

- 在范围：所有外部 channel 的可配置最终回复页脚；本期字段仅为模型名与上下文占用百分比；默认关闭、全局开启和单一 channel 覆盖；飞书作为首个真实外部 channel 验证入口。
- 非目标：在内部 Web IM 显示该页脚；显示工作目录、精确 token 数、费用、耗时、session ID、工具调用次数或其他运行指标；把运行信息加到中间进度、审批卡、控制确认或调试消息；为未来 channel 单独复制一套实现。
