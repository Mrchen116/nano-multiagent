# kernel delta-spec — feat-428 目录级项目指令自动加载

> 本文件是 feat-428 对 `docs/specs/kernel/spec.md` 的**增量草案**（design 期声明），
> 收尾由 orchestrator §7.0 据实际 diff 校正后并入 canonical。视角 = `agent.sdk` 消费者。

## ADDED Requirements

### Requirement: 会话上下文自带工作区 AGENTS.md（机制 A，默认恒开）

创建会话时，若 `workspace_root` 根目录存在 `AGENTS.md`，内核自动将其内容（含 `@import` 展开）纳入该会话的系统提示，无需消费者额外传入、无需 agent 主动读取。无该文件则不注入，会话照常工作。此行为不可经任何 per-session / per-agent 开关关闭。注入内容在一个上下文压缩窗口内**冻结**（与 MEMORY/USER 快照同生命周期，保前缀缓存稳定）；发生上下文压缩或开启新会话时**刷新**为磁盘最新内容。

#### Scenario: workspace 根有 AGENTS.md
- **WHEN** 消费者以一个根目录含 `AGENTS.md` 的 `workspace_root` 创建会话并提交一轮运行
- **THEN** 该 agent 的系统提示包含该 `AGENTS.md` 内容，agent 可据其中约定行动

#### Scenario: workspace 根无 AGENTS.md
- **WHEN** 消费者以一个根目录无 `AGENTS.md` 的 `workspace_root` 创建会话
- **THEN** 不注入项目指令，会话正常运行、无错误

#### Scenario: AGENTS.md 含 @import
- **GIVEN** 工作区根 `AGENTS.md` 内有 `@./sub.md` 形式的 import
- **WHEN** 会话启动注入
- **THEN** 被 import 文件的内容一并纳入（递归最深 5 层、环引用不重复、不存在的 import 静默忽略）

#### Scenario: 压缩窗口内冻结、压缩边界刷新
- **GIVEN** 会话已注入工作区根 `AGENTS.md`（快照 X），其后磁盘上被改为 Y
- **WHEN** 在同一压缩窗口内继续提交运行
- **THEN** 系统提示仍含 X（不随磁盘变动而变，保前缀缓存）
- **AND** 发生上下文压缩（或新会话）后的下一轮，系统提示刷新为 Y

#### Scenario: 系统提示预览显示 AGENTS.md 注入占位
- **WHEN** 消费者调 `assemble_prompt_preview` 取系统提示预览
- **THEN** 预览结果含 AGENTS.md 段的占位标记（`PREVIEW` 模式输出 `<运行时注入：…>` 占位，与 MEMORY/USER 一致；不读盘、不渲染实际文件内容）

### Requirement: read 工具触发就近项目指令加载（机制 B，可选，默认开）

当 `nested_memory` 内核特性开启（默认 `default_on=True`，不投影为产品/用户 toggle）时，agent 经 `read` 工具读取文件，内核在该 read 的工具结果中追加项目指令上下文：被读文件在 `workspace_root` 内 → 追加其目录链（至 workspace 根）上各级 `AGENTS.md` 的正文（`@import` 展开、`<project-instructions>` 标签包裹）；在 `workspace_root` 外 → 追加英文路径提示（`<project-instructions-hint>`），范围为该文件目录至最外层 git 仓根逐级、不含正文。同一份 AGENTS.md（按绝对路径）在一个上下文压缩窗口内只追加一次（含机制 A 已注入的工作区根那份）；发生上下文压缩后去重记录清空，使压缩后的 read 可重新追加（取磁盘最新内容）——与机制 A 的压缩边界刷新一致。

#### Scenario: 读工作区内子目录文件，链上有 AGENTS.md
- **GIVEN** `nested_memory` 开启，workspace 内某子目录有 `AGENTS.md`
- **WHEN** agent read 该子目录（或更深）下的文件
- **THEN** 该 read 的工具结果含该 `AGENTS.md` 正文（`<project-instructions>` 包裹）

#### Scenario: 读工作区外 git 仓内文件
- **GIVEN** `nested_memory` 开启，被读文件在 workspace 外、属于某 git 仓，文件目录至最外层仓根之间有 `AGENTS.md`
- **WHEN** agent read 该文件
- **THEN** 工具结果含英文路径提示（列出各级 AGENTS.md 路径，不含正文）

#### Scenario: 读不属于任何 git 仓的工作区外文件
- **WHEN** agent read 的文件在 workspace 外且不属于任何 git 仓
- **THEN** 工具结果不含任何项目指令提示

#### Scenario: 同一 AGENTS.md 多次命中只追加一次（压缩窗口内）
- **WHEN** 同一压缩窗口内多次 read 命中同一份 `AGENTS.md`（含机制 A 已注入的工作区根那份）
- **THEN** 仅首次追加，后续不重复

#### Scenario: 压缩后 read 重新追加（去重记录随压缩清空）
- **GIVEN** 某 `AGENTS.md` 已在本压缩窗口内因一次 read 被追加过
- **WHEN** 发生上下文压缩后，再次 read 命中该文件
- **THEN** 重新追加该文件当前磁盘内容（压缩已把旧追加内容摘要掉，去重记录已随压缩清空）

#### Scenario: 关闭 nested_memory 后 read 不再追加
- **GIVEN** `nested_memory` 特性关闭
- **WHEN** agent read 工作区内/外文件
- **THEN** 工具结果不含项目指令内容/提示
- **AND** 机制 A 的工作区根 AGENTS.md 仍照常注入系统提示（不随之关闭）
