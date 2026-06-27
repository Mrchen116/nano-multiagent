# kernel delta-spec — bugfix-443

> 本文件是 bugfix-443 对 canonical `docs/specs/kernel/spec.md` 的**增量草案**。
> 收尾由 orchestrator 软对账 + 合并进 canonical。写法纪律见 `docs/SPEC_GUIDE.md`。

## MODIFIED Requirements

### Requirement: LLM 配置可查询,每轮对话的模型由消费者随 run 提供

消费者可读当前 LLM 配置(provider/base_url/默认目录,供选择器/能力上报用);模型不再是 kernel 级固化的
全局属性,改为消费者在发起每个 run 时随 `submit` 提供,内核不持有对话默认 model。`get_llm_config()` 返回
SDK-owned `LLMConfig` DTO(内核内部 `LLMFactoryConfig` 不出边界),仍报告 build-time 的 active 连接供
选择器使用;`create_session` 不收 model。`reconfigure_llm`/`bind_llm_client` 失去调用方而退役,内核不再
有"当前全局 active model"的概念。**一个 run 内部派生的子运行(内核为该 run 派发的子 agent、该 run 的
自动上下文压缩摘要)同样复用该 run 的 model,不回退到内核构造期的全局默认。**

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
