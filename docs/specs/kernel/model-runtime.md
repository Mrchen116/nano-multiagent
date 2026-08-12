# kernel (agent) - Model Runtime Specification

> 对齐: feat-514
> 上级: [kernel (agent) Specification](spec.md)
>
> 写法纪律见 [`../CONTRIBUTING.md`](../CONTRIBUTING.md)「给库/内核写契约的额外纪律」。本目录只收 **消费者经 `agent.sdk` 真正依赖的对外行为**(CDC 裁剪);内部如何装配/实现不在此层(那在代码 + 归档 design)。

## Purpose

LLM 配置查询、每轮模型路由和模型错误恢复语义的对外契约。

## Requirements

### Requirement: 完整 session runtime 可携带未来模型请求的 provider-neutral 推理强度

消费者可在 `SessionRuntimeConfig` 为一个 session 的未来正常模型请求提供 provider-neutral 的 effective `reasoning_effort`，并可同时保存 nullable `reasoning_effort_override` 作为产品选择的 session 值。两者与 model、prompt、skills、tools、features 同属 complete runtime：创建、读取、fork、runtime identity 和 durable reconfigure 保持其语义。Kernel 不解释 override 的产品规则；它只在随后开始的普通模型请求中把 effective effort 交给已选 provider adapter。

#### Scenario: 消费者创建 session 后读取完整 runtime
- **WHEN** 消费者以同时带 effective `reasoning_effort` 与 `reasoning_effort_override` 的 `SessionRuntimeConfig` 创建 session，随后读取 runtime
- **THEN** 读取结果保留两者和对应 runtime identity

#### Scenario: consumer reconfigure 仅影响之后开始的模型请求
- **GIVEN** 一个 session 已有开始执行的 run
- **WHEN** 消费者 durable reconfigure 该 session 的 effort 或 override
- **THEN** 已开始的 run 使用开始时的完整 runtime，后续开始的正常模型请求使用新的 effective 推理强度

#### Scenario: fork 保留 future runtime 语义
- **WHEN** 消费者 fork 一个带 effective effort 与 session override 的 session
- **THEN** fork 得到的 session 在未被再次 reconfigure 前保留等价的 future runtime

#### Scenario: 传入 provider 的正常模型请求携带 runtime 推理强度
- **WHEN** 消费者以带 `reasoning_effort` 的 complete runtime 开始一轮正常对话
- **THEN** 该轮的 provider adapter 以其协议形式发送该推理强度
- **AND** Kernel 不将其用于独立 hook/审批模型调用

### Requirement: LLM 配置可查询,每轮对话的模型由消费者随 run 提供

消费者可读当前 LLM 配置(provider/base_url/默认目录,供选择器/能力上报用);模型不再是 kernel 级固化的全局属性,改为消费者在发起每个 run 时随 `submit` 提供,内核不持有对话默认 model。`get_llm_config()` 返回 SDK-owned `LLMConfig` DTO(内核内部 `LLMFactoryConfig` 不出边界),仍报告 build-time 的 active 连接和每个 `LLMModel` 的 safe reasoning descriptor；`ModelReasoningCatalog` 从同一 DTO 查询 fixed、selectable 或未声明能力。payload、JSON 与 SDK catalog 三种 LLMConfig 装配路径都保留该 descriptor；未声明时消费者不得猜测档位。`create_session` 不收 model。`reconfigure_llm`/`bind_llm_client` 失去调用方而退役,内核不再有"当前全局 active model"的概念。一个 run 内部派生的子运行(内核为该 run 派发的子 agent、该 run 的自动上下文压缩摘要)同样复用该 run 的 model,不回退到内核构造期的全局默认。

#### Scenario: 读取当前 LLM 配置
- **WHEN** 消费者 `kernel.get_llm_config()`
- **THEN** 返回 SDK-owned `LLMConfig`,含 `provider` / `model` / `base_url` 等字段

#### Scenario: 消费者从 SDK catalog 查询模型 reasoning capability
- **GIVEN** 模型在 LLM catalog 声明 fixed 或 selectable reasoning descriptor
- **WHEN** 消费者从 `get_llm_config()` 构造 `ModelReasoningCatalog` 并查询该模型
- **THEN** 得到相同的 safe descriptor；未声明的模型没有 selectable levels

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

内核对所有 LLM provider 使用同一 provider-neutral 错误事实与重试策略。网络、超时、限流、额度/余额及无法明确判定为永久的错误默认可重试;明确参数/格式错误、无效凭证、权限拒绝、资源或能力不存在/不支持不可重试。HTTP 状态码本身不单独决定 4xx 是否可重试。重试策略含退避,连续失败可能引入额外冷却等待——消费者观察到的恢复延迟可能超过单次重试间隔。重试不得造成重复输出:一次请求已向消费者产出部分内容后,中途故障按最终失败处理,不原位重放该请求。

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
- **THEN** 最终 `ModelError` 保留最后一次上游 message/code/type/status,重试次数仅作为附加诊断, 不用通用 exhaustion 或 stream-ended 文案替换真实原因
