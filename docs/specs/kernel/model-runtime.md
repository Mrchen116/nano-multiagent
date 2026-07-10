# kernel (agent) - Model Runtime Specification

> 对齐: feat-445
> 上级: [kernel (agent) Specification](spec.md)
>
> 写法纪律见 [`../../SPEC_GUIDE.md`](../../SPEC_GUIDE.md)「给库/内核写契约的额外纪律」。本目录只收 **消费者经 `agent.sdk` 真正依赖的对外行为**(CDC 裁剪);内部如何装配/实现不在此层(那在代码 + 归档 design)。

## Purpose

LLM 配置查询、每轮模型路由和模型错误恢复语义的对外契约。

## Requirements

### Requirement: LLM 配置可查询,每轮对话的模型由消费者随 run 提供

消费者可读当前 LLM 配置(provider/base_url/默认目录,供选择器/能力上报用);模型不再是 kernel 级固化的
全局属性,改为消费者在发起每个 run 时随 `submit` 提供,内核不持有对话默认 model。`get_llm_config()` 返回
SDK-owned `LLMConfig` DTO(内核内部 `LLMFactoryConfig` 不出边界),仍报告 build-time 的 active 连接供
选择器使用;`create_session` 不收 model。`reconfigure_llm`/`bind_llm_client` 失去调用方而退役,内核不再
有"当前全局 active model"的概念。一个 run 内部派生的子运行(内核为该 run 派发的子 agent、该 run 的
自动上下文压缩摘要)同样复用该 run 的 model,不回退到内核构造期的全局默认。

#### Scenario: 读取当前 LLM 配置
- **WHEN** 消费者 `kernel.get_llm_config()`
- **THEN** 返回 SDK-owned `LLMConfig`,含 `provider` / `model` / `base_url` 等字段

#### Scenario: submit 携带 model 并在该 run 生效
- **WHEN** 消费者 `kernel.submit(session_id=..., parts=..., model=M)`
- **THEN** 该 run 的 LLM 请求以 `model=M` 发出(session JSONL 该 turn 记录可见)

#### Scenario: 同一 run 的内核续跑复用本 run 的 model
- **GIVEN** 一个以 `model=M` 提交的 run 在处理中产生了需续跑的消息
- **WHEN** 内核自身发起续跑
- **THEN** 续跑仍以 `model=M` 发出,不要求消费者再次提供,也不回退到任何内核默认

#### Scenario: 模型按其注册的 provider 路由请求格式
- **GIVEN** model `M` 在 config 注册于 provider `P`
- **WHEN** 以 `model=M` 提交 run
- **THEN** 内核用 `P` 声明的 client / 请求格式发出(不跨 provider 借用其它格式)

#### Scenario: run 派发的子 agent 复用本 run 的 model
- **GIVEN** 一个以 `model=M` 提交的 run,其执行过程中派发了一个子 agent(前台、后台或续跑恢复)
- **WHEN** 子 agent 发起 LLM 请求
- **THEN** 该请求以 `model=M` 发出(子 agent 的 session JSONL turn 记录可见),不回退到内核构造期的全局默认

#### Scenario: run 的自动上下文压缩摘要复用本 run 的 model
- **GIVEN** 一个以 `model=M` 提交的 run,未配置独立摘要模型,其上下文增长触发自动压缩
- **WHEN** 内核生成压缩摘要
- **THEN** 摘要的 LLM 请求以 `model=M` 发出,不回退到内核构造期的全局默认
- **AND** 当消费者显式配置了独立摘要模型时,摘要仍以该独立模型发出(独立摘要模型优先)

### Requirement: 模型错误按统一可恢复语义重试并保留原始原因

内核对所有 LLM provider 使用同一 provider-neutral 错误事实与重试策略。网络、超时、限流、
额度/余额及无法明确判定为永久的错误默认可重试;明确参数/格式错误、无效凭证、权限拒绝、
资源或能力不存在/不支持不可重试。HTTP 状态码本身不单独决定 4xx 是否可重试。重试策略含
退避,连续失败可能引入额外冷却等待——消费者观察到的恢复延迟可能超过单次重试间隔。重试不得
造成重复输出:一次请求已向消费者产出部分内容后,中途故障按最终失败处理,不原位重放该请求。

#### Scenario: 语义不明或可能恢复的 4xx 继续重试
- **WHEN** provider 返回限流、额度/余额或没有明确永久语义的 4xx
- **THEN** 内核在既定预算内重试同一请求

#### Scenario: 明确永久错误快速失败
- **WHEN** provider 或本地 mapper 明确报告参数/格式、凭证、权限、not-found 或 unsupported 错误
- **THEN** 内核不重复发送相同请求,并把实际错误交给消费者

#### Scenario: 已产出内容后的中途故障不重复输出
- **GIVEN** 一次模型响应已向消费者产出部分内容
- **WHEN** 流在到达终态前故障
- **THEN** 内核不重放该请求、不产生重复内容,本轮以真实上游错误失败

#### Scenario: 重试耗尽返回最后真实错误
- **WHEN** 可重试错误耗尽重试预算
- **THEN** 最终 `ModelError` 保留最后一次上游 message/code/type/status,重试次数仅作为附加诊断,
  不用通用 exhaustion 或 stream-ended 文案替换真实原因
