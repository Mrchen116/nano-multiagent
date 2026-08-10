# feat-507: 统一工具审批模型

## Relations

- Related: feat-333

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
