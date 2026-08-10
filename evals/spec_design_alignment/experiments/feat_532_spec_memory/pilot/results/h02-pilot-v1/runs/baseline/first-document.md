# feat-507: 统一工具调用审批模型配置

## 原始需求

> 当前agent审批工具调用复用的agent自己的模型，我想改为所有统一用一个模型，通过配置文件来控制

## 澄清记录

- Q1: 你说的“所有统一用一个模型”，是指 Coding CLI 和 Personal Assistant 各自按现有配置目录解析审批模型，还是两个产品必须共用同一份全局配置？
  A(原话): 本次需求范围是 Personal Assistant；Coding CLI 不因本需求改变，也不要求两个产品共用一份全局配置。具体配置目录、作用域及 workspace/global 覆盖规则请基于仓库现状研究，并提出最小改动方案。
  Agent 解读: 本 unit 只改 Personal Assistant。仓库现状中，Gateway 运行时配置的权威入口是单个 `~/.nano-assistant/config.yaml`（也可由 `--config` 指定其他文件），其 `llm` 段已统一管理产品可用模型；没有这份 Gateway 配置的 workspace/global 覆盖链。因此最小产品方案是让审批模型归这份 Gateway 配置所有，对该 Gateway 下全部 Agent 统一生效，不再引入 per-agent 或 workspace 覆盖。

- Q2: Personal Assistant 的 Gateway 配置没有显式指定专用审批模型时，应该回退到 `llm.default_model`，还是拒绝启动并要求补配置？
  A(原话): 不应回退到 `llm.default_model`，也不应因缺省而拒绝启动。未显式配置时保持现有行为：每次自动审批分类复用触发它的 Agent 或 run 模型；显式配置后则使用专用模型，运行失败也不回退到 Agent、默认或其他模型。

- Q3: 修改 Personal Assistant 的专用审批模型配置后，是否接受重启 Gateway 才生效？
  A(原话): 接受。该配置在 Gateway 重启后生效，本需求不增加字段级热更新。

- Q4: 如果显式配置的专用审批模型没有登记在同一 Gateway 配置的 `llm.providers[].models[]` 中，Gateway 应该在启动时直接报配置错误，还是允许启动、等首次审批时再失败？
  A(原话): 启动时直接报配置错误。显式选择的专用审批模型若不在 Personal Assistant 模型目录中，不允许静默回退或延迟到首次审批时才失败。

## 用户场景

Personal Assistant 的运维者在一个 Gateway 下运行多个 Agent，这些 Agent 可以各自选择不同的对话模型。当工具调用需要 auto mode 分类器做自动审批时，运维者希望通过 Gateway 已有的本地配置文件为整个 Personal Assistant 进程选定一个专用模型。Gateway 重启后，无论工具调用来自哪个 Agent、直接聊天还是该 Agent 的其他 run，自动审批分类都使用这个专用模型；Agent 自身的对话模型选择不受影响。

这份配置的作用域是当前 Gateway 进程。它跟随实际启动 Gateway 时使用的配置文件：默认是 `~/.nano-assistant/config.yaml`，运维者显式传入 `--config` 时则以该文件为准。不再为这个选择叠加 per-agent、workspace 或 global/workspace 覆盖层。

未配置专用审批模型的现有部署无需迁移：自动审批分类继续复用当前 Agent 或 run 的模型。显式配置专用模型后，如果该模型的某次分类请求运行失败，系统保持现有的安全失败语义：有人值守的 run 转为询问用户，无人值守的 run 按现有 unattended fallback 处理；整个过程不改用 Agent 模型、产品默认模型或其他模型重试分类。若运维者在配置中选了未登记的模型，Gateway 在启动时就给出明确的配置错误，不把问题留到首次工具审批时才暴露。

## 验收标准

### Requirement: Gateway 可为全部 Agent 统一选定专用审批模型

#### Scenario: 不同 Agent 的自动审批使用同一专用模型
- **GIVEN** 同一 Personal Assistant Gateway 下有使用对话模型 A 和 B 的两个 Agent，且 Gateway 配置选定专用审批模型 C
- **WHEN** 两个 Agent 的工具调用分别触发自动审批分类
- **THEN** 运维者可观察到两次分类都使用模型 C
- **AND** 两个 Agent 的正常对话仍分别使用模型 A 和 B

#### Scenario: 同一 run 内的所有自动审批分类都使用专用模型
- **GIVEN** Gateway 配置选定专用审批模型 C
- **WHEN** 任一 Agent 的一个 run 中多次触发自动审批分类
- **THEN** 运维者可观察到每次分类都使用模型 C，不随 Agent 或 run 模型变化

### Requirement: 专用审批模型配置兼容现有部署并在重启后生效

#### Scenario: 未配置专用审批模型
- **GIVEN** Gateway 配置没有选定专用审批模型
- **WHEN** 任一 Agent 的工具调用触发自动审批分类
- **THEN** 分类继续使用触发它的 Agent 或 run 模型，Gateway 不因缺少专用配置而拒绝启动

#### Scenario: 修改配置并重启 Gateway
- **GIVEN** Gateway 当前使用审批模型 C
- **WHEN** 运维者在启动 Gateway 所用的配置文件中改选审批模型 D，并重启 Gateway
- **THEN** 重启后新触发的自动审批分类统一使用模型 D

#### Scenario: 配置未登记的专用审批模型
- **GIVEN** Gateway 配置选定的专用审批模型不在 Personal Assistant 模型目录中
- **WHEN** 运维者启动 Gateway
- **THEN** Gateway 拒绝启动并给出可理解的模型配置错误
- **AND** Gateway 不静默改用 Agent 模型、产品默认模型或其他模型

### Requirement: 专用审批模型失败时不切换到其他模型

#### Scenario: 有人值守的分类请求失败
- **GIVEN** Gateway 已选定专用审批模型，且当前 run 可以询问用户
- **WHEN** 专用模型的自动审批分类请求运行失败
- **THEN** 用户收到现有的权限询问，可以人工允许或拒绝工具调用
- **AND** 系统不改用 Agent 模型、产品默认模型或其他模型重试分类

#### Scenario: 无人值守的分类请求失败
- **GIVEN** Gateway 已选定专用审批模型，且当前 run 无人值守
- **WHEN** 专用模型的自动审批分类请求运行失败
- **THEN** 工具调用按现有的无人值守权限兜底规则处理
- **AND** 系统不改用 Agent 模型、产品默认模型或其他模型重试分类

## 范围与非目标

- 在范围：Personal Assistant Gateway 通过其已有本地配置文件选定一个进程级专用审批模型。
- 在范围：显式配置后，同一 Gateway 下所有 Agent 和 run 的自动审批分类统一使用该模型。
- 在范围：未配置时保持复用 Agent 或 run 模型的现有行为。
- 在范围：专用模型的目录校验、重启生效与失败不回退语义。
- 非目标：改变 Coding CLI 的审批模型或配置。
- 非目标：让 Coding CLI 与 Personal Assistant 共用一份审批模型配置。
- 非目标：提供 per-agent、per-run 或 workspace 级的专用审批模型覆盖。
- 非目标：增加字段级热更新或 Web IM 配置界面。
- 非目标：改变 Agent 正常对话的模型选择，或改变 auto mode 现有的 allow / deny / ask、有人值守 / 无人值守裁决语义。
