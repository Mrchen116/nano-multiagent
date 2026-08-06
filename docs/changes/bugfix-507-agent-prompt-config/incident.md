# bugfix-507: Agent 配置隐藏提示词生效 — 事故记录

## Relations

- Related: feat-379, bugfix-471, feat-397
- Closes: #244

## 原始报告

> Preview full system prompt中看到的是真实的吗

> 角色段 system_prompt是啥啊，我一头雾水，哪个unit做的设计

> 所以这个system_prompt字段就不应存在是吧，应该改nano的代码，对吗

> 好，你独立走spec，design，修复该问题。

附：用户在 IM Agent 配置页查看团队实验 Agent 时，`Custom Instructions` 为空；展开
“Preview full system prompt”后看到的是公共提示词，页面底部说明群聊和记忆运行时段未被预览。

## 澄清记录

- Q1: IM 中 Agent 的人设与专属约束，应由隐藏的 `system_prompt` 还是用户可见的
  `Custom Instructions` 管理？
  A(原话): 所以这个system_prompt字段就不应存在是吧，应该改nano的代码，对吗
  Agent 解读: IM/PA 的公开 Agent 配置不应保留第二个隐藏且有效的人设入口；用户可见的
  Custom Instructions 是唯一入口。

- Q2: 本次是只解释问题，还是独立完成从需求、设计到修复的完整变更？
  A(原话): 好，你独立走spec，design，修复该问题。
  Agent 解读: 用户授权在既有产品决策范围内独立完成 Full bugfix 流程，并以 #244 跟踪。

## 现象与复现

Agent owner 打开 IM 的 Agent 配置页，只能编辑 `Custom Instructions`。当该输入为空时，用户
合理地认为该 Agent 没有专属人设；展开提示词预览也只展示公共稳定提示词和当前草稿配置。

但只要该 Agent 持久 profile 中有非空 legacy `system_prompt`，实际下一轮聊天仍会采用这段
用户不可见、不可编辑的文本。预览没有携带它，因此用户看到的预览与实际稳定提示词不同。

这次团队实验的 Lead、Product、Architect 和 Verifier 正是通过该隐藏字段注入职责说明，直接暴露了
问题：用户无法从 Agent 配置理解团队成员的实际职责，也无法在 UI 中审阅或修改它。

## 影响范围

- 受影响对象是所有持有非空 legacy `system_prompt` 的 IM/PA Agent，以及它们的直聊和群聊后续新回复。
- 用户会得到“配置页显示为空、Agent 行为却带有专属约束”的错误心智模型；团队模板尤其无法被审阅。
- “Preview full system prompt”不能作为有效配置的可信检查工具，容易让用户基于错误信息调整 Agent。
- 当前未发现消息、聊天历史或工具调用数据损坏；风险是行为不透明和既有专属指令在删除字段时被静默丢失。

## 根因分析（RCA）

### 原始设计意图与不变量

`feat-379-system-prompt-sections` 将 IM/PA 的 per-agent 定制明确收敛为“特性开关 +
`custom_prompt` 追加段”：用户能在配置页看见、编辑并预览专属人设；公共规则和场景运行时段不由
用户覆盖。该 unit 的决策 5 同时废弃了用户面的整串 `system_prompt` 覆盖语义。

必须保住的不变量是：Agent owner 在 IM 中看到并保存的定制文本，才是改变该 Agent 专属人设的
唯一公开配置；公共提示词、群聊上下文、记忆等各自保持既有职责。

### 直接根因

`bugfix-471-agent-config-context-continuity` 为保证既有会话在运行配置改变后仍连续，重新把
`AgentWorkspaceConfig.system_prompt` 投影进 PA 的 `PromptSlots`，并排在 `custom_prompt` 前。
该字段仍由 IM profile、配置同步和 Gateway 本地配置保存，但前端已按 feat-379 隐藏其编辑入口。

提示词预览在同一修订后的架构中构造了不携带 `system_prompt` 的临时 Agent，因此它只预览
`custom_prompt`、features、tools 和 skills。运行时与预览没有使用同一份 per-agent 配置来源。

### 为什么能进入

回归测试验证了 legacy `system_prompt` 会先于 `custom_prompt` 注入运行时，却没有验证“公开配置页、
预览和实际聊天的稳定人设来源必须相同”。因此，运行连续性修复重新激活了已废弃的公开字段，
同时没有触发 UI/preview 一致性检查。

回归引入点：`062fb92ea6`（`fix(bugfix-471/M1/R3): 补全运行配置投影与持久化`）。

## 用户场景

**场景 1 — 配置即真实。** Agent owner 打开任一 Agent 配置页，看到 Custom Instructions 为空，
就能确信该 Agent 没有额外的人设文本；填写并保存一段职责或约束后，下一次新回复才采用这段内容。
用户不需要知道 legacy 字段、Gateway 配置或提示词拼装细节。

**场景 2 — 预览可用于检查。** Owner 保存或编辑专属说明时，展开预览就能检查该说明确实位于
公共规则之后。页面仍明确说明群聊参与者、记忆和其他运行时信息不在预览内，但不能遗漏任何
已保存的稳定用户配置。

**场景 3 — 已有 Agent 不丢约束。** 已经因 legacy 字段而实际带有专属说明的 Agent，升级后其说明
仍作为可见的 Custom Instructions 保留；owner 可以理解、审阅、修改或清空它，而不是在升级中
悄悄失去行为约束。

## 验收标准

### Requirement: Agent 专属人设只有可见的 Custom Instructions 入口

#### Scenario: 新建或编辑 Agent 没有隐藏的第二份人设
- **WHEN** owner 创建或编辑 IM Agent，并查看 Custom Instructions
- **THEN** 该输入是唯一会改变该 Agent 专属人设或职责的用户配置
- **AND** 留空时，Agent 不带任何其他由公开 Agent profile 注入的专属说明

#### Scenario: 保存专属说明只影响该 Agent 的后续新回复
- **GIVEN** owner 有两个 Agent
- **WHEN** owner 为其中一个 Agent 保存 Custom Instructions 后分别继续与两个 Agent 交流
- **THEN** 只有被编辑的 Agent 在后续新回复中体现该说明
- **AND** 已有聊天历史保持可继续使用

### Requirement: 预览如实呈现稳定的 Agent 配置

#### Scenario: 预览包含已保存或待保存的专属说明
- **WHEN** owner 展开 Agent 的提示词预览，或在编辑 Custom Instructions 后再次查看预览
- **THEN** 预览包含该 Agent 当前的专属说明和已选能力配置
- **AND** owner 不会看到“输入为空但实际仍有隐藏专属说明”的状态

#### Scenario: 预览明确边界而不冒充完整运行时上下文
- **WHEN** owner 查看提示词预览
- **THEN** 页面明确说明群聊、记忆等运行时内容不在预览内
- **AND** 除这些明确的运行时内容外，所有稳定用户配置都与实际新回复一致

### Requirement: 既有隐藏说明变为可审阅的公开配置

#### Scenario: 升级后保留已有 Agent 的有效专属说明
- **GIVEN** 某 Agent 在升级前因 legacy 配置实际带有专属说明
- **WHEN** 系统升级且 owner 重新打开该 Agent 配置
- **THEN** owner 能在 Custom Instructions 中看到并编辑该说明
- **AND** 该说明不会静默丢失或重复注入

## 范围与非目标

### 范围

- IM/PA Agent profile、Gateway 配置同步和 PA 提示词装配中 legacy `system_prompt` 的公开语义收敛。
- 将已有有效 legacy 专属说明迁入可见的 `custom_prompt`，并防止重复注入。
- Agent 配置页预览与实际稳定配置的同源性，以及对应跨进程回归覆盖。
- 将团队模板或实验 Agent 的成员职责改为可见的 Custom Instructions 数据，而不是隐藏字段。

### 非目标

- 改写公共 PA 默认提示词、feature 指引、群聊上下文、记忆内容或模型供应商提示词。
- 删除 Kernel 内部受控的完整 system-prompt override；它可继续服务子 Agent、测试或明确的内部 hook，
  但不再由 IM/PA 的公开 Agent 配置提供。
- 新增一套团队角色编辑器或模板 UI；该产品能力属于 feat-397 的后续范围。

