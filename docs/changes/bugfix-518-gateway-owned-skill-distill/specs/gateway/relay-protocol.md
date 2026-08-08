# gateway relay-protocol Specification (delta for bugfix-518)

## ADDED Requirements

### Requirement: Gateway 为同节点历史会话生成 distill prompt

IM 请求已选择的同节点 source conversations 的 distill prompt 时，Gateway 用自己持有的 durable
conversation/session binding 在本机解析 JSONL paths，并复核 execution Agent 的
`conversation-skill-distiller` 和 `skill_view`。它以 request_id 返回当前普通
`conversation-skill-distiller` 消息格式的 prompt 或 actionable error。Gateway 不返回 transcript 内容，也不执行
模型或 skill；后续由 IM 固定路由的普通聊天 relay 回到同一 Gateway 并按该 prompt 读取本机 paths。

#### Scenario: 本机 binding 生成可直接预填的 prompt
- **GIVEN** 所有 source conversation/Agent 与 execution Agent 都属于当前 Gateway，且 source 有本机可读 binding
- **WHEN** Gateway 收到 `node.distill.prompt.request`
- **THEN** 它以相同 request_id 和 node_id 返回当前 distiller 格式的 prompt，包含 slash command、全部本机 JSONL paths、execution Agent 与 scope
- **AND** 不读取 transcript、不启动模型、不创建 session 或 skill

#### Scenario: 任一 source 不能解析时不返回部分 prompt
- **GIVEN** 至少一个 source binding 缺失、path 不可读或不是当前 Gateway 的本机 source
- **WHEN** Gateway 收到 prompt request
- **THEN** 它以相同 request_id 和 node_id 返回可理解错误而非部分 prompt
- **AND** 不读取其余 transcript、不启动模型、不创建 session 或 skill

#### Scenario: execution Agent 缺少 distiller 能力时不返回 prompt
- **WHEN** Gateway 收到 prompt request，但 execution Agent 缺少 `conversation-skill-distiller` 或 `skill_view`
- **THEN** 它以相同 request_id 和 node_id 返回可理解错误
- **AND** 不读取 transcript、不启动模型、不创建 session 或 skill
