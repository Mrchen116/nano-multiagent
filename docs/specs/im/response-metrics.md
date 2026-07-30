# IM - Response Metrics Specification

> 对齐: feat-447
> 上级: [IM Specification](spec.md)
>
> 写法纪律见 [`../CONTRIBUTING.md`](../CONTRIBUTING.md)。本目录只收 **IM 的消费者真正依赖的对外行为**:浏览器前端、Node Gateway、终端用户，以及 `tests/im_service/` 里的契约测试。

## Purpose

agent 回复墙钟耗时、工具聚合展示和缓存命中率 token 气泡的用户可见契约。

## Requirements

### Requirement: agent 回复轮次的本轮墙钟耗时随终态对外可见

一轮 agent 回复从占位消息创建(`message.created`,`delivery_status=running`)到收尾(`message.completed`)之间的本轮处理墙钟,在收尾时作为该消息的 `elapsed_ms`(整数毫秒)对消费者可见——既随 `message.completed` 事件帧下发,也在历史消息读取的响应里回填。起点为占位消息的 `created_at` (agent 开始处理这一轮),终点为收尾时刻;仅 agent 消息有该值,进行中(未收尾)的消息无 `elapsed_ms`。

#### Scenario: message.completed 携带本轮墙钟
- **GIVEN** 一条 agent 占位消息已于 `created_at` 创建、处于 `running`
- **WHEN** 该轮收尾、IM 发出 `message.completed`
- **THEN** 该事件帧含 `elapsed_ms`,约等于收尾时刻与 `created_at` 之差(毫秒)

#### Scenario: 历史消息读取回填本轮墙钟
- **GIVEN** 一条已收尾的 agent 消息
- **WHEN** 消费者读取该会话历史消息
- **THEN** 该消息含 `elapsed_ms`,刷新后仍可见,与事件下发值一致

#### Scenario: 进行中消息无墙钟值
- **WHEN** 消费者读取一条尚未收尾(`running`)的 agent 消息
- **THEN** 该消息无 `elapsed_ms`,不呈现伪造耗时

### Requirement: agent 气泡呈现本轮墙钟,工具聚合徽标不再呈现累加耗时

agent 回复气泡显示本轮墙钟:进行中实时增长,收尾后定格为最终值;零工具的纯文本回复同样显示; 用户自己的消息气泡不显示耗时。工具调用聚合徽标折叠态只呈现调用次数,不再呈现各工具执行耗时的累加; 展开后每个工具仍各自显示其执行耗时。

#### Scenario: agent 气泡显示本轮墙钟(进行中与定格)
- **WHEN** 一轮 agent 回复正在进行
- **THEN** 气泡上显示一个随时间实时增长的计时
- **AND** 该轮收尾后,计时定格为本轮最终墙钟

#### Scenario: 零工具纯文本回复也显示耗时
- **WHEN** agent 这一轮只回文本、未调用任何工具
- **THEN** 气泡同样显示本轮墙钟

#### Scenario: 用户自己的消息气泡不显示耗时
- **WHEN** 用户查看自己发出的消息气泡
- **THEN** 该气泡不显示任何耗时

#### Scenario: 折叠态工具徽标不含累加时长
- **GIVEN** 一条有 N 次工具调用的 agent 气泡
- **WHEN** 查看折叠态工具徽标
- **THEN** 徽标只显示调用次数,不含各工具执行耗时的累加

#### Scenario: 展开后单工具耗时仍在
- **WHEN** 展开工具列表
- **THEN** 每个工具行仍各自显示其执行耗时

### Requirement: token 气泡展示整轮缓存命中率

#### Scenario: 有命中
- **WHEN** 用户点开一条助手回复的 token 气泡详情
- **THEN** 在「已用上下文」行下方看到「缓存命中」一行，含命中量与百分比（整轮累计口径）

#### Scenario: 无命中
- **WHEN** 本轮无任何缓存命中且用户点开详情
- **THEN** 「缓存命中」行仍显示，值为 `0 (0%)`，不隐藏该行
