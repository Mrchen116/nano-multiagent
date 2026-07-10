# feat-349: Skill 自进化 + Agent 策展式 Memory

## 原始需求

> 我要你复刻~/Repos/opensource-hub/self-evolution/hermes-agent的skill自进化和memory逻辑，给本项目加这个特性。下面是我做的一些笔记/Users/czj/Repos/opensource-hub/self-evolution/notes/hermes-agent-features/01-autonomous-skill-creation.md，/Users/czj/Repos/opensource-hub/self-evolution/notes/hermes-agent-features/02-skill-self-improvement.md，/Users/czj/Repos/opensource-hub/self-evolution/notes/hermes-agent-features/03-memory-nudges.md

参考笔记（用户调研产出，描述 hermes-agent 实现细节，供 design 阶段参考）：
- `~/Repos/opensource-hub/self-evolution/notes/hermes-agent-features/01-autonomous-skill-creation.md`
- `~/Repos/opensource-hub/self-evolution/notes/hermes-agent-features/02-skill-self-improvement.md`
- `~/Repos/opensource-hub/self-evolution/notes/hermes-agent-features/03-memory-nudges.md`

> 注：用户原话中"复刻 hermes 实现"是一个**实现保真约束**，交接给 `change-design-author` 处理（hermes 的双层 nudge 机制、后台 review agent fork、计数器阈值、文件格式、安全扫描回滚等均属实现层）。本 spec 的【验收标准】只覆盖用户可观察的行为。

## 澄清记录

- Q1: 这个"skill 自进化 + memory"能力面向哪个产品的用户——Coding CLI、个人助手，还是两个都做？
  A: 两个产品都做。
- Q2: agent 自动创建/更新的 skill 和 memory 怎么生效——后台静默生效 + 事后回显，还是需要用户审批？
  A: 复刻 hermes——后台静默生效，事后给用户一行简短回显，不设审批门；用户事后可自行查看/编辑/删除。
- Q3: skill 和 memory 按 agent 完全隔离（纯复刻 hermes 的 profile 级隔离），还是 memory 里的"用户画像"部分跨 agent 共享？
  A: 纯复刻——每个 agent 完全隔离自己的 memory（含用户画像）和 skill，不跨 agent 共享。跨 agent 共享层等真有痛点再单开 unit。
- Q4: agent 后台沉淀 skill/memory 后，用户在哪、以什么形式知道？
  A: 两个产品都用"轻量系统提示"形式回显（CLI 打印一行系统提示，个人助手在对话流里出现一条 meta 提示），不让 agent 用第一人称发消息。
- Q5: 这个"自进化"能力默认开启吗？用户能不能关？
  A: 默认开启，用户可关——既能整体关，也能分别关 skill 自进化 / memory 自动记录。
- Q6: 用户怎么查看/编辑/删除这些自动产出的 skill 和 memory？
  A: 直接就是文件，用户用编辑器改。IM 前端的可视化管理界面不做（不在本期范围）。

## 用户场景

本特性给 agent 内核加一种"越用越懂"的能力：agent 在和用户长期协作的过程中，能**自己**把零散的经验沉淀下来——把可复用的工作法存成 skill，把关于用户的事实和偏好记进 memory——而不需要用户开口要求。两个产品（Coding CLI、个人助手）都获得这个能力。

### 场景一：agent 自己沉淀一个 skill（Coding CLI）

老王用 Coding CLI 调一个流式渲染的 bug。过程很曲折：他和 agent 一起读了好几个文件、试了两种改法、跑了几轮测试，最后发现关键在于某个特定的处理顺序。任务完成，老王继续干别的。

这一回合结束后，REPL 里多出一行不起眼的系统提示：

```
· 已沉淀 skill: debug-streaming-render
```

老王没被打断，对话也没多出一条 agent 的"邀功"消息。一周后他又碰到类似的流式问题，这次 agent 一上来就走对了路子——因为它读到了上次自己存下的那个 skill。

### 场景二：agent 记住关于用户的事（个人助手）

小张在 IM 里跟自己的个人助手 agent 聊天。几轮下来，他提到自己习惯晚上工作、不喜欢长篇大论的回复、负责的项目叫 X。他没说"请记住这些"。

又聊了一阵，对话流里浮现一条轻量的 meta 提示（不是 agent 发的聊天消息）：

```
· agent 更新了 memory
```

此后小张再开新对话，agent 的回复风格就稳定地偏简洁了，也不用每次重新交代"我是谁、我在忙什么"。

### 场景三：用户发现并修正 agent 学到的东西

小张觉得 agent 最近某个自动沉淀的 skill 有点跑偏。他知道这些东西就是磁盘上的纯文本文件，于是直接用编辑器打开那个 agent 的 skill 文件，改了几行——或者干脆删掉。下次对话，agent 就按修改后的版本走。memory 同理：用户能找到文件、能读、能改、能删。

### 场景四：用户不想要这个能力

有的用户觉得"agent 自动改自己"让人不安。这个能力默认是开的，但用户能关：可以整体关掉自进化，也可以只关 skill 自进化、只关 memory 自动记录。关掉之后，agent 不再自动沉淀任何东西，也不再出现那行回显提示——回到一个"老实执行、不自作主张"的 agent。

### 场景五：多个 agent 各学各的

小张配了两个 agent：一个帮他写代码，一个帮他管日程。写代码的 agent 沉淀的 skill 和它记的 memory，对管日程的 agent 完全不可见，反之亦然。在 agent A 那里教过的事，到 agent B 不会自动生效——每个 agent 有自己独立的一套 skill 和 memory。

### 贯穿所有场景的一条线

整个"沉淀"过程不打断用户：它发生在 agent 回复完用户之后的后台，用户感知到的只有事后那一行轻量提示。agent 不会因为"该写 skill 了"而中途停下来问用户。

## 验收标准

- [ ] 在一段需要多轮协作 / 多次试错才完成的任务之后，agent 会在该回合结束后自动沉淀出一个新的 skill，无需用户主动要求
- [ ] 当某次协作中出现了对已有 skill 的新经验时，agent 会自动更新那个已有 skill，而不是只能新建
- [ ] 用户在对话中透露了关于自己的事实 / 偏好 / 工作习惯后，agent 会自动把它记进 memory，无需用户说"请记住"
- [ ] 每次 agent 自动沉淀 skill 或 memory 后，用户看到一行轻量系统提示告知发生了什么；这条提示不是 agent 的第一人称聊天消息（Coding CLI：REPL 中一行系统提示；个人助手：对话流中一条 meta 提示）
- [ ] 沉淀过程不打断当前对话——agent 先正常回复完用户，沉淀在之后发生，用户不会被中途打断或被要求确认
- [ ] agent 自动沉淀的 skill 和 memory 是用户可直接访问的纯文本文件 / 目录；用户用编辑器修改或删除后，agent 在后续会话中按修改后的内容行事
- [ ] agent 后续会话中确实会用到自己之前沉淀的 skill / memory（体现"越用越懂"——下次遇到类似情境，行为受此前沉淀内容影响）
- [ ] 自进化能力默认开启
- [ ] 用户可以整体关闭自进化能力；也可以单独关闭 skill 自进化、单独关闭 memory 自动记录
- [ ] 关闭后，agent 不再自动沉淀对应内容，也不再出现对应的回显提示
- [ ] 同一用户下的不同 agent，各自的 skill 和 memory 互不可见、互不影响——在一个 agent 处教的东西不会自动出现在另一个 agent 上
- [ ] Coding CLI 和个人助手两个产品都具备上述能力

## 范围与非目标

- **在范围**：
  - agent 内核获得"自动沉淀 / 自动改进 skill"和"自动策展 memory"的能力，复刻 hermes 的机制
  - Coding CLI 和个人助手两个产品都接入该能力
  - skill 与 memory 按 agent 隔离
  - 沉淀后的轻量系统提示回显（两个产品各自形态）
  - 自进化能力的开关（整体 / 分别关 skill、memory）
  - skill / memory 以纯文本文件形式落盘，用户可直接编辑 / 删除

- **非目标**：
  - 不做 IM 前端的 skill / memory 可视化管理界面（用户直接改文件；要做另开 unit）
  - 不做跨 agent 的 memory / skill 共享层（包括"用户画像"跨 agent 共享；等真有痛点再单开 unit）
  - 不做 skill / memory 的版本控制与历史回溯（hermes 本身也没有；用户的"回滚"手段就是直接改文件）
  - 不引入外部 memory provider（向量库、第三方 memory 服务等）
  - 不做自动沉淀内容的事前审批流程（明确选择后台静默生效）
  - 不改变用户手动创建 / 管理 skill 的既有方式（本特性是"自动沉淀"，不替换手动路径）
