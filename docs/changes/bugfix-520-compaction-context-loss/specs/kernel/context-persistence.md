# kernel (agent) - Context and Persistence Specification (delta for bugfix-520)

> Target canonical: `docs/specs/kernel/context-persistence.md`

## MODIFIED Requirements

### Requirement: 上下文压缩在长会话中保持可恢复

内核在 LLM 调用前后检查上下文是否接近/超出上限，必要时把旧轮次摘要化并落盘为压缩记录，保留首个保留事件 id 以保证可重建与可审计；overflow 后可恢复重试。包含 assistant tool call、匹配 tool result、并行分组或结构化内容的可恢复历史进入压缩时，这些关系在压缩结果与后续会话中保持有效。只有获得非空有效摘要且 compaction record 持久提交成功后，内核才以摘要替换活动上下文；摘要为空、生成错误或提交失败时，不追加 compaction record，也不以通用摘要替换原历史。

消费者也可手动触发压缩，且可经 `await kernel.compact(session_id, workspace_root=..., focus=..., idempotency_key=...)` 为这一次手动压缩提供可选非空文本重点和可选 opaque operation identity。内核用 focus 指导被摘要的旧窗口应优先保留什么，但不把 focus 作为普通用户消息或独立会话事件写入；同一非空 idempotency key 重试复用已经提交的 manual compaction，不产生第二条压缩边界。自动阈值和 overflow 压缩不接收也不受这两个参数影响。

手动压缩失败以可辨识错误结束。自动阈值摘要失败时，内核在仍可调用模型的前提下保留原上下文继续；同一进程中的同一会话连续三次自动摘要失败后停止新的自动摘要尝试，先向消费者流发送一条用户可见 assistant 消息“上下文压缩失败，已停止本轮以避免丢失对话内容。原对话仍保留。请稍后重试，或发送 `/compact <希望保留的重点>` 后继续。”，再以可辨识失败结束，避免无限重试。overflow 恢复摘要失败时不发起压缩后的模型重试，发送同一 assistant 消息，并在 failed terminal 的诊断信息中保留原始 overflow failure。该失败提示不作为普通会话历史提供给后续模型。任一成功压缩重置连续自动失败状态；该状态不进入会话档案，进程重启后可重新尝试。compaction record 持久化异常导致 automatic compaction 无法继续时发送同一提示并以可辨识失败结束，但不计作 summary failure。

压缩判定所用的**上下文上限按当前轮所用模型取**：消费者经 `build_kernel(llm=…)` 为某模型声明的上下文窗口生效于该模型的运行；未声明窗口的模型回退到内核默认上限。判定上限时保留的安全余量是全局策略量，不随模型变化。

#### Scenario: 手动触发压缩
- **WHEN** 消费者 `await kernel.compact(session_id)`
- **THEN** 返回压缩结果（或在无需压缩时返回 None），压缩落盘后会话仍可由事件重放重建

#### Scenario: focus 指导手动压缩的后续上下文
- **GIVEN** 一个已有可压缩历史的 workspace-bound session，历史包含认证方案和未完成事项
- **WHEN** 消费者调用 `await kernel.compact(session_id, workspace_root=..., focus="保留认证方案与未完成项")`
- **THEN** 返回压缩结果并落盘，后续运行可从压缩摘要延续该重点
- **AND** transcript 不包含一条把 focus 当作普通 user turn 的独立消息

#### Scenario: 手动压缩摘要失败不改变上下文
- **GIVEN** 一个已有可压缩历史的 session
- **WHEN** 消费者发起手动 compact，但摘要生成为空或发生错误，或 compaction record 无法持久提交
- **THEN** 调用以可辨识错误结束
- **AND** 不追加 compaction record，后续运行仍能使用压缩前的可恢复上下文

#### Scenario: 自动阈值压缩失败不伪装成功
- **GIVEN** 一个达到自动压缩阈值且包含完整工具调用历史的 session
- **WHEN** 摘要生成为空或发生错误
- **THEN** 不追加 compaction record，不以通用摘要替换活动上下文
- **AND** 在当前上下文仍可用时，后续模型调用继续看到压缩前的可恢复历史

#### Scenario: 连续自动压缩失败有界并可诊断
- **GIVEN** 同一 session 已连续两次自动摘要失败，期间没有成功压缩
- **WHEN** 第三次自动摘要仍失败，或失败上限后再次需要自动压缩
- **THEN** 消费者在 failed terminal 前收到上述用户可见 assistant 失败消息，本轮再以可辨识压缩失败结束，不继续重复调用摘要模型
- **AND** transcript 仍无这些失败尝试对应的 compaction record

#### Scenario: overflow 恢复摘要失败保留原错误与历史
- **GIVEN** 一次模型调用因上下文 overflow 失败，且内核无法获得有效压缩摘要
- **WHEN** 内核尝试 overflow 恢复
- **THEN** 不发起压缩后的模型重试，在 failed terminal 前发送上述用户可见 assistant 失败消息，并在诊断信息中保留原始 overflow failure
- **AND** 不追加 compaction record，后续恢复仍可读取压缩前历史

#### Scenario: 压缩记录持久化失败不暴露半提交上下文
- **GIVEN** manual、threshold 或 overflow 已获得有效摘要，但 compaction record 无法持久提交
- **WHEN** 本次压缩结束
- **THEN** 不追加 compaction record，也不以未提交摘要替换活动上下文
- **AND** manual 调用以可辨识错误结束；automatic 路径在 failed terminal 前发送上述 assistant 失败消息，诊断信息区分持久化失败与 summary failure

#### Scenario: 含工具历史的压缩在重启后继续任务
- **GIVEN** 一个会话的可压缩历史包含 assistant tool call、匹配 tool result 和尚未完成的用户目标
- **WHEN** 自动阈值、overflow 或手动压缩成功，随后消费者继续运行该会话或在进程重启后恢复它
- **THEN** 后续运行仍能延续压缩前的用户目标与未完成事项，且会话可从已提交的 compaction record 恢复

#### Scenario: 自动压缩不继承手动关注点
- **GIVEN** 一个 session 曾以 focus 完成手动压缩
- **WHEN** 该 session 后续因 token threshold 或 overflow 自动压缩
- **THEN** 自动压缩按既有 planner 和摘要策略执行，不复用先前手动 focus

#### Scenario: 相同手动操作 identity 不重复压缩
- **GIVEN** 消费者已使用非空 `idempotency_key` 成功完成一次手动压缩
- **WHEN** 消费者因重放或响应丢失以相同 key 再次调用 `kernel.compact`
- **THEN** 内核返回第一次已提交的手动压缩结果
- **AND** transcript 不新增 compaction record，focus 文本不作为该 identity 的替代

#### Scenario: 按当前轮模型的窗口判定压缩
- **GIVEN** 消费者为某模型声明了与内核默认不同的上下文窗口
- **WHEN** 用该模型推进一个持续增长的会话直到接近“该模型窗口 − 全局安全余量”
- **THEN** 内核在该模型窗口对应的边界触发压缩，而非内核默认上限对应的边界

#### Scenario: 未声明窗口的模型回退默认上限
- **GIVEN** 某模型未声明上下文窗口（或声明值非正整数）
- **WHEN** 用该模型推进会话
- **THEN** 内核按默认上限判定压缩，运行不因缺少该声明而报错

#### Scenario: 工作区绑定的会话压缩落盘后运行透明继续
- **GIVEN** 一个绑定了 `workspace_root` 的会话（消费者经 `create_session(workspace_root=…)` 创建），其上下文已增长到触发压缩（自动阈值或 overflow 恢复）
- **WHEN** 消费者继续推进该会话一轮
- **THEN** 内核完成压缩并落盘，该轮以成功终态正常完成，不因无法定位会话存储位置而失败；压缩后会话仍可由事件重放重建，且先前轮次内容不被清空

## ADDED Requirements

N/A.

## REMOVED Requirements

N/A.
