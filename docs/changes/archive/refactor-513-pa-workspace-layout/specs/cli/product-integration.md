# cli product-integration Specification (delta for refactor-513)

## MODIFIED Requirements

### Requirement: CLI 自有装配定义产品 prompt、工具集合和扩展目录

`coding_cli.product` 经 `agent.sdk.build_kernel` 提供 CLI 的 PromptSlots、默认工具集合、features 和搜索根。`.nanocode` 是 CLI 的 workspace 配置命名空间：会话、memory、workspace skills、tools、hooks、安全策略与后台运行产物均从这里派生。全局扩展从 `~/.nanocode/{tools,hooks,skills}` 发现，skills 还兼容 `~/.codex/skills`；workspace tools/hooks 从 `<workspace>/.nanocode/{tools,hooks}` 发现。CLI 不创建 PA 专属 `chat_history` 或 `HEARTBEAT.md`。

> 默认启用哪些内置工具由 `src/coding_cli/product.py` 表达，不在行为契约中复制清单。

#### Scenario: CLI 装配保持在产品包
- **WHEN** CLI 构建默认 Kernel 并创建会话
- **THEN** 产品 PromptSlots、默认工具和 feature 由 `coding_cli.product` 提供，内核不识别 `local_coding` 之类产品 profile

#### Scenario: workspace 与全局扩展目录被纳入
- **GIVEN** 用户在 `<workspace>/.nanocode/` 或受支持全局目录中放置有效扩展
- **WHEN** 用户在该 workspace 启动 CLI
- **THEN** 对应 tools、hooks 或 skills 被纳入该 CLI session 可见集合，且不读取 `<workspace>/.nano/{tools,hooks}` 作为 CLI fallback
