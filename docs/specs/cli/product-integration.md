# cli (coding_cli) - Product Integration Specification

> 对齐: refactor-486-agent-native-repository-knowledge-system
> 上级: [cli (coding_cli) Specification](spec.md)

## Purpose

约束 CLI 与共享内核之间的模块边界，以及开发者可依赖的 CLI 配置和扩展发现位置。

## Requirements

### Requirement: coding_cli 只经 agent.sdk 触达内核，不依赖内核内部

`coding_cli` 只允许 import `agent.sdk`，不得 import `agent.core`、`agent.platform` 或兄弟产品包
`personal_assistant`、`IM`。这是由契约测试把守的硬不变量。

#### Scenario: 越界 import 内核内部或兄弟包被拦
- **WHEN** `coding_cli` 任一文件 import `agent.core`、`agent.platform`、`personal_assistant` 或 `IM`
- **THEN** 契约测试失败，挡住越界依赖

### Requirement: CLI 自有装配定义产品 prompt、工具集合和扩展目录

`coding_cli.product` 经 `agent.sdk.build_kernel` 提供 CLI 的 PromptSlots、默认工具集合、features 和搜索根。
`.nanocode` 是 CLI 的 workspace 配置命名空间：会话、memory 和 workspace skills 从这里派生。全局扩展从
`~/.nanocode/{tools,hooks,skills}` 发现，skills 还兼容 `~/.codex/skills`；workspace tools/hooks 使用
共享内核的 `<workspace>/.nano/{tools,hooks}` 入口。

> 默认启用哪些内置工具由 `src/coding_cli/product.py` 表达，不在行为契约中复制清单。

#### Scenario: CLI 装配保持在产品包
- **WHEN** CLI 构建默认 Kernel 并创建会话
- **THEN** 产品 PromptSlots、默认工具和 feature 由 `coding_cli.product` 提供，内核不识别
  `local_coding` 之类产品 profile

#### Scenario: workspace 与全局扩展目录被纳入
- **GIVEN** 用户在受支持的 workspace 或全局目录中放置有效扩展
- **WHEN** 用户在该工作区启动 CLI
- **THEN** 对应 tools、hooks 或 skills 被纳入该 CLI 运行可见集合
