# cli (coding_cli) - Product Integration Specification

> 对齐: feat-519
> 上级: [cli (coding_cli) Specification](spec.md)

## Purpose

约束 CLI 与共享内核之间的模块边界，以及开发者可依赖的 CLI 配置和扩展发现位置。

## Requirements

### Requirement: coding_cli 只经 agent.sdk 触达内核，不依赖内核内部

`coding_cli` 只允许 import `agent.sdk`，不得 import `agent.core`、`agent.platform` 或兄弟产品包 `personal_assistant`、`IM`。这是由契约测试把守的硬不变量。

#### Scenario: 越界 import 内核内部或兄弟包被拦
- **WHEN** `coding_cli` 任一文件 import `agent.core`、`agent.platform`、`personal_assistant` 或 `IM`
- **THEN** 契约测试失败，挡住越界依赖

### Requirement: CLI 自有装配定义产品 prompt、工具集合和扩展目录

`coding_cli.product` 经 `agent.sdk.build_kernel` 提供 CLI 的 PromptSlots、默认工具集合、features 和搜索根。`.nanocode` 是 CLI 的 workspace 配置命名空间：会话、memory、原生 workspace skills、tools、hooks、安全策略与后台运行产物均从这里派生。对 Skill discovery，CLI 在当前 Workspace 依次发现 `.nanocode/skills/`、`.claude/skills/` 与 `.codex/skills/`，再依次发现 `~/.nanocode/skills/`、`~/.claude/skills/` 与 `~/.codex/skills/`；同名 Skill 使用最先命中的版本。全局扩展中的 tools/hooks 以及 workspace tools/hooks 仍只使用 `.nanocode` 的既有目录约定。CLI 不创建 PA 专属 `chat_history` 或 `HEARTBEAT.md`。

> 默认启用哪些内置工具由 `src/coding_cli/product.py` 表达，不在行为契约中复制清单。

#### Scenario: CLI 装配保持在产品包
- **WHEN** CLI 构建默认 Kernel 并创建会话
- **THEN** 产品 PromptSlots、默认工具和 feature 由 `coding_cli.product` 提供，内核不识别 `local_coding` 之类产品 profile

#### Scenario: CLI 在工作区发现 Claude/Codex Skill
- **GIVEN** 当前 Workspace 的 `.claude/skills/` 或 `.codex/skills/` 中有有效 Skill
- **WHEN** 用户从该 Workspace 启动 CLI 会话
- **THEN** 对应 Skill 进入该会话可见候选
- **AND** 不要求用户将文件复制到 `.nanocode/skills/`

#### Scenario: CLI 发现用户主目录 Claude Skill
- **GIVEN** 用户主目录的 `~/.claude/skills/` 中有有效 Skill
- **WHEN** 用户从任一 Workspace 启动 CLI 会话
- **THEN** 对应 Skill 进入该会话可见候选，除非同名的更高优先级工作区或原生全局 Skill 覆盖它

#### Scenario: workspace 与全局扩展目录被纳入
- **GIVEN** 用户在 `<workspace>/.nanocode/` 或受支持全局目录中放置有效扩展
- **WHEN** 用户在该工作区启动 CLI
- **THEN** 对应 tools、hooks 或 skills 被纳入该 CLI session 可见集合，且不读取 `<workspace>/.nano/{tools,hooks}` 作为 CLI fallback

#### Scenario: 缺失可选兼容目录不影响 CLI 启动
- **GIVEN** 当前 Workspace 或用户主目录中任一 Claude/Codex Skill 兼容目录不存在或为空
- **WHEN** 用户启动 CLI 会话
- **THEN** CLI 正常启动
- **AND** 其他有效 Skill roots 仍可发现
