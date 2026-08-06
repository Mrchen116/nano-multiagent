# IM web-chat-ux Specification (delta for bugfix-509)

## ADDED Requirements

### Requirement: Web IM 按当前语言和会话类型展示后台自进化提示

Web IM 在聊天时间线中把后台自进化结果显示为既有轻量 system 行：中文界面用中文、英文界面用英文，覆盖 skills、memory 与两者更新。群聊行显示产生该次 review 的 Agent 显示名，单聊不重复 Agent 名；system 行保持无头像、无发送者头和无消息操作。刷新、重进和实时到达使用同一结构化语义。

#### Scenario: 中文群聊显示来源 Agent 与更新对象
- **GIVEN** 当前界面语言为中文且 conversation 是包含多个 Agent 的群聊
- **WHEN** `SpecLab Product` 的 memory review notice 到达
- **THEN** 居中轻量 system 行以中文表达记忆已更新，并显示 `SpecLab Product`
- **AND** 该行不呈现为 Agent 消息气泡

#### Scenario: 英文群聊中的不同 Agent 分别归因
- **GIVEN** 当前界面语言为英文且群聊有多个 Agent
- **WHEN** 两个 Agent 先后产生 skills、memory 或两者更新 notice
- **THEN** 每行用英文表达自己的更新对象，并分别显示各自的来源 Agent 快照名

#### Scenario: 单聊本地化但不重复 Agent 名
- **WHEN** 用户在中文或英文 IM 单聊收到 self-evolution notice
- **THEN** system 行使用当前界面语言和正确更新对象
- **AND** 不额外显示当前 Agent 名

#### Scenario: 实时、刷新与语言切换使用同一语义
- **GIVEN** 一条结构化 self-evolution notice 已实时出现
- **WHEN** 用户刷新、重新进入 conversation 或切换界面语言
- **THEN** 来源归因与更新对象不变，文案按当时界面语言重新渲染

#### Scenario: 修复前历史提示不被改写
- **WHEN** 用户打开一条没有结构化 notice 的旧 system message
- **THEN** Web IM 继续显示其已存正文，不猜测来源 Agent 或改写历史语言

#### Scenario: fork 后的结构化提示继续按当前语言显示
- **GIVEN** direct-chat fork 带入了一条结构化 self-evolution notice
- **WHEN** 用户打开分支单聊或切换界面语言
- **THEN** 提示保留源消息的更新对象和来源快照，并按分支界面的当前语言显示

## MODIFIED Requirements

（无）

## REMOVED Requirements

（无）
