# feat-383: 系统提示词预览反映 UI 实时配置

## Relations

- Related: feat-379 （引入 `/v1/prompt-preview` 的 unit，是本 unit 直接改进的对象）

## 原始需求

> http://127.0.0.1:8011/settings/agents/code_review 你能看到预览系统提示词预览到啥吗

> 这不是问题，问题是 `## Available Tools - read: ` ... 冒号后面没东西，也没占位符，`Current date and time:` `Current working directory:` 这个也是。代码仓里看看实际上给 agent 的是啥？还是就是这样？无论 agent 实际用的啥，这对用户感官都很奇怪

> 预览展示的目的是，根据用户实时在界面上的配置，展示当前配置上的提示词。以这个为目的，你思考下应该如何呈现

> 前两者对。第三个，时间 "preview 模式下整行删掉"，不合适啊，这就不真实了。应该是放个占位 `<>`。对，Skills section 也要看有没有真实呈现配置。

> 添加 unit spec。a. 文案你设置。通常 workspace 不用空啊。按前面讨论"填真实 workspace_root"啊。 b. 当然要。用户写了 Agent ID 就可以有了吧，在没有的时候才是占位。c. 不截断。真实是放啥就是啥

> 预览展示的目的是，根据用户实时在界面上的配置，展示当前配置上的提示词。以这个为目的。这个要强调到 spec 中

## 澄清记录

- Q1: 现状是什么？打开 `/settings/agents/<id>` 的 "Preview full system prompt"，看到哪些字段是空的、误导的？
  A(原话):
    > 问题是 `## Available Tools - read:` ... 冒号后面没东西，也没占位符，`Current date and time:` `Current working directory:` 这个也是。
  Agent 解读: 三类字段表现异常——工具列表每行只有 `名称:` 后面空白；时间和工作目录两行只剩标签后空白。`Skills` 段同类问题（不响应 UI 勾选），后续 Q4 确认。

- Q2: 这个预览存在的意义是什么？它要回答用户的什么问题？
  A(原话):
    > 预览展示的目的是，根据用户实时在界面上的配置，展示当前配置上的提示词。以这个为目的，你思考下应该如何呈现
    > 预览展示的目的是，根据用户实时在界面上的配置，展示当前配置上的提示词。以这个为目的。这个要强调到 spec 中
  Agent 解读: **核心不变量**——预览是 UI 配置的实时投影。用户在 UI 上勾掉/勾上任何配置项（工具、技能、特性开关、custom prompt、模型），预览必须即时反映；运行时才注入的、UI 不可控的字段，须以明确占位符呈现，让用户区分"我配置的"与"运行时填的"。

- Q3: 工具列表、工作目录、技能段——这些是否归类为"UI 可控的配置"？时间字段呢？
  A(原话):
    > 前两者对。第三个，时间 "preview 模式下整行删掉"，不合适啊，这就不真实了。应该是放个占位 `<>`。对，Skills section 也要看有没有真实呈现配置。
  Agent 解读:
    - 工具描述、Skills 段、workspace 路径 → UI 可控（前两者直接对应 UI 勾选，workspace 由 agent profile 决定），预览须填**真实**内容。
    - 时间 → UI 不可控、运行时才注入，但不能整行删——删了用户不知道运行时会注入这个；要保留行但用占位符标明。

- Q4: agent-create 页面（agent 还未创建，workspace 路径尚未存在）怎么处理？
  A(原话):
    > b. 当然要。用户写了 Agent ID 就可以有了吧，在没有的时候才是占位。
  Agent 解读: 新建流程也走同样的预览语义。用户已填 Agent ID → 前端基于 ID 推导出真实 workspace 路径并预览；Agent ID 还未填 → 显示占位符。

- Q5: 工具描述源自 tool registry，真实描述可能很长（数百字符）。要不要在预览端截短？
  A(原话):
    > c. 不截断。真实是放啥就是啥
  Agent 解读: 预览原样展示真实 description，不做截断/摘要。"展示真实配置"的语义要求所见即所得。

- Q6: 占位符文案谁定？
  A(原话):
    > a. 文案你设置。
  Agent 解读: 由作者拟定。采用中文 + 尖括号标识"运行时注入"，保证用户一眼能看出"这里运行时才会填"：
    - 时间字段占位：`<运行时注入：当前时间>`
    - workspace 路径占位（仅 agent-create 且未填 Agent ID 时用）：`<运行时注入：workspace 路径>`

- Q7: 工具 id 在内核工具注册表中查不到、或 skill id 在 workspace 中解析不到，预览怎么处理？
  A(原话):
    > <未注册工具> 为啥有这个？没注册最后不就是没有工具吗，用户有可能希望不要任何工具啊
  Agent 解读: **注册表 / skill 解析器是 source of truth**——id 不存在意味着运行时本来也不会暴露给 agent，预览必须与运行时一致：**静默跳过**这些 id，不在预览中出现。"未注册" 不是预览要承担的诊断职责。用户取消所有工具勾选 → tool_ids 为空 → Available Tools 段为空（或不出现），这是合法的"我不想要任何工具"配置，预览自然反映即可。

## 用户场景

**主角**：在 IM 配置页配置 agent 的运营者（自己机器上的"自己"，或多 agent 多用户场景下的某用户）。

**触发**：在 `http://<im-host>:<port>/settings/agents/<agent_id>` 或 agent 创建页，展开 "▸ Preview full system prompt" 折叠块。

**叙事**：
- 用户在 UI 上调整 Tool Allowlist、Skills、Features 开关、Custom Instructions、Default Model 等配置；
- 展开预览，期望看到"假如我现在保存，agent 实际收到的系统提示词大致长什么样"；
- 预览中：
  - **由我控制的部分**应当真实呈现：勾上 `read` 工具，预览的 `## Available Tools` 里就要看到 `- read: <read 工具的真实 description>`；勾上某个 skill，Skills 段就要列出该 skill 的真实条目；这个 agent 的 workspace 路径就要显示真实路径；
  - **运行时才注入的部分**应当明确标记：当前时间不可能在用户配置时就有"正确值"，但行不能消失——以 `<运行时注入：当前时间>` 形式保留，让用户理解"这里运行时会填进真值"；
- 用户拖动勾选、改写 Custom Instructions，预览即时刷新（已有的 600ms 防抖逻辑保留）；
- agent-create 页同理：用户在表单顶部填了 Agent ID，下面预览里的工作目录路径就该跟着 Agent ID 推导出真实路径；Agent ID 还没填，工作目录显示占位。

**反例（要消除）**：用户看到 `- read:` 后面光秃秃一片空白，以为"agent 真的没拿到这个工具的说明"——产生对配置/系统的误判，丧失对预览的信任。

## 验收标准

### Requirement: 预览忠实反映用户在 UI 上的当前配置

预览是 UI 配置的实时投影。任何在配置面板上可见可调的项，其对系统提示词的影响必须在预览中被看到。

#### Scenario: 用户切换 Tool Allowlist 勾选
- **GIVEN** 用户在 agent 详情页打开了 "Preview full system prompt"
- **WHEN** 用户在 Tool Allowlist 区勾选某个工具（例如 `read`）
- **THEN** 预览的 `## Available Tools` 段中出现一行 `- read: <read 的真实说明文本>`
- **AND** 取消勾选后该行消失

#### Scenario: 用户切换 Skill 勾选
- **GIVEN** 用户在 agent 详情页打开了 "Preview full system prompt"
- **WHEN** 用户在 Skills 区勾选某个技能
- **THEN** 预览的技能段中出现该技能的真实条目（名称 + 真实描述）
- **AND** 取消勾选后该条目消失

#### Scenario: 用户修改 Custom Instructions
- **WHEN** 用户在 Custom Instructions 输入框写入或清空内容
- **THEN** 预览中对应段落在去抖窗口结束后跟随更新

### Requirement: 工具列表显示真实描述，不截断

#### Scenario: 已勾选的工具在预览中显示真实说明文本
- **GIVEN** 工具 `read` 在 agent 内核工具注册表中已注册并有说明文本
- **WHEN** 用户勾选 `read` 后查看预览
- **THEN** `## Available Tools` 段中 `- read:` 之后展示完整的真实说明文本（与运行时实际发给 agent 的内容一致），不进行截断、摘要、加省略号

#### Scenario: 用户未勾选任何工具
- **WHEN** 用户取消所有 Tool Allowlist 勾选后查看预览
- **THEN** `## Available Tools` 段为空（或不出现），不显示任何工具行

#### Scenario: 配置中存在内核未注册的工具 id
- **GIVEN** 配置中保留了某个工具 id，但该 id 在当前内核工具注册表中已不存在（例如内核版本变更后旧配置遗留）
- **WHEN** 用户查看预览
- **THEN** 该 id 不出现在预览中（与运行时行为一致——运行时本来也不会将不存在的工具暴露给 agent）

### Requirement: 工作目录显示真实 workspace 路径或明确占位

#### Scenario: 已存在 agent 的预览显示真实路径
- **GIVEN** 用户正在编辑一个已存在 agent 的配置
- **WHEN** 用户查看预览
- **THEN** "Current working directory:" 之后显示该 agent 的真实 workspace 路径（与右下角 "Workspace Root" 字段显示的一致）

#### Scenario: agent-create 页已填 Agent ID
- **GIVEN** 用户在 agent-create 页面
- **WHEN** 用户已填入 Agent ID，查看预览
- **THEN** "Current working directory:" 之后显示基于该 Agent ID 推导出的真实 workspace 路径

#### Scenario: agent-create 页未填 Agent ID
- **GIVEN** 用户在 agent-create 页面
- **WHEN** 用户尚未填入 Agent ID，查看预览
- **THEN** "Current working directory:" 之后显示占位 `<运行时注入：workspace 路径>`

### Requirement: 运行时才注入的字段以占位符明确呈现

#### Scenario: 时间字段在预览中显示占位
- **WHEN** 用户查看预览
- **THEN** "Current date and time:" 之后显示占位 `<运行时注入：当前时间>`（不留空白、不删除整行）

### Requirement: Skills 段反映当前勾选的技能集合

#### Scenario: 勾选了若干技能
- **GIVEN** 当前 agent 的工作空间下存在被勾选技能对应的 skill 文件
- **WHEN** 用户查看预览
- **THEN** 预览中出现 Skills 段，按勾选集合列出每个技能的名称与真实描述

#### Scenario: 未勾选任何技能
- **WHEN** 用户取消所有 Skill 勾选后查看预览
- **THEN** Skills 段不出现，或显示明确的"无技能"占位（不是悬空标题）

#### Scenario: 配置中存在 workspace 下解析不到的 skill id
- **GIVEN** 配置包含某个 skill id 但当前 agent workspace 中无对应 skill 文件
- **WHEN** 用户查看预览
- **THEN** 该 id 不出现在预览中（与运行时行为一致——运行时本来也加载不了无对应文件的 skill）

## 范围与非目标

**在范围**：
- agent 详情页 (`/settings/agents/<id>`) 的 "Preview full system prompt" 视图
- agent 创建页的 "Preview full system prompt" 视图
- 上述视图相关的端到端链路：IM 前端 → IM HTTP → Gateway WS → kernel client → agent `/v1/prompt-preview`
- 占位符文案与显示规则
- 工具描述、技能描述、workspace 路径的真实化呈现

**非目标**：
- 不改变 agent 真实运行时（非预览路径）的系统提示词拼装逻辑——本 unit 只调整"预览端"的呈现，运行时 agent 仍收到完整真实的 datetime / cwd / tool description / skills
- 不调整提示词模板本身的文案、段落顺序、字段命名
- 不重新设计 Preview 入口或交互（仍是 "▸ Preview full system prompt" 折叠块 + 600ms 防抖刷新）
- 不引入新的 UI 配置项（不新增 toggle、不新增表单字段）
- 不改变缓存策略 / cache_safe 段过滤规则——预览仍仅展示 cache-stable 段落
- 不优化预览性能 / 不引入额外的缓存层
