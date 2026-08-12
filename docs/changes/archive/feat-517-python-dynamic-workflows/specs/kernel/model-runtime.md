# kernel (agent) - Model Runtime Specification (delta for feat-517)

## MODIFIED Requirements

### Requirement: 完整 session runtime 可携带未来模型请求的 provider-neutral 推理强度

消费者可在 `SessionRuntimeConfig` 为一个 session 的未来正常模型请求提供 effective `reasoning_effort`，并可独立提供 nullable `reasoning_effort_override` 表示本 session 显式选择的档位。两者与 model、prompt、skills、tools、features 同属 complete runtime：创建、读取、fork、runtime identity 和 durable reconfigure 保持其语义。Kernel 不把 override 解释为某个产品的配置，也不替消费者按模型能力替换它；它只在随后开始的普通模型请求中把 effective value 传给已选 provider adapter，由 adapter 使用其协议字段。

#### Scenario: 消费者创建 session 后读取完整 runtime
- **WHEN** 消费者以带 `reasoning_effort` 和可选 `reasoning_effort_override` 的 `SessionRuntimeConfig` 创建 session，随后读取 runtime
- **THEN** 读取结果保留等价的 effective 推理强度、override 和 runtime identity

#### Scenario: consumer reconfigure 仅影响之后开始的模型请求
- **GIVEN** 一个 session 已有开始执行的 run
- **WHEN** 消费者 durable reconfigure 该 session 的 `reasoning_effort` 或 `reasoning_effort_override`
- **THEN** 已开始的 run 使用开始时的完整 runtime，后续开始的正常模型请求使用新的 effective 推理强度

#### Scenario: fork 保留 future runtime 语义
- **WHEN** 消费者 fork 一个带 `reasoning_effort` 和可选 override 的 session
- **THEN** fork 得到的 session 在未被再次 reconfigure 前保留等价的 future runtime

#### Scenario: 传入 provider 的正常模型请求携带 runtime 推理强度
- **WHEN** 消费者以带 `reasoning_effort` 的 complete runtime 开始一轮正常对话
- **THEN** 该轮的 provider adapter 以其协议形式发送该 effective 推理强度
- **AND** Kernel 不将其用于独立 hook/审批模型调用

### Requirement: LLM 配置可查询,每轮对话的模型由消费者随 run 提供

消费者可读当前 LLM 配置(provider/base_url/默认目录和每模型安全 reasoning capability,供选择器/能力上报用);模型不再是 kernel 级固化的全局属性,改为消费者在发起每个 run 时随 `submit` 提供,内核不持有对话默认 model。`get_llm_config()` 返回 SDK-owned `LLMConfig` DTO(内核内部 `LLMFactoryConfig` 不出边界),仍报告 build-time 的 active 连接供选择器使用;`create_session` 不收 model。`reconfigure_llm`/`bind_llm_client` 失去调用方而退役,内核不再有"当前全局 active model"的概念。一个 run 内部派生的子运行(内核为该 run 派发的子 agent、该 run 的自动上下文压缩摘要)同样复用该 run 的 model,不回退到内核构造期的全局默认。

#### Scenario: 读取当前 LLM 配置
- **WHEN** 消费者 `kernel.get_llm_config()`
- **THEN** 返回 SDK-owned `LLMConfig`,含 `provider` / `model` / `base_url` 以及每模型声明的 fixed/selectable reasoning capability（如果存在）

#### Scenario: LLM catalog 装配保留 reasoning capability
- **WHEN** 消费者用 payload、JSON 或 SDK-owned catalog 装配带 reasoning capability 的 `LLMConfig`
- **THEN** 后续经 `get_llm_config()` 读取同一模型时保留等价 descriptor
- **AND** 未声明 capability 的模型保持未声明，Kernel 不猜测 levels

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
