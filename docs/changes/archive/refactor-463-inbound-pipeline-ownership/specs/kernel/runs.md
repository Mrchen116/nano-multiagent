# kernel Runs Specification (delta for refactor-463)

## ADDED Requirements

### Requirement: 消费者可只尝试向预期活跃 run 注入且不创建 fallback

已拥有 normal-run admission 的消费者可调用 `Kernel.try_steer()`；该调用只尝试注入，不负责创建 fallback run。消费者可携带自己观察到的 active run id，避免在 run 切换窗口把消息注入同 session 的替代 run。

#### Scenario: 预期 run 仍活跃时原子注入
- **GIVEN** 消费者持有某会话当前活跃 run 的 id
- **WHEN** 消费者调用 `try_steer(session_id, parts, expected_run_id=<该 id>)`
- **THEN** 返回 `RunInfo.injected=True`，返回的 `run_id` 与预期 id 相同，且消息只进入该 run

#### Scenario: 会话空闲或预期 run 已过期时零副作用拒绝
- **GIVEN** 会话没有活跃 run，或同 session 的活跃 run 已替换为另一个 id
- **WHEN** 消费者调用 `try_steer(..., expected_run_id=<旧 id>)`
- **THEN** 返回 `None`，不注入替代 run，也不创建新 run；normal fallback 是否提交仍由消费者决定

#### Scenario: inject-only steer 保留多模态内容
- **GIVEN** 预期 run 仍活跃
- **WHEN** 消费者经 `try_steer()` 投递文本与图片 parts
- **THEN** 下一轮模型上下文完整保留文本与图片；若消息因 `/stop` 或非用户终态转交后续 run，内容仍不降级

### Requirement: 消费者可按 terminal run 身份选择性清理其持久化消息

需要隐藏内部静默轮次的消费者可调用 `await Kernel.discard_run_messages(run_id)`。清理以 run 的持久化 turn 身份为边界，不把文件位置或行数暴露给消费者，也不得删除更晚到达的消息。

#### Scenario: terminal run 的消息被删除且后继历史保持可达
- **GIVEN** 一个 terminal run 已持久化消息，之后同会话又完成了用户 turn
- **WHEN** 消费者调用 `await discard_run_messages(<terminal run id>)`
- **THEN** 只删除该 run 的消息并返回 `True`，更晚的用户消息与回复、父链和下一轮模型上下文保持完整

#### Scenario: 无可清理消息时无副作用
- **GIVEN** run 不存在、尚未 terminal、尚未形成持久化 turn，或已经清理过
- **WHEN** 消费者调用 `discard_run_messages(run_id)`
- **THEN** 返回 `False`，会话历史不变

## MODIFIED Requirements

N/A.

## REMOVED Requirements

N/A.
