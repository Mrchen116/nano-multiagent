# gateway (personal_assistant) - Agent Capabilities Specification (delta for feat-514)

## MODIFIED Requirements

### Requirement: Agent 选定的模型在每次新回复开始时生效

Gateway 在每次新回复开始时按 Agent 当前 `default_model` 选择模型；未选模型时回退产品层全局默认。
模型声明可调推理能力时，Gateway 为该轮使用 Agent 已保存的 `reasoning_effort`；未保存时使用该模型
配置的推荐 default。既有聊天改模型或推理强度不创建空会话，模型与同代 prompt、skills、tools、
features 一起生效并保留历史。已经开始的整轮及其采纳的插话继续使用启动时的完整配置。

#### Scenario: Agent 选定模型和推理强度后对话使用这一组配置
- **GIVEN** 某 Agent 配置模型 B 和 B 支持的推理强度 H
- **WHEN** 用户与该 Agent 开始一轮新交流
- **THEN** 该轮使用 B 和 H

#### Scenario: 改模型或推理强度后旧会话继续聊且保留历史
- **GIVEN** 某 Agent 曾用模型 A 和强度 X 形成历史会话
- **WHEN** 配置改为模型 B、强度 Y 后回到该历史会话发新消息
- **THEN** 新回复使用 B 和 Y，并仍能引用此前聊天历史

#### Scenario: 正在进行的回复不在中途换运行配置
- **GIVEN** Agent 正在用模型 A 和强度 X 回复
- **WHEN** 配置改为模型 B 或强度 Y，且用户插话被纳入当前回复
- **THEN** 当前整轮仍使用 A 和 X，下一轮新回复才使用成功保存的完整配置

#### Scenario: Agent 未选模型时用产品层默认与其推荐强度
- **GIVEN** Agent 的 `default_model` 为空
- **WHEN** 与其开始一轮新交流
- **THEN** 使用 Gateway 产品默认模型正常回复
- **AND** 若该默认模型声明可调推理能力，使用其推荐强度而不要求 Agent 持久化独立选择

#### Scenario: heartbeat 与 cron 使用当前完整模型配置
- **WHEN** heartbeat 复用专用会话或 cron 为某 Agent 开始一轮新工作
- **THEN** 该轮使用开始时 Agent 当前的模型、有效推理强度及其他完整运行配置，并保留适用的会话历史

## ADDED Requirements

### Requirement: 每模型推理能力由 Gateway 配置声明并安全上报

运维者可在 Gateway config 的 `llm.providers[].models[]` 条目配置 `reasoning: fixed`，或配置含
`default` 与 `levels` 的可调能力。Gateway 只向 IM 上报可调档位、推荐 default 或 fixed 状态；不
上报静态请求 body。错误的 reasoning 配置使 Gateway 在启动期拒绝运行。

#### Scenario: 配置新增或调整模型档位后 IM 无需发布即可使用
- **GIVEN** 运维者更新某节点模型的 reasoning 配置并重启 Gateway
- **WHEN** Gateway 上线且 IM 查询该节点能力
- **THEN** IM 看到该节点当前声明的可选档位、推荐项或 fixed 状态
- **AND** 其他节点仍只上报自己的配置

#### Scenario: fixed 模型不接受独立推理强度
- **GIVEN** 某模型配置为 `reasoning: fixed`
- **WHEN** Gateway 收到该模型搭配非空 `reasoning_effort` 的 Agent 配置
- **THEN** Gateway 拒绝该配置而不写入本地配置

#### Scenario: Gateway apply ACK 先于 IM 显示配置已保存
- **WHEN** IM 请求 Gateway apply 一个已有 Agent 的完整候选配置
- **THEN** Gateway 在当前模型能力目录校验后持久化并发布该配置，再返回成功 ACK
- **AND** 校验失败时返回可由 IM 映射为配置冲突的 rejected result，不改本地配置

### Requirement: Gateway 配置 operation 可幂等恢复

Gateway 对 `agent.create` 与 `agent.config.apply` 接收稳定 operation id 和候选 fingerprint。在任何
workspace、local config 或 live publication 变更前，Gateway 先持久化不含 secret 的 `prepared` intent：
operation id、candidate/expected-previous fingerprint、canonical candidate 和 create identity。Gateway 以
expected-previous 保护 local config 写入；因为 local config 会持久化 workspace root，Gateway 必须先
幂等初始化 candidate workspace，再写 config，随后将 intent 变为 terminal applied/rejected receipt；IM
可在 ACK 丢失或重连后查询 `agent.config.operation.status`。同一个 operation 与同一 fingerprint 可安全
重试，operation id 不得重用到不同候选。

#### Scenario: applied operation 重试不重复写入或发布
- **GIVEN** Gateway 已为某 operation id 持久化同一候选 fingerprint 的 applied receipt
- **WHEN** IM 因超时再次发送相同 create 或 apply operation
- **THEN** Gateway 返回同一 canonical applied result
- **AND** 不第二次创建 workspace 或重复发布该配置

#### Scenario: operation status 使丢失 ACK 可恢复
- **GIVEN** Gateway 已落盘某 operation 的 applied 或 rejected receipt，但结果 frame 未送达 IM
- **WHEN** IM 查询该 operation id 的 status
- **THEN** Gateway 返回已持久化的终态和 canonical payload 或 rejected reason

#### Scenario: Gateway 在任意 config operation 持久边界崩溃后能恢复
- **GIVEN** Gateway 已持久化一个 prepared intent
- **WHEN** 它在 workspace 初始化前、workspace 初始化后、local config 写入后或 live publication 后但
  terminal receipt 前崩溃
- **THEN** 同一 operation 的 retry 或 status 以 expected-previous/candidate fingerprint 重新协调该 intent
- **AND** 已是 candidate 时只完成 live 收敛和 terminal receipt；仍是 expected previous 时先幂等初始化
  workspace、再只应用一次候选；已变为第三种配置时写 rejected conflict
- **AND** Gateway 每次都能重启；create 不创建第二个 workspace，apply 不第二次持久写入或发布

#### Scenario: operation id 不得重用到不同候选
- **GIVEN** Gateway 已见过某 operation id
- **WHEN** 调用方以不同候选 fingerprint 重试该 operation id
- **THEN** Gateway 稳定拒绝，不改变本地 Agent 配置或既有 receipt

#### Scenario: 配置或已保存档位不再合法时不静默替换
- **GIVEN** Agent 的已保存推理强度不再位于其模型当前的 levels 中
- **WHEN** Gateway 要同步该配置或开始下一轮新回复
- **THEN** Gateway 明确拒绝该不兼容配置或运行
- **AND** 不将用户选择静默替换为另一档
