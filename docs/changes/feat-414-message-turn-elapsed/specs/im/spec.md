# IM 契约层增量 — feat-414

> 本文件是 feat-414 对 `docs/specs/im/spec.md` 的 delta-spec(草案)。收尾由 orchestrator 软对账后并入 canonical。

## ADDED Requirements

### Requirement: agent 回复轮次的墙钟耗时随终态对外可见

一轮 agent 回复从占位消息创建(`message.created`,`delivery_status=running`)到收尾(`message.completed`)之间的墙钟时长,在收尾时作为该消息的 `elapsed_ms`(毫秒,整数)对消费者可见——既随 `message.completed` 事件下发,也在历史消息读取(`GET /im/v1/.../messages`)中回填。起点为占位消息的 `created_at`(agent 开始处理这一轮),终点为收尾时刻。仅 agent 消息有该值;进行中(尚未收尾)的消息无 `elapsed_ms`。

#### Scenario: message.completed 携带本轮墙钟
- **GIVEN** 一条 agent 占位消息已于 `created_at` 创建、处于 `running`
- **WHEN** 该轮收尾、IM 发出 `message.completed`
- **THEN** 该事件载荷含 `elapsed_ms`,其值约等于收尾时刻与 `created_at` 之差(毫秒)

#### Scenario: 历史消息读取回填墙钟
- **GIVEN** 一条已收尾的 agent 消息
- **WHEN** 客户端读取该会话历史消息
- **THEN** 该消息的序列化结果含 `elapsed_ms`(刷新后仍可见,与事件下发值一致)

#### Scenario: 进行中消息无墙钟值
- **WHEN** 客户端读取一条尚未收尾(`running`)的 agent 消息
- **THEN** 该消息无 `elapsed_ms`(或为空),不呈现伪造的耗时

### Requirement: 聊天界面在 agent 气泡上呈现本轮墙钟,工具聚合不再呈现累加耗时

agent 回复气泡显示本轮墙钟:进行中实时增长,收尾后定格为最终值;零工具的纯文本回复同样显示。用户自己发出的消息气泡不显示耗时。工具调用聚合徽标(折叠态)只呈现调用次数,不再呈现各工具执行耗时的累加;展开后每个工具仍各自显示其执行耗时。

#### Scenario: agent 气泡显示本轮墙钟(含进行中与定格)
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
