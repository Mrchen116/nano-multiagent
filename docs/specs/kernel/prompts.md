# kernel (agent) - Prompts Specification

> 对齐: feat-446
> 上级: [kernel (agent) Specification](spec.md)
>
> 写法纪律见 [`../../SPEC_GUIDE.md`](../../SPEC_GUIDE.md)「给库/内核写契约的额外纪律」。本目录只收 **消费者经 `agent.sdk` 真正依赖的对外行为**(CDC 裁剪);内部如何装配/实现不在此层(那在代码 + 归档 design)。

## Purpose

产品专属 prompt 条件、PromptSlots 和系统提示组装的内核契约。

## Requirements

### Requirement: feature 内核只留通用项,产品专属条件 prompt 全 per-session 经 PromptSlots

内核 feature 目录只含配内核内置工具的通用项:`memory_curation`(`memory` 工具)、`skill_creation`
(`skill_manage` 或 `skill_view` 工具),其开关在 `create_session(features=…)`,gate 内核统一模板对应段
(flag 开 + 所需工具在场)。内核不含任何产品专属 feature。产品专属条件 prompt(cron 指引 / heartbeat 指引 /
群聊上下文)**全是 per-session**(由 agent 配置在 create_session 时定、整会话不变),经
`create_session(prompt=PromptSlots)` 注入;产品**不向系统提示做 per-turn 注入**。

#### Scenario: 通用 feature 由会话开关 + 工具在场门控
- **GIVEN** 会话 `features={"memory_curation": true}` 且 `memory` 工具在 `enabled_tools` 中
- **WHEN** 装配该会话 system prompt
- **THEN** memory guidance 段出现;flag 未开或工具不在场则不渲染

#### Scenario: 能力查询返回内核 feature、产品对外 feature 由应用投影
- **GIVEN** Gateway 拿 `kernel.list_features()`(内核通用项)组装 IM payload
- **WHEN** 产品需对外呈现自己的"feature"概念(含 heartbeat/cron 等纯产品开关)
- **THEN** 该呈现是应用层投影,可叠加无内核 feature 对应的纯产品开关,不要求与内核目录一一对应

### Requirement: 系统提示由内核模板 + PromptSlots(四槽) 组装,产品内容纯 per-session

内核拥有模板骨架(顺序固定:head → core 行为规则 → body → 通用 feature 指引 → 后台任务/runtime footer →
custom → **内核自有工作区 AGENTS.md 段** → 内核易变尾部(memory/时间) → tail)。`create_session(prompt=PromptSlots(head/body/custom/tail))`
填产品文案槽。系统提示的**产品内容全是 per-session**:建会话时由模板 + PromptSlots 组装一次、整会话
稳定;内核易变尾部由内核自管,产品不碰。**工作区 AGENTS.md 段也由内核自管**(源自 `workspace_root/AGENTS.md`,
首轮冻结、压缩边界刷新,见「会话上下文自带工作区 AGENTS.md」Requirement)。产品无任何向系统提示做
per-turn 注入的通道(hook 不注入系统提示)。`PromptSection` / `PromptContext` / `RenderMode` 不在公共表面。

#### Scenario: 系统提示产品内容在会话内稳定
- **GIVEN** 一个已创建会话
- **WHEN** 同一会话多回合运行
- **THEN** 系统提示的产品内容(PromptSlots 四槽)逐回合不变(仅内核自管的易变尾部随 memory/时间变、
  以及内核自管的工作区 AGENTS.md 段随上下文压缩边界刷新);产品无机制在回合间改写系统提示

#### Scenario: prompt preview 与真实装配同源
- **GIVEN** `kernel.assemble_prompt_preview(*, prompt=PromptSlots, features, enabled_tools,
  workspace_root, scenario)`,消费者用与真实会话同一工厂构造的 `PromptSlots`
- **WHEN** 以某 agent 配置请求预览
- **THEN** 预览输出与该配置真实会话装配的 system prompt 一致(**易变尾部 + 工作区 AGENTS.md 段**以
  `<runtime-injected:…>` 占位,不读盘);内核侧 product-neutral(产品段全在传入的 PromptSlots)
