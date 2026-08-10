# bugfix-508: IM 会话控制命令面板与群聊全体重开

## Relations

- Related: feat-501

## 原始需求

> IM上命令为啥没/new，不是刚最近加的吗

> 补，立刻补。改完代码自己快速看看效果，ok之后补一个spec然后提pr

> 还有一个问题，现在群聊发“/new”支持吗，是不是所有agent都统一new的逻辑。

> 那你改下，支持 “/new” 可以全部重开。

## 澄清记录

- Q1: `/new` 已在 Gateway 支持，为何 Web IM 输入 `/` 的面板只显示 `/stop`？
  A: 现有面板的内置命令列表只登记了 `/stop`；手动输入 `/new` 可执行，但不可发现。
- Q2: 群聊裸 `/new` 的作用域是什么？
  A: 用户明确要求“可以全部重开”。在内置 Web IM 群聊中，一条精确裸 `/new` 重开该群内每个 Agent 自己的会话，而不是让所有 Agent 共用同一个新会话。
- Q3: 是否由用户亲自走查后再收尾？
  A: 用户明确授权 Agent 先自行进行快速实际界面检查，确认后补 spec 并提 PR。

## 用户场景

用户在 Web IM 聊天输入框键入 `/` 时，应能直接看见可用的会话控制命令，而不用记住未展示的文本命令。在单聊中选择或发送 `/new` 后，当前 Agent 在原聊天确认新会话已开始。

内置 Web IM 的多人群聊中，用户可发送一条裸 `/new` 结束当前群组工作线：群内每个 Agent 在同一聊天各自确认新会话，之后每个 Agent 都不再沿用自己先前的群聊上下文。用户能从 slash 面板的说明预先知道这是全体重开，而非只重开某一个 Agent。

## 验收标准

### Requirement: Web IM 展示可发现的会话控制命令

#### Scenario: 单聊中选择 `/new`
- **WHEN** 用户在 Web IM composer 开头输入 `/`
- **THEN** slash 面板显示 `/stop`、`/new`、`/compact` 及其本地化说明
- **AND** 用户选择 `/new` 后，composer 填入可发送的 `/new`

#### Scenario: 群聊中理解 `/new` 的全体作用域
- **GIVEN** 当前群聊有多个 Agent
- **WHEN** 用户在 composer 开头输入 `/`
- **THEN** `/new` 的说明明确它会为群内所有 Agent 开始新会话

### Requirement: Web IM 群聊裸 `/new` 重开每个 Agent

#### Scenario: 两 Agent 群聊发送裸 `/new`
- **GIVEN** 群聊中有两个 Agent
- **WHEN** 用户发送精确的裸 `/new`
- **THEN** 两个 Agent 都在同一群中确认已开始新会话
- **AND** 后续面向任一 Agent 的消息不使用该 Agent 原先的群会话上下文

## 范围与非目标

- 在范围：Web IM slash 面板展示 `/new`、`/compact`；Web IM 群聊裸 `/new` 为每个参与 Agent 重开其各自会话；群聊面板说明这一作用域。
- 非目标：让群内 Agent 共用一个 Kernel session；改变 `/stop` 行为；将裸 `/compact` 放宽为全群操作；改变外部 IM 群聊的 Bot 定向命令规则；新增 `/reset` 别名或飞书原生命令菜单。
