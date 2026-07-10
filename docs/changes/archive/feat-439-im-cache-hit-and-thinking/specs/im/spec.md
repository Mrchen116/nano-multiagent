# im 契约层增量 — feat-439

> feat-439 对 `docs/specs/im/spec.md` 的增量草案（delta-spec）。
> 视角=内部 Web IM 用户可观察到的结果。

## ADDED Requirements

### Requirement: token 气泡展示整轮缓存命中率

#### Scenario: 有命中
- **WHEN** 用户点开一条助手回复的 token 气泡详情
- **THEN** 在「已用上下文」行下方看到「缓存命中」一行，含命中量与百分比（整轮累计口径）

#### Scenario: 无命中
- **WHEN** 本轮无任何缓存命中且用户点开详情
- **THEN** 「缓存命中」行仍显示，值为 `0 (0%)`，不隐藏该行

### Requirement: 内部 IM 把思考与工具调用展示为过程时间线、外部不展示

#### Scenario: 内部 Web IM 一轮含多段思考与工具调用
- **WHEN** 一轮带多段思考、多次工具调用的助手回复在内部 Web IM 展示
- **THEN** 气泡内有一个可折叠「过程」区域，把多段思考与工具调用按真实先后次序混排；每段思考可展开读完整内容、可收起；历史回看仍可展开

#### Scenario: 内部 Web IM 无思考
- **WHEN** 助手回复本轮无任何思考
- **THEN** 过程区域里不出现思考行（无思考不留空壳）

#### Scenario: 外部 channel
- **WHEN** 同一条回复送达外部接入的 IM
- **THEN** 只显示正文、不含任何思考
