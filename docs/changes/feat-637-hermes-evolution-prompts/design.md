# feat-637: Hermes 自进化提示词与 F4 约束 — 技术方案

> 对齐：[spec.md](spec.md)。状态：用户于 2026-10-23 明确要求直接实施。当时 Gate 2 尚未完成独立复审；当前已通过独立 Round 3，不追溯改写历史。实施与验证见 [M1 记录](M1-evolution-prompts/progress.md)。

## Changelog

## 现状分析

### 涉及范围

| 路径 | 当前职责 | 本次变化 |
|---|---|---|
| `packages/dsh-integration/assets/knowledge/{memory,skills}.txt` | 两条独立后台 review 的指令 | 更新知识质量规则，新增 `combined.txt` 联合指令 |
| `packages/dsh-integration/src/features/{memory-curation,skill-creation}.ts` | 前台工具说明、参数说明和维护指引 | 使用同一质量规则；保留工具协议 |
| `packages/dsh-integration/src/knowledge/runtime.ts` | 原生 fork、工具执行边界、使用事件和 review 生命周期 | 恢复单项／联合复盘选择；放行父 Agent 已启用的读取工具，登记本轮 Skill 读取；增加非 Global 的 F4 专用入口、证据筛选及目标限制 |
| `packages/dsh-integration/src/knowledge/files.ts` | 原子文件写入、来源、使用记录、确定性扫描 | 检查 Skill 先读后改及 F4 写入条件，维护已处理证据及计数 |
| `packages/dsh-integration/src/knowledge/state.ts` | review 与知识更新事实 | 记录联合复盘类型；持久记录 F4 目标、所用证据和跳过原因 |
| `packages/dsh-integration/src/trajectory-runs.ts`、`packages/product-contracts/src/trajectory.ts` | 后台发起事实、持久 schema 和公开轨迹类型 | 增加真实的 combined 用途，保留原生执行坐标与状态 |
| `packages/trajectory-ui/src/client/navigation-model.ts`、`packages/dsh-trajectory-viewer/src/boot.jsx` | 轨迹入口与导航用途名称 | 将 combined 显示为“记忆与技能复盘” |
| `packages/dsh-integration/tests/knowledge*.test.ts` | 知识写入及真实 DSH 进程回归 | 补充拒绝路径、模式差异和并发回归 |

当前 F4 复用通用 Skill prompt。运行时按主 session 和知识类型去重。历史加载没有两个不同会话的门槛。现有测试在一个 session 中调用 20 次后预设合法 patch，无法证明旧 F4 边界。

原生 `skill` 只接收 `name`，返回解析后的指令正文，不含原始 YAML frontmatter，也没有支持文件路径参数。完整原文件必须通过 `read` 取得。`skill_manage` 采用单操作协议。文件层只保证单次写入的原子替换，不保证多个工具调用共同回滚。

### 既有约束

- DSH 只通过公开 exports 接入。复用原生 fork、session query、工具 guard 和存储域。
- Global 运行模式不触发 F4。Skill 的 `global` 存储范围不等于 Global 运行模式。
- 后台 review 继续继承父请求的 system prompt、工具定义及历史。执行权限在 guard 检查，不通过缩减工具定义重建前缀。
- Memory 快照、feature 开关、来源记录、知识更新事实和 PA 通知保持现有语义。
- 只修改本 unit 的设计产物。实施前不覆盖 current spec。

### 可复用能力

| 能力 | 决定 | 原因 |
|---|---|---|
| `policyAsset` 和现有 knowledge assets | 用 | 已有固定提示词加载入口 |
| `KnowledgeRuntime`、`reviewStart`、`reviewIdentity` | 改 | 已拥有后台执行及受控身份，无需另建 Agent 系统 |
| `KnowledgeFiles` 的路径检查、锁、原子写入 | 用 | 可在同一写入边界检查目标和来源 |
| `.usage.json` 与 `.curator_state.json` | 改 | 已有计数、来源及 `reviewed_session_ids` 字段，后者尚未用于 F4 |
| `knowledge.changed` 和 PA 调和 | 用 | 只发布真实落盘事实，已有重放与通知处理 |
| Hermes combined review 与 Nano 旧版三分支 | 恢复 | 用户明确纳入本 unit；同时到期只运行一个 fork |
| Hermes 批量工具与 curator consolidation | 不用 | 批量协议不在范围；内容整理属于 feat-638 |

### 相关历史

- [feat-349](../archive/feat-349-self-evolving-skills-memory/design.md)：建立自进化、来源及隔离约束；§5 明确选择 skill / memory / combined。迁移前 `self_improvement.py` 两项同时到期时使用一个 combined fork。当前 DSH 调度遗漏该分支，本次恢复。
- [feat-446](../archive/feat-446-skill-view-tool/design.md)：定义 F4 目标、证据及去重边界。其确定性 curator 与 F4 是不同流程。
- `refactor-581` 的 `ef4d3dd2be0e14e00f6225c1a0f176513b771b52` 引入当前 DSH 知识维护；旧实现删除前仍保有专用证据门槛和提示词。
- feat-638：内容整理需求另行登记在主 checkout，未纳入本分支；本设计不推进它。

设计基线于 2026-10-23 重新核对。首次提示词核对固定在 `3ba2b0787ed3a73ec3b08085ed0137f235209cf4`。随后核对 Hermes `HEAD/main` 为 `bf0203a794a07aac3ff764972ab9087baa4e4f4e`，补查后台工具继承、读取检查及 Memory 写入链路。补查的七个实现文件与首次基线内容一致。固定来源和散列见 [prompt-map.md](prompt-map.md)。不能从提示词相同推断完整机制相同。

## 架构总览

保留前台、对话后维护和 F4 三类路径。对话后维护恢复 Memory / Skill / combined 三种选择。前台工具和 F3 使用通用知识质量规则。F4 使用独立的目标技能复盘指令，运行时额外检查模式、来源、证据及写入目标。

```text
前台任务 ── memory / skill_manage ─────────────┐
已完成对话 ── 到期检查 ─ 单项或 combined ─────┤
                                             ├─ KnowledgeFiles ─ facts ─ PA 调和
Skill 使用 ─ 使用记录 ─ 非 Global F4 检查 ────┤
                         └─ 专用 fork + guard ┘
```

Global 模式仍记录 Skill 使用，也仍运行已启用的 Memory、普通 Skill 或 combined review。它在 F4 调度入口退出。内容质量改善不依赖 F4。

## 关键决策

**直接复用适用的上游段落，仅改写能力和策略不同的段落。**

复用单位是具名文本块和明确的句子，不复制整个 Python 文件。保留固定 SHA、内容散列及差异理由。没有更新配额；没有足够依据时允许不修改。来源注记仍由 Nano 的持久化逻辑保存。

**保留 Nano 的工具协议。**

不增加 `operations[]`、整个 Skill 删除或跨调用事务。局部改动使用 `patch`；`edit` 仍是整文件替换。说明文字必须准确区分两者。复用 Hermes 的读取流程，以 DSH 的 `read` 读取 Memory 和 Skill 支持文件。读取工具不可用时跳过依赖该读取的修改。

**复用 Hermes 的工具权限和先读后改机制。**

后台执行范围取父 Agent 有效权限与本类 review 白名单的交集。父 Agent 禁用的工具不能在后台恢复。保留读取、搜索及知识写入工具；不放行通用文件写入、终端、发消息或委派工具。后台修改已有 Skill 文件前，检查本轮是否完整读取过同一文件。使用公开工具事件，不修改 DSH。

**保留 Nano 已确认的 Memory 自动纠错策略。**

Hermes 对无人值守的 Memory patch/remove 暂存审批提案。Nano 继续使用受控 `memory` 工具自动 add/replace/remove，不引入审批队列。两者策略不同，不能声称完整复制上游。现有文件锁和原子写入继续有效；读取工具本身不保证语义去重，也不构成跨模型调用的事务。

**F4 使用专用指令和执行限制。**

新增目标 asset `assets/knowledge/skill-batch.txt`。不再把通用“创建或改善技能库”指令追加到 F4。工具定义仍继承父请求；guard 只允许读取绑定目标主文档及对该目标执行 `skill_manage action=patch`。文件层在锁内再次核对真实 root、名称、自动来源和存在状态。

**保持原跨会话门槛，不为 Global 发明替代证据单位。**

非 Global 至少需要两个不同 session 的有效历史。排除正在运行、等待执行、无完成记录、无法确认归属、记录不可读及已处理的会话。仅采用各 session 自有事件，不能把继承的父历史重复算成新证据。判断同一问题是否重复发生仍由模型完成；代码只强制数量、来源和范围，不能宣称代码已验证语义。

DSH 的 session 可再次接收输入。这里的历史证据在读取时冻结；没有永久结束标记。筛选使用原生公开的执行状态、Inbox 和 `turn/end`，要求该历史会话当前没有运行或待执行输入，且包含正常完成的使用过程。同一 session 以后继续运行，也不会成为第二份 session 证据。此映射是设计解释，须在独立设计审查中核对其与原需求的相容性；不得把单个 session 的两轮作为通过条件。

**同一目标只保留一个排队或运行中的 F4。**

在现有 `KnowledgeRuntime` 内，以规范化 writable root 和 Skill name 作为 F4 去重键。不要只按触发 session 去重。同一目标在多个普通会话、多个 Agent 中出现时，共用该运行槽；不同目标不混为一个目标。沿用本节点普通运行分区的现有 owner，不新增分布式调度系统。

**默认一个 M1，完整交付本次范围。**

提示词、F4 边界及验证共同形成一个可验收结果。无需按代码层次拆多个 milestone，也无需为每个验证步骤创建 worktree。

## 接口与数据流

### 单项与联合复盘调度

在现有 `KnowledgeRuntime` 中统一处理前台正常 `turn/end`。Feature 仍独立登记和撤销能力，但不分别启动两个普通复盘。一次事件使用同一组读数，分别计算 Memory 和 Skill 是否到期，再检查开关及所需工具。两项可用且到期时选择 combined；只有一项时选择对应单项；均不满足时跳过。

普通 review 按主 session 共用一个排队／运行槽。重复监听通知不能重复启动。任务真正启动前重新检查有效配置和读数；已运行的单项不临时扩为 combined。运行期间的新读数保留，在后续正常触发时检查；不立即自循环重试。F4 保留目标级运行槽，不参加该选择，也不消耗普通维护计数。

combined 使用一个原生 fork、一个 review ID 和一份联合 prompt。工具范围是本次两类维护工具的并集，再与父 Agent 的有效权限取交集。Memory 当前文件读取、Skill 本轮读取检查和各自写入 scope 均照常生效。一次联合复盘不使单操作工具变成事务。

原生 fork 正常结束且宿主未记录 Memory 读取未完成时，才按启动时冻结的读数推进本次参与类别的重置点。未参与类别不变，运行期间的新活动不丢失；不得覆盖前台维护已推进的更晚重置点。失败、取消或 Memory 读取未完成均不推进后台重置点。无须修改知识且未尝试读取 Memory 文件时，也可以正常完成复盘；成功事实仍只来自实际写入。

任一参与 Feature 关闭时，取消整个联合 fork，并阻止该能力的新写入。已成功写入和真实事实保留。另一项保持启用，不被关闭；后续正常触发时按剩余条件选择单项。继续使用现有取消路径，不新增部分 fork 恢复机制。

`KnowledgeReview.kind` 增加 `combined`，活动运行保存本次参与类别及冻结读数。`KnowledgeFact.kind` 仍只取 `memory` 或 `skills`，不新增 combined 写入事实。Skill 在联合复盘中的创建来源仍为 F3。检查 review 查询、取消、恢复和 PA 等待路径对新类型的兼容；通知按各条真实 fact 调和，不按复盘类型虚构两类更新。

### 提示词装配

`memory.txt`、`skills.txt`、`combined.txt` 与 `skill-batch.txt` 各自形成完整 review 指令。combined 不拼接两份包含排他写入限制的单项 prompt。共用规则保持同一语义，可由小型内部文本片段复用；不新增可配置的提示词框架。前台说明使用精简版本，不重复注入整份后台 prompt。

维护指令只追加在原生 fork 的历史之后。工具可见前缀保持父请求原样。以下白名单限制实际执行，且必须再与父 Agent 的有效权限取交集。沿用现有审批及路径策略；白名单不覆盖其拒绝结果。

| 路径 | 可执行工具 | 写入边界 |
|---|---|---|
| Memory review | `memory`、`read`、`glob`、`grep` | 仅由 `memory` 修改本 Agent 的持久记忆 |
| F3 Skill review | `skill`、`skill_manage`、`read`、`glob`、`grep` | 仅由 `skill_manage` 修改已配置的可写 scope |
| Combined review | `memory`、`skill`、`skill_manage`、`read`、`glob`、`grep` | 分别通过两类知识工具写入各自合法范围 |
| F4 | `skill`、`read`、`skill_manage` | 读取只限绑定目标 `SKILL.md`；写入只限该目标的 patch |

combined 的两项资格分别按下列条件检查；只有一项满足时运行该单项。

不注入父请求没有的工具定义。Memory review 缺少 `read` 或 `memory` 时不启动，记录原因，不消耗维护周期。F3 缺少 `skill_manage` 时不启动；缺少 `read` 时可用 `skill` 理解现有指令、创建新 Skill 或新增支持文件，但不能修改任何已有文件。F4 缺少 `read` 或 `skill_manage` 时不启动；`skill` 的正文不能代替原文件读取。`glob`、`grep` 只辅助发现；结果不能替代完整读取。

Memory/F3/combined 的读取继承父 Agent 的文件访问权限，不新增文件系统授权，也不把产品 binding 描述为文件系统沙箱。读到的文件只是资料，不能改变写入 scope、维护目标或用户授权。F4 不用搜索发现其他历史；跨会话证据仍只由宿主筛选后提供。

前台 Memory 写入前同样先用获准的 `read` 读取 workspace 下 `.nanoassistant/memory/USER.md` 与 `MEMORY.md` 当前全文，避免冻结快照缺少后台已保存内容而重复追加；仅 read 明确确认不存在时视为空内容；权限拒绝、其他读取失败或未读完整时跳过。此处为操作指引，不新增前台硬检查、快照刷新或写入协议。前台回复消息不构成进入后台 review；用户只允许后续维护时，同一执行不在回复后自行继续知识写入。

### Memory review 的当前存储输入

本节同时适用于 Memory 单项和 combined。前台冻结快照不承担后台维护的当前状态输入。宿主在维护指令中提供本 Agent 的 `USER.md` 和 `MEMORY.md` 准确路径，不附加文件内容。模型在准备写入前调用 `read`，完整读取这两个文件，并以工具结果核对重复和纠正。继承 notes 只能提供历史背景，不能代替本次读取。

路径由现有 `KnowledgeFiles` 的 workspace/root 解析产生，使用结构化数据附在指令之后。不存在的文件按空内容处理；只有明确的文件不存在结果可作此判断。权限拒绝、其他读取失败或内容截断不等于空文件。能分页时继续读取；仍不能取得完整内容时不写入，并说明本次维护未完成。沿用现有 review 取消、失败及步数限制，不增加重试循环。

本条是模型操作流程，不宣称 Hermes 对每次 Memory 写入都设有强制读取检查。Nano 不新增 Memory 专用读取工具，也不使用宿主注入内容作为读取失败的后备路径。真实模型验收必须证明写入前收到本轮当前文件的读取结果，不能只验证白名单包含 `read`。

`memory` 保留现有 add/replace/remove。写入仍在文件锁内读取当前文件并原子保存。读写之间可能有并发变更；替换失败时读取当前状态再判断，不宣称整个 review 是事务。上游另有逐字去重和审批逻辑，本次不把它们描述成 Nano 已有保证，也不增加语义去重引擎。

连续维护验证：同一主 session 内，review A 保存事实 P；不压缩、不重建父会话，等待 A 完成后启动 review B。分别让 B 处理重复的 P 和对 P 的明确纠正。B 写入前的真实模型请求须包含本轮 `read` 返回的 A 持久产物。最终文件分别保持单份 P 或只保留纠正后的事实。普通模式与 Global 模式均覆盖。前台快照和 fork 前缀保持原回归通过。

### Memory 读取结果与维护终态

原生 fork 的 `completed` 只表示模型正常结束，不直接表示知识维护完成。宿主在本轮记录两份指定 Memory 文件的读取状态，使用公开工具结果，不解析模型结尾文字。此状态仅用于当前 review，最终原因写入已有 `diagnostic`，不新增公开工具。

初始状态为未尝试。首次对指定 Memory 路径调用 `read` 后，开启本轮 Memory 读取结算。每个文件记录未读、未完成、完整或明确不存在。成功且完整的结果记为完整；分页只有合并覆盖完整内容后才满足。明确不存在记为已确认空文件。拒绝、其他错误、行内截断及未补完分页记为未完成。允许本轮稍后成功读取清除此前失败，但不自动重试。仅读取 Skill 或其他资料不改变此状态。

结算规则：

- 没有尝试读取两份 Memory 文件，且没有 Memory 写入调用时，可按无增量完成，无须为完成 review 强制读文件。
- 一旦尝试读取其中一个文件，或调用 Memory 写入工具，结束时必须确认两份文件均完整或明确不存在；否则本轮维护未完成。
- 原生 fork 正常结束但上述条件不满足时，`KnowledgeReview.status` 记为 `error`，诊断代码为 `memory_read_incomplete`。Memory 单项和 combined 都不推进任何参与类别的后台重置点。combined 已成功写入的 Skill 及其事实保留，PA 仍据事实通知。
- 原生失败或取消保留相应终态。原生正常结束且读取条件满足时，沿用正常结算；不要求实际写入才能结算。后续在正常触发点重试，不立即循环启动。

本规则区分维护结果与模型执行结果。轨迹仍如实保留原生 fork 的执行状态；不得把模型正常结束伪造成原生错误。维护未完成由知识 review 的状态及诊断表达。

### 后台 Skill 的先读后改检查

复用 Hermes 的“本轮完整读取才允许修改”规则，适配 DSH 工具结果。`KnowledgeRuntime` 在 child 创建时建立 review 专属读取记录，通过公开 `tools/result` 事件接收成功结果。记录不继承父会话，不跨 review 复用，结束或取消时释放。

只有原生 `read` 返回完整原文件，才取得该真实路径的读取资格。`skill` 返回的是解析正文，可用于理解技能，但不登记原文件读取资格。即使仅改正文，也统一先读原文件；本次不增加另一套正文级写入权限。这样 YAML 头、正文和支持文件使用同一检查规则。

核对 `read` 的实际结果路径及完整内容，不能只按参数、Skill name 或成功标志判断。分页必须覆盖同一内容版本的全部行；以受控目标文件内容核对，不只检查行数。字节截断、行内截断、失败结果、搜索片段及目录列表均不能取得完整读取资格。父 Agent 未启用 `read` 时跳过已有文件修改，不调用 shell 或宿主内容注入绕过。

写入入口检查本轮读取资格：`edit/patch` 对应包含 YAML 头的完整 `SKILL.md`；覆盖已有支持文件的 `write_file` 和 `remove_file` 对应该支持文件。检查在既有路径校验和文件锁内完成。目标与本轮已知内容不一致时拒绝修改并要求重读。创建新 Skill 或新支持文件不要求读取不存在的文件；锁内发现文件已存在时按已有文件规则处理。

成功写入后，用本次实际落盘且由该调用确定的完整内容更新本轮基线。连续 patch 不要求无条件重读。删除成功后移除该路径记录。写入失败不把模型请求中的内容作为已提交基线。若写入结果不确定，清除该路径资格并要求重新读取。基线只在本轮内存中保存，不新增版本服务或持久账本。

锁内内容比较用于避免覆盖其他会话或其他复盘的新修改。这是 Nano 的额外检查，不是 Hermes 路径标记的原样复制。移除“每次成功写入后强制重读”的额外规则，减少无必要的工具调用。
这项检查仅作用于后台 review。前台保留先读后改指引，不声称新增同等硬检查。读取资格检查与 F4 目标、来源、动作检查同时生效；任何一项不通过，都不写文件、不发布成功 fact。实现使用现有工具事件、guard 和 `KnowledgeFiles`，不新增公开工具协议或持久读取账本。

### F4 调度与证据

1. 成功使用 Skill 后，沿用 call ID 去重和使用计数。Global 模式在记录使用后退出 F4 路径。
2. 非 Global 检查 feature、知识维护开关、自动创建来源和 20 次使用门槛。只接受工具可写 root 内的现存目标。
3. 按目标键取得运行槽。冻结计数和引用快照。同一目标已有任务时只保留新使用记录，不创建第二个 fork。
4. 从最多 60 条引用选取不同 session，最多读取 20 个候选。通过公开 `sessionQuery.observeSession` 读取，核对产品 binding 的 owner、Agent 和 workspace。共享 root 不扩大历史访问权限。
5. 排除不合格及已处理证据。保留正常完成的使用过程和工具结果；按事件边界限长，单 session 最多 20,000 字符，总计最多 100,000 字符。截断后缺少关键使用或结果的记录不计入两份门槛。不可读的单条记录不能中断所有候选的筛选。
6. 不足两份时记录跳过原因，不启动模型、不重置计数、不记为已处理。后续正常使用或相关会话完成时可再次检查，不立即自循环重试。
7. 合格后启动原生 fork。工具 guard 在子 Agent 创建时就绑定目标，避免 child ID 尚未回填时出现权限空档。指令包含真实目标、已筛选的证据 ID 和事件；历史内容标为事实，不能提供新授权。
8. fork 接受后，在文件锁内扣除本轮冻结的使用计数，不抹掉快照之后的新使用。启动失败不扣除。F4 运行失败沿用旧设计的下次累计再触发策略，不立即重试。
9. 成功完成后，把实际提供的证据 ID 加入现有 `reviewed_session_ids`，按原机制保留最近 200 个。模型判断无需修改也是完成复盘；不能因此虚报知识更新。失败或取消不标记已处理。
10. 所有退出路径释放目标运行槽。新使用记录仍保留。取消或 feature 关闭后，尚未完成的 F4 不得继续写入。F4 调度入口与写入入口均核对当前配置不是 Global；现有 `configuration.apply` 不允许修改 work mode，本 unit 不增加运行模式切换能力。

F4 不推进普通 F3 的 review 周期；两者的触发与计数分开。F4 读取目标 Skill 也不能再次构成前台使用证据，触发递归复盘。

### 写入与状态

不修改公开 `skill_manage` schema 的动作或数据字段。给现有字段补充准确描述。F4 的目标约束来自宿主运行上下文，不接受模型传入来源、运行模式或目标 root。

文件写入前检查：动作必须为 `patch`；名称和 scope 解析后的 root 必须与绑定目标相同；目标仍存在且为 F3/F4 自动来源；`old_string` 必须唯一匹配。拒绝 `create/edit/write_file/remove_file`、其他技能、其他 root 和手工来源。拒绝发生时不得落盘，也不得发布成功 fact。若同名原生 Skill 解析到别的路径，停止本次修改，不把另一份文档当作目标内容。

现有 review 记录增加可选的 `source`、`target`、`evidenceSessionIds` 和 `skipReason`。旧记录缺字段仍可读取。事实记录继续只描述真实成功写入。`.curator_state.json` 继续由现有 root 锁串行读改写，保留 `last_scan_at`，不覆盖确定性扫描状态。保留历史 root 级已处理集合，本次不迁移为另一套账本。

多个调用部分成功时不回滚已成功文件。报告成功、失败和未完成部分。重试前重新读取当前内容。F4 已写入但随后失败时，同样保留真实 fact，不把复盘失败等同于写入撤销。

### Combined 的轨迹用途

一次 combined fork 对应一条真实发起记录。沿用 `withKnowledgeRun`，将其参数、`nano_trajectory_runs` 的持久 schema 和公开 `TrajectoryRun.kind` 同步增加 `combined`。保留既有 `tool/memory/skills/unknown` 值；旧记录可继续读取，不把 combined 存成某个单项或 unknown。

producer 直接记录 `kind=combined`、`delegation=background` 及真实原生 fork provider。发起坐标、开始／结束范围和原生状态仍由现有 start/end 观察产生。通过既有 `trajectory/runs` 返回，不从 `nano-review:<id>` 推断用途。存储层只扩可接受值，不重写旧轨迹或复制会话历史。

`navigation-model.ts` 的入口名称与查看器 `boot.jsx` 的导航名称统一显示“记忆与技能复盘”。名称仅表达用途，不代表两类知识都已更新；实际更新仍看知识事实。消费者必须同时发布支持新值的版本，不承诺旧客户端能显示新用途。

局部文案对照与体验边界：

| 真实用途 | 发起位置与子执行导航名称 | 保留的相邻信息和操作 |
|---|---|---|
| Memory | 记忆整理 | 原生 fork／后台标识、执行状态、进入与返回 |
| Skill | 技能复盘 | 同上 |
| Combined（本次新增） | 记忆与技能复盘 | 同上；只有一个入口，进入同一联合执行范围 |

本次只补现有控件的用途映射，不新建页面、布局或交互。当前对照依据是上述两个消费者代码；尚未取得本次真实画面，不能声称视觉验收通过。实施验收在 Web IM 的现有轨迹入口检查名称、单一入口、进入／返回和刷新回父轨迹后从持久入口重入相同执行范围。无需另做整页原型或 iOS 专项交互验收。

## 契约层增量 (delta-spec)

目标为 [Gateway delta](specs/gateway/agent-capabilities.md) 和 [IM 轨迹 delta](specs/im/agent-work.md)。前者覆盖知识质量、读取结算、工具结果、联合复盘及 F4；后者补充联合复盘的真实用途及执行入口。现有快照、fork 前缀和知识调和条目保持不变。实施验收后再归并。

## 风险与回退

- Prompt 不能保证模型永不误判。用真实输入和持久化产物验收，不能用字符串命中证明行为正确。
- 已冻结 Memory 在原会话内不会立即刷新。纠正后的使用效果在新会话或既有压缩刷新点检查。
- 严格筛选会使部分 F4 跳过。这是证据不足的结果；不能通过放宽成单会话多轮来提高触发率。
- 单次成功写入后运行失败，可能留下有效的部分结果。沿用实际事实通知，不声称事务回滚。
- 运行版本回退仅撤回本次代码和 assets，不批量撤销用户知识。新增可选 review 字段不改变旧字段。没有存储迁移或批量重写。

## Runbook for Reviewer

**Review 驱动方式**：使用真实 Web IM 调用的会话及消息接口驱动隔离 IM → Node → DSH → provider → 知识写入 → 通知链路。轨迹用途文案通过 Web IM 现有轨迹入口实测，核对一次联合执行的入口、名称、范围及刷新后从持久入口重新进入。DSH fixture 测试只证明执行边界，不替代真实模型的内容质量验收。不新增页面布局；无需 iOS 专项验收。

使用一个专用临时运行目录，复用本次实施 checkout。不要启动或停止用户正式实例。按照 [worktree runtime 契约](../../development/worktree-runtime.md) 保存并停止自己启动的进程。

| 服务 | 停止命令 | 启动／构建命令 | 健康检查 |
|---|---|---|---|
| 隔离 IM、Node 及其 DSH 子进程 | `./scripts/e2e-down.sh --wt "$NANO_637_RUN"` | `pnpm build`，然后 `./scripts/e2e-up.sh --wt "$NANO_637_RUN"` | 加载该目录 `.e2e-ports.env`；`curl -fsS "$IM_URL/health"`；核对 `/im/v1/nodes` 中测试 owner 的节点 online |

`NANO_637_RUN` 由本次验收用 `mktemp -d` 创建，只创建一次。启停脚本失败也执行 down。E2E 默认配置来自 `config/e2e/gateway.yaml`；测试账号由启动脚本建立。验收配置副本显式启用 `memory`、`skill`、`skill_manage`、`read`、`glob`、`grep` 及两个 feature，分别准备普通 Agent 和 Global Agent，不修改模板或生产配置来加速试验。

通过 `/im/v1/auth/login` 获取隔离用户凭据；使用 `/im/v1/conversations` 及 `/im/v1/conversations/:conversation_id/messages` 建立和发送测试输入，再读取同一消息接口的结果。请求体复用现有 [IM 黑盒客户端](../../../tests/e2e/critical_paths/_im_client.py) 的认证、会话和消息接口；当前 TypeScript IM 不提供 `/openapi.json`。保存消息 ID、原生 session ID、review ID 和脱敏后的知识差异；不提交 token、原始私有日志或运行数据库。

**验收前置**：本地 Node/pnpm、仓库 E2E 脚本、隔离测试账号、LLM_PROXY。2026-10-23 已确认本机代理 `/health` 返回 200，默认模型在仓库无密钥配置中声明为 `deepseek:deepseek-v4-flash`。尚未验证当前模型鉴权及真实生成成功；健康检查不等于模型可用。实施验收前需验证一次正常回复；若不可用，记录资源缺口，不用 fixture 替代质量验收。无外部业务对象、Feishu 账号或硬件需求。

### 验证覆盖

| 组 | 输入与观察 | 退出条件 |
|---|---|---|
| Memory | 长期画像和环境事实、重复表达、明确纠正、普通闲聊 | 归属正确、去重、旧事实被替换；无信号可无写入；新会话使用正确知识 |
| Memory 连续维护 | 普通及 Global 主 session 不发生 compaction，连续两次 review；分别输入重复事实及明确纠正 | 第二次写入前的模型请求含本轮 read 返回的第一次持久产物；最终文件无重复或新旧冲突；前台冻结快照和继承前缀保持原行为 |
| 读取权限 | 父 Agent 禁用 read、空工具集合、下游拒绝、明确不存在的 Memory 文件、其他读取错误 | 不恢复禁用工具，不注入新 schema；不能读完整内容时不写入；不存在与读取失败区分处理；不通过宿主注入绕过 |
| Skill 读取检查 | 真实 filesystem Skill 带 YAML 头；分别通过 skill/read 加载；无 read、仅头变化、分页不全、行截断、连续 patch、整文件 edit、支持文件覆盖 | skill 正文不授予原文件资格；原生 read 完整后可改；头变化拒绝旧基线；连续已知成功 patch 无须重读；有效内容保留 |
| Memory 未完成结算 | 真实 DSH fork 收到拒绝／失败／不完整 read 后正常输出；单项及 combined 中 Skill 已写入；随后读全恢复、明确不存在、无增量不读 | 未读全时知识 review=error，不推进参与类别计数；原生轨迹仍记真实 stop；已写 Skill 与通知保留；读全或确认不存在可正常结算，无增量不强制读取 |
| Combined 轨迹 | 真实 trajectory/runs、冷恢复及 Web IM 发起点／子执行导航 | 一个 kind=combined 的 background fork，真实发起坐标与执行范围；用途显示“记忆与技能复盘”，不暴露内部 label 代替名称；刷新后可进入同一次执行 |
| Skill 质量 | 已验证的新方法、失败尝试、临时新建 worktree、Agent 自己的选择 | 原位更新既有技能；失败不变可靠流程；保留条件和清理责任；不伪造用户要求 |
| 前后台一致 | 同一任务纠正分别经过前台与后台，包含部分写入失败 | 完整规则单一归属；按实际成功结果报告 |
| F4 正向 | 非 Global、两个不同会话、同一重复问题、自动目标 | 仅目标 patch；真实来源和通知；证据完成后去重 |
| F4 拒绝 | 单会话 20 次、未完成会话、缺失历史、已处理历史、手工来源、错目标、错 root、禁用、Global | 无越界写入；Global 不启动 F4；普通 review 仍可执行 |
| F4 并发与失败 | 两个会话同时越线、运行中新增使用、启动失败、运行失败、重启 | 同目标不重叠；后续使用不丢失；计数和已处理状态符合设计；事实反映实际落盘 |
| 联合调度 | 两项同时到期、各自单项到期、工具缺失、关闭一项、重复事件；普通及 Global 模式 | 同时到期只有一个 combined fork；单项不等待另一项；未参与类别计数不变；F4 不合并 |
| 联合生命周期 | 两类真实写入、无修改、部分成功后失败、在途关闭、运行期间新增活动 | 只通知实际写入；失败不推进后台周期；关闭阻止后续写入；新活动与前台较新重置点保留 |
| 继承约束 | Memory snapshot/fork/compaction、feature off、facts 重放 | 当前相关回归保持通过 |

先运行 `pnpm exec vitest run packages/dsh-integration/tests/knowledge.test.ts packages/dsh-integration/tests/knowledge-policy.test.ts`，再运行该包 typecheck 和 runtime dependency contract。新增测试覆盖行为边界，不为 prompt 段落创建逐字快照测试。现有 `lib` fixture 消费构建产物，运行测试前需完成相关构建。

真实模型每类正反场景至少执行一次并保存输入与产物。只复测失败或修改影响的场景，不反复抽样直到碰到一次成功。不能将这组有限案例表述为所有未来会话的保证。

## Milestones

| ID | 标题 | 依赖 | 并行组 | 范围 | 退出标准 |
|---|---|---|---|---|---|
| M1 | 更新自进化提示词并恢复联合复盘及非 Global F4 边界 | Gate 2 Approved | 无 | 上述 assets、features、knowledge 模块、轨迹 producer/contract/consumer、相关测试及本 unit delta | [reviewer] spec 的 21 个场景有真实输入与可复查结果；联合与单项选择正确，联合轨迹用途和范围可辨认，F4 模式和来源保护有效，其他自进化保持可用。[worker] 上游复用及适配逐项对账，继承读取权限、Skill 读取检查、执行拒绝与并发测试通过，相关构建和契约检查通过，验证证据与未验证边界明确。 |

## 设计阶段历史交付状态

独立 thread 已完成 [Round 2/full 审查](design-review.md)，结论为 Issues Found，0 CRITICAL / 3 WARNING。R1 条目已在设计层关闭。作者已核对并修订 R2-W1 的原文件读取、R2-W2 的读取未完成结算和 R2-W3 的轨迹用途接线，并采纳 R2-R1 移除无条件重读。处置记录追加在原报告末尾；原报告保留。修订尚未独立复审，Gate 2 未通过。模型可用性仍需验证，通过 Gate 2 后才交给实施流程。

作者检查：本 unit 的本地链接、行尾空白及单 M1 骨架检查通过。全仓 `python scripts/docs_check.py` 返回 6 个失败，均为本次未修改的索引引用未跟踪文件，包括 product-tryout、prod_tunnel 和两份研究目录；本轮不修复这些已有工作。该全仓检查不能记为通过，也不代替新建未跟踪文档的局部检查。本轮未运行产品测试，未创建实施分支或 worktree，未提交或推送。

## 交付接力更新

2026-10-23 独立 Round 3/full 已 Approved，0 CRITICAL / 0 WARNING，见 [design-review.md](design-review.md)。历史 Gate 2 未闭环即获用户授权实施的时间顺序保留。接力仅校正刷新措辞、未纳入分支的 feat-638 引用和 runbook 的请求契约入口；不改变需求、设计决定、delta 或 M1 范围。真实模型已在隔离环境成功回复，产品与实现门禁继续独立执行。
