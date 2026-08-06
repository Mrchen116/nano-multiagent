# kernel (agent) - Context and Persistence Specification (delta for feat-501)

> Target canonical: `docs/specs/kernel/context-persistence.md`

## MODIFIED Requirements

### Requirement: 上下文压缩在长会话中保持可恢复

内核在 LLM 调用前后检查上下文是否接近/超出上限,必要时把旧轮次摘要化并落盘为压缩记录,保留首个保留事件 id 以保证可重建与可审计;overflow 后可恢复重试。消费者也可手动触发压缩，且可经 `await kernel.compact(session_id, workspace_root=..., focus=..., idempotency_key=...)` 为这一次手动压缩提供可选非空文本重点和可选 opaque operation identity。内核用 focus 指导被摘要的旧窗口应优先保留什么，但不把 focus 作为普通用户消息或独立会话事件写入；同一非空 idempotency key 重试复用已经提交的 manual compaction，不产生第二条压缩边界。自动阈值和 overflow 压缩不接收也不受这两个参数影响。若手动压缩无法获得有效摘要或无法持久提交 compaction record，调用失败且会话保持调用前的可恢复上下文，不以通用摘要替换历史。压缩判定所用的**上下文上限按当前轮所用模型取**：消费者经 `build_kernel(llm=…)` 为某模型声明的上下文窗口生效于该模型的运行;未声明窗口的模型回退到内核默认上限。判定上限时保留的安全余量是全局策略量,不随模型变化。

#### Scenario: 手动触发压缩
- **WHEN** 消费者 `await kernel.compact(session_id)`
- **THEN** 返回压缩结果(或在无需压缩时返回 None),压缩落盘后会话仍可由事件重放重建

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
- **WHEN** 用该模型推进一个持续增长的会话直到接近"该模型窗口 − 全局安全余量"
- **THEN** 内核在该模型窗口对应的边界触发压缩,而非内核默认上限对应的边界

#### Scenario: 未声明窗口的模型回退默认上限
- **GIVEN** 某模型未声明上下文窗口(或声明值非正整数)
- **WHEN** 用该模型推进会话
- **THEN** 内核按默认上限判定压缩,运行不因缺少该声明而报错

#### Scenario: 工作区绑定的会话压缩落盘后运行透明继续
- **GIVEN** 一个绑定了 `workspace_root` 的会话(消费者经 `create_session(workspace_root=…)` 创建),其上下文已增长到触发压缩(自动阈值或 overflow 恢复)
- **WHEN** 消费者继续推进该会话一轮
- **THEN** 内核完成压缩并落盘,该轮以成功终态正常完成,**不因无法定位会话存储位置而失败**;压缩后会话仍可由事件重放重建,且先前轮次内容不被清空
