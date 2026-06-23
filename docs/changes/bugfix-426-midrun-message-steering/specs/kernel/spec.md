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

#### Scenario: run 结束竞态时续跑保留来源与内容
- **GIVEN** 一条 steer 消息在活跃 run 恰好结束的竞态窗口被注入
- **WHEN** 内核以续跑 run 兜底消费该消息
- **THEN** 续跑 run 的 origin 跟随注入来源（用户消息为 USER），且消息内容（含图片）完整保留
