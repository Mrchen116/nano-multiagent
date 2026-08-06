# bugfix-509: 群聊后台自进化提示标明 Agent

## Relations

- Related: feat-349, feat-397

## 原始报告

> 群聊中没指定哪一个agent的后台自进化，用户不友好

> 截图：`/var/folders/mf/fxm1x6xs7pbf34h6rnmvjz1c0000gn/T/codex-clipboard-9663515b-413a-43a4-8d4a-4593fb5a99d7.png`

## 澄清记录

- Q1: 只在群聊标明 agent，还是 IM 单聊也统一标明？
  A(原话): 群聊才显示吧
  Agent 解读: 仅群聊中的后台自进化提示增加 agent 归因；IM 单聊和 Coding CLI 都不额外显示 agent 名。
- Q2: 群聊里继续显示为居中的轻量系统提示，只把 agent 名加入文案，可以吗？
  A(原话): 没所谓，注意i18n
  Agent 解读: 呈现形态由 Agent 按现有轻量 system 提示决定；群聊提示必须遵循 IM 的国际化语言，不能硬编码单一语言。
- Q3: `i18n` 是只覆盖这次新增的群聊提示，还是单聊现有的英文提示也一起本地化？
  A(原话): 按你推荐
  Agent 解读: 所有 IM 后台自进化提示都随界面语言显示；只有群聊额外带 agent 名，单聊不增加身份显示。

## 现象与复现

用户在包含多个 agent 的 IM 群聊里协作。某个 agent 完成后台自进化 review 并更新自己的 skill 或 memory 后，聊天流居中出现一条轻量 system 提示，例如：

```text
· background self-evolution review: memory updated
```

这条提示没有来源 agent 的显示名。群里同时存在 `SpecLab Lead`、`SpecLab Product`、`SpecLab Architect` 等多个各自维护独立 skill/memory 的 agent，用户仅凭提示无法判断究竟是哪一个 agent 更新了自己的内容。

同时，这段提示由 Gateway 固定生成为英文；即使用户的 IM 界面语言为中文，群聊和单聊仍看到英文系统文案，没有遵循界面语言。

复现条件：

1. 创建或进入一个至少包含两个 agent 的 IM 群聊。
2. 与其中一个 agent 协作，直至该 agent 的后台自进化 review 完成并更新 skill 或 memory。
3. 观察聊天流中出现的居中 system 提示。

实际结果：提示只说明更新对象，不说明来源 agent，且固定为英文。

期望结果：群聊提示明确显示来源 agent；所有 IM 自进化提示按当前界面语言展示。提示仍是轻量 system 信息，不显示成该 agent 主动发送的聊天气泡。

## 影响范围

- 受影响用户：在 IM 群聊中同时使用多个开启自进化能力的 agent 的用户；单聊用户也受到固定英文文案影响。
- 触发范围：后台自进化 review 实际产生 skill、memory 或两者更新并回显时。
- 用户影响：用户无法把一次更新归因到正确 agent，难以判断后续该查看或修正哪一个 agent 的独立 skill/memory；非英文界面中的固定英文提示也破坏界面一致性。
- 严重度：不阻断聊天和自进化执行，但会误导用户理解后台状态，削弱多 agent 群聊的可解释性与信任感。
- 数据影响：未发现 skill/memory 写入错 agent、跨 agent 共享或数据损坏；当前缺陷位于用户可见通知的身份与本地化表达。

## 根因分析（RCA）

### 直接根因

后台订阅请求已经持有明确的 `agent_id`，但 `self_evolution_review` 的 session-event callback 只接收会话回复上下文和事件内容。Gateway 在回显边界直接把事件格式化为一段英文正文，再向 IM 发送只有 `conversation_id` 与 `text` 的通用 system 消息。来源 agent 身份以及可供本地化的事件语义都没有进入 IM 消息。

IM 将其作为普通 `sender_type=system` 消息持久化；Web 前端遇到 system 消息时只居中输出已存正文，不解析来源 agent，也不经过 i18n 文案映射。因此：

- 单聊尚可由会话上下文推断 agent，群聊则没有唯一可推断主体；
- 中文和英文界面都只能显示 Gateway 生成的同一段英文。

### 原始设计意图与必须保住的不变量

该能力由 `feat-349` 引入。原始需求明确：

- skill 与 memory 按 agent 完全隔离，每个 agent 各自学习；
- 后台 review 完成后只给一行轻量 meta/system 提示；
- 提示不能伪装成 agent 的第一人称聊天消息；
- 后台沉淀不打断当前对话。

本次修复必须保住这些不变量。尤其不能为了获得现成的 agent 头像和名称，简单把提示改造成普通 agent 消息；也不能改变自进化的触发、写入或 agent 隔离行为。

### 引入点与为何未被拦截

- 功能意图由 commit `72801295e69c15ad76d8369fed5d21415abb6549`（`docs(feat-349): add design and reference documents for self-evolving skills and memory`）确立。
- 当前缺陷形态由 commit `dc82efc6ee5334bcba529fd9fa5aa664e410dd40`（`feat(R6): SSE背景事件送达 — BackgroundSessionEventSubscriber + IM system消息`）引入：该提交把提示格式化为英文文本，并以通用 system 消息送入 IM。后续重构移动了代码，但没有改变这一产品语义。

问题能进入系统，是因为 `feat-349` 分别覆盖了“个人助手里显示 meta 提示”和“多个 agent 的 skill/memory 彼此隔离”，却没有覆盖“多个 agent 同处一个群聊时，提示如何归因”这一组合场景，也没有提出 IM i18n 要求。相应测试只断言固定英文字符串和 `conversation_id + text` 消息形态，验证了送达，却没有验证群聊身份或中英文界面表现。

## 修复方向

- 让 IM 自进化提示保留足以表达“来源 agent + 更新对象”的稳定语义，再由 IM 的用户界面按语言呈现；具体消息模型与协议由 design 阶段决定。
- 群聊提示加入来源 agent 的显示名；多个 agent 先后产生提示时，每条都能独立归因。
- 单聊不额外显示 agent 名，保持现有简洁形态；群聊与单聊的提示正文都按 IM 当前界面语言本地化。
- 继续以轻量 system/meta 形态展示，不变成普通 agent 气泡，不进入 agent 对话上下文。
- 保持 skill、memory、skills + memory 三类结果的区分；不改变 Coding CLI 的现有提示。

## 目标状态与验收标准

### Requirement: 群聊自进化提示明确归因到来源 Agent

在包含多个 agent 的 IM 群聊中，每条后台自进化提示都显示实际执行该次 review 的 agent 显示名，同时保留本次更新对象。提示仍以轻量 system/meta 形态居中展示，不显示为 agent 主动发出的聊天气泡。

#### Scenario: 群聊中的 memory 更新显示来源 Agent

- **GIVEN** IM 群聊中存在多个 agent
- **WHEN** 其中 `SpecLab Product` 完成后台自进化 review 并更新 memory
- **THEN** 用户看到的轻量 system 提示同时包含 `SpecLab Product` 和 memory 已更新的含义
- **AND** 用户不会把它误认为其他 agent 的更新或一条普通 agent 消息

#### Scenario: 不同 Agent 的连续更新分别归因

- **GIVEN** IM 群聊中存在多个开启自进化能力的 agent
- **WHEN** 两个不同 agent 先后产生 skill 或 memory 更新提示
- **THEN** 每条提示分别显示自己的来源 agent，用户可以逐条区分

### Requirement: 所有 IM 自进化提示遵循界面语言

群聊与单聊中的后台自进化提示都使用 IM 当前界面语言，覆盖 skill、memory、skills + memory 三类更新结果；不能继续向所有语言界面展示同一段硬编码英文。

#### Scenario: 中文界面显示中文提示

- **GIVEN** 用户的 IM 界面语言为中文
- **WHEN** 任一 agent 的后台自进化 review 产生提示
- **THEN** 提示中的动作和更新对象使用中文；若位于群聊，还显示来源 agent 名

#### Scenario: 英文界面显示英文提示

- **GIVEN** 用户的 IM 界面语言为英文
- **WHEN** 任一 agent 的后台自进化 review 产生提示
- **THEN** 提示中的动作和更新对象使用英文；若位于群聊，还显示来源 agent 名

#### Scenario: 实时到达与重新打开会话一致

- **WHEN** 用户先实时看到一条自进化提示，之后重新打开或刷新该会话
- **THEN** 提示的来源归因、更新对象和语言表达保持一致，不退回无来源或硬编码英文的形态

### Requirement: 单聊与 Coding CLI 保持既定身份呈现

本次只在群聊提示中新增 agent 身份。IM 单聊继续依靠会话上下文确定 agent，不在提示中重复显示 agent 名；Coding CLI 的提示行为不变。

#### Scenario: IM 单聊只做本地化而不重复 Agent 名

- **WHEN** 用户在 IM 单聊中收到后台自进化提示
- **THEN** 提示按当前界面语言显示更新对象，但不额外重复当前 agent 的显示名

#### Scenario: Coding CLI 不受影响

- **WHEN** Coding CLI 中发生后台自进化更新
- **THEN** 其现有提示形态与行为保持不变

## 范围与非目标

在范围：

- IM 群聊后台自进化提示的来源 agent 归因。
- IM 群聊与单聊后台自进化提示的中文、英文界面本地化。
- 新提示的实时展示与历史重载一致性。
- skill、memory、skills + memory 三类更新结果。

非目标：

- 不改变 Coding CLI 提示。
- 不把 system/meta 提示改成普通 agent 消息。
- 不改变自进化的触发条件、后台执行、skill/memory 内容或 per-agent 隔离。
- 不扩展为其他 system 消息的通用改版。
- 不回填或重写修复前已经持久化的历史英文提示。
- 不处理 agent 改名后历史提示是否随之改名；新提示只需在产生时显示正确的当前名称。
