# IM - Web Chat UX Specification (delta for feat-517)

## MODIFIED Requirements

### Requirement: Web IM slash 面板发现并填写会话控制命令

用户在聊天输入框开头输入 `/` 时，slash 面板将 `/stop`、`/new`、`/compact`、Gateway 为当前 Agent runtime 报告的动态 commands 与可用 skill 一起显示并按前缀过滤；用户可通过键盘或指针选择命令，输入框收到可直接发送的文本命令。在群聊中，`/new` 明确说明它会为群内所有 Agent 开始新会话。

#### Scenario: 单聊中从 slash 面板选择新会话
- **WHEN** 用户在单聊 composer 开头输入 `/` 或 `/new` 的未完成前缀
- **THEN** 面板显示 `/new` 及“在当前聊天中开始新会话”的说明
- **AND** 用户选择后，composer 填入可发送的 `/new`

#### Scenario: 群聊中从 slash 面板选择全体新会话
- **GIVEN** 当前群聊有多个 Agent 参与
- **WHEN** 用户在 composer 开头输入 `/`
- **THEN** 面板显示 `/new` 并说明它会为群内所有 Agent 开始新会话
- **AND** 用户选择后，composer 填入可发送的 `/new`

#### Scenario: 群聊中选择模型专属的推理档位
- **GIVEN** 群聊中的多个 Agent 报告不同有效模型或不同 `/effort` levels
- **WHEN** 用户在 composer 打开 `/effort` 候选
- **THEN** 每个候选显示其来源 Agent 和该 Agent 的完整 levels，不合并成公共集合
- **AND** 用户选择其中一项后，composer 填入指向该 Agent 的 `@Agent /effort `，使任意 group reply policy 下也只更新该 Agent 的 session

#### Scenario: 当前有效模型的 effort command 由 Gateway 动态发现
- **GIVEN** Gateway 报告当前 Agent 有 selectable reasoning 的有效模型
- **WHEN** 用户打开 slash picker
- **THEN** 面板显示 `/effort`，说明中列出该模型完整的普通 levels
- **AND** 只有 Gateway 同时报告 Workflow active 与 `xhigh` capability 时，说明中额外列出 `ultracode`
- **AND** 前端不写死档位、也不自行把 Workflow disabled 的普通 `/effort` 候选过滤掉
