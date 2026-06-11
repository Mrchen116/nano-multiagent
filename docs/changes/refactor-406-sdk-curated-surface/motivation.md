# refactor-406: 收敛 agent.sdk 公共表面

## Relations

- Related: refactor-387
- Closes: #65
- Closes: #69

## 原始诉求

> $change-spec-author 帮我做这个重构，让架构真正合理，后续可以长久演进

> 对，这个sdk后续任何产品都能用简单的代码就能配套上自己的工具等等，变成一个新的agent产品。

关联上下文：

> 确实架构不妥对吧

- https://github.com/Mrchen116/nano-multiagent/issues/65
- https://github.com/Mrchen116/nano-multiagent/issues/69

## 澄清记录

- Q1: 本次只处理 issue 点名的 4 个内部导出，还是全面审计 `agent.sdk` 的所有公开符号，并建立长期防回退约束？
  A(原话): 对
  Agent 解读: 接受推荐范围：全面审计 `agent.sdk` 的公开符号，保留稳定的公共能力，消除实现级 passthrough，并建立长期防回退约束。
- Q2: 需要兼容仓库外部调用方当前直接 import 的这些 SDK 符号吗？
  A(原话): 对的。而且必须保证重构不影响现有的产品对外功能
  Agent 解读: 不承诺兼容内部实现级导出；真正稳定的公共 API 应保持或提供明确替代。同时，Coding CLI、Gateway、IM 等现有产品的用户可观察功能必须保持不变。
- Q3: SDK 是否只能暴露产品中立的内核能力，Gateway 专属的 skills/features/tools 能力报告由 Gateway 自己组合？
  A(原话): 对
  Agent 解读: `agent.sdk` 只承担产品中立的稳定能力与数据契约；Gateway 负责把这些能力组合为 IM 所需的产品专属 capability payload，SDK 不承载 IM/Gateway 展示语义。
- Q4: 本次是否严格保持当前 capability payload 的对外语义，包括 models、skills、tools、features、默认模型和 workspace skill 差异？
  A(原话): 对
  Agent 解读: 本次只改变内部边界和依赖方式，不调整 capability payload 的字段、默认值、可用性判断或展示语义；若发现既有产品问题，另立变更单元处理。
- Q5: 是否要求新增可执行的 SDK 公共表面守卫，让未来新增导出必须是明确批准的稳定契约，不能再任意 re-export `core/platform` 内部符号？
  A(原话): ok
  Agent 解读: 本 unit 必须建立自动化公共表面守卫；具体采用静态清单、对象来源检查或 SDK 自有 facade 等机制，留给 design 阶段决定。
- Q6: 全面审计发现其他内核分层问题时，本 unit 是否只处理 SDK 公共边界及其直接调用方，不顺带重构无关的 core/platform 内部结构？
  A(原话): ok
  Agent 解读: 本 unit 聚焦 `agent.sdk` 公共边界及其直接消费方；审计发现但不属于该边界的其他问题单独记录，不扩大成本次内核重构。
- Q7: 新 Agent 产品是否应当无需修改 `agent` 包内部代码，仅通过 SDK 提交自己的产品定义和 tools/hooks/skills/prompt 配置即可装配？
  A(原话): 对
  Agent 解读: SDK 必须是开放的产品装配契约，而不是只认识 Coding CLI 与个人助手的封闭双产品工厂。新增产品可以在自身代码中声明产品能力并装配 Kernel，不需要向 `agent.products` 或 SDK 内部增加产品分支。
- Q8: 新产品扩展是否只需要支持自定义工具，还是覆盖完整产品定义？
  A(原话): 现在就是这样设计的了吧，本来就是不单单是自定义工具
  Agent 解读: 当前 `ProductProfile` / bootstrap 已经覆盖 tools、hooks、skills、prompt、配置目录和默认策略等完整产品定义。本 unit 应保留并公开化这条完整扩展能力，而不是把目标降级成新增一个仅支持工具的插件机制。

## 现状痛点

`refactor-387` 把内核改造成经 `agent.sdk` 嵌入产品的进程内库，并确立“产品只能 import
`agent.sdk`”的边界。当前边界在语法上成立，但未完全实现“稳定公共契约”的原始意图：

- 为满足 Gateway 的能力报告需求，`agent.sdk` 直接公开了 skill registry、配置路径解析器、feature
  registry 等内核实现细节。
- Gateway 虽未直接 import `agent.core` / `agent.platform`，仍通过 SDK 暴露的内部对象了解其组织方式，
  因而内核内部重构可能被这些间接依赖阻塞。
- 现有边界测试只能发现产品直接越界 import，无法发现 SDK 通过 re-export 把内部实现抬成公共 API。
- SDK 文档把一部分导出描述为 Gateway 的扩展表面，产品专属需求正在反向塑造内核的唯一公共入口。

这不造成当前功能故障，但会持续扩大兼容负担：每次产品需要一个内部对象，都可能通过新增 re-export
绕过边界约束，最终使 `agent.sdk` 退化为 `core/platform/products` 的聚合入口。

## 目标状态

`agent.sdk` 成为可长期演进的、产品中立的内核公共契约：

- 全面审计当前公共符号，明确哪些是稳定能力，哪些只是偶然暴露的内部实现。
- 移除实现级 passthrough；内部实现符号不因已有错误导出而获得长期兼容承诺。
- 产品真正需要的内核能力以稳定、窄化、产品中立的契约提供，不暴露其背后的 registry、resolver 或
  可变内部数据结构。
- Gateway 自己负责把内核能力组合成 IM 使用的 models / skills / tools / features 等产品语义；
  内核 SDK 不认识 IM 展示与 Gateway 协议。
- 新产品可以只依赖 SDK，在自己的包内用少量产品定义代码接入自有 tools、hooks、skills、prompt
  等完整产品定义并装配可运行 Kernel；这是对现有多产品设计能力的稳定公共化，不是另造仅支持
  自定义工具的插件机制。接入新产品不要求修改 `agent` 包内部源码。
- 建立自动化公共表面约束，使新增导出必须被明确纳入稳定契约并有相应契约测试，不能再次靠任意
  re-export 满足产品依赖。
- Coding CLI、Gateway 与 IM 的现有用户和运维行为保持不变。

## 用户侧验收标准（不变性）

本重构不引入新产品功能。用户仍通过 Coding CLI 与个人助手使用同一套既有能力；IM 中节点与 Agent
设置页仍获得相同语义的可选模型、技能、工具与 feature 信息。运维者仍按现有方式启动和连接 Gateway。

### Requirement: Coding CLI 的现有 Agent 工作流保持可用

#### Scenario: 用户在 Coding CLI 完成带工具调用的任务
- **GIVEN** 用户在一个可读写的工作区启动 Coding CLI
- **WHEN** 用户提交需要读取、修改或执行工作区内容的任务
- **THEN** CLI 仍能创建会话、流式展示过程并完成任务，权限询问、中断和错误反馈的用户体验与重构前一致

#### Scenario: 用户选择已配置模型启动 CLI
- **GIVEN** 本地配置中存在可用的 provider 与 model
- **WHEN** 用户按现有命令启动 Coding CLI 并选择或指定模型
- **THEN** CLI 正常启动并使用该模型，不要求用户迁移配置或改用新的启动参数

### Requirement: 个人助手的消息处理能力保持可用

#### Scenario: 用户经 Web IM 向 Agent 发送消息
- **GIVEN** IM 与 Gateway 已连接且 Agent 在线
- **WHEN** 用户在既有会话中发送消息
- **THEN** Agent 正常处理并回复，消息状态、流式内容与最终结果的用户体验与重构前一致

#### Scenario: IM 暂时离线时 Gateway 保持本地自治
- **GIVEN** Gateway 已配置外部消息通道且 IM 服务不可达
- **WHEN** 外部通道收到用户消息
- **THEN** 消息仍可由 Gateway 交给 Agent 处理并回发，不因 SDK 公共表面收敛而依赖 IM 在线

### Requirement: IM 中的 Agent 配置与能力选择保持一致

#### Scenario: 用户创建 Agent 时查看节点能力
- **GIVEN** 一个在线 Gateway 节点
- **WHEN** 用户在 IM 中进入创建 Agent 的配置流程
- **THEN** 可选 models、skills、tools、features、默认模型及其默认选中和可用状态与重构前一致

#### Scenario: 用户编辑不同工作区的 Agent
- **GIVEN** 不同 Agent 工作区具有不同的可发现 skills
- **WHEN** 用户在 IM 中分别查看这些 Agent 的配置能力
- **THEN** 每个 Agent 仍展示其对应工作区可见的 skill 名称与描述，不出现跨工作区混用或丢失

#### Scenario: 用户保存既有 Agent 配置
- **GIVEN** 用户选择了模型、skills、tools 或 features
- **WHEN** 用户保存配置并再次打开该 Agent
- **THEN** 配置可正常同步并回显，字段语义与默认行为不因内部重构改变

### Requirement: Gateway 的现有运维方式保持不变

#### Scenario: 运维者按现有配置启动 Gateway
- **GIVEN** 一份当前可用的 Gateway 配置
- **WHEN** 运维者使用现有启动命令启动 Gateway
- **THEN** Gateway 正常装配内核、连接 IM、注册节点并报告在线，不要求新增兼容开关或人工迁移步骤

#### Scenario: 运维者停止或重启 Gateway
- **WHEN** 运维者执行现有 stop 或 restart 命令
- **THEN** Gateway 仍能收拢活动任务并正常退出或重启，行为与重构前一致

### Requirement: 新产品可通过 SDK 独立装配 Agent

#### Scenario: 产品开发者接入新的 Agent 产品
- **GIVEN** 产品开发者已有自己的产品包和需要接入的工具等能力
- **WHEN** 开发者仅使用 `agent.sdk` 提供的公共契约声明产品能力并创建 Kernel
- **THEN** 新产品能够运行自己的 Agent 工作流，且不需要修改 `agent` 包内部源码或依赖其内部模块

#### Scenario: 新产品逐步增加自身能力
- **GIVEN** 一个已经通过 SDK 装配并运行的 Agent 产品
- **WHEN** 产品开发者增加或调整该产品自己的 tools、hooks、skills 或 prompt
- **THEN** 产品可以在自身代码范围内完成演进，不要求把产品专属实现加入 SDK 公共表面

## 影响范围

- `agent.sdk` 的公共契约定义、文档与架构守卫。
- Coding CLI 与 Gateway 对 SDK 公共能力的直接使用。
- 新 Agent 产品通过 SDK 接入产品自有 tools、hooks、skills、prompt 等能力的开发者体验。
- Gateway 向 IM 提供 node / agent capability 信息的既有行为。
- 与公共表面和上述产品行为相关的契约测试、单元测试及长青规格。

非目标：

- 不改变 models / skills / tools / features capability payload 的字段、默认值、可用性判断或展示语义。
- 不新增、删除或调整 Coding CLI、Gateway、IM 的用户功能。
- 不在本 unit 交付第三个具体 Agent 产品；只交付足以装配新产品的稳定 SDK 契约，并用现有产品和
  最小示例/契约测试证明该扩展路径可用。
- 不为错误暴露的内部实现级符号提供仓库外兼容层或弃用周期。
- 不顺带重构与 SDK 公共边界无直接关系的 core/platform 内部结构。
- 不借本 unit 修复审计过程中发现的其他产品问题；此类问题另立 issue 或 change unit。

## 迁移与回滚策略

- 先用现有产品行为和公共契约建立回归基线，再迁移直接调用方，最后移除不合理的公开符号；任何阶段都不得
  依赖“先破坏产品、最后一起修复”的大爆炸迁移。
- 稳定公共能力必须先有可用替代，直接调用方完成迁移后才能删除对应的内部实现级导出。
- capability payload 的外部语义作为迁移不变量；若新边界无法保持 models / skills / tools /
  features 的当前结果，应停止迁移并回到设计阶段，而不是修改产品行为迁就实现。
- 每个迁移步骤应可独立回退到前一稳定状态；回滚不得恢复产品直接 import 内核内部的做法。
- 最终公共表面及防回退约束必须进入自动化测试和长青规格，避免后续维护再次扩大 passthrough。
