# IM Response Metrics Specification (delta for bugfix-497)

> Target canonical: `docs/specs/im/response-metrics.md`

## MODIFIED Requirements

### Requirement: agent 回复轮次的本轮墙钟耗时随终态对外可见

一轮 agent 回复的本轮处理墙钟在收尾时作为该消息的 `elapsed_ms`（整数毫秒）对消费者可见——既随 terminal 消息事件下发，也在历史消息读取的响应里回填。普通 Agent 消息的起点为占位消息 `created_at`、终点为 IM 收尾时刻；external shadow Agent 消息由 Gateway 以该逻辑气泡的 source begin/terminal 计算权威 `elapsed_ms`，live terminal 与离线 terminal snapshot 使用同一值，IM 不按迟到的建泡或恢复时刻重新计算。仅 Agent terminal 消息有该值，进行中消息无 `elapsed_ms`。

#### Scenario: 普通 message.completed 携带本轮墙钟
- **GIVEN** 一条不带 external shadow source elapsed 的 Agent 占位消息已于 `created_at` 创建、处于 `running`
- **WHEN** 该轮收尾、IM 发出 `message.completed`
- **THEN** 该事件帧含 `elapsed_ms`，约等于 IM 收尾时刻与 `created_at` 之差（毫秒）

#### Scenario: external shadow terminal 保持来源墙钟
- **GIVEN** Gateway 已为某 external shadow 逻辑气泡记录 source begin 与 terminal 时刻
- **WHEN** IM 通过 live terminal 或离线 terminal snapshot 完成该消息
- **THEN** terminal 事件与持久消息都使用 Gateway 提交的同一个 `elapsed_ms`
- **AND** IM 不因断线、迟建 user anchor、恢复时间或重试时间改变该值

#### Scenario: 历史消息读取回填本轮墙钟
- **GIVEN** 一条已收尾的 Agent 消息
- **WHEN** 消费者读取该会话历史消息
- **THEN** 该消息含 `elapsed_ms`，刷新后仍可见，与 terminal 事件下发值一致

#### Scenario: 进行中消息无墙钟值
- **WHEN** 消费者读取一条尚未收尾（`running`）的 Agent 消息
- **THEN** 该消息无 `elapsed_ms`，不呈现伪造耗时
