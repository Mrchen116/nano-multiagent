# IM conversations-messages Specification (delta for bugfix-509)

## ADDED Requirements

（无）

## MODIFIED Requirements

### Requirement: 用户可从单聊里某条已完成的 agent 回复 fork 出带历史的分支单聊

在「你 ↔ 单个 agent」的单聊里，用户可在一条已回复完成的 agent 消息上发起 fork，得到一个与同一 agent 的新单聊：新单聊带入从会话起点到该条回复（含）的全部消息，且 agent 在新单聊里带着这段历史的记忆继续对话。带入消息保留完整气泡形态与持久展示语义；其中结构化自进化 system 提示在分支中保持原更新对象和产生时的来源快照，并继续按分支浏览器的当前语言显示。fork 入口只出现在单聊中已完成的 agent 消息上；用户自己的消息、生成中的 agent 消息、群聊中的消息均不提供 fork。新单聊作为普通 direct-agent 单聊出现在会话列表，名称为 agent 名。

#### Scenario: 在已完成的 agent 回复上 fork 得到带历史的新单聊
- **GIVEN** 用户在与某 agent 的单聊里，有一条已回复完成的 agent 消息 M，且该 agent 在线
- **WHEN** 用户在 M 上发起 fork
- **THEN** 系统新建一个与同一 agent 的单聊，带入从会话起点到 M（含 M）的全部消息（顺序与原会话一致、保留完整气泡形态），M 之后的消息不带入；用户被自动带入该新单聊并可立即发消息

#### Scenario: fork 保留自进化 system 提示语义
- **GIVEN** fork 点以前存在一条结构化自进化 system 提示
- **WHEN** 用户完成 fork 并打开分支单聊
- **THEN** 分支历史中的该提示保留相同更新对象与产生时来源快照，并按当前界面语言显示
- **AND** 不退回需要解析的固定英文正文，也不因 Agent 后续改名改写该历史快照

#### Scenario: 分支单聊里 agent 记得到 fork 点为止的历史
- **GIVEN** 带入的历史里 agent 给过一条「分多点」的回复
- **WHEN** 用户在分支单聊里发「第二点再展开讲讲」（不重述第二点内容）
- **THEN** agent 的回复针对历史里那条回复的「第二点」展开，表明它带着历史上下文继续，而非从零开始

#### Scenario: 原会话不受 fork 影响、两线独立
- **GIVEN** 用户已从某会话 fork 出分支单聊并在其中继续对话
- **WHEN** 用户切回原会话
- **THEN** 原会话消息与对话状态完全不变，不出现分支单聊里的新消息；反之在原会话继续聊也不影响分支单聊

#### Scenario: fork 入口只在单聊已完成 agent 回复上出现
- **WHEN** 用户查看自己的消息、生成中的 agent 回复、或群聊中的任意消息
- **THEN** 这些消息上都不提供 fork 入口

## REMOVED Requirements

（无）
