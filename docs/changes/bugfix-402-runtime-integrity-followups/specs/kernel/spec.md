# Kernel Specification (delta for bugfix-402)

## ADDED Requirements

### Requirement: 持久化 transcript 在进入模型前保持 tool call 闭合

消费者中断、取消或关闭包含工具调用的运行后，内核必须使已持久化的每个 assistant tool call
具有对应的 tool result。进程异常退出留下的历史悬空调用在下次加载时自动恢复为取消终态；
恢复保持 append-only、按 tool call id 幂等，并向 provider 物化为合法消息顺序。

#### Scenario: 中断权限等待后继续同一会话

- **GIVEN** 一个运行已经持久化 assistant tool call，正在等待权限决定
- **WHEN** 消费者调用 `kernel.interrupt(session_id)`，随后向同一会话再次 `submit`
- **THEN** 原 tool call 以取消结果闭合，新一轮模型请求收到合法 transcript 并可继续运行

#### Scenario: 重启后恢复悬空 tool call

- **GIVEN** JSONL 历史中存在没有对应 tool result 的 assistant tool call
- **WHEN** 新 Kernel 实例加载该 session 并提交下一轮
- **THEN** 内核自动追加一次引用原 call id 的恢复记录，并把取消结果物化到合法位置

#### Scenario: 重复加载恢复保持幂等

- **GIVEN** 某个 call id 已有恢复记录
- **WHEN** session 被重复加载、fork 或继续运行
- **THEN** 不为该 call id 产生第二条恢复结果，transcript 仍保持闭合

### Requirement: 模型错误按统一可恢复语义重试并保留原始原因

内核对所有 LLM provider 使用同一 provider-neutral 错误事实与重试策略。网络、超时、限流、
额度/余额及无法明确判定为永久的错误默认可重试；明确参数/格式错误、无效凭证、权限拒绝、
资源或能力不存在/不支持不可重试。HTTP 状态码本身不单独决定 4xx 是否可重试。

#### Scenario: 语义不明或可能恢复的 4xx 继续重试

- **WHEN** provider 返回限流、额度/余额或没有明确永久语义的 4xx
- **THEN** 内核在既定预算内重试同一请求

#### Scenario: 明确永久错误快速失败

- **WHEN** provider 或本地 mapper 明确报告参数/格式、凭证、权限、not-found 或 unsupported 错误
- **THEN** 内核不重复发送相同请求，并把实际错误交给消费者

#### Scenario: 重试耗尽返回最后真实错误

- **WHEN** 可重试错误耗尽重试预算
- **THEN** 最终 `ModelError` 保留最后一次上游 message/code/type/status，重试次数仅作为附加诊断，
  不用通用 exhaustion 或 stream-ended 文案替换真实原因

### Requirement: Kernel 关闭会收拢所有 owned runs

`Kernel.close()` 必须幂等地停止接受新运行，解除权限等待，中断或取消仍在执行/排队的 run，
等待 RunsRegistry 自己创建的 Task 在所属 event loop 与 Context 中进入终态，再停止并关闭 loop。
关闭开始后不得创建新的 queued run。

#### Scenario: 有活动运行时关闭

- **GIVEN** Kernel 存在 running run 或权限等待
- **WHEN** 消费者调用 `kernel.close()`
- **THEN** 相关 run 在有限 grace period 内进入 completed/failed/cancelled 之一，Registry 不遗留 Task，
  tracing scope 在原 Task Context 中退出

#### Scenario: 关闭期间拒绝新提交

- **GIVEN** Kernel 已进入 draining 或 closed 状态
- **WHEN** 消费者调用 `submit`
- **THEN** 返回稳定的 closed error，不创建 queued run 或后台 Task

#### Scenario: 重复关闭

- **WHEN** 消费者多次调用 `kernel.close()`
- **THEN** 后续调用安全返回，不重复停止 loop、不抛 secondary exception
