# feat-519：工作区 Claude/Codex Skill 兼容与分组选择

## 原始需求

> 为啥我明明在你的Workspace下的点Claude目录下有一些Skill，为什么这里没展示？就我在IM中的Agent配置里面没有看到有展示这些Skill。

> 那得新建个特性，你按照.claude/skills/下的skill，帮我新建一个unit。兼容的工作区级的 Claude/Codex 目录的skill

> 本次还要额外做一个事情，就是现在的Agent配置那里，要选Skill，要一个一个选。我想一个大类一个大类的选就不行。你要帮我把这个功能设计上，但是你要巧妙的加。不要很丑的，随便加一个大按钮在那。
>
> 不存在，那当然是跳过呀。这都是跟之前一样的吧？之前不已经做了那个全局的兼容吗？

## 澄清记录

- Q1: 这项兼容是否只适用于 PA / IM Agent 的 Workspace，还是也要求 Coding CLI 在项目 Workspace 中发现 `.claude/skills` 和 `.codex/skills`？
  A(原话): `<workspace>/.codex/skills/`，`<workspace>/.claude/skills/`，`~/.claude/skills/` 这3个两边都要支持。
  Agent 解读: PA / IM Agent 与 Coding CLI 都应发现用户指定的三个 Claude/Codex Skill 根目录；既有各自产品命名空间中的目录和已支持目录不因本变更失效。

- Q2: 同一个 Skill 名称同时出现在多个受支持目录时，哪个版本应被发现、在配置页显示并供运行时读取？
  A(原话): 对，是这样
  Agent 解读: 两个产品使用同一优先级：各自产品原生的工作区目录优先，其后依次为 `<workspace>/.claude/skills/`、`<workspace>/.codex/skills/`、各自产品原生的全局目录、`~/.claude/skills/` 与 `~/.codex/skills/`。同名 Skill 只采用该顺序中最先发现的版本。

- Q3: PA 的 IM Agent 配置页发现兼容目录中的 Skill 后，是否应与现有 Workspace Skill 一样显示为可选项，由用户勾选后在该 Agent 的下一轮新回复生效，而不是自动为所有已有 Agent 启用？
  A(原话): 对
  Agent 解读: PA 在对应 Agent 的配置页列出来自兼容工作区目录的 Skill；用户显式选择后，Agent 的下一轮新回复才可使用。新增文件不静默扩大已有 Agent 的已保存 skills。Coding CLI 沿用既有会话发现语义，在启动该 Workspace 的新会话时提供可见候选。

- Q4: 当某个兼容目录不存在、为空，或其中有不符合 Skill 格式的文件时，期望如何表现？
  A(原话): 不存在，那当然是跳过呀。这都是跟之前一样的吧？之前不已经做了那个全局的兼容吗？
  Agent 解读: 新增的兼容根目录沿用既有全局兼容来源的发现与容错语义；可选目录不存在或为空时跳过，不影响其他有效来源、PA 配置页、Coding CLI 启动或已有会话。无效条目继续依既有 Skill 发现规则处理，不为新增路径引入额外失败。

- Q5: 批量选择是否按页面已有的全局、本地和兼容来源分组执行，并在分组标题旁提供紧凑的全选、部分选中和取消选择控制？
  A(原话): 这个设计阶段来定吧，我不做这么细的管控。最后你设计完之后给我review的时候，我直接看你的设计，再给点子。
  Agent 解读: 本 unit 必须让用户能按显示的 Skill 分组批量选择，同时保留单项选择；具体控件、状态反馈、文案和视觉处理由设计阶段提出。设计方案须融入既有 Agent 配置体验，不以突兀的大按钮破坏页面，并在 Gate 2 前交用户评审和反馈。

## 用户场景

开发者在同一项目中既会通过 PA / Web IM 配置 Agent，也会在终端中通过 Coding CLI 工作。项目已随代码携带 Claude 或 Codex 格式的 Skill，不应为了让不同入口发现它们而复制为 PA 或 Coding CLI 私有目录。

当开发者打开某个 PA Agent 的配置时，项目 Workspace 中的 Claude/Codex Skill 应与既有 Skill 一起成为可理解、可选择的候选；保存选择后，Agent 在下一轮新回复中使用这份选择。项目增加新 Skill 不能反过来静默改变已有 Agent 已保存的能力范围。

当开发者从同一项目启动 Coding CLI 时，CLI 也应发现同一批兼容 Skill。若项目级 Skill 与用户主目录或产品原生目录中存在同名版本，开发者需要可预测地知道项目哪个版本生效：越贴近当前 Workspace 的来源覆盖全局来源，而产品原生目录保持对兼容目录的既有优先级。

PA 的配置页当前按来源分组显示一系列单独的 Skill。Skill 较多时，开发者应能以一个分组为单位完成选择或取消选择，仍可再调整单个 Skill。这个能力应自然地融入已有分组和标签布局，而不是在页面中另加突兀、笨重的批量操作区。

项目不一定拥有全部兼容目录；目录不存在、为空或不含有效 Skill 时，开发者仍应正常打开 PA 配置、开始 Coding CLI 会话和使用来自其他目录的 Skill。

## 验收标准

### Requirement: PA 与 Coding CLI 一致发现指定的 Claude/Codex 兼容根目录

#### Scenario: PA 配置页提供工作区与用户主目录的兼容 Skill
- **GIVEN** 某 PA Agent 的 Workspace 或当前用户主目录中的下列任一路径含有有效 Skill：`<workspace>/.claude/skills/`、`<workspace>/.codex/skills/`、`~/.claude/skills/`
- **WHEN** 开发者打开该 Agent 的 Skill 配置
- **THEN** 该有效 Skill 成为该 Agent 可选择的候选
- **AND** 开发者能保留或调整既有选择并成功保存

#### Scenario: Coding CLI 在同一项目中提供兼容 Skill 候选
- **GIVEN** 当前项目 Workspace 或当前用户主目录中的下列任一路径含有有效 Skill：`<workspace>/.claude/skills/`、`<workspace>/.codex/skills/`、`~/.claude/skills/`
- **WHEN** 开发者从该 Workspace 启动 Coding CLI 会话
- **THEN** 该有效 Skill 成为该会话可见的 Skill 候选

#### Scenario: 原生与既有兼容来源保持可用
- **GIVEN** PA 或 Coding CLI 已在各自原生 Workspace 或全局 Skill 目录中使用 Skill，或在已支持的 `~/.codex/skills/` 中使用 Skill
- **WHEN** 升级到支持新增兼容根目录的版本后重新打开配置或启动会话
- **THEN** 这些既有来源中的有效 Skill 仍按既有方式可发现和使用

### Requirement: 同名 Skill 按统一、可预测的来源优先级解析

#### Scenario: PA 中同名 Skill 选择最优先来源
- **GIVEN** 同名 Skill 同时存在于多个 PA 受支持来源
- **WHEN** 开发者在该 Workspace 查看或选择该 Skill，并在后续新回复中使用它
- **THEN** 产品采用以下最先命中的版本：`<workspace>/.nanoassistant/skills/`、`<workspace>/.claude/skills/`、`<workspace>/.codex/skills/`、`~/.nanoassistant/skills/`、`~/.claude/skills/`、`~/.codex/skills/`
- **AND** 配置页和实际新回复使用同一版本，而不把同名的低优先级副本作为另一个可选项

#### Scenario: Coding CLI 中同名 Skill 选择最优先来源
- **GIVEN** 同名 Skill 同时存在于多个 Coding CLI 受支持来源
- **WHEN** 开发者从该 Workspace 开始会话并使用该 Skill
- **THEN** 产品采用以下最先命中的版本：`<workspace>/.nanocode/skills/`、`<workspace>/.claude/skills/`、`<workspace>/.codex/skills/`、`~/.nanocode/skills/`、`~/.claude/skills/`、`~/.codex/skills/`

### Requirement: PA 配置显式选择兼容 Skill 后才在下一轮生效

#### Scenario: 新发现的兼容 Skill 不静默扩大已保存 Agent 的能力
- **GIVEN** 某已有 PA Agent 已保存显式 Skill 选择，且其 Workspace 或用户主目录中新出现一个兼容 Skill
- **WHEN** 开发者重新打开该 Agent 的配置
- **THEN** 该 Skill 可供开发者显式选择
- **AND** Agent 已保存的选择不因发现该文件而自动增加

#### Scenario: 开发者选择兼容 Skill 后继续既有聊天
- **GIVEN** 某 PA Agent 在配置页中尚未选择一个可见的兼容 Skill，且该 Agent 已有聊天历史
- **WHEN** 开发者选择该 Skill、成功保存配置并回到该聊天发送新消息
- **THEN** 下一轮新回复可使用该 Skill
- **AND** 既有聊天历史保持可继续引用

### Requirement: PA 配置支持按已显示的 Skill 分组批量选择

#### Scenario: 开发者以一个分组为单位调整 Skill 选择
- **GIVEN** Agent 配置页的一个已显示 Skill 分组包含多个可选 Skill
- **WHEN** 开发者对该分组执行批量选择或批量取消选择
- **THEN** 该分组内的 Skill 选择作为同一项表单草稿更新
- **AND** 开发者仍可在保存前继续调整任一单独 Skill

#### Scenario: 分组状态如实反映单项选择
- **GIVEN** 开发者已选择一个分组中的部分、全部或没有 Skill
- **WHEN** 开发者查看该分组并继续调整单项选择
- **THEN** 页面明确反映该分组的实际选择状态
- **AND** 批量能力与单项选择不会让用户误以为未保存或未选中的 Skill 已生效

#### Scenario: 批量选择自然融入既有配置体验
- **GIVEN** 开发者在桌面或移动布局中打开 Agent 的 Skill 配置
- **WHEN** 页面提供按分组批量选择的能力
- **THEN** 该能力与现有分组和单个 Skill 选择一起呈现，保持页面信息层级清晰
- **AND** 页面不出现脱离 Skill 分组、突兀或笨重的独立批量操作区

### Requirement: 可选兼容目录缺失时保持正常使用

#### Scenario: 工作区不含某个兼容目录
- **GIVEN** 当前 Workspace 未创建 `.claude/skills/` 或 `.codex/skills/`，或用户主目录未创建 `.claude/skills/`
- **WHEN** 开发者打开 PA Agent 配置或从该 Workspace 启动 Coding CLI
- **THEN** 操作正常完成，不要求创建缺失目录
- **AND** 其他受支持来源中的有效 Skill 仍可发现和使用

#### Scenario: 兼容目录没有有效 Skill
- **GIVEN** 某个兼容目录为空或不含可发现的有效 Skill
- **WHEN** 开发者打开 PA Agent 配置或从该 Workspace 启动 Coding CLI
- **THEN** 产品继续提供其他有效来源中的 Skill
- **AND** 不把该可选目录状态误报为配置或会话启动失败

## 范围与非目标

- 在范围：PA / IM Agent 与 Coding CLI 对 `<workspace>/.claude/skills/`、`<workspace>/.codex/skills/`、`~/.claude/skills/` 的一致 Skill 发现。
- 在范围：两个产品的同名 Skill 来源优先级；PA 配置页候选与实际新回复使用同一解析结果。
- 在范围：PA Agent 配置页按现有显示分组批量选择 Skill，同时保留单项选择和既有保存/下一轮生效语义。
- 在范围：缺失、空或无有效 Skill 的新增兼容目录沿用现有可选来源的容错行为。
- 非目标：迁移、复制、改写或同步任一目录中的 Skill 文件。
- 非目标：改变 Skill 文件格式、工具权限、`skill_view` 行为，或让兼容目录中的 Skill 绕过 Agent 已保存的显式选择。
- 非目标：发现 Claude/Codex 的其他配置、命令、插件、工具、hooks、memory 或不在三个指定路径内的资源。
- 非目标：在首文档锁定批量选择控件、文案、布局或视觉样式；设计阶段负责提出可评审方案，用户将在设计评审时反馈。
