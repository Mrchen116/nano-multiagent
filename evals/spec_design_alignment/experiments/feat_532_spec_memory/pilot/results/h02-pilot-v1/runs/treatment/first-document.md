# feat-507: 统一工具审批模型

## Relations

- Related: feat-333

## 原始需求

> 当前agent审批工具调用复用的agent自己的模型，我想改为所有统一用一个模型，通过配置文件来控制

## 澄清记录

- Q1: 这里的“所有”是否同时覆盖 Coding CLI 和 Personal Assistant / IM 中所有 Agent 的工具审批？
  A(原话): 不同时覆盖。此次产品范围是 Personal Assistant；Coding CLI 保持不变。内核可以保持产品中立，支持显式选择或省略审批分类模型，但不能据此扩大到 Coding CLI。
  Agent 解读: 产品验收范围只包含 Personal Assistant；Coding CLI 的审批模型行为保持现状。内核只提供产品中立的显式选择能力与省略语义，不替产品扩大生效面。

- Q2: Personal Assistant 配置中没有显式指定统一审批模型时，应使用哪个模型？
  A(原话): 不应回退到 PA 的产品级默认模型。未显式配置时保留现有行为：每次自动审批分类继续复用触发该分类的 Agent 或 run 模型。
  Agent 解读: 统一审批模型是 Personal Assistant 的显式可选配置；只在配置后才覆盖各 Agent/run 模型，省略时行为与变更前一致。

- Q3: 如果 PA 显式配置的统一审批模型不存在、未注册或配置不可用，Gateway 应如何表现？
  A(原话): 同意。若显式选择的模型不在 PA 模型目录中，应作为 Gateway 启动配置错误明确失败，不能静默回退。
  Agent 解读: Gateway 启动时必须验证显式选择的统一审批模型属于 PA 当前模型目录；验证失败时不进入运行态。

- Q4: 这次是否只统一“需要调用模型判断 allow / deny / ask 的自动审批分类”所用模型，而保持 Agent 正常回复模型、工具自身的确定性安全规则以及用户人工审批流程不变？
  A(原话): 是，只改变自动工具审批分类器的模型选择。Agent 正常请求和工具调用后的续写仍使用当前 run 模型；确定性安全规则与人工审批流程不在此次变更范围内。
  Agent 解读: 专用配置只控制自动工具审批分类的模型请求；它不成为 run 模型，也不改变无需模型的安全判定与人工决策。

## 用户场景

Personal Assistant 的运维者可以在 Gateway 配置文件中为自动工具审批选定一个统一模型。当同一 Gateway 下的不同 Agent 分别使用不同对话模型时，只要工具调用进入需要模型判断的自动审批分类，它们都由配置的同一模型给出分类结果，不再随各自 Agent 或 run 模型漂移。

统一审批模型是显式可选配置。运维者未配置时，Personal Assistant 完全保留变更前行为：每次自动审批分类仍复用触发它的 Agent 或 run 模型。运维者一旦显式选择统一审批模型，Gateway 就必须在启动时确认该模型存在于 PA 模型目录中；配错时明确报错并停止启动，不用静默回退制造“看似统一、实际没统一”的错觉。

这项配置只切换自动工具审批分类器的模型。各 Agent 的正常回复以及工具调用后继续生成的内容仍使用当前 run 模型；既有确定性安全规则、向用户发起人工审批及处理用户决定的体验不受影响。Coding CLI 也继续按现有方式选择自动审批分类模型。

## 验收标准

### Requirement: Personal Assistant 可显式统一自动工具审批分类模型

#### Scenario: 不同 Agent 的自动审批使用同一配置模型
- **GIVEN** 运维者在 Personal Assistant 配置中选定统一审批模型 M，且两个 Agent 的 run 分别使用模型 A 和 B
- **WHEN** 两个 Agent 都发起需要模型进行自动审批分类的工具调用
- **THEN** 两次审批分类均使用 M，不使用 A 或 B
- **AND** 运维者可以从模型服务的请求记录中核对这一结果

#### Scenario: 未配置统一审批模型时保持现有行为
- **GIVEN** Personal Assistant 没有显式配置统一审批模型
- **WHEN** 某 Agent 的工具调用需要模型进行自动审批分类
- **THEN** 该次分类继续复用触发它的 Agent 或 run 模型，不改用 PA 的产品级默认模型
- **AND** 运维者可以从模型服务的请求记录中核对这一结果

### Requirement: 显式配置的审批模型必须有效

#### Scenario: 配置 PA 模型目录内的模型
- **GIVEN** 运维者选定的统一审批模型存在于 PA 模型目录
- **WHEN** 运维者使用该配置启动 Gateway
- **THEN** Gateway 正常启动，后续需要模型的自动工具审批分类统一使用该模型

#### Scenario: 配置 PA 模型目录外的模型
- **GIVEN** 运维者显式选定的统一审批模型不在 PA 模型目录中
- **WHEN** 运维者启动 Gateway
- **THEN** Gateway 以可理解的配置错误明确失败，指出统一审批模型无效
- **AND** Gateway 不静默回退到 Agent/run 模型或 PA 产品级默认模型

### Requirement: 统一审批模型不改变其他模型与权限体验

#### Scenario: Agent 正常生成与工具后续写保持 run 模型
- **GIVEN** Personal Assistant 已配置统一审批模型 M，当前 run 使用模型 A
- **WHEN** Agent 正常回复，或在工具调用完成后继续生成回复
- **THEN** 用户获得的 Agent 回复仍由 A 生成，不改用 M

#### Scenario: 确定性安全规则与人工审批保持原有语义
- **GIVEN** Personal Assistant 已配置统一审批模型
- **WHEN** 工具调用被既有确定性安全规则直接裁决，或自动审批要求用户人工确认
- **THEN** 工具仍按既有安全规则执行，或向用户展示原有的人工审批体验
- **AND** 用户的允许或拒绝决定仍按现有方式生效

#### Scenario: Coding CLI 保持现有审批模型选择
- **WHEN** Coding CLI 的工具调用需要模型进行自动审批分类
- **THEN** Coding CLI 继续按变更前的方式选择分类模型，不受 Personal Assistant 的统一审批模型配置影响

## 范围与非目标

- 在范围：Personal Assistant 在 Gateway 配置文件中显式选择一个统一的自动工具审批分类模型。
- 在范围：所有进入模型自动审批分类的 Personal Assistant Agent/run 共享该模型。
- 在范围：未显式配置时保持按 Agent/run 模型分类的现有行为。
- 在范围：Gateway 启动时对显式选择的审批模型做 PA 模型目录有效性检查，无效时明确失败。
- 非目标：改变 Coding CLI 的自动工具审批模型选择。
- 非目标：改变 Agent 正常请求或工具调用后续写所用的 run 模型。
- 非目标：改变工具的确定性安全规则、自动审批的 allow / deny / ask 判定语义或人工审批交互。
- 非目标：在 Gate 1 规定配置字段名、内核接口或模块分工；这些实现决策留给设计阶段。
