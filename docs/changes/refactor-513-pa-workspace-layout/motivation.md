# refactor-513: 产品化 workspace 与全局持久化目录

## Relations

无。

## 原始诉求

> 当前PA会在workspace中存哪些东西，我考虑把PA的某个agent的workspace放在某个代码仓根目录，然后开展这个代码仓的工作是否合适

> 我觉得应该规整一下目录了。有nanoassistant还搞个nano，很奇怪，而且chat_history是啥，也应该放在nanoassistant中吧？

> 我觉得本unit要把内核改为默认用.nano，但是产品可传其他目录名，比如
>
> ```
> .nanoassistant
>
> 一旦传了的话，那就是按照传进来的这个。然后chat history也放进去。CLI那边也要改。理解吗？现在可以跟我进行需求澄清。
> ```

> 那我觉得应该做的是PA首次启动的时候把.nano/tools、.nano/hooks 这类共享扩展拷贝到自己那里，然后不删除他原本的，CLI首次启动的时候则放到.nanocode里

> 全局的还没考虑，卧槽。全局的有这种问题吗

> 要扩大。你建议怎么整理

> ```
> nanoassistant我觉得也可以整合到.nanoassistant吧？有什么单独的必要性
> ```

> 旧的按照之前的原则，启动时一次性 搬迁，搬迁了就删掉

> 绝对路径变了没事，workspace内相对路径没变就行。

## 澄清记录

- Q1: 这次是否定义为“PA 自己产生的所有持久化数据统一进 `.nanoassistant/`，但保留 `.nano/{tools,hooks}` 这个通用扩展入口”？
  A(原话): 我觉得本unit要把内核改为默认用.nano，但是产品可传其他目录名，比如
  ```
  .nanoassistant

  一旦传了的话，那就是按照传进来的这个。然后chat history也放进去。CLI那边也要改。理解吗？现在可以跟我进行需求澄清。
  ```
  Agent 解读: 内核未收到产品目录名时使用 `.nano`；收到时该产品的 workspace 持久化遵循传入目录。PA 使用 `.nanoassistant`，CLI 使用其既有产品目录名 `.nanocode`。

- Q2: 产品首次使用一个已有 `.nano/tools` 或 `.nano/hooks` 的 workspace 时，旧共享扩展应如何处理？
  A(原话): 那我觉得应该做的是PA首次启动的时候把.nano/tools、.nano/hooks 这类共享扩展拷贝到自己那里，然后不删除他原本的，CLI首次启动的时候则放到.nanocode里
  Agent 解读: PA 首次启动时将旧 `.nano/tools`、`.nano/hooks` 拷贝至 `.nanoassistant/` 下对应位置，且保留来源；CLI 对应拷贝至 `.nanocode/`。之后各产品从自身目录加载 workspace 扩展。

- Q3: 如果目标中已存在同相对路径的产品扩展，例如 `.nanoassistant/tools/foo.py` 与旧 `.nano/tools/foo.py` 同时存在，首次导入应如何处理？
  A(原话): 好
  Agent 解读: 保留产品目录中的已有文件，只复制目标缺少的文件；不覆盖、不删除、不合并内容。

- Q4: 已有 workspace 里旧的 `chat_history/` 与 `.nano/background-tasks/` 要不要在首次启动时自动搬到产品目录？
  A(原话): 好
  Agent 解读: 不自动搬迁旧运行数据；新版本仅在产品目录写新数据，旧文件原处保留供人工查看或清理。

- Q5: `chat_history` 迁入 `.nanoassistant/chat_history/` / `.nanocode/chat_history/` 后，是否继续保留这份简化、人工可读的对话副本？
  A(原话): 对
  Agent 解读: 保留 `chat_history`，仅改变其目录归属。

- Q6: 首次导入完成后，如果仓库作者又在旧 `.nano/tools` 或 `.nano/hooks` 增加文件，后续 PA/CLI 启动是否继续自动补拷？
  A(原话): 不再同步
  Agent 解读: 旧共享扩展只在首次产品初始化时快照导入；后续产品目录是唯一生效来源。

- Q7: PA 的 `HEARTBEAT.md` 目前仍在 workspace 根目录。它也是 PA 的配置，应否一并迁为 `.nanoassistant/HEARTBEAT.md`？CLI 没有这个文件。
  A(原话): 好
  Agent 解读: PA 的 `HEARTBEAT.md` 迁入 `.nanoassistant/HEARTBEAT.md`；workspace 根只保留项目自身资产。

- Q8: 当 Agent workspace 是 Git 仓库时，PA/CLI 是否应在首次初始化时自动修改该仓库的 `.gitignore`，忽略 `.nanoassistant/` 或 `.nanocode/`？
  A(原话): 对
  Agent 解读: PA/CLI 不自动修改 workspace Git 仓库的 `.gitignore`；版本控制策略仍由仓库维护者决定。

- Q9: CLI 的“也要改”是指它同样把 session、skills、workspace tools/hooks、后台输出等遵循 `.nanocode/`；但不新增 PA 专属的 `chat_history`，对吗？
  A(原话): 对
  Agent 解读: CLI 适配统一的 `.nanocode/` workspace 目录规则，但不新增 PA 专属 `chat_history`。

- Q10: 升级已有 PA workspace 时，根目录的旧 `HEARTBEAT.md` 要如何处理？
  A(原话): 对
  Agent 解读: 首次初始化时，若 `.nanoassistant/HEARTBEAT.md` 不存在，则拷贝根目录旧 `HEARTBEAT.md`；保留来源且不覆盖已有目标文件。

- Q11: 这次是否把 PA 的全局目录和默认 Agent workspace 根也纳入收敛范围？
  A(原话): 要扩大。你建议怎么整理
  Agent 解读: 本 unit 除 workspace 内目录规则外，还要收敛 PA 的全局配置、状态、扩展和默认创建的 Agent workspace 根。

- Q12: PA 的默认 Agent workspace 是否单独保留在 `~/nanoassistant/`，还是也整合进隐藏的全局产品目录？
  A(原话):
  ```
  nanoassistant我觉得也可以整合到.nanoassistant吧？有什么单独的必要性
  ```
  Agent 解读: 不保留单独的默认 workspace 父目录。PA 的全局产品 home 为 `~/.nanoassistant/`，默认 workspace 位于其 `workspaces/<agent-id>/` 下；用户显式指定的外部 workspace 不改变位置。

- Q13: 旧的 PA 全局 home 与旧默认 workspace 根如何处理？
  A(原话): 旧的按照之前的原则，启动时一次性 搬迁，搬迁了就删掉
  Agent 解读: `~/.nano-assistant/` 和 `~/nano-assistant/` 均在 PA 首次启动时一次性迁往新的 `~/.nanoassistant/` 体系；迁移成功后删除相应旧源目录，不持续同步。

- Q14: 整体迁移旧默认 workspace 后，旧根目录 `chat_history/` 与 `.nano/background-tasks/` 的绝对路径会改变；这是否推翻“不迁入产品目录”的既有决定？
  A(原话): 绝对路径变了没事，workspace内相对路径没变就行。
  Agent 解读: 旧默认 workspace 可以整体迁移。其遗留聊天副本和后台输出保留在迁后 workspace 根的原相对位置，不迁入 `<workspace>/.nanoassistant/` 或 `<workspace>/.nanocode/`；绝对路径变化可接受。

- Q15: 若迁移目标已有同名但内容不同的 PA 全局配置或状态，是否应停止迁移、保留旧目录，而不是覆盖或删除数据？
  A(原话): 好
  Agent 解读: 迁移先检查冲突；不同内容的同名项使本次迁移失败，旧路径与既有目标均保留，PA 提示用户处理。仅无冲突时才完成搬迁并删除旧源。

## 现状痛点

产品已经把会话、memory、skills 和 cron 等状态分别放入 `.nanoassistant/` 或 `.nanocode/`，但仍有 PA 的简化聊天记录写在 workspace 根目录，heartbeat 配置也写在根目录；后台 bash 输出则被内核硬编码到 `.nano/`。当 PA workspace 指向一个代码仓根目录时，这些产品产物混在项目资产中，既难以统一管理，也使仓库维护者难以判断哪些文件应纳入版本控制。

`.nano` 同时承担了内核默认 workspace 命名空间和旧的仓库扩展入口；它与 PA/CLI 的产品目录没有统一的选择规则。因而产品明明传入了自己的配置目录，部分运行时文件仍落到 `.nano` 或根目录。

PA 的全局数据也有同类分裂：`~/.nanoassistant/` 已承载全局扩展，`~/.nano-assistant/` 却承载 Gateway 配置和绑定状态，而默认 Agent workspace 又位于 `~/nano-assistant/`。用户需要区分三个近似名字，且无法从目录名判断哪些是 PA 的全局控制数据、哪些是 Agent 工作区。

## 目标状态

内核对未声明产品目录的消费者仍以 `.nano` 作为 workspace 默认目录。产品可显式提供自己的目录名；一旦提供，所有该产品管理的 workspace 持久化、workspace extensions 与后台输出均使用该目录。PA 的目录为 `.nanoassistant/`，CLI 的目录为 `.nanocode/`。

PA 继续提供人工可读的 `chat_history`，但它、heartbeat、会话和其他 PA 管理状态均收敛到 `.nanoassistant/`。CLI 不新增这份 PA 专属聊天副本。

PA 的唯一全局产品 home 为 `~/.nanoassistant/`：全局配置、持久状态以及全局 skills、tools、hooks 均在此处。默认创建的 Agent workspace 位于 `~/.nanoassistant/workspaces/<agent-id>/`；其中的 PA workspace 状态仍遵循 `<workspace>/.nanoassistant/`。用户显式指定的代码仓或其他外部 workspace 保持原位置和相同的 workspace 内目录规则。

## 用户侧验收标准（不变性）

### Requirement: 未指定产品目录的内核用户保持 `.nano` 默认行为

#### Scenario: 消费者未提供 workspace 目录名
- **WHEN** 一个内核消费者在 workspace 中运行且未声明产品目录名
- **THEN** 其 workspace 管理文件仍使用 `.nano/`，现有默认使用者不需要改配置

### Requirement: PA 的 workspace 状态收敛到 `.nanoassistant/`

#### Scenario: PA 在代码仓 workspace 中产生新状态
- **GIVEN** 一个 PA Agent 的 workspace 是代码仓根目录
- **WHEN** 用户与 Agent 对话、触发 heartbeat 或启动后台 bash 任务
- **THEN** 新产生的 PA 聊天副本、heartbeat 配置与后台输出均位于 `.nanoassistant/` 下，而不在仓库根目录或 `.nano/` 下

#### Scenario: PA 继续提供简化聊天副本
- **WHEN** 用户完成一轮 PA 对话
- **THEN** 该轮仍有人工可读的 user/assistant 文本副本，路径位于 `.nanoassistant/chat_history/`

#### Scenario: 已有 PA heartbeat 在升级后继续生效
- **GIVEN** 已有 PA workspace 的根目录中存在 `HEARTBEAT.md`，且 `.nanoassistant/HEARTBEAT.md` 尚不存在
- **WHEN** 用户升级后首次启动 PA
- **THEN** PA 在 `.nanoassistant/` 中保留可用的 heartbeat 配置并继续按原有配置执行，根目录旧文件不被删除

### Requirement: PA 的全局数据与默认 workspace 收敛到 `~/.nanoassistant/`

#### Scenario: 新建默认 PA Agent
- **WHEN** 用户创建未显式指定 workspace 的 PA Agent
- **THEN** 该 Agent 的 workspace 创建在 `~/.nanoassistant/workspaces/<agent-id>/`，其 PA 状态继续写入该 workspace 的 `.nanoassistant/`

#### Scenario: 首次迁移没有冲突的旧 PA 全局数据和默认 workspaces
- **GIVEN** 用户已有 `~/.nano-assistant/` 或 `~/nano-assistant/` 中的 PA 数据，且 `~/.nanoassistant/` 没有内容不同的同名项
- **WHEN** 用户升级后首次启动 PA
- **THEN** 全局配置、状态和默认 Agent workspaces 均可从 `~/.nanoassistant/` 继续使用，旧 `~/.nano-assistant/` 与旧 `~/nano-assistant/` 已被删除

#### Scenario: 默认 workspace 的遗留运行文件随 workspace 保持相对位置
- **GIVEN** 旧默认 workspace 根目录有 `chat_history/` 或 `.nano/background-tasks/`
- **WHEN** 该默认 workspace 在首次启动时迁至 `~/.nanoassistant/workspaces/<agent-id>/`
- **THEN** 这些遗留文件仍位于迁后 workspace 根的相同相对位置，不会被迁入该 workspace 的 `.nanoassistant/` 或 `.nanocode/`

#### Scenario: 迁移遇到内容冲突
- **GIVEN** 旧 PA 目录与 `~/.nanoassistant/` 存在内容不同的同名项
- **WHEN** 用户首次启动 PA
- **THEN** PA 明确告知迁移冲突，旧目录和已有目标内容均不被覆盖或删除

#### Scenario: 用户指定外部 workspace
- **GIVEN** PA Agent 的 workspace 被用户显式指定为一个外部目录或代码仓根目录
- **WHEN** 用户升级后首次启动 PA
- **THEN** 该 workspace 不被迁入 `~/.nanoassistant/workspaces/`，但 PA 状态仍按 `<workspace>/.nanoassistant/` 规则管理

### Requirement: CLI 的 workspace 状态遵循 `.nanocode/`

#### Scenario: CLI 在 workspace 中运行后台任务或使用 workspace extension
- **WHEN** 用户通过 CLI 在一个 workspace 中运行相关能力
- **THEN** CLI 使用 `.nanocode/` 作为其产品目录，不产生 PA 的 `chat_history`

### Requirement: 旧共享扩展在首次产品初始化时安全分叉

#### Scenario: PA 首次初始化已有共享扩展的 workspace
- **GIVEN** workspace 有 `.nano/tools/` 或 `.nano/hooks/`，且对应 `.nanoassistant/` 位置缺少同名文件
- **WHEN** 用户首次启动 PA
- **THEN** 这些扩展被拷贝到 `.nanoassistant/` 对应位置，原 `.nano/` 文件保持不变，PA 后续从产品目录加载扩展

#### Scenario: CLI 首次初始化已有共享扩展的 workspace
- **GIVEN** workspace 有 `.nano/tools/` 或 `.nano/hooks/`，且对应 `.nanocode/` 位置缺少同名文件
- **WHEN** 用户首次启动 CLI
- **THEN** 这些扩展被拷贝到 `.nanocode/` 对应位置，原 `.nano/` 文件保持不变，CLI 后续从产品目录加载扩展

#### Scenario: 目标已有同名产品扩展
- **GIVEN** 旧 `.nano/` 与产品目录中存在同相对路径的 extension 文件
- **WHEN** 用户首次启动该产品
- **THEN** 产品目录中的文件保持不变，旧文件不会覆盖或合并进它

#### Scenario: 完成首次导入后的旧目录发生变化
- **GIVEN** 产品已完成该 workspace 的首次导入
- **WHEN** 仓库作者在旧 `.nano/tools/` 或 `.nano/hooks/` 中新增或修改文件并再次启动产品
- **THEN** 产品目录不再自动同步这些变化，产品继续使用自己的 extension 副本

### Requirement: 旧运行数据与仓库版本控制不被静默改写

#### Scenario: 外部 workspace 的旧聊天副本和后台输出保持可查看
- **GIVEN** 一个不属于 PA 默认 workspace 根的 workspace 已有根目录 `chat_history/` 或 `.nano/background-tasks/`
- **WHEN** 用户升级并启动 PA 或 CLI
- **THEN** 旧文件不被自动移动、删除或归属到某个产品；后续新数据按产品目录写入

#### Scenario: workspace 是 Git 仓库
- **WHEN** 用户首次启动 PA 或 CLI
- **THEN** 产品不修改该仓库的 `.gitignore` 或其他项目版本控制文件

## 范围与非目标

- 范围：把 workspace 目录选择收敛为“内核默认 `.nano`、产品显式目录覆盖”的一致规则，并使 PA 与 CLI 按各自产品目录写入和发现 workspace 资源。
- 范围：PA 保留 `chat_history`，但将其和 `HEARTBEAT.md` 迁入 `.nanoassistant/`；CLI 适配同一目录选择规则，不新增聊天副本。
- 范围：PA 全局配置、持久状态、全局扩展和默认 Agent workspace 收敛到 `~/.nanoassistant/`；旧 `~/.nano-assistant/` 与 `~/nano-assistant/` 在无冲突首次迁移成功后删除。
- 非目标：将遗留 `chat_history/`、`.nano/background-tasks/` 重新归属或搬入 PA/CLI 产品目录；默认 workspace 整体迁移时保留这些文件的 workspace 内相对位置。
- 非目标：首次导入后持续同步 `.nano/tools`、`.nano/hooks`，覆盖或合并产品已有 extension，或自动修改 Git 忽略规则。
- 非目标：改变未提供产品目录名的内核消费者的 `.nano` 默认行为。

## 影响范围

- 内核 workspace 目录选择，以及 session、background task 和 workspace extension 的一致性。
- PA 的 workspace 初始化、heartbeat、聊天副本和 Agent workspace 运行。
- PA 的全局配置、绑定状态、全局扩展发现和默认 workspace 创建/迁移。
- CLI 的 workspace 初始化、workspace extension 与后台任务路径。
- 相关的用户文档、行为契约与回归测试。

## 迁移与回滚策略

- 对每个产品与 workspace，旧 `.nano/tools`、`.nano/hooks` 只在首次初始化时快照导入一次；只补缺失文件，保留旧来源和已有目标文件。
- PA 首次初始化时，缺少目标 heartbeat 配置才从根目录拷贝旧 `HEARTBEAT.md`；不删除来源或覆盖目标。
- PA 首次启动前检查 `~/.nano-assistant/` 与 `~/nano-assistant/` 到 `~/.nanoassistant/` 的一次性迁移。无内容冲突时搬迁全局数据和默认 workspaces，成功后删除相应旧源目录；迁后默认 workspace 内遗留文件保留原相对位置。
- 若迁移发现内容不同的同名项，不覆盖、不删除，保留旧源和既有目标并提示用户处理；不把半完成迁移视为成功。
- 外部 workspace 的旧根目录聊天副本和 `.nano/background-tasks/` 不自动迁移；新版本只在产品目录写新文件。
- 产品不自动改写 Git 忽略规则。迁移失败或升级在完成前中断时不得删除旧来源、既有产品目录内容或历史运行数据；成功迁移后旧路径按本单元约定删除。
