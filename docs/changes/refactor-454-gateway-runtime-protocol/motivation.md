# refactor-454: gateway runtime protocol

## Relations

- Related: bugfix-404, bugfix-446, feat-447, refactor-387

## 原始诉求

> [$change-spec-author](/Users/czj/Repos/nano-multiagent/.claude/skills/change-spec-author/SKILL.md) 帮我把A和F联合设计，进行一次重构

## 澄清记录

- Q1: 这次 A+F 联合重构的范围，是不是定义为“用户可见行为完全不变，只改善内部结构和可维护性”？
  A(原话): 对
  Agent 解读: 本 unit 按纯 refactor 处理；用户侧验收写成既有行为不变性，不在本 unit 新增用户功能。
- Q2: 这次 refactor 的回归基线，我建议只覆盖 A+F 直接相关的 5 条用户可见链路：Gateway/IM 连接与重连、Web IM relay 投递、外部 channel shadow 会话、`workspace_root` 权威规则、运行态气泡/工具收口。是否明确不把候选 B/C/D 纳入本 unit？
  A(原话): 对
  Agent 解读: 本 unit 不纳入 user stream/timeline、tool extension interface、LLM config/provider/model seam；这些可作为后续独立 unit。
- Q3: 迁移/回滚边界是否要求“无感兼容现有本地状态”，也就是不能要求用户清空 IM DB、Gateway session binding、relay dedup、agent config 或 workspace 才能升级？
  A(原话): 不要求，只要用户侧使用完全一致就行，比如某个字段你改位置了，没所谓，但是用户用起来要完全一模一样
  Agent 解读: 本 unit 不要求内部字段位置、内部 protocol 表示、内部持久化形态完全兼容；允许 design 阶段改变内部结构或做必要迁移。验收口径是终端用户和运维者的操作方式、可见结果、失败/恢复表现完全一致。
- Q4: 外部 channel 的 Feishu/shadow 会话是否必须纳入这次“用户用起来完全一样”的回归基线？
  A(原话): 必须纳入
  Agent 解读: 本 unit 的不变性验收必须覆盖 Feishu 私聊/群聊、shadow 会话、未 @ 群消息同步、agent 回复镜像、IM 离线时 Feishu 主路径不受影响等外部 channel 可见行为。
- Q5: 运行中和失败恢复场景是否也纳入用户侧不变性，比如断线重连、Gateway 重启、running 气泡、工具调用状态、权限等待、后台任务完成回复？
  A(原话): 纳入
  Agent 解读: 本 unit 的不变性验收必须覆盖运行态、终态、断线/重启恢复、权限等待、后台任务完成回复等用户可见边界。

## 现状痛点

本 unit 来自架构检查候选 A 与 F 的联合收口：Gateway/IM runtime protocol 已经承载核心产品行为，但这些行为背后的运行期事实分散在多条链路中维护；同时 `personal_assistant/main.py` 作为 composition root 还承担了大量运行期事件翻译、投递上下文、运行态气泡和外部 channel 镜像规则。用户平时看到的是“消息能发、agent 能回、节点能在线、shadow 会话能同步”，但内部结构越浅，后续任何改动越容易让某条用户旅程在边界态上跑偏。

当前必须保住的用户侧行为包括：

- Web IM 用户在内置 IM 中向 agent 发消息，Gateway 经 IM relay 收到消息，agent 回复回到同一会话；重复 relay 不产生重复消息，投递状态最终收口。
- 运维者启动 Gateway 后，IM 中节点按注册和心跳显示在线；IM/Gateway 瞬断、IM 重启或 Gateway 重启后，用户不需要手工清状态或重配 agent，节点和会话仍能恢复到可用状态。
- 外部 channel 用户在 Feishu 私聊或群聊中与 bot 对话，Gateway 保持外部主路径可用；内部 IM 中的 shadow 会话继续按现有规则展示用户消息、agent 回复、群成员显示名和未 @ 群消息。
- worktree / 多 agent 场景下，用户实际使用的 agent workspace 行为保持不变；内部重构不能让 agent 读写到错误工作区，不能让 IM mirror 值改变 Gateway runtime 的实际工作路径。
- 一轮 agent run 的运行态、终态、权限等待、工具调用状态、后台任务完成回复，在 Web IM 和外部 channel 中继续按现有用户可见语义收口，不出现永久 running、重复回复、错误会话投递或丢失最终结果。

痛点不是“某个用户功能现在不可用”，而是这些用户旅程背后的 runtime protocol 与 composition root 过浅：同一条用户可见行为需要多个位置共同解释相同运行期事实。一旦后续继续扩外部 channel、运行态事件或 Gateway/IM frame，改动者需要跨 Gateway、IM、relay、session、observer、外部 channel 与前端可见状态一起推理，风险和回归成本持续上升。

## 目标状态

本 unit 是纯 refactor：用户可见行为完全不变，不新增功能，不改变用户操作入口，不改变用户看到的正常路径、失败路径和恢复路径。

目标是把 A+F 涉及的内部结构收口到更可维护的形态，使后续改 Gateway/IM runtime protocol、relay/shadow 会话、运行态事件和 Gateway composition root 时，变更影响更集中、行为更容易被验证。内部字段位置、内部 protocol 表示、内部持久化形态可以在 design 阶段改变；验收口径只看终端用户和运维者“用起来完全一模一样”。

本 unit 不纳入候选 B/C/D：不重构 frontend user stream/timeline projection，不重构 kernel tool extension interface，不重构 LLM config/provider/model seam。

## 用户侧验收标准（不变性）

下面是回归基线。每条 Scenario 均要求重构后与重构前的用户可见结果一致。

### Requirement: Web IM 对话与 relay 投递行为不变

#### Scenario: 用户在 Web IM 直聊 agent
- **GIVEN** Gateway 已在线，Web IM 中存在一个可用 agent
- **WHEN** 用户在该 agent 的直聊会话发送一条普通文本消息
- **THEN** 用户在同一会话看到 agent 回复，消息顺序、发送者展示、投递状态和完成状态与重构前一致

#### Scenario: 重复 relay 不产生重复用户消息
- **GIVEN** Web IM 中某条用户消息已经被 relay 给 Gateway 并处理过
- **WHEN** 同一逻辑消息因重试或重连再次被投递
- **THEN** 用户不会在会话中看到重复 agent 回复或重复用户消息，最终投递状态与重构前一致

#### Scenario: Web IM group chat 的 agent 选择语义不变
- **GIVEN** Web IM 群聊中有多个 agent 参与
- **WHEN** 用户按现有方式 @ 某个 agent 或发送普通群消息
- **THEN** 被触发的 agent、未触发 agent 的静默表现、群上下文使用方式与重构前一致

### Requirement: Gateway/IM 连接、重连和节点状态表现不变

#### Scenario: Gateway 启动后节点在线
- **GIVEN** Gateway 配置了 IM 服务和至少一个 agent
- **WHEN** 运维者启动 Gateway，并打开 IM 的节点或 agent 页面
- **THEN** 用户看到该节点进入 online，agent 列表和基础状态与重构前一致

#### Scenario: IM 瞬断后 Gateway 自动恢复
- **GIVEN** Gateway 节点已经 online
- **WHEN** IM 服务短暂不可用后恢复
- **THEN** 用户不需要手工重启 Gateway 或重新绑定节点，IM 中节点恢复 online，之后 Web IM 对话继续可用

#### Scenario: Gateway 重启后会话续接
- **GIVEN** 用户已与某 agent 在 Web IM 中建立过上下文
- **WHEN** Gateway 重启后，用户在同一会话继续发送消息
- **THEN** agent 仍能按重启前的会话上下文继续回复，而不是表现为全新空会话

### Requirement: workspace_root 相关用户行为不变

#### Scenario: 本地 runtime 工作区不被 IM mirror 改变
- **GIVEN** IM 中某 agent profile 的 workspace 展示值与 Gateway 本地配置存在差异
- **WHEN** Gateway 同步配置并处理该 agent 的会话、heartbeat 或 cron
- **THEN** 用户侧观察到的 agent 文件读写、会话记忆和 heartbeat/cron 行为仍使用原本应使用的 Gateway runtime 工作区

#### Scenario: 用户在 IM 新建 agent 后可立即使用
- **WHEN** 用户在 IM 中通过已在线节点创建新 agent
- **THEN** 用户看到新 agent 创建成功，随后可与该 agent 对话；Gateway 重启后该 agent 仍存在且可继续使用

### Requirement: 外部 channel 与 shadow 会话行为不变

#### Scenario: Feishu 私聊同步到内部 IM shadow 会话
- **GIVEN** Gateway 配置了 Feishu 私聊 bot
- **WHEN** 用户在 Feishu 1:1 中发送消息并收到 bot 回复
- **THEN** Feishu 对话正常进行，内部 IM 中对应 shadow 会话继续显示用户消息和 agent 回复，发送者展示与重构前一致

#### Scenario: Feishu 群聊 @Bot 触发回复
- **GIVEN** Gateway 配置了 Feishu 群聊 bot，且该 bot 所属 agent 在群聊中按 @ 触发
- **WHEN** 用户在 Feishu 群里 @Bot 并发送消息
- **THEN** bot 在 Feishu 群中回复；内部 IM shadow group 中继续显示群成员消息和 agent 回复，群成员显示名与重构前一致

#### Scenario: Feishu 群聊未 @ 消息只同步上下文
- **GIVEN** 某 Feishu 群聊 agent 的回复策略要求 @ 才触发
- **WHEN** 群成员发送未 @Bot 的普通消息
- **THEN** 内部 IM shadow group 继续可见该消息，Gateway 不因此启动 agent 回复，后续触发时群背景上下文表现与重构前一致

#### Scenario: IM 离线时 Feishu 主路径不受影响
- **GIVEN** IM 服务暂时不可达
- **WHEN** 用户在 Feishu 私聊或群聊中与 bot 对话
- **THEN** bot 仍按现有规则回复用户；IM 恢复后，后续外部消息继续按 shadow 会话规则同步

### Requirement: 运行态、终态和恢复表现不变

#### Scenario: agent 回复运行态正常收口
- **WHEN** 用户发送一条会触发较长 agent 回复的消息
- **THEN** 用户看到的 running 气泡、增量内容、完成状态与重构前一致；回复完成后不会永久停留 running

#### Scenario: 工具调用状态正常收口
- **GIVEN** agent 回复过程中触发一个工具调用
- **WHEN** 工具开始、完成、失败或因 run 终止被收口
- **THEN** 用户看到的工具卡片状态、原因展示和最终状态与重构前一致，不出现永久运行中的工具卡片

#### Scenario: 权限等待与审批结果不变
- **GIVEN** agent 触发需要用户审批的工具调用
- **WHEN** 用户在现有审批入口允许或拒绝
- **THEN** agent run 的继续或终止表现、审批卡片状态、重复点击处理与重构前一致

#### Scenario: 后台任务完成回复回到原会话
- **GIVEN** 用户让 agent 启动一个后台任务
- **WHEN** 主轮结束后后台任务完成
- **THEN** 用户在触发该任务的原会话看到完成回复；Gateway 重启或重放后不出现重复完成回复

### Requirement: 本 unit 不引入新的用户能力或入口变化

#### Scenario: 用户入口保持一致
- **WHEN** 用户按重构前的方式启动 Gateway、打开 Web IM、创建 agent、发送消息、查看 shadow 会话或处理权限审批
- **THEN** 操作入口、可见文案、主要交互流程和结果语义保持一致；用户不需要学习新流程

#### Scenario: 内部结构变化不暴露给用户
- **WHEN** 本 unit 改变内部字段位置、内部 protocol 表示或内部持久化形态
- **THEN** 终端用户和运维者使用产品时看不到行为差异，也不需要手工迁移、清空状态或修改日常操作方式

## 影响范围

本 unit 的用户可见影响范围是 Gateway 与 IM 协作承载的 runtime 用户旅程：

- Node Gateway 与 IM 的持久连接、注册、心跳、重连、下行 relay、配置同步和上行运行态事件。
- Web IM 中的 direct/group relay 投递、幂等、投递状态、agent 选择和会话续接。
- 外部 channel，尤其 Feishu 私聊/群聊与内部 IM shadow 会话同步、reply routing、未 @ 群消息上下文、IM 离线时外部主路径。
- Gateway runtime 中与 run lifecycle 相关的用户可见状态：assistant 气泡、工具调用、权限审批、后台任务完成回复、异常/取消/失败终态。
- workspace_root 对用户可见行为的影响：agent 实际文件读写、session 记忆、heartbeat/cron 读取路径、新建 agent 后的可用性。

明确不属于本 unit：

- 不重构 frontend user stream/timeline projection。
- 不重构 kernel tool extension interface。
- 不重构 LLM config/provider/model seam。
- 不新增新的外部 channel 能力。
- 不改变用户可见的产品入口、配置流程或 IM 页面交互。

## 迁移与回滚策略

本 unit 允许 design 阶段改变内部结构、字段位置、runtime protocol 内部表示或必要的内部持久化形态；但这些变化不得改变用户侧使用方式和可见结果。

迁移策略的用户侧约束：

- 正常升级后，用户不需要为了继续使用产品而清空 IM DB、Gateway session binding、relay dedup、agent config 或 workspace。
- 如果 design 阶段判断必须对内部状态做迁移或兼容读取，应保证用户侧操作与结果仍与重构前一致。
- 如果发现历史脏状态，只能在不改变用户正常使用流程的前提下修复、忽略或兼容；不能把“让用户清空重来”作为正常迁移路径。

回滚策略的用户侧约束：

- 回滚后，Web IM 对话、Gateway/IM 节点状态、Feishu/shadow 会话、workspace_root 相关行为、运行态和终态展示应恢复到重构前语义。
- 若内部状态在重构版本中被迁移，design 阶段必须说明回滚是否需要兼容读旧/新两种内部形态；这属于实现层决策，不在本首文档拍板。
