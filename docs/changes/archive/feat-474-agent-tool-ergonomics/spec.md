# feat-474: agent 工具更好用

## Relations

- Related: feat-337-cc-background-subagents
- Refs: [nano-vs-cc-agent-tool.md](./nano-vs-cc-agent-tool.md)（调研对比）；[cc-subagent-system-prompts/](./cc-subagent-system-prompts/)（实机系统提示词摘录）
- Follow-up（非本 unit）: 子→主边跑边推消息（用户确认强需求、本期不做）

## 原始需求

> 我觉得oh-my-opencode这个有点赘余设计。load_skills没啥必要。category也是和subagent_type重叠。你觉得呢？

> 还有一个问题。子agent工作没停下来，想给他插入一条消息。CC有对应的方式吗？

> 那么，如果子agent想发消息给主agent又不想停止工作。有对应方法吗

> 我要改造，让agent工具更加好用。给我推荐下要做哪些改造

## 澄清记录

- Q1: `timeout_seconds` 要不要从 agent 工具参数里删掉（对齐 CC：系统默认 120s 自动转后台，模型不可调）？
  A(原话): 我觉得CC这种思路更好
  Agent 解读: 同意去掉 schema 上的 `timeout_seconds`；保留系统默认前台预算（约 120s）到时自动转后台，不把超时暴露成模型可调参数。

- Q2: `load_skills` 本期怎么处理——改可选，还是整字段去掉？
  A(原话): load_skills直接也干掉。CC就没有，主agent如果觉得subagent要调用，可以直接prompt中给
  Agent 解读: 完全移除 `load_skills` 参数；需要子 agent 用某 skill 时，由主 agent 写进 `prompt`，不再经工具字段强制注入。

- Q3: `category` 要不要一并删掉，只留 `subagent_type`（可省略+默认）？
  A(原话): 对
  Agent 解读: 删除 `category`；新建只认 `subagent_type`，可省略并走默认类型。

- Q4: 新建不传 `subagent_type` 时默认成什么？
  A(原话): 好。我们也有general-purpose吧？
  Agent 解读: 默认字面量用 `general-purpose`。当时以为只做标签默认；后经实机日志确认 CC 类型有真差别，用户要求 **subagent_type 对齐也纳入本期**（见 Q5/Q6），默认仍落在真类型 `general-purpose` 上。

- Q5: （范围追加）要把 CC 式「真 subagent_type」（按类型换能力）纳入本期吗？
  A(原话): 这你要放入对比md中，后面不用再挖日志。 subagent_type的对齐也纳入本需求。你思考下我们应该放哪些 subagent_type
  Agent 解读: 实机目录已写入 `nano-vs-cc-agent-tool.md` §3；`claude`=Agent View 看板默认会话人格（人派后台会话用），非对话内常用子 agent。本期做真类型目录，清单见 Q6。

- Q6: 本期内置哪几个真类型？
  A(原话): 好
  Agent 解读: 本期内置 `general-purpose`（默认）、`Explore`、`Plan`。不放 `claude` / `claude-code-guide` / `statusline-setup` / `verification`。

- Q7: 「子 agent 边跑边给主 agent 推消息」本期做不做？
  A(原话): 不做，但是这是个强功能！后续会做
  Agent 解读: 本期明确非目标；记为后续强需求（可另开 unit），不并进 feat-474。主→子插话（`agent_id`）保持现状。

- Q8: 传了不认识的 `subagent_type` 怎么办？
  A(原话): follow CC
  Agent 解读: 对齐 CC：直接失败，错误信息含未知类型名 + `Available agents: …` 列出可用类型；不静默降级为 general-purpose。CC 源码：`Agent type '${effectiveType}' not found. Available agents: ...`

- Q9: 类型名大小写是否跟 CC 字面量一致？
  A(原话): ok
  Agent 解读: 使用 `general-purpose` / `Explore` / `Plan`，区分大小写；`explore` 等错误大小写按未知类型失败。

## 用户场景

主 agent（个人助手 / Coding CLI 里正在对话的那个）要派活给子 agent。改造后，它调用 `agent` 时不再填一堆仪式字段：不用 `load_skills`、不用在 `category` 和 `subagent_type` 之间二选一、也不用拧 `timeout_seconds`。只写清任务描述和 prompt；需要专用能力时选类型，不选就走通用默认。

三种内置类型对主 agent / 用户可感知的差别：

1. **general-purpose（默认）** —— 全能工人：可以改文件、跑命令、完成多步实现类任务；适合「去把这件事做完」。
2. **Explore** —— 只读探索：广搜代码/文件，回答「在哪 / 是什么」；**不能改仓库**。适合并行摸底，不污染工作区。
3. **Plan** —— 只读规划：摸清现状后给出实现步骤与关键文件；**不能直接改仓库**。适合先方案后动手。

需要子 agent 用某 skill 时，主 agent 把 skill 名和用法写进 `prompt` 即可，不再有单独传参。

前台子 agent 跑太久时，系统仍会在默认预算后自动转后台（主 agent 拿到可继续关注的 `agent_id` / 输出路径），但主 agent **不能再**用参数自定义这笔超时。

主 agent 仍可用已有方式给**还在跑**的子 agent 插话（带上该子 agent 的 id 发 follow-up）；子 agent **不能**在不停工时主动推消息给主 agent——本期不做，后续另开。

传错类型名或大小写（如 `explore`、`oracle`）时，派发失败，并告诉主 agent 当前有哪些可用类型，避免假装成功。

## 验收标准

### Requirement: agent 调用更轻，去掉赘余传参

#### Scenario: 最少参数即可新建子 agent
- **WHEN** 主 agent 新建子 agent，只提供短描述与完整任务说明，不传 skill 列表、不传 category、不传前台超时
- **THEN** 派发成功，并按默认类型 `general-purpose` 运行

#### Scenario: 旧仪式字段不再被要求
- **WHEN** 主 agent 查看或使用 `agent` 工具
- **THEN** 不必再提供 `load_skills` / `category` / `timeout_seconds`；需要 skill 时写在任务说明里即可

### Requirement: 三种真类型能力可区分

#### Scenario: 默认 general-purpose 能改代码类工作
- **WHEN** 主 agent 不传类型，或显式选择 `general-purpose`，并要求子 agent 修改某个文件
- **THEN** 子 agent 可以完成修改类工作（在父会话允许的工具范围内）

#### Scenario: Explore 只读探索
- **WHEN** 主 agent 选择 `Explore` 去搜索/定位代码
- **THEN** 子 agent 能完成只读探索并回报结论
- **AND** 它不能修改仓库文件

#### Scenario: Plan 只读出方案
- **WHEN** 主 agent 选择 `Plan` 去规划实现路径
- **THEN** 子 agent 回报规划性结论（步骤/关键文件等），而不是直接改仓库
- **AND** 它不能修改仓库文件

#### Scenario: 主 agent 能知道有哪些类型可选
- **WHEN** 主 agent 准备使用 `agent` 工具
- **THEN** 它能获知可用类型至少包含 `general-purpose`、`Explore`、`Plan`，以及不传类型时默认是 `general-purpose`

### Requirement: 未知类型失败可理解

#### Scenario: 未知类型名
- **WHEN** 主 agent 使用不存在的类型名（例如 `oracle`）新建子 agent
- **THEN** 派发失败
- **AND** 失败信息指出类型未找到，并列出当前可用类型

#### Scenario: 错误大小写
- **WHEN** 主 agent 使用 `explore`（小写）而非 `Explore`
- **THEN** 按未知类型失败（与上一条同类表现）

### Requirement: 后台超时与插话行为保持产品语义

#### Scenario: 前台过久仍自动转后台，但不可调超时参数
- **WHEN** 主 agent 前台派子 agent，且运行超过系统默认前台预算
- **THEN** 该调用转为后台继续跑，主 agent 仍能拿到可继续跟进的标识/输出路径
- **AND** 主 agent 无法通过 `agent` 传参自定义这笔超时

#### Scenario: 运行中仍可向子 agent 插话
- **GIVEN** 某子 agent 仍在运行，主 agent 已持有其 id
- **WHEN** 主 agent 用该 id 发送 follow-up
- **THEN** 消息进入该子 agent，稍后被消费，而不是另起一个无关子 agent

## 范围与非目标

- 在范围：
  - 去掉 `load_skills` / `category` / `timeout_seconds` 传参负担
  - 落地真类型：`general-purpose`（默认）、`Explore`、`Plan`（字面量与大小写对齐 CC）
  - 未知类型失败并列出可用类型（对齐 CC）
  - 保留既有主→子插话、自动转后台（系统默认预算）
- 非目标：
  - 子→主边跑边推（后续强需求，另开 unit）
  - `claude` / Agent View 看板默认会话人格
  - `claude-code-guide` / `statusline-setup` / `verification`
  - CC 的 `model` / `isolation` / `cwd` / teammate（`name`/`team_name`/`mode`）
  - 自定义类型目录（`.claude/agents` 式用户扩展）——本期不做
  - 把续跑拆成独立 `SendMessage` 工具（继续用现有 `agent_id`）
