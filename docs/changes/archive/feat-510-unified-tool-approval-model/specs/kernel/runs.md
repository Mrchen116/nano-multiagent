# kernel (agent) Runs Specification (delta for feat-510)

## ADDED Requirements

### Requirement: 自动工具权限分类可使用消费者指定模型且不静默降级

消费者可在装配 Kernel 时选择一个已注册模型，专用于自动工具权限分类；未选择时，分类
复用当前 run 的模型。该选择不改变 run 的正常模型，也不改变分类失败后的既有权限处理。

#### Scenario: 显式模型只用于自动分类
- **GIVEN** 消费者以已注册模型 C 装配 Kernel，并以模型 A 提交一个 run
- **WHEN** 该 run 触发自动工具权限分类、执行工具并继续运行
- **THEN** 自动分类使用 C
- **AND** 分类前后的正常 run 请求继续使用 A

#### Scenario: 未显式选择时复用当前 run 模型
- **GIVEN** 消费者未在装配 Kernel 时选择自动工具权限分类模型
- **WHEN** 一个以模型 A 提交的 run 触发自动分类
- **THEN** 分类使用 A

#### Scenario: 显式模型必须属于已注册 catalog
- **GIVEN** 消费者提供的自动工具权限分类模型不在 Kernel 的 LLM catalog 中
- **WHEN** 消费者经 `agent.sdk` 装配 Kernel
- **THEN** 装配失败并明确指出无效模型

#### Scenario: 显式模型调用失败时不改用 run 模型
- **GIVEN** 消费者选择模型 C 用于自动工具权限分类，当前 run 使用模型 A
- **WHEN** C 的分类调用超时、失败或返回不可解析结果
- **THEN** 内核不改用 A 或其他模型重新分类
- **AND** 该次工具调用进入既有的显式审批或 unattended fallback
