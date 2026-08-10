# bugfix-413: IM 网页端块级 Markdown（标题/分隔线/部分代码块）不渲染

## Relations

- Closes: #95

## 原始报告

> 见 GitHub issue #95: https://github.com/Mrchen116/nano-multiagent/issues/95

报告人 @Mrchen116（手动测 refactor-406 时发现，与该 unit 无关，是既有缺陷）：

> ## 现象
>
> IM 网页端 agent 回复里的块级 Markdown **不渲染、显示字面量**：
> - 标题 `## 4. 两个产品的使用对比` / `### Coding CLI:` 原样显示 `##` / `###`
> - 分隔线 `---` 原样显示
> - 部分代码围栏 ` ```python ... ``` ` 退化成普通段落（内容挤成一行 prose）
>
> ## 根因
>
> `src/IM/frontend/src/features/chat/v2/components/message-pane.tsx` 用的是**手写 Markdown 渲染器**（非 react-markdown）：
> - `MarkdownContent`（:446）+ `splitMarkdownBlocks`（:489）只覆盖：代码围栏、GFM 表格、有序/无序列表、段落，行内只有 `` `code` `` / `**bold**` / @mention。
> - **没有 heading（`#`~`######`）分支，也没有 horizontal rule（`---` / `***`）分支** → 它们落进末尾的 `return <p>{renderInlineContent(block)}</p>`（:483）当字面量输出。
> - 代码围栏检测 `block.startsWith("```") && block.endsWith("```")`（:457）对未闭合 / 闭合 ``` 不独占一行的情况会失配 → 整块退化成 `<p>`，表现为 prose。
>
> ## 影响
>
> agent 的结构化长回复（带标题/分节/代码块）在 IM 上可读性显著下降。
>
> ## 建议方向（实现留 design 阶段）
>
> - 轻量：扩展手写渲染器补 heading（`<h1>`~`<h6>`）+ hr（`<hr>`）分支，并加固围栏检测（按 fence 行配对而非 startsWith/endsWith）。
> - 彻底：换 `react-markdown` + `remark-gfm`，但需评估 bundle 体积、既有 `.im-md` 样式、@mention 段（`renderInlineContent`）如何作为自定义 renderer 集成。
>
> ## 复现
>
> IM 任一 agent 让它输出含 `##` 标题 + `---` + ```` ```代码块 ```` 的回复即可。

## 澄清记录

- Q1: 验收面锁多宽——只修报告的三类（标题 / 分隔线 / 异常代码围栏），还是「agent 结构化回复整体正确渲染」？
  A(原话): 对，按你的推荐是对的。
  Agent 解读: 验收面锁定「agent 结构化长回复整体正确渲染」，至少覆盖报告三类 + 常见块级（引用块、嵌套列表、行内链接）。这是用户可观察范围声明，不预设 react-markdown 选型（留 design）。

- Q2: 块级渲染的适用范围——保持「只 agent/对方回复渲染块级，用户自己发的消息只走行内」，还是用户消息也要块级渲染？
  A(原话): 对。
  Agent 解读: 保持现状——只 agent/对方回复走块级 Markdown，用户自己消息维持行内渲染不变，不动 @mention 编辑链路。

- Q3: 未闭合代码围栏期望显示成什么？
  A(原话): OK，这个我不是特别 care。那就按行业。常见做法。
  Agent 解读: 按 CommonMark / react-markdown 默认——未闭合围栏视为延伸到消息结尾的代码块，等宽呈现，而非退化成一行 prose。

## 现象与复现

环境：IM 网页端 chat v2（`message-pane.tsx` 的 `MarkdownContent`），渲染 agent / 对方回复。

复现步骤：

1. 在 IM 让任一 agent 输出一段含 `##` / `###` 标题、`---` 分隔线、以及一个代码围栏（尤其是未独占一行收尾或未闭合的围栏）的回复。
2. 观察 agent 气泡的渲染结果。

期望 vs 实际：

| 构造 | 期望 | 实际（现状） |
|---|---|---|
| `## 标题` / `### 标题` | 渲染成 `<h2>`/`<h3>` 层级标题 | 原样显示 `##` / `###` 字面量 |
| `---` / `***` 分隔线 | 渲染成 `<hr>` 横线 | 原样显示 `---` |
| 未闭合 / 收尾不独占一行的代码围栏 | 渲染成代码块 | 退化成普通段落，内容挤成一行 prose |
| 引用块 `>`、嵌套列表、行内链接 `[t](url)` | 正常渲染 | 多数当字面量塞进 `<p>` |

## 影响范围

- **受影响用户**：所有 IM 网页端用户，凡接收 agent 的结构化长回复（带标题/分节/代码块/引用）。
- **严重度**：可读性显著下降，不阻断功能，无数据损坏（纯前端渲染层，消息内容本身完好）。
- **范围边界**：仅 chat v2 的 agent/对方气泡（`MarkdownContent`，:401）；用户自己消息走行内渲染（:400），不在本缺陷范围。
- **非数据问题**：服务端、内核、Gateway 不涉及。

## 根因分析（RCA）

**直接原因**：`src/IM/frontend/src/features/chat/v2/components/message-pane.tsx` 的手写 Markdown 渲染器只覆盖部分块级构造。

- `MarkdownContent`（:456-484）的 block 分支仅：代码围栏 → 表格 → 无序列表 → 有序列表，其余全部落到 `return <p>{renderInlineContent(block)}</p>`（:483）当字面量。**无 heading（`#`~`######`）分支、无 horizontal rule（`---`/`***`）分支**。
- 代码围栏判定 `block.startsWith("```") && block.endsWith("```")`（:457）：`splitMarkdownBlocks`（:489）用 `inFence` toggle 正确切块，已闭合围栏首尾都是 ` ``` ` 行能命中；但**未闭合围栏**收尾时 `inFence` 仍为 true，末尾 `flush()` 产出以 ` ``` ` 开头却不以 ` ``` ` 结尾的块，:457 判 false → 退化成 `<p>`。

**为什么这种错能进来**（系统性根因）：手写渲染器是**靠撞一个补一个增量长出来的**——`16c0141a` 初版只有段落/列表 → `84b378af` 有人撞到表格才补表格 → `b0611588`（bugfix-402）有人撞到代码块才补围栏保留。每一步都只补「当下有人遇到」的那一类构造，从无一份「该支持哪些 Markdown 构造」的契约。标题/分隔线/引用块从一开始就没人显式补过。这种反应式渲染器结构上**永远落后于 agent 下次吐出的语法**，本 issue 只是其必然产物之一。

**原始设计意图追溯 + 必须保住的不变量**：该渲染器属于 IM chat v2 消息渲染（`16c0141a` 引入 MessagePane），意图是「把 agent 回复以可读富文本呈现，并保留 @mention 的特殊渲染」。修复必须保住的不变量：
1. @mention（`renderInlineContent` 的 `<mention>` 解析）在块级内容内（标题/列表/引用/段落里）仍正确渲染。
2. 已支持的表格 / 有序无序列表 / 闭合代码围栏 / `**bold**` / `` `code` `` 渲染不回归。
3. 用户自己消息的行内渲染 + @mention 可视编辑链路（:400）零改动。

**非回归**：标题/分隔线自渲染器诞生（`16c0141a`）起就从未支持，不存在「曾经能用后来坏掉」的引入点，故无 `git blame` 回归定位——属未实现的能力缺口，非回归。

## 验收标准

> bugfix-full 的验收标准描述「修复后用户能观察到什么 / 什么不变」。选型（轻量补分支 vs react-markdown）不在此处，留 design。

### Requirement: agent 回复的块级 Markdown 正确渲染

#### Scenario: 标题渲染成层级标题
- **WHEN** agent 回复含 `## 二级标题` / `### 三级标题`
- **THEN** 气泡内呈现对应层级的标题样式，不出现字面量 `##` / `###`

#### Scenario: 分隔线渲染成横线
- **WHEN** agent 回复含独占一行的 `---` 或 `***`
- **THEN** 气泡内呈现一条水平分隔线，不出现字面量 `---`

#### Scenario: 闭合代码围栏渲染成代码块
- **WHEN** agent 回复含 ```` ```python ... ``` ```` 闭合围栏
- **THEN** 围栏内容以等宽代码块呈现，保留换行，不挤成一行 prose

#### Scenario: 未闭合代码围栏（边界）
- **WHEN** agent 回复以 ` ```python ` 开头但没有收尾 ` ``` `
- **THEN** 按 CommonMark 默认——围栏起始行之后到消息结尾的内容以代码块呈现，而非退化成一行普通文字

#### Scenario: 引用块渲染
- **WHEN** agent 回复含 `> 引用文本`
- **THEN** 气泡内呈现引用块样式，不出现字面量 `>`

#### Scenario: 嵌套列表渲染
- **GIVEN** agent 回复含带缩进的多层无序/有序列表
- **WHEN** 该消息渲染
- **THEN** 子项以缩进层级呈现，不被拍平成同级

#### Scenario: 行内链接渲染
- **WHEN** agent 回复含 `[文本](https://example.com)`
- **THEN** 呈现为可点击链接文本，不出现字面量方括号 / 圆括号语法

#### Scenario: @mention 在块级内容内仍渲染
- **GIVEN** agent 回复在标题 / 列表项 / 段落里含一个 @mention
- **WHEN** 该消息渲染
- **THEN** @mention 仍以既有的高亮样式呈现，不被当字面量或破坏块级结构

#### Scenario: 已支持构造不回归
- **WHEN** agent 回复含 GFM 表格、有序/无序列表、`**bold**`、`` `inline code` ``
- **THEN** 渲染结果与修复前一致（不回归）

#### Scenario: 纯文本回复
- **WHEN** agent 回复是无任何 Markdown 标记的普通文字
- **THEN** 呈现为普通段落，与修复前一致

### Requirement: 用户自己消息渲染不变（不变性）

#### Scenario: 用户消息保持行内渲染
- **GIVEN** 用户在群聊用 @mention 选择器发了一条带 @mention 的消息
- **WHEN** 该消息在自己气泡渲染
- **THEN** 行内渲染 + @mention 高亮与修复前一致，不引入块级 Markdown 解析

## 修复方向

> 高层方案，选型 + 行级实现留 design 阶段拍板。

issue 给出两条候选，design 阶段权衡：

- **轻量**：扩展手写渲染器，补 heading（`<h1>`~`<h6>`）+ hr（`<hr>`）+ 引用块 / 嵌套列表 / 行内链接分支，并加固围栏检测（按 fence 行配对而非 `startsWith/endsWith`）。
- **彻底**：换 `react-markdown` + `remark-gfm`，一次对齐 CommonMark/GFM；需评估 bundle 体积、既有 `.im-md` 样式对齐、@mention 段（`renderInlineContent`）如何作为自定义 renderer / rehype 插件集成。

RCA 的系统性根因（反应式手写渲染器永远落后）指向彻底方案更治本，但 bundle 体积与 @mention 集成成本需 design 量化后定夺。无论选哪条，都须满足上述「必须保住的不变量」。

> **交接给 design 的实现层约束**（澄清时浮现，不进验收标准）：raw HTML 安全（agent 输出里的 `<script>` 等不得执行，react-markdown 默认转义即可，勿引 rehype-raw）；@mention 的 `<mention>` XML 解析须作为自定义节点接入新渲染管线。
