# kernel (agent) - Runs Specification (delta for feat-517)

## MODIFIED Requirements

### Requirement: 经 submit 投递的消息可 steer 进活跃 run 的下一轮

消费者经 `Kernel.submit(steer=True)` 投递消息时，内核按会话当前是否有活跃 run 决定注入或新建，结果由返回的 `RunInfo.injected` 标识；`steer=False`（默认）保持"总是新建 run"的既有语义。消息的 origin 由消费者随原始注入来源提供，注入、异常转交或新建 fallback 都不改变它。

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
- **THEN** 该消息不丢失，由一个后续 run 接着消费；可信人工消息保持 HUMAN，普通 SDK 用户消息保持 USER，自动来源保持原 automation origin
- **AND** 内容（含图片）完整保留

## ADDED Requirements

### Requirement: 消费者可保留运行来源并把可信人工输入与自动输入区分

#### Scenario: 交互产品提交可信人工输入
- **GIVEN** 消费者已验证本次内容来自当前交互用户
- **WHEN** 消费者以 human origin 提交该内容
- **THEN** 内核在该轮 provider input 和事件中保留可信人工来源
- **AND** 依赖人工来源的 turn attachment 可据此生效

#### Scenario: 自动来源保持非人工
- **WHEN** 消费者提交 heartbeat、cron、后台通知、webhook、bot 转发或普通非交互 SDK 内容
- **THEN** 对应 origin 保持自动或普通 user 来源，不被提升为可信人工输入
- **AND** 内容中出现与人工触发相同的关键词也不能改变来源

#### Scenario: Workflow 子运行有独立来源
- **WHEN** Workflow 派发子 Agent
- **THEN** 子运行的 origin 可被消费者识别为 workflow
- **AND** 该来源不能冒充新的人工 opt-in
