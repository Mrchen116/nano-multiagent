# kernel spec delta — bugfix-426

> 本 unit 对长青契约层 `docs/specs/kernel/spec.md` 的增量。主语 = `agent.sdk` 消费者。

## ADDED Requirements

### Requirement: 经 submit 投递的消息可 steer 进活跃 run 的下一轮

消费者经 `Kernel.submit(steer=True)` 投递用户消息时，内核按会话当前是否有活跃 run 决定注入或新建，结果由返回的 `RunInfo.injected` 标识；`steer=False`（默认）保持"总是新建 run"的既有语义。

#### Scenario: 有活跃 run 时注入其下一轮
- **GIVEN** 某会话有一个正在执行的 run
- **WHEN** 消费者对该会话 `submit(steer=True)`
- **THEN** 消息进入该活跃 run 的待注入队列，于其下一次模型调用前被带入上下文
- **AND** 返回 `RunInfo.injected=True` 且 `run_id` 等于该活跃 run 的 id（不新建 run）

#### Scenario: 无活跃 run 时退化为新建 run
- **GIVEN** 某会话当前没有活跃 run
- **WHEN** 消费者对该会话 `submit(steer=True)`
- **THEN** 照常新建一个 run，返回 `RunInfo.injected=False`

#### Scenario: 默认 steer=False 维持新建语义
- **WHEN** 消费者 `submit()` 不传 steer（或 steer=False）
- **THEN** 无论是否有活跃 run，都新建 run、`injected=False`（与既有调用方行为一致）

#### Scenario: 注入消息携带多模态 parts
- **GIVEN** 某会话有活跃 run
- **WHEN** 消费者 `submit(steer=True)` 投递含文本与图片附件的 parts
- **THEN** 注入上下文的消息完整保留文本与图片，与一次普通 turn 的用户消息无差别

#### Scenario: 多条 steer 消息按序全部注入
- **GIVEN** 某会话有活跃 run
- **WHEN** 消费者在该 run 结束前连续多次 `submit(steer=True)`
- **THEN** 这些消息按提交顺序全部进入上下文，无丢失、无乱序

#### Scenario: 活跃 run 异常终止时注入的消息不丢
- **GIVEN** 一条 steer 消息注入了一个活跃 run，而该 run 随后因非用户原因异常终止（消息尚未被消费）
- **WHEN** 内核处理这次终止
- **THEN** 该消息不丢失，由一个后续 run 接着消费，其 origin 跟随注入来源（用户消息为 USER）、内容（含图片）完整保留

## ADDED Requirements (M4，修 #140)

### Requirement: steer 进活跃 run 的消息，其后续事件始终归属同一个 run

消费者经 `submit(steer=True)` 注入活跃 run 的消息，由该 run 接着消费、`injected=True` 且 `run_id` 不变；该消息触发的后续事件（工具调用、回复直到完成）始终出现在**这同一个 run** 的事件流上，事件归属不会静默转移到另一个 run——无论注入时该 run 离结束有多近。只有当该 run 在消费前已确实结束、无法再接续时，才退化为新建 run。

#### Scenario: steer 的后续事件都出现在该 run 的事件流上
- **GIVEN** 某会话有一个正在执行的 run，消费者已按其 `run_id` 订阅事件流
- **WHEN** 消费者对该会话 `submit(steer=True)`，返回 `injected=True`、`run_id` 为该 run
- **THEN** 该消息触发的后续事件（工具调用、回复、完成）都出现在这同一个 `run_id` 的事件流上
- **AND** 按该 `run_id` 订阅即可完整收到这条 steer 引发的全部事件直到该 run 结束

#### Scenario: 活跃 run 已结束无法接续时退化为新建
- **GIVEN** 某会话的活跃 run 在 steer 到达时已经结束
- **WHEN** 消费者 `submit(steer=True)`
- **THEN** 退化为新建 run、`RunInfo.injected=False`（消息不丢，作为新 run 处理）

#### Scenario: 事件流标出 steer 消息进入上下文的位置
- **GIVEN** 某会话有活跃 run、有 steer 消息待注入
- **WHEN** 该消息被带入模型上下文
- **THEN** 该 run 的事件流上出现一个可观察标记，携带该 `run_id`，使消费者能把"对这条 steer 的回应"与此前的输出区分开
