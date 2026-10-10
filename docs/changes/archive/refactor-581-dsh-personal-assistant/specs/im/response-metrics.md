# im/response-metrics Specification (delta for refactor-581)

## MODIFIED Requirements

### Requirement: token 气泡展示整轮缓存命中率

用量仅取已获得的 provider 计数；缺失值表示未知，不把缺失缓存计数当成零命中。IM 沿用 `context_used`、`output`、`cache_read_tokens`、`cache_total_input_tokens` 等既有字段，未获得的计数可以省略。

#### Scenario: 有命中
- **WHEN** 用户点开一条助手回复的 token 气泡详情，且 provider 已提供缓存计数
- **THEN** 在「已用上下文」行下方看到「缓存命中」一行，含命中量与百分比（整轮累计口径）

#### Scenario: 无命中
- **WHEN** provider 明确报告本轮零缓存命中，且用户点开详情
- **THEN** 「缓存命中」行仍显示，值为 `0 (0%)`，不隐藏该行

#### Scenario: 计数未知
- **WHEN** provider 没有提供缓存、总量或上下文窗口中的某项计数
- **THEN** Web 和原生 iOS 的缓存行及总量入口以 `—` 表示未知；详情可省略未提供的总量或上下文窗口，显示未知值时使用 `—`
- **AND** 不把缺失值伪造为零，不显示 NaN 或依赖缺失计数计算的百分比
- **AND** 已获得的输入、输出等计数仍按真实值展示。
