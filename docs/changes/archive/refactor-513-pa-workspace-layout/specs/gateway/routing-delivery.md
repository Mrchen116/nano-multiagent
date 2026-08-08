# gateway routing-delivery Specification (delta for refactor-513)

## ADDED Requirements

### Requirement: PA 在 workspace 产品目录保留可读聊天副本

Gateway 在每个 PA 会话的 user 或 assistant 文本进入其持久化投递路径时，向 `<workspace_root>/.nanoassistant/chat_history/<conversation-id>.jsonl` 追加一个简化 JSONL 条目。条目保留 `ts`、`role` 与文本 `content`，供用户在 workspace 中查看；它不替代内核 session transcript，也不作为会话恢复的唯一来源。Gateway 不在 workspace 根新建 `chat_history/`。

#### Scenario: 用户与助手文本写入 PA 产品目录
- **GIVEN** 一个 PA Agent 的 workspace 为代码仓目录，且用户完成一轮有 assistant 文本回复的聊天
- **WHEN** Gateway 持久化该轮的简化聊天副本
- **THEN** user 和 assistant 条目写入该 workspace 的 `.nanoassistant/chat_history/`，每项含 `ts`、`role`、`content`，workspace 根没有新建 `chat_history/`

#### Scenario: 可读聊天副本不替代会话恢复记录
- **WHEN** Gateway 在已有简化聊天副本后恢复该会话
- **THEN** 仍从内核 session transcript 恢复上下文，而非把简化 JSONL 当作唯一恢复来源
