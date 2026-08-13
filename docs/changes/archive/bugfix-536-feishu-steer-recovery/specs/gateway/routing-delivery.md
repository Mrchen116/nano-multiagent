# gateway routing-delivery Specification (delta for bugfix-536)

## ADDED Requirements

### Requirement: Gateway 为已接收的普通消息维持可见恢复交付

Gateway 在非用户终态前已接受、但尚未进入模型上下文的普通消息，必须在 Kernel 给出可验证的恢复 batch 后继续由原聊天交付；恢复的最终文本一次发送，已接受消息各自只收到一次 terminal delivery status。

#### Scenario: 真中断前已接收的插话由同一聊天继续交付
- **GIVEN** Agent 的当前 run 确实因非用户原因终止，且 Gateway 已接受一条尚未进入模型上下文的普通消息
- **WHEN** Kernel 创建并结算该消息的关联恢复 batch
- **THEN** Gateway 在原聊天接收恢复 run 的结果并一次完成该普通消息
- **AND** 用户不必重发，也不会收到超时或重复回复

#### Scenario: 无法验证或无法创建恢复 batch 时明确收口
- **GIVEN** Gateway 正在等待已接受普通消息的恢复 batch
- **WHEN** Kernel 明确结算为无 successor/无法恢复，或后继 descriptor 与已接受消息不匹配
- **THEN** Gateway 只将尚未恢复的消息收口为失败并释放会话
- **AND** 不把无关 run 的输出投到原聊天，也不无限等待

#### Scenario: 显式控制命令不进入恢复
- **GIVEN** 某会话有活动 run 或正在等待恢复的已接受普通消息
- **WHEN** 用户发送精确 `/stop` 或精确 `/new`
- **THEN** Gateway 分别保持既有停止或重开语义，并抑制已知恢复 run 的可见输出
- **AND** 其他自然语言文本仍按普通消息处理，不触发停止或重开

## MODIFIED Requirements

### Requirement: 入站消息按四步决策路由并回发原通道原目标

任一通道（外部 IM 或内置 Web IM）收到一条入站消息时，Gateway 依次决策：路由到哪个 Agent、用哪个会话、是否串行排队、回复发回哪个通道目标。同一会话的回复**只**回发原通道原目标，不跨通道混发。idle 看门狗按 **liveness 心跳**判定一轮是否仍有进展——执行静默长工具、等待主模型返回和自动整理上下文三类“活着但安静”的窗口都有周期性 liveness 心跳，看门狗不再以“无业务输出事件”判卡死；等待用户权限决策的窗口则完全豁免于 idle 看门狗超时。只有该轮收到 `permission_resolved` 或判定窗口内既无业务事件也无 liveness 心跳时才判失去进展并收尾。

#### Scenario: 直聊消息被默认 Agent 处理并把回复发回原通道
- **GIVEN** 一个配置了至少一个 Agent 的 Gateway，且消息未显式指定 `agent_id`
- **WHEN** 终端用户经某通道发来一条直聊消息
- **THEN** 消息被路由到命中的 Agent，交内核执行，最终 Agent 回复经原通道的出站路由回发到发起会话

#### Scenario: 同会话串行、跨会话并行
- **GIVEN** 同一会话已有一轮在执行，另有一条属于不同会话的消息同时到达
- **WHEN** 两条消息先后进入 Gateway
- **THEN** 同一会话的消息排进串行 FIFO 队列、前一轮结束后才消费下一条；不同会话的消息并行推进，互不阻塞

#### Scenario: 失去 liveness 后释放同会话队列
- **GIVEN** 同一会话的前一轮已开始运行，但在判定窗口（120 秒）内既无业务事件也无任何 liveness 心跳，后一条消息正在 FIFO 中等待
- **WHEN** Gateway 判定前一轮失去进展
- **THEN** Gateway 取消前一轮并上报失败，随后消费后一条消息，不得让该会话永久阻塞

#### Scenario: 执行静默长命令期间不被 idle 看门狗误杀
- **GIVEN** 某轮正在执行一个耗时远超判定窗口、其间无标准输出的命令
- **WHEN** 命令持续在执行（有周期性 liveness 心跳）
- **THEN** 该轮不被看门狗取消，命令跑完结果正常返回

#### Scenario: 等待主模型返回期间不被 idle 看门狗误杀
- **GIVEN** 某轮长时间等待主模型返回但连接活着（有周期性 liveness 心跳）
- **WHEN** 等待时长超过判定窗口
- **THEN** 该轮不被看门狗误判卡死

#### Scenario: 自动整理上下文期间不被 idle 看门狗误杀
- **GIVEN** 某轮正在自动整理过长上下文且摘要仍正常推进（有周期性 liveness 心跳）
- **WHEN** 等待时长超过判定窗口
- **THEN** Gateway 不把该轮误判为 idle 超时
- **AND** 该轮后续普通消息连同已有上下文照常进入对话并得到正常回复

#### Scenario: 等人工权限决策期间不被 idle 看门狗误杀
- **GIVEN** 某轮已发起一个需要授权的工具，正等待用户在权限卡片上决策
- **WHEN** 等待时长超过判定窗口（即使用户离开、关闭 IM 页面、其间没有 liveness 心跳到达）
- **THEN** 该轮不被 idle 看门狗取消；用户随后批准则工具正常执行、该轮继续推进
- **AND** 一旦用户做出决策、内核发出 `permission_resolved`，正常 idle 看门狗立即恢复，决策后的卡死/断连仍会被捕获
