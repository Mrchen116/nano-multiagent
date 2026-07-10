# im delta-spec — feat-445

> 对齐: feat-445

本 unit 对 `docs/specs/im/spec.md` 的增量。收尾由 orchestrator 据实际 diff 校正后并入 canonical。

## ADDED Requirements

### Requirement: 用户可从单聊里某条已完成的 agent 回复 fork 出带历史的分支单聊

在「你 ↔ 单个 agent」的单聊里，用户可在一条已回复完成的 agent 消息上发起 fork，得到一个与同一 agent 的新单聊：新单聊带入从会话起点到该条回复（含）的全部消息，且 agent 在新单聊里带着这段历史的记忆继续对话。fork 入口只出现在单聊中已完成的 agent 消息上；用户自己的消息、生成中的 agent 消息、群聊中的消息均不提供 fork。新单聊作为普通 direct-agent 单聊出现在会话列表，名称为 agent 名。

#### Scenario: 在已完成的 agent 回复上 fork 得到带历史的新单聊
- **GIVEN** 用户在与某 agent 的单聊里，有一条已回复完成的 agent 消息 M，且该 agent 在线
- **WHEN** 用户在 M 上发起 fork
- **THEN** 系统新建一个与同一 agent 的单聊，带入从会话起点到 M（含 M）的全部消息（顺序与原会话一致、保留完整气泡形态），M 之后的消息不带入；用户被自动带入该新单聊并可立即发消息

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

### Requirement: agent 离线时 fork 不可用且给出明确提示

被 fork 的 agent 当前离线 / 不可用时，fork 操作不执行，用户得到明确反馈；系统不会建出一个 agent 不记得历史的空壳单聊（fork 过程中任一步失败均原子回滚，不留孤儿会话）。

#### Scenario: agent 离线时 fork 被拒并明确提示
- **GIVEN** 某 agent 当前离线
- **WHEN** 用户尝试在其历史回复上 fork
- **THEN** fork 不执行，用户看到「该 agent 当前不可用，暂时无法 fork」一类明确提示；会话列表里不新增任何单聊

#### Scenario: fork 中途失败不留孤儿会话
- **GIVEN** 校验通过、新会话已建并复制了展示历史，但委托内核侧 fork 的步骤失败
- **WHEN** fork 流程结束
- **THEN** 已建的新会话被回滚删除，用户看到 fork 失败提示；不留下一个有历史显示但 agent 不记得的单聊
