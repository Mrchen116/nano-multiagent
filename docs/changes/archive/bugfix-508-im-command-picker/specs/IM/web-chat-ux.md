# IM Web Chat UX Specification (delta for bugfix-508)

## ADDED Requirements

### Requirement: Web IM slash 面板发现并填写会话控制命令

用户在聊天输入框开头输入 `/` 时，slash 面板将 `/stop`、`/new`、`/compact` 与可用 skill 一起显示并按前缀过滤；用户可通过键盘或指针选择命令，输入框收到可直接发送的文本命令。在群聊中，`/new` 明确说明它会为群内所有 Agent 开始新会话。

#### Scenario: 单聊中从 slash 面板选择新会话
- **WHEN** 用户在单聊 composer 开头输入 `/` 或 `/new` 的未完成前缀
- **THEN** 面板显示 `/new` 及“在当前聊天中开始新会话”的说明
- **AND** 用户选择后，composer 填入可发送的 `/new`

#### Scenario: 群聊中从 slash 面板选择全体新会话
- **GIVEN** 当前群聊有多个 Agent 参与
- **WHEN** 用户在 composer 开头输入 `/`
- **THEN** 面板显示 `/new` 并说明它会为群内所有 Agent 开始新会话
- **AND** 用户选择后，composer 填入可发送的 `/new`
