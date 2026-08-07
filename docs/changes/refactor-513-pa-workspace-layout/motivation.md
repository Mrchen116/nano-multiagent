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

> “首次迁移”这个事情如果落入到代码里面的话，会有很多垃圾代码，以后用不到的。现在我们部署只部署了两台机子，我觉得可以这样，代码仍然是干净的终态代码。然后在首次部署的时候进行一次手动迁移就好了。

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

- Q16: 手动迁移是否替代所有一次性兼容逻辑，包括旧全局 home、默认 workspace、`.nano/tools`、`.nano/hooks` 和根目录 `HEARTBEAT.md`？
  A(原话): 对的
  Agent 解读: 所有历史目录整理均由首次部署前的人工迁移完成；产品运行时代码只使用终态路径，不包含首次启动复制、冲突检测、删除旧目录或同步逻辑。本结论覆盖 Q2、Q3、Q6、Q10、Q13、Q15 中“首次启动”的表述；其中 `.nano` extensions 的人工迁移仍遵循既定的只补缺失、保留旧来源和不持续同步规则。

- Q17: 旧 `.nano/policy.toml` 是否也应随产品目录走，在人工迁移时进入 PA/CLI 各自目录，并由终态产品读取？
  A(原话): 好
  Agent 解读: `policy.toml` 是 workspace 安全配置的一部分。首次部署前按目标缺失才复制、保留旧来源和不持续同步的规则迁入 `.nanoassistant/` 或 `.nanocode/`；PA/CLI 终态只读取自己的产品策略，未指定产品目录的内核消费者仍使用 `.nano/policy.toml`。

- Q18: mini 上旧 `~/.nano-assistant/` 内的 IM JWT 签名密钥是否也随全局根迁入 `~/.nanoassistant/`，并同步修改生产运维路径？
  A(原话): 好
  Agent 解读: 人工迁移同时移动 `im-jwt-secret` 至 `~/.nanoassistant/im-jwt-secret`，保持其密钥内容和私有文件权限；IM 启动与生产运维文档改用新路径，不重新生成密钥。

## 现状痛点

产品已经把会话、memory、skills 和 cron 等状态分别放入 `.nanoassistant/` 或 `.nanocode/`，但仍有 PA 的简化聊天记录写在 workspace 根目录，heartbeat 配置也写在根目录；后台 bash 输出则被内核硬编码到 `.nano/`。当 PA workspace 指向一个代码仓根目录时，这些产品产物混在项目资产中，既难以统一管理，也使仓库维护者难以判断哪些文件应纳入版本控制。

`.nano` 同时承担了内核默认 workspace 命名空间和旧的仓库扩展入口；它与 PA/CLI 的产品目录没有统一的选择规则。因而产品明明传入了自己的配置目录，部分运行时文件仍落到 `.nano` 或根目录。

PA 的全局数据也有同类分裂：`~/.nanoassistant/` 已承载全局扩展，`~/.nano-assistant/` 却承载 Gateway 配置、绑定状态和 mini 的 IM JWT 签名密钥，而默认 Agent workspace 又位于 `~/nano-assistant/`。用户需要区分三个近似名字，且无法从目录名判断哪些是 PA 的全局控制数据、哪些是 Agent 工作区。

## 目标状态

内核对未声明产品目录的消费者仍以 `.nano` 作为 workspace 默认目录。产品可显式提供自己的目录名；一旦提供，所有该产品管理的 workspace 持久化、workspace extensions、安全策略与后台输出均使用该目录。PA 的目录为 `.nanoassistant/`，CLI 的目录为 `.nanocode/`。

PA 继续提供人工可读的 `chat_history`，但它、heartbeat、会话和其他 PA 管理状态均收敛到 `.nanoassistant/`。CLI 不新增这份 PA 专属聊天副本。

PA 的唯一全局产品 home 为 `~/.nanoassistant/`：全局配置、持久状态以及全局 skills、tools、hooks 均在此处。默认创建的 Agent workspace 位于 `~/.nanoassistant/workspaces/<agent-id>/`；其中的 PA workspace 状态仍遵循 `<workspace>/.nanoassistant/`。用户显式指定的代码仓或其他外部 workspace 保持原位置和相同的 workspace 内目录规则。mini 的 IM JWT 签名密钥也在人工迁移后由 `~/.nanoassistant/im-jwt-secret` 持有。

首次部署前由部署者手动完成历史路径整理；部署后的 PA 与 CLI 仅识别和写入终态目录，不在启动时检查、导入、删除或同步任何旧路径。

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

#### Scenario: 人工迁移后的既有 PA heartbeat 继续生效
- **GIVEN** 已有 PA workspace 的根目录中存在 `HEARTBEAT.md`，且 `.nanoassistant/HEARTBEAT.md` 尚不存在
- **WHEN** 部署者按首次部署迁移步骤准备该 workspace
- **THEN** PA 在 `.nanoassistant/` 中保留可用的 heartbeat 配置并继续按原有配置执行，根目录旧文件不被删除

### Requirement: PA 的全局数据与默认 workspace 收敛到 `~/.nanoassistant/`

#### Scenario: 新建默认 PA Agent
- **WHEN** 用户创建未显式指定 workspace 的 PA Agent
- **THEN** 该 Agent 的 workspace 创建在 `~/.nanoassistant/workspaces/<agent-id>/`，其 PA 状态继续写入该 workspace 的 `.nanoassistant/`

#### Scenario: 首次部署前人工迁移旧 PA 全局数据和默认 workspaces
- **GIVEN** 用户已有 `~/.nano-assistant/` 或 `~/nano-assistant/` 中的 PA 数据，且 `~/.nanoassistant/` 没有内容不同的同名项
- **WHEN** 部署者执行首次部署迁移步骤
- **THEN** 全局配置、状态和默认 Agent workspaces 均可从 `~/.nanoassistant/` 继续使用，旧 `~/.nano-assistant/` 与旧 `~/nano-assistant/` 已被删除

#### Scenario: 默认 workspace 的遗留运行文件随 workspace 保持相对位置
- **GIVEN** 旧默认 workspace 根目录有 `chat_history/` 或 `.nano/background-tasks/`
- **WHEN** 部署者在首次部署迁移中将该默认 workspace 迁至 `~/.nanoassistant/workspaces/<agent-id>/`
- **THEN** 这些遗留文件仍位于迁后 workspace 根的相同相对位置，不会被迁入该 workspace 的 `.nanoassistant/` 或 `.nanocode/`

#### Scenario: 人工迁移遇到内容冲突
- **GIVEN** 旧 PA 目录与 `~/.nanoassistant/` 存在内容不同的同名项
- **WHEN** 部署者执行首次部署迁移步骤
- **THEN** 旧目录和已有目标内容均不被覆盖或删除，部署者可在处理冲突后重新执行迁移

#### Scenario: mini 的 IM JWT 签名密钥随全局根保留
- **GIVEN** mini 的旧 `~/.nano-assistant/im-jwt-secret` 是正在使用的 IM JWT 签名密钥
- **WHEN** 部署者执行首次部署迁移并重启 IM
- **THEN** IM 使用 `~/.nanoassistant/im-jwt-secret` 中同一密钥继续签名，文件保持私有权限，不因迁移重新生成密钥

#### Scenario: 用户指定外部 workspace
- **GIVEN** PA Agent 的 workspace 被用户显式指定为一个外部目录或代码仓根目录
- **WHEN** 用户升级后首次启动 PA
- **THEN** 该 workspace 不被迁入 `~/.nanoassistant/workspaces/`，但 PA 状态仍按 `<workspace>/.nanoassistant/` 规则管理

### Requirement: CLI 的 workspace 状态遵循 `.nanocode/`

#### Scenario: CLI 在 workspace 中运行后台任务或使用 workspace extension
- **WHEN** 用户通过 CLI 在一个 workspace 中运行相关能力
- **THEN** CLI 使用 `.nanocode/` 作为其产品目录，不产生 PA 的 `chat_history`

### Requirement: 旧共享扩展在首次部署时安全分叉

#### Scenario: 人工迁移 PA 的已有共享扩展 workspace
- **GIVEN** workspace 有 `.nano/tools/` 或 `.nano/hooks/`，且对应 `.nanoassistant/` 位置缺少同名文件
- **WHEN** 部署者按首次部署迁移步骤整理该 workspace
- **THEN** 这些扩展被拷贝到 `.nanoassistant/` 对应位置，原 `.nano/` 文件保持不变，PA 后续从产品目录加载扩展

#### Scenario: 人工迁移 CLI 的已有共享扩展 workspace
- **GIVEN** workspace 有 `.nano/tools/` 或 `.nano/hooks/`，且对应 `.nanocode/` 位置缺少同名文件
- **WHEN** 部署者按首次部署迁移步骤整理该 workspace
- **THEN** 这些扩展被拷贝到 `.nanocode/` 对应位置，原 `.nano/` 文件保持不变，CLI 后续从产品目录加载扩展

#### Scenario: 目标已有同名产品扩展
- **GIVEN** 旧 `.nano/` 与产品目录中存在同相对路径的 extension 文件
- **WHEN** 部署者按首次部署迁移步骤整理该 workspace
- **THEN** 产品目录中的文件保持不变，旧文件不会覆盖或合并进它

#### Scenario: 人工迁移后的旧目录发生变化
- **GIVEN** 部署者已完成该 workspace 的迁移
- **WHEN** 仓库作者在旧 `.nano/tools/` 或 `.nano/hooks/` 中新增或修改文件并再次启动产品
- **THEN** 产品目录不再自动同步这些变化，产品继续使用自己的 extension 副本

### Requirement: workspace 安全策略随实际产品目录生效

#### Scenario: 人工迁移已有 workspace 的安全策略
- **GIVEN** workspace 有 `.nano/policy.toml`，且对应产品目录中没有 `policy.toml`
- **WHEN** 部署者按首次部署迁移步骤整理 PA 或 CLI workspace
- **THEN** 原策略被复制到该产品目录，旧 `.nano/policy.toml` 保持不变

#### Scenario: PA 或 CLI 运行 workspace 命令
- **GIVEN** PA 或 CLI workspace 的产品目录中有 `policy.toml`
- **WHEN** 用户通过该产品触发受安全策略约束的命令
- **THEN** 该产品按自身目录中的策略执行，而不依赖旧 `.nano/policy.toml`

### Requirement: 旧运行数据与仓库版本控制不被静默改写

#### Scenario: 外部 workspace 的旧聊天副本和后台输出保持可查看
- **GIVEN** 一个不属于 PA 默认 workspace 根的 workspace 已有根目录 `chat_history/` 或 `.nano/background-tasks/`
- **WHEN** 用户升级并启动 PA 或 CLI
- **THEN** 旧文件不被自动移动、删除或归属到某个产品；后续新数据按产品目录写入

#### Scenario: workspace 是 Git 仓库
- **WHEN** 用户首次启动 PA 或 CLI
- **THEN** 产品不修改该仓库的 `.gitignore` 或其他项目版本控制文件

### Requirement: 产品运行时只使用终态目录

#### Scenario: 部署后启动 PA 或 CLI
- **GIVEN** 部署者已经完成所需的首次部署迁移
- **WHEN** 用户启动 PA 或 CLI
- **THEN** 产品仅从自己的终态全局目录和 workspace 产品目录读写数据，不自动检查、导入、删除或同步任何旧路径

## 范围与非目标

- 范围：把 workspace 目录选择收敛为“内核默认 `.nano`、产品显式目录覆盖”的一致规则，并使 PA 与 CLI 按各自产品目录写入和发现 workspace 资源。
- 范围：PA 保留 `chat_history`，但将其和 `HEARTBEAT.md` 迁入 `.nanoassistant/`；CLI 适配同一目录选择规则，不新增聊天副本。
- 范围：workspace 安全策略随实际产品目录生效；部署前人工将旧 `.nano/policy.toml` 按既定的安全分叉规则整理至产品目录。
- 范围：mini 的 IM JWT 签名密钥随旧全局根迁至 `~/.nanoassistant/`，并更新 IM 与生产舰队的运维路径。
- 范围：PA 全局配置、持久状态、全局扩展和默认 Agent workspace 收敛到 `~/.nanoassistant/`；首次部署前由部署者将旧 `~/.nano-assistant/` 与 `~/nano-assistant/` 在无冲突时迁移并删除。
- 非目标：将遗留 `chat_history/`、`.nano/background-tasks/` 重新归属或搬入 PA/CLI 产品目录；默认 workspace 整体迁移时保留这些文件的 workspace 内相对位置。
- 非目标：首次导入后持续同步 `.nano/tools`、`.nano/hooks`，覆盖或合并产品已有 extension，或自动修改 Git 忽略规则。
- 非目标：在 PA 或 CLI 运行时代码中保留旧路径检测、首次启动迁移、冲突处理、删除或同步逻辑。
- 非目标：因目录迁移主动轮换或重新生成 IM JWT 签名密钥。
- 非目标：改变未提供产品目录名的内核消费者的 `.nano` 默认行为。

## 影响范围

- 内核 workspace 目录选择，以及 session、background task 和 workspace extension 的一致性。
- 内核 workspace 安全策略路径与产品目录选择的一致性。
- PA 的 workspace 初始化、heartbeat、聊天副本和 Agent workspace 运行。
- PA 的全局配置、绑定状态、全局扩展发现和默认 workspace 创建/迁移。
- mini 上 IM JWT 签名密钥的部署路径和生产运维文档。
- CLI 的 workspace 初始化、workspace extension 与后台任务路径。
- 相关的用户文档、行为契约与回归测试。

## 迁移与回滚策略

- 首次部署前，部署者将旧 `.nano/tools`、`.nano/hooks` 和 `.nano/policy.toml` 快照导入相关产品目录：只补缺失文件，保留旧来源和已有目标文件；之后不持续同步。
- 首次部署前，部署者在目标缺少 heartbeat 配置时从 workspace 根复制旧 `HEARTBEAT.md`，不覆盖目标或删除来源。
- 首次部署前，部署者将 `~/.nano-assistant/` 和 `~/nano-assistant/` 迁入 `~/.nanoassistant/`；无内容冲突时删除旧源目录，迁后默认 workspace 内遗留文件保留原相对位置。
- 该迁移在 mini 保持 `im-jwt-secret` 的内容与私有权限，并使 IM 启动和生产运维改从 `~/.nanoassistant/im-jwt-secret` 读取；不重新生成密钥。
- 人工迁移发现内容不同的同名项时不覆盖、不删除，待部署者处理后重新执行；运行时代码不参与该判断。
- 外部 workspace 的旧根目录聊天副本和 `.nano/background-tasks/` 不自动迁移；新版本只在产品目录写新文件。
- 产品不自动改写 Git 忽略规则，也不在运行时处理任何旧路径或迁移失败状态。
