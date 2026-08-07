# im agents-nodes Specification (delta for refactor-513)

## ADDED Requirements

### Requirement: IM 独立判定 PA 托管默认 workspace

IM 自己维护 PA 托管默认 workspace 的路径规则，不 import `personal_assistant` 或 `agent`：未显式 workspace 的 Agent 为 `~/.nanoassistant/workspaces/<agent-id>/`，并以该路径判定 `workspace_is_default`。IM 只保存和转发这一路径；实际 workspace 文件仍由 Gateway 读写。显式外部 workspace 保持非默认。

#### Scenario: 新建未指定 workspace 的 Agent 使用新托管默认路径
- **WHEN** IM 为在线节点创建一个未显式 workspace_root 的 Agent
- **THEN** 下发、保存并在响应中标记 `~/.nanoassistant/workspaces/<agent-id>/` 为该 Agent 的默认 workspace

#### Scenario: 外部 workspace 不被判为默认
- **GIVEN** Agent profile 保存的是任意显式外部代码仓路径
- **WHEN** IM 返回该 Agent 的配置
- **THEN** `workspace_is_default` 为 false，且原路径不被改写
