# feat-449: subagent 可观测性

## Relations

无外部依赖。

## 原始需求

> 当前IM上subagent在工作的话，没有可观测性，不知道subagent正在干嘛。你看看openclaw和hermes agent是怎么设计的

## 澄清记录

- Q1: 最想看到 subagent 的哪一层活动？推荐"工具调用级别"（当前跑什么工具、已完成几个、耗时），不钻 token 流/thinking。
  A(原话): 工具，thinking，输出的text
  Agent 解读: 用户要全部三层——工具调用、thinking 段、LLM 文字输出都要实时可见。

- Q2: subagent 活动展示位置——直接流进父对话气泡 vs 收在 AgentCard 展开面板内？
  A(原话): 需要设计。我没结论
  Agent 解读: 展示位置留给 design-author 决策，spec 只描述"用户能看到 subagent 活动"。

- Q3: subagent 自己又派了子 subagent（嵌套），用户需要看到哪一层？推荐"只看直接子 agent（第一层）"。
  A(原话): 对
  Agent 解读: 只展示第一层子 agent 的活动，深层嵌套不暴露。

- Q4: subagent 跑太久/卡住时用户需要能干预吗？推荐"需要能终止"。
  A(原话): 先只是能观测。我们原本就有/stop可以终止主agent+subagent
  Agent 解读: 本期只做观测，终止能力已有 `/stop` 覆盖，不重复建设。

- Q5: subagent 完成后用户还需要能回看活动过程吗？推荐"需要能回看"。
  A(原话): 对
  Agent 解读: 活动过程需要持久化，完成后仍可查看历史。

## 用户场景

用户在 IM 里让 agent 做一件事，agent 判断需要派一个子 agent 去做（比如代码审查、重构、跑测试）。子 agent 启动后，用户看到 AgentCard 上一个 "running" 脉冲动画，然后——什么都没有。子 agent 可能跑 30 秒，也可能跑 5 分钟，期间用户完全不知道它在做什么：跑了多少个工具、thinking 了什么、产出了什么文字。用户只能干等，或者反复问"好了吗"。

有了这个功能后：子 agent 启动，用户实时看到它的活动——工具调用一个接一个出现（🔧 bash 执行命令、✏️ edit 编辑文件、🔍 web_search 搜索...），thinking 段随着推理产生，LLM 的文字输出逐步流进来。用户能判断子 agent 是否在正确轨道上。子 agent 完成后，用户还能回看完整的活动历史。

## 验收标准

### Requirement: subagent 运行时工具调用实时可见

#### Scenario: 子 agent 执行多个工具调用
- **GIVEN** 用户让 agent 做一件事，agent 派了一个子 agent
- **WHEN** 子 agent 执行 bash 命令、编辑文件等工具调用
- **THEN** 用户实时看到每个工具调用的名称、状态（运行中/已完成）、耗时
- **AND** 工具调用按执行顺序排列

#### Scenario: 子 agent 工具调用失败
- **WHEN** 子 agent 的某个工具调用执行失败
- **THEN** 用户看到该工具调用标记为失败状态，能看到失败原因

### Requirement: subagent 运行时 thinking 实时可见

#### Scenario: 子 agent 产生 thinking 内容
- **WHEN** 子 agent 在推理过程中产生 thinking 段
- **THEN** 用户实时看到 thinking 段内容出现

### Requirement: subagent 运行时文字输出实时可见

#### Scenario: 子 agent 产出 LLM 文字输出
- **WHEN** 子 agent 产生 assistant message（文字回复）
- **THEN** 用户实时看到文字输出逐步流入

### Requirement: subagent 完成后可回看活动历史

#### Scenario: 子 agent 完成后查看过程
- **GIVEN** 子 agent 已完成运行
- **WHEN** 用户查看该子 agent 的 AgentCard
- **THEN** 用户能看到完整的工具调用列表、thinking 段、文字输出，按时间顺序排列

#### Scenario: 子 agent 失败后查看过程
- **GIVEN** 子 agent 运行失败
- **WHEN** 用户查看该 AgentCard
- **THEN** 用户能看到失败前的活动历史（已执行的工具调用、thinking、文字输出）以及失败原因

### Requirement: 只展示直接子 agent 活动

#### Scenario: 子 agent 又派了子 subagent
- **GIVEN** 子 agent 内部又派了一个子 subagent
- **WHEN** 用户查看父 agent 对话
- **THEN** 用户只看到直接子 agent 的活动，不看到孙 agent 的内部活动

### Requirement: 子 agent 完成状态明确

#### Scenario: 子 agent 正常完成
- **WHEN** 子 agent 正常完成运行
- **THEN** 用户看到完成状态标记、总耗时

#### Scenario: 子 agent 长时间运行
- **WHEN** 子 agent 运行超过 2 分钟仍在执行
- **THEN** 用户仍能看到持续更新的活动（工具调用、thinking、文字输出），不会因为长时间运行而丢失可见性

## 范围与非目标

- 在范围：
  - subagent 工具调用实时可见（名称、状态、耗时）
  - subagent thinking 段实时可见
  - subagent 文字输出实时可见
  - subagent 完成/失败状态明确标记
  - 完成后可回看活动历史
  - 只展示第一层子 agent（不展示深层嵌套）
- 非目标：
  - 用户干预运行中的 subagent（已有 `/stop` 覆盖）
  - IM 原生命令查 subagent 列表（如 `/tasks`）
  - 多层嵌套 subagent 层级展示
  - subagent 进度百分比/步骤计数
  - subagent token 用量实时展示
