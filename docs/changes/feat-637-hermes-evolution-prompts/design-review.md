# feat-637 独立设计审查

## Round 1

### Metadata

- reviewer_target: Codex `/root`，独立 Gate 2 reviewer。未参与本 unit 的需求或设计编写。未派发 subagent。
- review_mode: `full`
- mode_reason: 无历史报告。本轮是首次独立审查，覆盖全部受审材料、实际接线、公开 API、测试及相关历史。
- started_at: `2026-10-23T10:39:15+08:00`
- completed_at: `2026-10-23T10:47:56+08:00`
- duration: `8m41s`
- executed_base: `0404656449cb5c2bab8efbdda9903025bacbafe3`
- validated_at: 下表所列工作区文件的 SHA-256。文件尚未跟踪，不能用 HEAD 代表受审内容。
- effective_base: 与 executed_base 相同。
- effective_through: 下表内容版本。后续实质修改需按 workflow 判断复审范围。
- checkout: `/Users/czj/Repos/nano-multiagent`，`main`。已有大量无关 dirty/untracked 内容。本轮只新增本报告，未修改其他文件，未创建分支或 worktree，未提交、推送或实施。

| 受审文件 | SHA-256 |
|---|---|
| `spec.md` | `21975c6c81d05c6686fea3b3dff95ca2085ec6ac758e6a4fbbf49839b9f69366` |
| `design.md` | `d6f5f3b1ae1c55baebab3a4226b535474f5826982abf8f7963f64b0ef417276d` |
| `prompt-map.md` | `6ece20f1c9d47a24b5ecc16e2d878fbd79bf3dec4c14f0af48502850b044938f` |
| `specs/gateway/agent-capabilities.md` | `27ed567e5422cf9ba8eb1e2e15c42c222d2439123466b2a582c70331ea8ddb35` |
| `M1-evolution-prompts/.gitkeep` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |

### Verdict

**Issues Found — 0 CRITICAL / 1 WARNING。Gate 2 未通过。**

主体方案符合已确认范围。Memory review 的最新持久内容输入尚未闭合。修复 R1-W1 后再复审；本轮不启动修改或实施。

### Coverage 与证据

#### 1. 当前契约及真实产品接线

核对了 [仓库架构](../../../SPEC.md)、[current agent-capabilities](../../specs/gateway/agent-capabilities.md)、[Global 契约](../../specs/gateway/global-agent.md) 及 [change workflow](../../development/change-workflow.md)。current 的 Memory 快照、fork 前缀、独立工具白名单和成功事实调和继续适用。active delta 尚未归并。

实际产品路径为：

```text
Node Configuration.runtime
  → 普通运行分区的 RuntimeSupervisor / DSH initialize
  → ConfigurationScopes / MemoryCuration / SkillCreation
  → KnowledgeRuntime
  → KnowledgeFiles
  → knowledge.changed / knowledge.facts
  → PA KnowledgeUpdates / IM 系统通知
```

- [apps/node/src/configuration.ts](../../../apps/node/src/configuration.ts):69-92 将 `work_mode`、feature、维护周期和 owner Skill root 传给 integration。运行模式与 Skill 存储范围确实是两个字段。
- [apps/node/src/main.ts](../../../apps/node/src/main.ts):87-115 按实际运行分区装配 supervisor、Agent 配置和 binding。
- [integration 组装入口](../../../packages/dsh-integration/src/index.ts):128-129、255-268 安装唯一 `KnowledgeRuntime` 并登记产品 binding。[agent-config.ts](../../../packages/dsh-integration/src/agent-config.ts):94-109、164-172 挂载 feature。
- [KnowledgeRuntime](../../../packages/dsh-integration/src/knowledge/runtime.ts):170-237 确认当前 F4 复用通用 Skill 指令，按 session/kind 去重，未设两个合格 session 的前置门槛。设计对当前缺口的描述成立。
- [KnowledgeUpdates](../../../packages/personal-assistant/src/knowledge.ts):41-69 按真实 fact 调和，并等待运行中的 review 结束。没有写入时不产生成功 fact；单次写入成功后整轮失败，仍可有真实写入事实。设计没有把复盘完成、知识写入和通知送达混为一件事。

#### 2. Hermes 来源与复用

本轮直接读取固定 SHA `3ba2b0787ed3a73ec3b08085ed0137f235209cf4` 的四份远端文件，并重算 SHA-256。四项结果均与 `prompt-map.md`:11-14 一致。

- [background_review.py](https://github.com/NousResearch/hermes-agent/blob/3ba2b0787ed3a73ec3b08085ed0137f235209cf4/agent/background_review.py)：核对两类 Memory 路由、规则提炼、禁止捕获、Skill 优先级和 combined review 的单一归属规则。
- [prompt_builder.py](https://github.com/NousResearch/hermes-agent/blob/3ba2b0787ed3a73ec3b08085ed0137f235209cf4/agent/prompt_builder.py)：核对事实型 Memory 指引及 Skill 不可写时仍不改变知识归属的规则。
- [skill_manager_tool.py](https://github.com/NousResearch/hermes-agent/blob/3ba2b0787ed3a73ec3b08085ed0137f235209cf4/tools/skill_manager_tool.py)：核对工具说明和参数。上游的批量事务、整个 Skill 删除及支持文件 patch 不适合直接复制。
- [curator.py](https://github.com/NousResearch/hermes-agent/blob/3ba2b0787ed3a73ec3b08085ed0137f235209cf4/agent/curator.py)：核对其内容整理与本次 F4 的职责区别。

具名文本块和逐项适配可以指导实施。移除更新压力、收紧未经验证的方法、按 Nano 能力替换读取指令，均有需求依据。支持文件无法读取时跳过替换，符合当前工具能力。上游的 fresh-read 强制检查和 curator 后续整理承诺没有被误写成 Nano 已有能力。

本轮核实的是固定来源及内容。没有把该 SHA 声称为审查结束时仍然最新的远端 HEAD。

#### 3. 用户约束与需求覆盖

已逐项对照首文档的 18 个 Scenario：

| 范围 | 设计判断 |
|---|---|
| Memory 分类、去重、纠正、无学习信号 | 路由及质量规则覆盖；最新持久内容输入缺口见 R1-W1 |
| Skill 提炼、失败方法排除、workaround 条件及清理责任 | `prompt-map.md`:40-82 覆盖；无更新配额，也没有把 Agent 自选方法升级为用户授权 |
| Memory/Skill 单一归属及能力关闭 | 两条 review 不互相代写；保留独立开关和执行白名单 |
| 主 Agent 直接维护及部分失败 | 描述保留单操作、整文件 edit、局部 patch、scope 和部分成功的真实结果 |
| 非 Global F4 的正向、证据不足、手工来源保护及同目标并发 | 专用指令、运行槽、证据筛选、guard 与文件锁构成完整的目标路径 |
| Global | 记录使用后退出 F4；普通 Skill 学习和 Memory 维护仍运行 |

`feat-638` 仍只有需求登记；本设计没有安排跨 Skill 合并、迁移工具协议或整个 Skill 删除。范围无冲突。

#### 4. F4 的完成状态映射与公开 API

**设计解释可接受。它不是额外获得用户批准的决定。** 本轮接受的含义是：读取时冻结两个不同产品 session 的历史；每份历史含有本 session 自有、正常完成的使用过程；读取时没有正在执行的工作或待执行输入。同一 session 的后续轮次仍不增加独立证据数量。这个条件没有将两轮、换窗或两个内部子会话替代为两份证据。

依据如下：

- 锁定的 `@deepseek-ai/dsh-session-query` 公开入口导出 `observeSession`。其 `SessionObservation` 提供不可变 `events`、`cursor`、`inheritedEventCount` 和 header。可以按继承事件数剔除父历史；本仓 [usage.ts](../../../packages/dsh-integration/src/usage.ts):14-15 已使用这一公开能力。
- 锁定的 `@deepseek-ai/dsh-agent` 公开类型提供 `Agent.status`、`Agent.inbox` 及 Inbox 的两个待执行列表。`idle` 本身只表示没有 driver，不能单独当作完成证据。
- 锁定的 `@deepseek-ai/dsh-session` 公开 `turn/end.reason` 区分 `completed`、`aborted`、`error`、`interrupted` 和 `forked`。只有正常完成的实际使用过程符合本设计；冷读取补出的 `interrupted` 和 fork seed 的 `forked` 不能充数。
- 产品 binding 提供 owner、Agent 和 cwd，见 [index.ts](../../../packages/dsh-integration/src/index.ts):68-74。设计已要求核对这些事实，不能因为共享 Skill root 就扩大历史访问范围。
- [feat-446 原需求](../archive/feat-446-skill-view-tool/spec.md):163-168、498-526 要求跨 session、正常可用历史、目标自动 Skill 和不并发。Git 历史 `ef4d3dd2be0e14e00f6225c1a0f176513b771b52^:src/agent/platform/background/skill_batch_review.py`:76-106、165-190 确认旧版两份历史门槛及目标专用提示词。旧加载器只检查文件存在和非空，不能以旧代码本身证明它已正确排除所有未结束会话。

未发现必须新增 DSH API、私有 import 或第二套执行运行时的理由。实施仍须用真实锁定 DSH 验证冷历史、继承事件、待执行 Inbox 和异常结束分支；类型存在不能代替这些验证。

#### 5. 架构、状态与并发

职责分配合适：integration 的 `KnowledgeRuntime` 拥有调度、历史资格和受控运行身份；`KnowledgeFiles` 拥有路径、来源和落盘检查；PA 继续消费成功事实并投递通知。Node/PA 不直接调用 DSH。

复用现有 fork、root 锁、原子替换、usage 及 curator 状态，比新增维护服务更适合本次范围。设计将同目标去重从 session/kind 改为规范化 root/name，避免两个普通会话同时复盘同一 Skill。计数按冻结快照扣除，保留运行期间的新使用。F4 与 F3 的提醒周期分开。guard 在 child 创建时绑定目标，文件锁内再次核对目标和自动来源。以上边界能够指导实施。

`reviewed_session_ids` 的 root 级集合及最近 200 项保留策略来自历史机制；本轮没有要求另建账本。部分写入后失败保留真实 fact，符合当前通知路径。

#### 6. Delta、milestone 与验收

delta 的 canonical target 正确。三个条目均为 ADDED，没有删除或改写 current 的既有 Scenario。知识归属、实际结果和 F4 限制以消费者可观察结果表达。R1-W1 修订后，应继续保证 delta 的去重与纠错承诺有可执行的数据输入。

单 M1 覆盖本次完整交付，未按代码层次机械拆分。目录仅有 `.gitkeep`；未预填任务或进度。无客户端内容或交互改动，不需要 UI 原型及 iOS 专项验收。现有通知结果仍须经真实产品链路观察。

Runbook 使用仓库 E2E 脚本和独立临时目录。`e2e-up.sh`:28-32、113、178-197、225-269 支持从当前 checkout 的构建产物启动临时目录内的隔离栈。配置副本需启用 `memory`、`skill_manage` 和对应 feature，设计已说明。HTTP 消息入口足以驱动本次知识维护旅程。

[knowledge.test.ts](../../../packages/dsh-integration/tests/knowledge.test.ts):80-81、133-137 当前仍在 Global、单 session 下预设 F4 合法 patch。它只能证明既有接线，必须随实施改为非 Global 两个合格 session 的正向路径，并保留 Global 不触发的反向覆盖。设计的验证矩阵已要求这两项。

[knowledge-policy.test.ts](../../../packages/dsh-integration/tests/knowledge-policy.test.ts):11-45 保护 Memory 快照及 fork 继承；67-98 保护失败 review 不消耗普通提醒周期。设计保留这些回归有依据。真实模型正反例、输入、持久化产物和通知记录也已纳入退出标准；fixture 结果不能代替内容质量验收。

### 历史问题闭环

无历史 Round，无 Author Resolution 可核实。本轮首次建立稳定问题 ID。

### Issues

#### R1-W1 — Memory review 没有取得最新持久内容，去重与纠错的数据输入未闭合

- 级别：WARNING，阻断 Gate 2。
- 位置：`design.md`:28-29、96-100、133-134；`prompt-map.md`:58-65。
- 需求：`spec.md`:82-93、123-126；delta 的“知识维护按长期价值与明确归属保存内容”。

设计要求 review 利用上下文中的现有 notes 去重和原位纠正，同时保留父会话的冻结 Memory 快照。它没有在维护指令后附加最新持久 Memory，也没有定义 review 的读取能力。因此，“上下文中的 notes”可能早于最近一次成功的后台写入。

证据链：

1. [memory-curation.ts](../../../packages/dsh-integration/src/features/memory-curation.ts):12-15、25-32 让 fork 继承父快照；没有压缩时不重读文件。[对应回归](../../../packages/dsh-integration/tests/knowledge-policy.test.ts):29-37 明确验证这一行为。
2. [runtime.ts](../../../packages/dsh-integration/src/knowledge/runtime.ts):211-218 只附加维护指令；Memory 路径不读取最新持久内容。[memory 工具](../../../packages/dsh-integration/src/features/memory-curation.ts):17-20 只有 add/replace/remove，没有读取操作。
3. [files.ts](../../../packages/dsh-integration/src/knowledge/files.ts):53-67 在写入时读取当前文件，但不把条目返回给 review；add 直接追加，也不做语义去重。

具体影响：同一长会话内，review A 保存事实 P；父会话未压缩；review B 再处理 P 或用户对 P 的纠正。B 继承的 notes 仍不含 A 的产物。B 无法确认该事实是否已落盘，也无法检查当前完整条目是否已被另一条维护改正。只增加“检查重复”的文字，无法提供缺失的当前状态。Global 长期主会话仍保留 Memory 自进化，因此这不是被 F4 的 Global 禁用规则排除的路径。

必要修改：明确后台 Memory review 如何获得本次维护时的最新 `USER.md` 和 `MEMORY.md`。可在继承历史后的维护输入中附加受控读取结果，保留前台冻结快照与原请求前缀。说明这些内容是当前存储状态，不能作为新授权。无需新增通用文件工具或知识平台。

验证要求：在同一主 session、没有 compaction 的情况下，连续完成两次 Memory review。第二次 review 的真实模型输入须能看到第一次的持久产物。分别覆盖重复事实和明确纠正，核对持久文件没有同义副本或并存的旧事实。前台快照与 fork 前缀的既有回归仍须保持。

未修后果：实施者可能仅替换 assets，保留缺少最新状态的输入路径，却据新提示词或单次样例宣称完成了去重与纠错。

### Recommendations

#### R1-R1 — 用当前配置契约表述运行模式限制

`design.md`:113 提到运行中切为 Global。当前 [configuration.apply](../../../packages/dsh-integration/src/index.ts):477-478 拒绝改变 work mode。建议写清这是 F4 入口及写入时核对的模式条件；本 unit 不需要增加运行模式切换能力。该措辞不阻断本轮，也不要求扩展配置 API。

### 本轮验证与边界

- 已完成全范围静态审查、实际装配入口追踪、公开 exports/type 核对、历史源码核对，以及四份远端来源散列复算。
- 独立检查受审 Markdown 的本地链接和行尾空白，结果通过。单 M1 目录仅含 `.gitkeep`。
- 未运行产品测试、未起服务、未调用真实模型，未声称有产品验收结果。
- 作者记录的全仓 docs_check 六项无关失败保持为已知前提；本轮未重跑，也未修复无关索引，不能记为全仓通过。
- LLM_PROXY `/health=200` 是作者提供的已有检查。当前模型鉴权及真实生成仍未验证，须在实施验收时落实。
- R1-W1 是缺少当前状态输入的设计问题，不是本轮已观察到生产 Memory 重复或错误的事故结论。

### Author Resolutions

作者已核对以下证据并修订设计。此段不改变 reviewer 的 Round 1 结论，也不代表复审通过。

| ID | 处置 | 核对证据 | 修改及验证要求 |
|---|---|---|---|
| R1-W1 | accepted | `memory-curation.ts` 让 fork 继承冻结快照；`runtime.ts` 原维护输入没有最新持久记忆；`files.ts` 只在写入时内部读取。这些路径证实当前输入缺口。 | `design.md` 新增“Memory review 的当前存储输入”：在启动前通过既有 memory root 锁读取当前两份完整文件，作为受控数据追加到继承历史之后；保留原前缀及前台快照，明确禁用、空文件和读取失败语义。`prompt-map.md` 改为使用该数据块去重纠错。验证矩阵新增普通及 Global 主会话无压缩的连续两次 review，检查实际模型输入及最终持久产物。 |
| R1-R1 | accepted | `index.ts` 的 `configuration.apply` 明确拒绝改变 work mode。 | `design.md` F4 流程第 10 步改为调度和写入时核对当前模式；取消及 feature 关闭阻止后续写入。明确本 unit 不新增模式切换能力。 |

本次只改 `design.md`、`prompt-map.md` 并追加本处置记录。首文档、delta 和 M1 骨架保持受审版本。R1-W1 属于实质设计变化，需要独立 reviewer 复审；复审模式由 reviewer 判断。尚未实施或验证产品行为。

### Author Resolution 修订：采用读取工具

2026-10-23，用户要求对照 Hermes 完整机制并修改设计。以下记录取代上表 R1-W1 的修复方案，不改写 reviewer 原判断，也不代表独立复审通过。

- **R1-W1：accepted，方案已替换。** 撤下宿主自动读取并追加 `Current persisted memory` 的方案。Memory review 继承父 Agent 已启用的 `read`，在写入前读取当前两份 Memory 文件。宿主仅提供准确路径。缺少读取工具时不启动；读取失败或不完整时不写入。连续 review 验收检查实际工具结果进入模型输入，不以工具可用替代实际读取。
- **关联设计补齐。** F3 继承读取和搜索工具。已有 Skill 文件的修改增加本轮完整读取检查。F4 仍仅读取及 patch 绑定目标；不通过搜索扩大证据范围。父权限、独立写入链路、前台快照和可见工具前缀保持既定边界。
- **上游适配明确。** 新核对来源固定在 Hermes `bf0203a794a07aac3ff764972ab9087baa4e4f4e`。上游无人值守 Memory patch/remove 会暂存审批；Nano 按已确认需求保留自动纠错，不迁移审批队列。单操作协议、F4 的非 Global 限制和 feat-638 登记范围不变。
- **R1-R1：保留先前修订。** 入口和写入时检查模式，不新增运行模式切换能力。

本轮修改 `design.md`、`prompt-map.md`、本 unit delta，并追加本记录。首文档及 M1 骨架保持原受审内容。这是实质设计变化，Gate 2 仍未通过，须独立复审。尚未修改产品代码或验证产品行为。

### Author 范围修订：恢复 combined review

用户明确要求：“本需求内要补回来”。本条纳入 feat-637，不另建需求，也不改变原 Round 1 的结论。

历史依据：feat-349 设计明确列出三种 review；M6 记录同次复盘调用 Memory 和 Skill 工具。迁移提交 `ef4d3dd2be0e14e00f6225c1a0f176513b771b52` 的父版本仍有两项同时到期时选择 combined 的代码，新 DSH 版本按 kind 分别调度。已查迁移材料未找到明确取消联合复盘的决定。此前作者将两条独立 review 写成保留约束，依据不足，现已修正。

- 首文档新增联合复盘 Requirement 和三个 Scenario，现为 8 个 Requirement、21 个 Scenario。
- 设计恢复统一到期判断、单项／combined 选择及普通复盘运行槽。各自开关、读数和写入权限保留；F4 仍单独运行。
- 提示词映射新增联合指令，去除“combined 不在范围”的表述。delta 与验证矩阵补充同时到期、单项可用、部分成功和取消。
- 审查须覆盖复盘类型记录、Feature 关闭、计数重置、来源事实和 PA 通知；原有单项回归继续适用。

本轮仅修改本 unit 的首文档和设计产物。未改产品代码，未运行产品验收。范围变化及此前实质设计修改均待独立复审，Gate 2 未通过。


## Round 2

### Metadata

- reviewer_target: Codex `/root`，原 R1 独立 reviewer。未参与受审设计编写，未派发 subagent。
- review_mode: `full`
- mode_reason: R1 后恢复 combined，改变普通维护调度、review 类型和生命周期；读取白名单与 Skill 写入检查也有实质变化。首文档、delta 和 M1 范围均已改变，不能仅做 closure。
- started_at: `2026-10-23T11:51:50+08:00`
- completed_at: `2026-10-23T12:00:22+08:00`
- duration: `8m32s`
- executed_base: `0404656449cb5c2bab8efbdda9903025bacbafe3`
- effective_base: 与 executed_base 相同。
- validated_at / effective_through: 下表工作区文件的 SHA-256。受审材料尚未跟踪，不以 HEAD 代替内容版本。
- checkout: `/Users/czj/Repos/nano-multiagent`，`main`。已有无关 dirty/untracked 内容。本轮仅追加本报告，未修改设计或产品代码，未创建分支或 worktree，未提交、推送或实施。
- 历史保全: 追加前报告 SHA-256 为 `7f226c2b88db2d29f878ffb612832fc5b752398e62152ee0e9c88a7f3d66e4d0`。保留 R1 原文及全部作者处置记录。

| 受审文件 | SHA-256 |
|---|---|
| `spec.md` | `69b3f765a1a26ed4a316e758595abc8c186362215e560725af23bd40ebf14710` |
| `design.md` | `cb9aaf4ffa8f13003a98863452114ac1c701014b9fe24fe8a05f182202a6dc29` |
| `prompt-map.md` | `25144f1125e17d442b4ddf74110dd5ee7bf723947cfda8e72507b95be9d73702` |
| `specs/gateway/agent-capabilities.md` | `0856cb6e6d6ad49842e005034a24e5effce9a7dd0bea5edf87f4f08815f0dbcc` |
| `M1-evolution-prompts/.gitkeep` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |

### Verdict

**Issues Found — 0 CRITICAL / 3 WARNING。Gate 2 未通过。**

R1 的两个条目在设计层关闭。新方案仍有三个会使实施走偏的缺口：原生 `skill` 的完整文件读取假设不成立；Memory 读取未完成与计数结算未闭合；combined 没有接入现有轨迹用途契约。本轮不启动修订或实施。

### 历史问题闭环

| 原 ID | Author Resolution | 本轮核对及结论 |
|---|---|---|
| R1-W1 | accepted；最初的宿主附加内容方案已撤下，改为 review 使用继承的读取工具 | **closed，限设计层。** `design.md`:138-148 和 `prompt-map.md`:74-88 已提供真实文件路径、当轮完整读取、缺失与失败区分，以及普通/Global 长会话连续 review 的真实模型输入验收。此方案能提供 R1 所缺的当前内容；不刷新父快照，也不扩大父权限。读取失败的生命周期另见 R2-W2。尚无实现或真实模型结果。 |
| R1-R1 | accepted；不新增运行模式切换能力 | **closed。** `design.md`:173 改为 F4 入口及写入时检查模式，并明确当前配置不允许切换。与 `index.ts`:477-478 一致。 |

### Coverage 与证据

#### 1. 需求、历史与范围

本轮逐项核对 8 个 Requirement、21 个 Scenario。Memory 分类、去重和纠错，Skill 提炼，失败方法排除，workaround 条件及清理责任，知识单一归属，前台部分成功，以及非 Global F4 均继续在范围内。combined 是用户明确新增的范围，不能按旧版“只保留分离 review”的判断排除。

历史依据成立：[feat-349 design](../archive/feat-349-self-evolving-skills-memory/design.md):192、282 明确列出三种复盘；[M6 progress](../archive/feat-349-self-evolving-skills-memory/M6-wire-default-session-metadata/progress.md):65-70 保存同次复盘调用两类工具的记录。迁移父版本 `ef4d3dd2be0e14e00f6225c1a0f176513b771b52^:src/agent/platform/hooks/builtins/self_improvement.py`:245-274 有两项同时到期时选择 combined 的代码。当前 [runtime.ts](../../../packages/dsh-integration/src/knowledge/runtime.ts):148-168、186-218 按 kind 分开调度，确实没有该分支。历史记录证明曾有接线，不代替本次产品验收。

Nano 的单操作协议、自动 Memory 纠错和成功后结算周期是已确认的产品选择。Hermes 的批量事务、整个 Skill 删除、无人值守 Memory 审批未被纳入。feat-638 仍仅登记，不与本次实施混合。

#### 2. Hermes 固定来源

本轮直接读取 `bf0203a794a07aac3ff764972ab9087baa4e4f4e` 下的七个实现文件并复算 SHA-256。结果均与 `prompt-map.md`:20-26 一致。重点核对：

- [background_review.py](https://github.com/NousResearch/hermes-agent/blob/bf0203a794a07aac3ff764972ab9087baa4e4f4e/agent/background_review.py) 的父工具继承与读取白名单。
- [skill_manager_guards.py](https://github.com/NousResearch/hermes-agent/blob/bf0203a794a07aac3ff764972ab9087baa4e4f4e/tools/skill_manager_guards.py) 的本轮路径读取标记及写入检查。
- [file_tools.py](https://github.com/NousResearch/hermes-agent/blob/bf0203a794a07aac3ff764972ab9087baa4e4f4e/tools/file_tools.py) 的完整读取和分页覆盖登记。
- [memory_tool.py](https://github.com/NousResearch/hermes-agent/blob/bf0203a794a07aac3ff764972ab9087baa4e4f4e/tools/memory_tool.py)、[memory_tool_store.py](https://github.com/NousResearch/hermes-agent/blob/bf0203a794a07aac3ff764972ab9087baa4e4f4e/tools/memory_tool_store.py)、[skill_manager_tool.py](https://github.com/NousResearch/hermes-agent/blob/bf0203a794a07aac3ff764972ab9087baa4e4f4e/tools/skill_manager_tool.py) 和 [skill_manager_batch.py](https://github.com/NousResearch/hermes-agent/blob/bf0203a794a07aac3ff764972ab9087baa4e4f4e/tools/skill_manager_batch.py) 的写入与协议边界。

`prompt_builder.py`、`curator.py` 保留 R1 的固定来源判断。本轮没有把它们声称为新 SHA 下已重查的文件，也未将新 SHA 声称为审查结束时仍最新的 HEAD。

新增读取权限与先读后改规则有上游依据。锁内内容一致性和成功写入后读取资格失效是 Nano 自行增加的策略。上游本轮路径标记本身不证明这两项是必要协议适配。独立复杂度判断见下文及 R2-R1。

#### 3. 当前产品装配与权限

重新核对实际组装入口：[Node Configuration.runtime](../../../apps/node/src/configuration.ts):69-92 → [Node 普通运行分区](../../../apps/node/src/main.ts):87-115 → [integration KnowledgeRuntime](../../../packages/dsh-integration/src/index.ts):128-129 → [feature 挂载](../../../packages/dsh-integration/src/agent-config.ts):94-109、164-172 → 知识工具、文件及 PA 事实调和。产品路径不是测试专用实现。

读取工具应复用原生工具及现有 [ToolSelection](../../../packages/dsh-integration/src/capabilities.ts):15-77。设计按“父有效权限与 review 白名单的交集”执行，保留原工具 schema 前缀，并不恢复父 Agent 禁用的 read/glob/grep。这个选择符合架构与授权边界。读取资料不能改变 scope、目标或授权。F4 继续只读取绑定主文档及使用宿主筛选历史。

锁定 DSH 的公开 `tools/result` 提供执行期 canonical `value` 和最终 `content`，可以观察真正返回的结果；不能只按参数或调用成功登记完整读取。原生 read 返回路径、offset、编号行和 totalLines，可以支持分页完整性检查。长行会截断，因此行数齐全也不等于内容完整。设计对此已有要求。原生 skill 的结果与原始主文档存在差异，见 R2-W1。

#### 4. 当前 Memory 与连续 review

`design.md`:140-148 已明确宿主只提供路径，review 自行读取两份当前文件。读取失败不回退到冻结 notes。普通与 Global 都覆盖不压缩的连续两次维护，检查第二次真实请求是否含第一次持久产物。这能验收 R1 的具体风险。

当前 [memory-curation.ts](../../../packages/dsh-integration/src/features/memory-curation.ts):11-15、25-32 和 [knowledge-policy.test.ts](../../../packages/dsh-integration/tests/knowledge-policy.test.ts):11-45 仍保护父快照与 fork 继承。新方案没有要求破坏该行为。Memory 写入仍使用既有锁及原子替换，不声称读取与写入跨模型请求构成事务，也不引入语义去重引擎。

读取失败、不完整及明确不存在已区分，但“未完成”如何参与复盘终态和计数还未定义，见 R2-W2。

#### 5. Combined 调度、取消、计数和来源

以下决策足以指导相应实施：

- 以一次正常前台 `turn/end` 统一计算两项资格。两项均到期且可用时只选一个 combined fork；只满足一项时运行单项。按主 session 的普通运行槽去重，并在启动前重查资格。
- F4 使用独立目标槽，不进入 combined，也不推进普通维护计数。运行中的单项不临时升级。
- 参与类别和启动读数冻结。正常完成后只推进参与类别，保留运行期间的新读数及前台较新的维护点。失败或取消不推进。
- 任一参与 Feature 关闭时取消整个联合 fork，保留已成功写入；另一项后续可单独维护。不增加部分 fork 恢复系统。
- `KnowledgeReview.kind` 可增加 combined；`KnowledgeFact.kind` 保持 memory/skills；联合创建 Skill 的来源仍为 F3。普通写入来源不能因新 review 类型误落为 F1。

[review-readings.ts](../../../packages/dsh-integration/src/knowledge/review-readings.ts):5-13 目前按 Memory 的 turn/start、Skill 的 step/start 读数，并以对应工具的成功结果作为前台维护点。默认周期在 [runtime.ts](../../../packages/dsh-integration/src/knowledge/runtime.ts):203-208 为各 10。用户已接受的“后台正常完成才推进、前台工具成功才重置”继续适用，不要求改为 Hermes 的更早重置时机。

当前取消按 kind 精确匹配，来源也按 kind=skills 判断，见 `runtime.ts`:111-115、239-242。设计已明确改为参与类别和 F3 来源，须由实施验证新的分支，不能仅扩 enum。轨迹记录是另一个真实消费者，现有设计遗漏它，见 R2-W3。

[PA KnowledgeUpdates](../../../packages/personal-assistant/src/knowledge.ts):41-69 按 review ID 合并真实 facts，只检查 review 是否 running，不依赖 review.kind。它能够沿用一份 combined review 的两类更新，并仅通知真正写入的类别。无写入完成不产生成功通知；部分写入后失败仍保留事实。该方向与现有产品通知相容。

#### 6. F4、职责及复杂度

重新对照 F4 目标、模式、证据、去重和写入章节。R1 对两个不同产品 session、当前无运行/待执行输入、正常完成的自有事件的接受仍成立。两轮、继承历史或内部 child 不能充当两个独立 session。Global 不启动 F4，但保留普通和 combined 维护。

目标槽、冻结计数扣除、已处理证据集合、root 锁与真实写入 fact 均沿用原方案。新增 Skill 读取检查不能放宽 F4 绑定 root/name、自动来源和仅 patch 的限制。F4 当前资格仍受 R2-W1 的读取假设影响。

职责仍应集中在 integration：KnowledgeRuntime 管调度、读结果及受控运行身份；KnowledgeFiles 管真实目标、锁和落盘；PA 管事实调和与交付。无需另建审批、通用读取服务或持久读取账本。

锁内一致性有具体使用场景：普通复盘、F4 及其他会话可能修改同一可写 root；整文件 edit/write_file 会覆盖并发变更。但应只实现必要范围，不能将成功写入后无条件重读归因于单操作协议。后者的成本及可选简化见 R2-R1。

#### 7. Delta、M1 和验收

delta 的 canonical target 仍正确。四个 ADDED Requirement 覆盖知识质量、单操作结果、F4 以及 combined；未删除 current 的已有 Scenario。新增后台当前内容和 Skill 读取检查已经投影到消费者行为。三个发现修订后，应同步真实读取资格、计数结算及轨迹影响，不能只改设计正文。

单 M1 仍可覆盖完整交付，目录只含 `.gitkeep`。21 个 Scenario 的数量正确，未预填任务或进度。Runbook 提供隔离目录、受控配置及 IM→Node→DSH→模型→落盘→通知的路径。当前客户端无需重做交互，但“完全不影响轨迹展示”的判断尚不能成立，须由 R2-W3 的接口选择明确。

验证矩阵已覆盖：连续 Memory、父权限、读取失败、Skill 不完整读取、combined 去重/单项回退、取消/部分成功、新活动、F4 正反向和继承约束。还需补充三个发现要求的具体分支。当前 [knowledge.test.ts](../../../packages/dsh-integration/tests/knowledge.test.ts):99-107 已通过真实轨迹 API 验证维护用途与边界坐标，是新增 combined 投影的合适回归位置。

### Issues

#### R2-W1 — 原生 skill 不返回完整 SKILL.md，不能按设计直接取得完整文件读取资格

- 级别：WARNING，阻断 Gate 2。
- 位置：`design.md`:134、152-156；`prompt-map.md`:95-101、119、158；delta:37-40。

设计将 `skill` 的成功结果视为完整主文档，并据此允许 edit/patch、比较读取后的文件版本。它还允许没有 read 的 F3/F4 使用 skill 取得主文档读取资格。锁定 DSH 实际返回的是解析后的 Skill 正文。

证据：

1. `@deepseek-ai/dsh-skill-filesystem@0.2.1-alpha.1` 的 `lib/index.js`:665-703 先解析 YAML frontmatter，再令 `content = parsed.body.trim()`。
2. `@deepseek-ai/dsh-tool-skill@0.2.1-alpha.1` 的 `lib/index.js`:787-792 返回 name、provider、resourceBase 和上述 content。它不返回原始 YAML 头或原文件字节。
3. `@deepseek-ai/dsh-skill` 的 `renderSkillContent` 包装正文及资源目录，不补回 YAML 头。
4. [KnowledgeFiles.skill](../../../packages/dsh-integration/src/knowledge/files.ts):76-92 读取并修改包含 YAML 头的原始 `SKILL.md`；edit 要求完整文档。两种内容不是同一个比较对象。

未修后果：实施若直接比较正文与原文件，合法写入会一直被拒绝；若只凭 skill 成功就登记完整文件读取，则模型没看见的 frontmatter 也能被整文件覆盖。两种结果都不满足 delta 的完整当前文件约束。

必要修改：区分“加载完整 Skill 指令”与“读取完整原始文件”。不要把原生 skill 的正文认作原文件内容。原文件整体验证和改写应取得原生 read 的完整结果；父 Agent 没有该权限时按真实能力跳过对应修改，不自动增加权限。同步 F3/F4 资格、提示词及测试前提。若保留正文级 patch 路径，须明确其可修改范围，不能让正文读取解锁整个文件 edit。

验证：使用带 YAML 头的真实 filesystem Skill，经原生 skill 和 read 分别获取结果，检查写入资格。覆盖无 read 的路径、仅 frontmatter 变化、正文 patch 和整文件 edit；不能用手写“skill 返回原始文件”的 fixture 代替。

#### R2-W2 — Memory 读取未完成没有接入复盘终态，正常结束的 fork 可能错误消耗维护周期

- 级别：WARNING，阻断 Gate 2。
- 位置：`design.md`:113、140-146、228-229；`prompt-map.md`:79、117；current 维护周期契约。

设计规定读取拒绝、失败或无法取得完整内容时不写 Memory，并报告维护未完成。但结算仍按 fork 正常完成推进参与类别。没有定义“工具失败后模型报告未完成并正常停止”如何成为维护失败。

具体路径：combined 已启动，Skill 写入成功；Memory 的 read 被拒绝；模型按 prompt 不写 Memory，并用普通文本报告未完成后结束。原生 fork 可以正常 completed，工具失败本身不等于整轮异常退出。当前 [runtime.ts](../../../packages/dsh-integration/src/knowledge/runtime.ts):222-224 仅按 `result.stopReason === 'completed'` 推进计数；设计新增的运行状态没有补充读取未完成的结算事实。按现方案延续该路径，就会推进两项冻结读数，尽管 Memory 维护未完成。

必要修改：定义并记录读取未完成如何参与本轮 review 的终态和计数结算。不要依靠模型回复中的“未完成”几个字，也不要将原生正常 stop 自动等同于知识维护完成。明确 combined 在上述路径是否整轮未完成，并保留已成功 Skill 写入及其真实通知。无知识增量的正常完成仍可结算；无需强制所有无修改 review 都先读文件。

验证：让真实 DSH fork 接收失败或不完整 read 的工具结果，再正常输出结束。分别覆盖 Memory 单项和 combined 中 Skill 已成功的情况。检查 review 状态、下次到期判断、保留的文件和实际通知。现有“provider 抛错”的失败 fixture 不覆盖这个分支。

#### R2-W3 — Combined 遗漏现有轨迹用途接口，实际装配路径与“不改客户端”范围尚未闭合

- 级别：WARNING，阻断 Gate 2。
- 位置：`design.md`:11-18、117、201、240；现有 trajectory 链路。

设计只扩展 KnowledgeReview.kind 并讨论 PA 的等待路径，却没有处理同一次 fork 的轨迹用途记录。当前每次维护都通过 `withKnowledgeRun` 进入该路径。

证据：

- [runtime.ts](../../../packages/dsh-integration/src/knowledge/runtime.ts):215 将维护 kind 传给 `withKnowledgeRun`。
- [trajectory-runs.ts](../../../packages/dsh-integration/src/trajectory-runs.ts):14、32 将参数与持久 kind 限制为现有类型，没有 combined。
- [product-contracts/trajectory.ts](../../../packages/product-contracts/src/trajectory.ts):26-33 的 `TrajectoryRun.kind` 同样没有 combined。
- [navigation-model.ts](../../../packages/trajectory-ui/src/client/navigation-model.ts):18-19 及 [查看器 boot.jsx](../../../packages/dsh-trajectory-viewer/src/boot.jsx):130 只识别 memory/skills，其余回退到内部 label 或普通执行名称。
- [current agent-work](../../specs/im/agent-work.md) 的“从真实发起位置进入子 Agent 的本次执行”要求从真实发起事实辨认后台用途，不从内部标签或 UUID 猜测。

未修后果：直接传 combined 会遇到类型或持久 schema 不匹配；用某个单项或 unknown 隐式替代，会丢失联合用途，或把 `nano-review:<id>` 暴露为名称。维护可执行并不能证明现有轨迹导航及用途展示正确。

必要修改：在设计中选定 combined 的真实用途投影，列出相应的 producer、持久 schema、公开契约和展示消费者。可以选择最小兼容表达，但不能伪装成单项或依赖不透明 label。按所选方案修正文件范围、必要 delta 和验收；不要求重做页面布局。

验证：经真实 `trajectory/runs` 读到一个 combined fork 的用途、background/fork 状态、发起坐标及本次执行范围；持久恢复后保持。用户看到的用途应准确，不能仅检查 knowledge.facts。

### Recommendations

#### R2-R1 — 缩小成功写入后强制重读的范围

这是可选简化，不计入 WARNING。`design.md`:156-158 要求每次成功写入后清除读取资格。对同一次 review 连续执行两个合法 patch，它会增加一次完整 read，也会消耗当前 16 步限制。Hermes 本轮路径标记没有规定这一失效步骤；Nano 的单操作协议也不要求它。

锁内内容一致性对整文件覆盖有实际价值。建议按动作保留必要检查，或用已成功写入的已知内容更新本轮基线，减少无条件重读。若保留现策略，应将它作为 Nano 的明确取舍说明成本，不能以“复用 Hermes”或“单操作适配”代替理由。此建议不要求新增版本服务或复杂缓存。

### 本轮验证与边界

- 已完成 full 静态审查，含实际装配、公开工具结果、持久 schema、轨迹消费者、历史 combined 分支及七份上游散列。
- 五份受审材料散列与本轮开头一致。独立本地链接、行尾空白检查通过；首文档为 8/21，单 M1 仅含 `.gitkeep`。
- 本轮未运行产品测试、未起服务、未调用真实模型。代码与类型检查是设计可行性证据，不是产品行为通过结果。
- 全仓 docs_check 六项无关失败仍为作者已记录的前提。本轮未重跑或修复，不能声称全仓通过。
- LLM_PROXY 健康检查是已有检查；模型鉴权、真实生成及内容质量仍须在实施验收时验证。

### Author Resolutions — Round 2

作者已逐项核对锁定 DSH 的真实返回值、维护计数路径和轨迹消费者。以下记录仅说明修订，不改变 Round 2 的 Issues Found 结论，也不表示独立复审通过。

| ID | 处置 | 核对证据及修改 |
|---|---|---|
| R2-W1 | accepted | filesystem provider 返回 `parsed.body.trim()`，原生 skill 不含完整 YAML 头。设计和 prompt 改为仅 read 的完整原文件结果授予已有文件修改资格，正文 patch 同样先读原文件；无 read 的 F3 只保留理解及新增能力，F4 不启动。验证补充带 YAML 头的真实 filesystem Skill、无 read、头变化、正文 patch 和整文件 edit。 |
| R2-W2 | accepted | 当前代码仅按原生 stopReason=completed 推进计数；工具失败后正常停机不代表维护完成。新增宿主读取状态结算：Memory 读取已开始或已调用写入时，两份文件须完整或明确不存在，否则 review=error、diagnostic=memory_read_incomplete，单项和 combined 均不推进后台周期。真实成功写入仍通知。无增量且未尝试读取可正常完成。验证包含工具读取失败后正常结束，而非仅 provider 抛错。 |
| R2-W3 | accepted | withKnowledgeRun、轨迹持久 schema、公开 TrajectoryRun.kind 和两个名称消费者均只有原类型。设计同步增加 combined 的 producer/contract/storage/consumer 接线，名称为“记忆与技能复盘”，保留真实发起点、范围及原生状态；增加 IM delta 和 Web 入口／冷恢复验收。产品原生执行状态与知识维护终态分别表达，不伪造原生失败。 |
| R2-R1 | accepted | 额外强制重读并非单操作协议要求。移除无条件失效；本轮以实际成功写入内容更新基线，连续 patch 无须重读。保留锁内比较以发现其他写入；失败不使用未提交内容，结果不确定时重读。不新增持久账本。 |

已同步首文档的联合轨迹可观察结果、design、prompt-map、Gateway delta，并新增 IM delta；M1 仍为一个，骨架不变。首文档仍为 8 个 Requirement、21 个 Scenario。本轮未改产品代码、未运行产品测试或真实界面验收。局部文档检查单独执行，所有实质修订待独立复审。
