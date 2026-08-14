# gateway external-channels Specification (delta for feat-523)

## ADDED Requirements

### Requirement: 外部 channel 最终回复的可配置运行信息页脚

Gateway 默认不在外部 channel 回复中暴露运行信息。启用全局设置后，Gateway 在由外部用户消息触发的普通最终 assistant 回复正文下方附加本轮已解析模型与 context 占用百分比；特定外部 channel 可以覆盖全局开关。内部 Web IM 及其外部影子会话保持原正文。

#### Scenario: 全局启用后外部最终回复显示本轮运行信息
- **GIVEN** Gateway 已全局启用运行信息页脚，且本轮外部触发的普通最终回复具有已解析模型、prompt token 与 context window
- **WHEN** 用户在飞书或另一已接入的外部 channel 收到该最终回复
- **THEN** 用户在回复正文下方看到模型名与 context 占用百分比，例如 `gpt-5.4 · 42%`
- **AND** 该百分比基于本轮实际 prompt token 与该模型的 context window 计算

#### Scenario: 单一外部 channel 覆盖全局设置
- **GIVEN** Gateway 已全局启用运行信息页脚
- **WHEN** 飞书被单独配置为关闭该页脚并向用户发送普通最终回复
- **THEN** 飞书回复不显示运行信息页脚
- **AND** 未单独关闭的外部 channel 仍按全局设置显示页脚

#### Scenario: 单一外部 channel 可以独立启用页脚
- **GIVEN** Gateway 未全局启用运行信息页脚
- **WHEN** 飞书被单独配置为开启该页脚并向用户发送普通最终回复
- **THEN** 飞书回复显示运行信息页脚
- **AND** 未单独开启的外部 channel 保持不显示

#### Scenario: 非最终或内部消息不附加运行信息
- **GIVEN** 某外部 channel 的运行信息页脚已启用
- **WHEN** 同一 run 产生中间 assistant 文字、工具进度、审批卡、控制确认或内部 Web IM 影子回复
- **THEN** 这些消息都不显示运行信息页脚
- **AND** 只有普通最终外部 assistant 回复可以显示该页脚

#### Scenario: 运行信息缺失时静默省略
- **GIVEN** 某外部 channel 的运行信息页脚已启用
- **WHEN** 最终回复只具有模型或只具有有效 context 占用数据
- **THEN** 页脚只显示可取得的那一项，不显示未知占位符
- **WHEN** 两项都不可取得
- **THEN** Gateway 发送原最终回复，不增加空白页脚
