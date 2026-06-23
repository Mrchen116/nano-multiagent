# feat-428: 目录级项目指令自动加载（nested project instructions）

## Relations

- Related: 现有 `MemoryStore`（MEMORY.md / USER.md 会话级注入）—— 不同机制，并存
- Related: feat-379（曾从 core prompt 主动移除 CLAUDE.md 提及，决策10/M4）—— 本期"只认 AGENTS.md、不认 CLAUDE.md"沿用其取向

## 原始需求

> 我觉得需要做，两个产品都需要，所以做成一个可选feature，放到core中吧，而且需要不单单本workspace能带上。读workspace外的文件也应该带上，但是带上的方式不同。workspace内是直接把文件注入进去了。外呢，我觉得应该把路径注入进去，提醒agent如果有必要就读，这样平衡浪费和需求。举个例子，PA的agent有自己的固有workspace，但是往往他也在某个代码仓去工作，如果不读他的AGENTS.md，就不了解这个代码仓的上下文。

> （承接前文对话）参考 CC 的 nested_memory 设计：agent 读某个文件时，CC 顺着该文件目录链往上，把沿途的 CLAUDE.md/AGENTS.md 自动加载进上下文；有 workspace 边界闸（工作区外的文件不加载，除非 /add-dir）；有跨会话/跨注入去重。我们项目现状：core 只有 MemoryStore（固定两文件、会话级一次性注入），没有任何目录级指令自动加载机制。

## 澄清记录

- Q1: 触发动作只盯 `read` 工具读到的文件，还是其它接触文件的动作（bash cat/grep、edit/write）也算？
  A(原话): 对齐CC
  Agent 解读: 只有 `read` 工具读取文件时触发目录链回溯；bash 路径、edit/write 不单独作为触发点（CC 仅在 FileRead 时登记 trigger）。

- Q2: "workspace 内 vs 外"的边界以什么为准？是否支持 add-dir（显式追加目录算内）？
  A(原话): 本期不做 add-dir
  Agent 解读: 边界 = 该 agent 自己的工作区（产品语义；具体锚 workspace_root 还是 repo_root 由 design 定）。本期只做"单一 workspace 内/外"二分，add-dir（显式追加额外目录算内）列为非目标。

- Q3: workspace "外"那条路径注入给 agent 时长什么样？（裸路径 vs 带提示）找到多份怎么办？回溯上界？
  A(原话): 对，类似这种，用英文。找到多个就都列。"外"的回溯也有上界，上界我觉得应该是不属于任何git repo就停。
  Agent 解读: 外部命中走"路径 + 英文提示"模式（不灌全文），提示点明这是哪个项目的项目说明、按需自行 read。提示文案用英文。回溯范围 = 从被读文件目录逐级上行直到**最外层** git 仓根（某级不属于任何 git 仓即停）；范围内**每一级**都找 AGENTS.md，多份全列。"最外层"覆盖嵌套仓（e/y 都是仓且 e 最外 → e~z 各级都找，不是只看最近的 y）。不属于任何 git 仓 → 不给提示。
  （后续澄清修正：原"该外部文件所属 git repo 工作树内"措辞会被读成最近仓，已改为最外层 + 逐级。）

- Q4: 哪些文件名算"项目指令文件"？（AGENTS.md + CLAUDE.md，还是只 AGENTS.md）
  A(原话): （承接下条）只认AGENTS.md
  Agent 解读: 只识别 `AGENTS.md`（本仓事实标准）；不认 CLAUDE.md、不认 README/.cursorrules。

- Q5: grounding 发现 system prompt 当前完全不注入任何项目指令文件（agent 只有 operator 手填的 custom System Prompt + MEMORY/USER）。本 unit 是否扩张范围补上基线注入？
  A(原话): 那，本unit的范围要增大点，要在系统提示词中注入AGENTS.md，这个不属于可选feature，这个是默认的。另外，只认AGENTS.md。然后read的时候nested_memory是可选的内核feature。但是两个产品都默认带上，如果后面效果不好，我可以保留关了的空间
  Agent 解读: 本 unit 含两个机制——
    机制 A（基线，默认恒开，非可选）：会话启动时把 agent 自己 workspace 的 AGENTS.md 注入 system prompt。这是从无到有的底座，不提供关闭开关。
    机制 B（nested_memory，可选内核 feature）：read 文件时按 Q1–Q4 规则做目录链回溯加载/提示。它是一个可在内核层开关的 feature，但两个产品（Coding CLI + PA）出厂默认开启；保留"日后效果不好可关掉"的配置余地。
    两机制都只认 AGENTS.md。

- Q6: 同一份 AGENTS.md 被多条路径命中时是否重复注入？
  A(原话): 对，和CC对齐。
  Agent 解读: 全局去重，每份指令一次会话只生效一次。三种重叠都去重：① 机制 A 已注入的 workspace 根 AGENTS.md，机制 B 回溯再次命中时跳过；② 同一份 AGENTS.md 被多次 read 命中只在首次注入；③ 同一外部 AGENTS.md 的路径提示一次会话只提醒一次。

## 用户场景

今天系统里**没有任何机制**让"项目指令文件"（AGENTS.md）进入 agent 的上下文：system prompt 不注入、启动不读、read 时也不带。一个 agent 想知道某个项目的约定，唯一办法是 operator 把 AGENTS.md 内容手动复制粘贴进该 agent 配置里的 System Prompt 框。本 unit 从无到有补上这件事，分两层：

**机制 A —— 工作区项目说明的基线注入（默认恒开）。**
两个产品下场景一致：Coding CLI 用户打开一个项目开始干活；PA 的 agent 有自己固有的 workspace。两种情况下，agent 一启动就应当"自带"它所在工作区的项目说明——就像新人入职先读到部门手册。于是会话启动时，系统自动把该 agent 工作区根目录的 `AGENTS.md` 注入 system prompt。agent 从第一句话起就了解这个工作区的约定，无需 operator 手填、也无需 agent 自己先去 read。若工作区没有 `AGENTS.md`，则什么都不注入，照常启动。

**机制 B —— 顺着 read 就近带上项目说明（nested_memory，可选，两产品默认开）。**
真实工作里 agent 会读到工作区各处、甚至工作区以外的文件。

- *工作区内*：agent read 了 `backend/api/user.py`，而 `backend/api/` 下有一份子目录级 `AGENTS.md` 写着这块的接口约定。系统顺着这个文件的目录链往上，把沿途的 `AGENTS.md` 内容自动带进上下文，让 agent 改这块代码时就知道这块的规矩。若已被机制 A 注入过（工作区根那份），不重复带。

- *工作区外*：这正是 PA agent 的高频场景——agent 有自己固有 workspace，但它常跑去某个**代码仓**干活，那个仓在它 workspace 之外。agent read 了该仓里的一个文件，系统发现这个文件属于工作区外的 git 项目、链上有 `AGENTS.md`。这时**不灌全文**（省 token），而是给 agent 一条英文提示：「你刚读的文件在工作区外的项目 X 下，该项目有项目说明 `<path>`，需要了解其约定可自行 read」。agent 据此自行判断要不要读。

  扫描范围 = 从被读文件的目录逐级上行，**直到最外层 git 仓根为止**（不属于任何 git 仓的那一级即停，再往上不找）；这段范围内**每一级**都找 `AGENTS.md`，找到多份就都列。"最外层"覆盖嵌套仓：若读 `/q/w/e/x/y/z/a.py`，e、y 都是 git 仓且 e 在最外层，则 e、x、y、z 各级都要找 AGENTS.md（不是只看最近的 y 那个仓）。文件不属于任何 git 仓（如系统配置文件）→ 不给任何提示。

去重贯穿全程：每份 `AGENTS.md`（或每条外部路径提示）在一次会话里只生效一次，不反复刷、不重复占上下文。

机制 B 作为内核可选 feature 存在，两个产品出厂默认开启；若日后实测效果不好，保留在配置层关掉它的余地（关掉后机制 A 仍然生效，因为 A 是非可选基线）。

## 验收标准

### Requirement: 启动时把工作区 AGENTS.md 注入 system prompt（机制 A，默认恒开）

#### Scenario: 工作区根有 AGENTS.md
- **GIVEN** agent 的工作区根目录下存在 `AGENTS.md`
- **WHEN** 该 agent 开启一个新会话
- **THEN** 无需 operator 手填、也无需 agent 主动 read，agent 即已掌握该 `AGENTS.md` 的内容（可通过让 agent 复述/应用其中的约定来验证）

#### Scenario: 工作区根无 AGENTS.md（空态）
- **GIVEN** agent 的工作区根目录下不存在 `AGENTS.md`
- **WHEN** 该 agent 开启一个新会话
- **THEN** 不注入任何项目说明，会话照常启动，无报错

#### Scenario: 两个产品都生效
- **WHEN** 分别在 Coding CLI 和 PA 下开启带 `AGENTS.md` 工作区的 agent 会话
- **THEN** 两个产品下 agent 都自带各自工作区的 `AGENTS.md`

#### Scenario: 工作区根 AGENTS.md 含 @import
- **GIVEN** 工作区根 `AGENTS.md` 内有 `@./sub.md` 形式的转引，`sub.md` 存在
- **WHEN** 该 agent 开启新会话
- **THEN** agent 同时掌握 `AGENTS.md` 与被转引 `sub.md` 的内容（可通过复述被转引文件中的约定验证）

#### Scenario: 会话运行中 AGENTS.md 被改（压缩窗口内冻结，压缩边界刷新）
- **GIVEN** 一个会话已启动、已注入工作区根 `AGENTS.md`（快照 X）
- **WHEN** 会话运行过程中磁盘上的该 `AGENTS.md` 被改成 Y，且**尚未发生上下文压缩**，在同一会话内继续对话
- **THEN** 当前会话仍按快照 X 行动，不反映 Y（压缩窗口内冻结，保前缀缓存）
- **AND** 一旦发生上下文压缩（或开启新会话），下一轮重读盘，注入更新后的 Y

### Requirement: read 工作区内文件时就近带上 AGENTS.md 内容（机制 B·内）

#### Scenario: 读到的文件目录链上有子目录级 AGENTS.md
- **GIVEN** nested_memory 处于默认开启状态，且工作区内某子目录下有 `AGENTS.md`
- **WHEN** agent 用 read 读取该子目录（或更深层）下的某个文件
- **THEN** agent 的上下文随即带上该子目录 `AGENTS.md` 的内容（可由 agent 引用其中约定验证）

#### Scenario: 读到的文件目录链上没有 AGENTS.md（空态）
- **WHEN** agent read 的文件，其目录链上不存在任何 `AGENTS.md`
- **THEN** 不带入任何内容，read 结果照常返回

#### Scenario: 命中的是已注入过的工作区根 AGENTS.md（去重）
- **GIVEN** 工作区根 `AGENTS.md` 已被机制 A 注入进 system prompt
- **WHEN** agent read 工作区内文件、回溯命中这同一份根 `AGENTS.md`
- **THEN** 不重复注入

#### Scenario: 注入后该 AGENTS.md 被改、同会话再 read（压缩窗口内冻结，压缩边界刷新）
- **GIVEN** 某子目录 `AGENTS.md`（内容 X）已在本会话因一次 read 被注入过、且**尚未发生上下文压缩**
- **WHEN** 磁盘上它被改成 Y，且同一会话内再次 read 触发命中它
- **THEN** 不再注入（按路径去重），上下文里保留的仍是首次注入的 X，不更新为 Y
- **AND** 一旦发生上下文压缩，去重记录清空；压缩后再 read 命中该文件时重新注入最新的 Y

### Requirement: read 工作区外文件时注入路径提示而非全文（机制 B·外）

#### Scenario: 读到工作区外某 git 项目内的文件，该项目有 AGENTS.md
- **GIVEN** nested_memory 默认开启，agent read 的文件位于其工作区之外、但属于某个 git 仓，从该文件目录到最外层 git 仓根之间有一份或多份 `AGENTS.md`
- **WHEN** agent read 该文件
- **THEN** agent 收到一条英文提示，点明该文件所属的工作区外项目及其 `AGENTS.md` 路径，并提示可按需自行 read
- **AND** 从文件目录到最外层 git 仓根逐级找到的多份 `AGENTS.md`，路径全部列出（含嵌套仓的外层那份）
- **AND** 提示中不包含 `AGENTS.md` 的正文内容

#### Scenario: 读到不属于任何 git 仓的工作区外文件（边界）
- **WHEN** agent read 的文件位于工作区外、且不属于任何 git 仓（例如系统配置文件）
- **THEN** 不给出任何路径提示

#### Scenario: 同一外部 AGENTS.md 被多次命中（去重）
- **WHEN** agent 在同一会话内多次 read 命中同一份外部 `AGENTS.md`
- **THEN** 该路径提示只出现一次

### Requirement: nested_memory 可在配置层关闭，关闭后机制 A 不受影响

#### Scenario: 关闭 nested_memory 后 read 不再触发目录加载/提示
- **GIVEN** 通过配置关闭了 nested_memory（机制 B）
- **WHEN** agent read 工作区内/外的文件
- **THEN** 不再带入就近 `AGENTS.md` 内容、也不再给出外部路径提示
- **AND** 启动时工作区根 `AGENTS.md` 仍照常注入 system prompt（机制 A 不随之关闭）

## 范围与非目标

- 在范围：
  - 机制 A：会话启动时把 agent 工作区根 `AGENTS.md` 注入 system prompt（默认恒开，无开关）。
  - 机制 B：read 触发的目录链回溯——工作区内注入内容、工作区外注入英文路径提示（外部以最外层 git repo 为界、逐级），全局去重。作为可选内核 feature，两产品默认开。
  - 仅识别文件名 `AGENTS.md`。
  - 支持 `AGENTS.md` 内的 `@import` 转引展开（对齐 CC：`@path`，最深 5 层、防环、不存在静默忽略）；仅在"注入内容"场景生效（机制 A、机制 B 工作区内），外部路径提示不展开。
- 非目标：
  - 不认 `CLAUDE.md`、`README.md`、`.cursorrules` 等其它文件名（CLAUDE.md 曾被 core 主动剔除，本期不恢复）。
  - 不做 `/add-dir` 式"显式追加目录算工作区内"。
  - read 之外的触发点不做：bash 里 `cat`/`grep` 命中的路径、`edit`/`write` 不单独触发回溯。
  - 工作区外不灌全文（仅路径提示），本期不提供"外部也注入全文"的模式。
  - 不做指令文件名可配置化。
  - AGENTS.md 不硬截断（对齐 CC）。
  - 不替代或改动现有 `MemoryStore`（MEMORY.md / USER.md）机制，二者并存。
