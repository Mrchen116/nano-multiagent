# feat-665: 通用 Personal Agent — 技术方案

> 对齐: spec.md；核对基线 eddaf52ba3bc8276787e86dce43ec999f88d9341，与附件一致。

## Changelog

## 现状分析

### 涉及范围

- `apps/im-server/src/personal-agent.ts` 是可信 binding、owner 原话与来源并集权限的 owner；`personal-actions.ts` 冻结、复核并提交实际公开载荷；`media.ts` 已能持久上传与按聊天读取附件，但普通附件上传目前不使用调用者幂等键。
- `packages/personal-assistant/src/global-agent.ts` 管理主 Inbox、十分钟观察合并、产品工具路由及可靠回执；`inbox.ts` 已把提醒和完整摄取分开。`attention.ts` 是消息准入的 mention/reply 判定，并非本次候选存储；现有隐私事件也不能当作私人待关注事项。
- `packages/dsh-integration/src/knowledge/{files,runtime,review-files}.ts`、`features/memory-curation.ts` 负责受控知识写入和维护。USER/MEMORY 限额是 1375/2200 字符，内容按段落分隔；替换取首个 substring 命中。模型摘要缓存只看 compaction seq。维护使用 native fork 与专用可调用工具集合。
- `packages/personal-assistant/src/task-execution.ts` 读取 canonical 责任并验证真实 Schedule；integration 的同名模块依据 doing 和无进展短轮次计数续推。当前不绑定具体 child，不能依据任意 child 活跃抑制全部工作。
- `packages/dsh-integration/src/descendants.ts`、`owned-sessions.ts` 提供原生 catalog、持久恢复和 owner；DSH 公开 `startContinuable/sendMessage/interrupt/listChildren` 与结算消息复用。
- `packages/dsh-integration/src/agent-config.ts`、`capabilities.ts` 负责真实工具、Feature、Skill 选择与 scope；`builtin-skills.ts` 更新随包目录，用户 workspace Skill 的原生发现优先级另行保留。

### 既有约束

DSH 只经 integration 与声明的公开 exports；无新 runtime fork、HTTP kernel、Agent Loop。PA/Channels/IM 不 import DSH；Task/Work 为唯一执行事实。新接口必须经过 binding、lifecycle 与真实选择限制。只读观察不能有 shell/network 或 write 能力。主仓只保存已提交设计，实施在独立 worktree。生产不用于验收。

### 可复用能力

| 能力 | 处理与理由 |
|---|---|
| Global/IM/来源/十分钟批次 | 复用，不改变 participant/observer 语义和主 Inbox 消费 |
| KnowledgeRuntime、ReviewFiles、锁与原子 rename | 扩展 PA 的记录和检索；非 PA 保留文件行为 |
| Task/Work/native child/schedule | 扩展 Task 的 execution 引用；不新建任务状态库或轮询器 |
| PersonalAgents + SQLite | 增加 private attention、偏好与查询收据，沿用绑定/生命周期 |
| IM media 与 PersonalActions | 新工具只导入真实文件到 owner 私聊；外发继续审核复制 |
| Intelligent UI / ComposeMessage / ToAssistant | 复用渲染、用户输入和 source interaction；关注反馈走有版本的业务工具 |
| dsh-agent-context 公开 API | 受控重建活跃上下文；既有 session/event 与 Task 回执保留 |

### 相关历史

feat-658 保留默认指导可编辑/清空；feat-635、bugfix-656 定义 Task 持续责任与停止；feat-645 定义 Feature 依赖与工具独立开关；feat-659 要求最终 Context 取证；bugfix-664 的维护身份/轨迹已有基线，不重做。

## 架构总览

保持 `IM source → Global Inbox/原生 wake → 主 PA → 现有 Task/child/Knowledge → IM 交付`。
新增三个深度边界：KnowledgeFiles 内的 PA 记录事务；PersonalAgents 内的私人关注与只读组合查询；既有媒体上的私有产物发布。所有者、来源和受众由宿主决定。模型提出内容和引用，不能自填 owner、角色、已授权或发送成功。

Before：小摘要唯一权威、按 compaction 刷新、观察主要提供原消息、Task 与 child 无绑定、生成文件需手工上传。
After：记录检索+短投影+即时 revision，关注候选/反馈及最新来源核对，Task 绑定真实 child，文件通过原媒体链路交付。

## 关键决策

**一个 Full unit，三个纵向切片。** M1/M2/M3 分阶段稳定 fixture、真实链路与证据；不按包机械拆工，也不为每个领域建立 Agent 或工作台。

**PA 记忆以一个受控记录事务为唯一权威。** 使用现有 memory root 的 `records.json`（有 schema version、owner binding、scope revision、records、最小 tombstones 和幂等回执）。原子写入整个文件隐藏跨记录更新与投影一致性；当前规模无需数据库/向量库。USER/MEMORY 是可重建短投影，读取时从权威 revision 派生；旧写操作命中唯一记录后映射，不独立写投影。已有 PA 用显式迁移动作/脚本初始化，失败不破坏旧文件；新建 PA 首次受控写入建立空记录层。未迁移时仍可读旧概要但结构化写提示迁移，不能后台暗中迁移生产。

**服务指导与固定边界分开。** 新默认仅进入 custom_prompt，旧实例保持；固定层只保留身份、数据边界和工具契约。三种服务模式（仅应答/主动准备/授权内代办）存于 PA 私人设置，需原始 owner 指令，不能扩大动作权限。普通委托继续执行不受主动探索模式影响。

**观察优先在主 PA 内完成。** `personal_context` 非消费读取，不给任意 child 主人查询身份。可选 observer 用最小冻结输入、restricted tool allowlist（无 shell/network/发送/写 Task/写 memory/主 Inbox），只有父级回传；第一版无需独立长期 observer。主 Inbox cursor 与 query cursor 分离，查询结果明示 partial/error/coverage，来源撤销即失效。

**Task 只增加原生执行引用。** child ID、请求 revision、纠正引用、最近回执跟 Task 的已有版本一起提交，不复制 Task status。没有 Task 的小事仍可直接 native child。正常活跃且已建立原生结算回调的绑定 child 才抑制该 Task 的自动重做；新增更正、失败、结果未交付、状态未知恢复协调。其他 doing 继续；waiting 仍验证真实一小时内 Schedule。

**交互复用聊天。** 用户通过普通提问或现有 ToAssistant 提交反馈。发布 attention 交互时，将真实 message ID → attention ID、发布 revision、动作/载荷摘要在同一发送事务保存；业务变更使该 revision 的旧卡失效。ToAssistant 回传原 source_message_id 后，宿主从已存关联恢复被点击版本，不能让模型改填最新 expected_revision。业务幂等按 proposal message/item revision/action/owner 计算，跨设备不同请求 key 仍为同一个业务动作；现有 IM attempt idempotency 只处理传输重试。纯文字反馈仍经原始 ownerMessage，目标唯一时使用当前版本，歧义才澄清。ComposeMessage 仍只采用草稿。无新前端组件/页面，本次无 prototype；须用真实浏览器检查既有渲染/反馈旅程。

## 接口与数据流

### M1：记忆、相关上下文与遗忘

扩展 `memory` 为判别动作：旧 add/replace/remove 保留；search/get/upsert/retract/forget/migrate。PA upsert 参数包含 ID/expected_revision、kind、subject_ref、domain/applicability、content、certainty、有效时间、source_refs、idempotency_key。host 写 owner/time/author；`pa.memory.sources` 通过 PersonalAgents 校验引用原消息可读、真实作者/主体，未知旧来源标 legacy_unverified。source 引用只证明资料，不产生授权。明确 forget 另须 `ownerMessage` 校验；后台维护不能 forget 或迁移。

记录事务：取得现有根锁 → 重新读权威状态 → 验证 scope/record revision 与幂等 key → 校验读前写版本 → source tombstone 检查 → 原子提交 → 派生投影 → 返回 revision/已生效层。若投影失败，权威已提交且回执明确 pending；下一读自权威重建，不能重新追加。检索按主体/领域/类型/关键词与有效期过滤，分页输出短摘与 IDs，get 返回指定当前记录；排除 retract/superseded/expired。不以第一条相似文本覆盖多条。

模型消费：root 和 memory-maintenance 可见个人记忆，普通 task child 默认不注入全量概览。稳定前缀只在必要时更新；所有 PA model boundary 校验当前 revision，纠正/遗忘下一安全边界刷新，不等待 compaction。相关查询走 memory search/get，不全量加载正文。Memory 与 combined maintenance 同步采用新语义，旧非 PA 路径不变。ReviewFiles 补权威记录读/version 证据；维护开始冻结 revision，提交冲突必须重新读，不能覆盖前台纠正。

遗忘：先持久删除选定记录正文、索引项与派生内容，清除包含正文的旧回执，保存仅 source IDs/content hash/时间的防复活信息。正在用旧事实的执行先取消/失效；主上下文与相关子上下文在原生 paired safe boundary 用公开 deterministic rollover 重建，不能只追加“忽略”。已有 notes/history 的受控读取对遗忘前的可能污染内容建立 fence，相关 note 清理或置 unavailable；保留 Task/执行/投递回执，不能恢复被忘正文。重启从 fence 恢复。若某层不能重建，返回 pending/unavailable 并阻止继续消费该层；重试同一 key 继续清理。原始 IM、审计、备份保留策略不变，回执明确不在清除范围。通用 shell/plugin 不是本机制的完整数据沙箱。

### M2：personal_context 与 personal_attention

`personal_context`：root PA 专属只读组合，输入 query、已有 conversation/Task 引用、cursor、limit；owner/role 不在参数中。integration 合并受控 memory 检索与产品源查询，返回 source_coverage、短消息引用、canonical Task 当前状态、attention 摘要、下一 cursor。默认只查相关指定来源/有限最近范围，不全库扫描；相关领域能力返回真实工具/Skill 选择，外部连接未探测标 unknown，不伪装 connected。每页持久记录查过的 message IDs/当前来源 revision 与 watermark；failed/partial 不授予完整核对收据。这个查询从不调用 inbox ack。

`personal_attention`：list/get/upsert/snooze/dismiss/resolve/link/settings。SQLite 在现有 IM DB 存 binding-scoped 私人候选 `{id, revision, kind, source_refs, topic, why_now, next_step, prepared_result_refs, canonical_task_ref?, status, snoozed_until?, checked_watermarks, last_delivery_receipt?}`；无 scheduler、无执行状态副本。候选唯一键由可信来源集合+kind+topic 生成，模型 idempotency key 另防重放。来源必须可读，Task link 必须当前可访问且存在，不改 assignee/status。

候选创建与发送分离。`send_message` 的 attention ID/revision 对主动探索结果是必需字段。所有 PA 私聊发送（含当前绕过 PersonalActions 的 owner-private 快路径）必须经过同一分类入口：宿主只能依据当前 turn 的真实 live Inbox 原始直接请求、原生 schedule 来源+其创建授权引用、或调用者当前负责的 canonical Task/result 引用授予相应普通回复豁免；模型给 reason/type/旧 owner message 不能授予豁免。新 call 若无这些可信证据且无 attention 绑定，返回 requires_attention，不发送；关闭 personal_proactivity 后旧的未委托调用同样被拒绝。直接请求的进度/结果可共享该请求引用，不用重新审批；任意历史授权不等于当前回复机会。主 PA 私聊主动投递前，服务端检查模式/静默时段/主题抑制/snooze/current revision、重读来源 watermark 与 canonical Task 完成状态。未核对最新状态返回 held_for_revalidation；已完成、无变化或已送该版不再发。回执绑定已提交 message ID，超时走既有 operation 查询重试，未知不写 sent。用户直接请求的回复/明确 schedule 提醒不套探索静默策略；外部自称紧急不豁免。

反馈必须引用最新 item revision；snooze 保存绝对 UTC 时间并经现有 schedule 建立一次恢复（失败回执保留 pending，不说已设置）；dismiss 不写主题策略；主题抑制/settings 需 owner 原话和 settings revision。每次/每日新增探索预算和单批候选限额通过同一存储计数，budget 只限制未委托研究，不限制 Task 完成。十分钟背景/现有 heartbeat/schedule 是唯一触发，snooze 到期只恢复候选可见性并由正常 wake 决策，不能无条件重发。

### M3：执行、角色、领域与产物

在现有 `task_graph` 增加 execution 绑定/解除操作及查询字段：原生 child identity、request revision、correction source ref、delivery receipt。写前由 integration 用公开 catalog 核实 child 属于该 root 且 continuable；产品层核实 Task 原 owner 与调用者，Task revision 乐观并发。driver 对每条绑定查询原生状态；只有已知 running 且无待协调变化抑制该条；settled/error/unavailable/重启未知均触发协调。停止/暂停/改派解除或取消对应执行，旧 revision 结果只可审阅，不复活 Task/自动发送。追加要求用原 child sendMessage 并记录实际接收回执；取消使用原生 interrupt 并等待真实状态，不把发送取消文本当停止。

任务 child 采用 native spawn + 最小 handoff，宿主 guard 拒绝普通 PA child 的 fork/history/private memory/personal_*/代表发送；maintenance 的可信内部 fork 单独沿用原生命周期，不被模型角色声明解锁。DSH 当前继承父 cwd，因此不能把 spawn 本身当文件隔离。

默认 PA task child 使用宿主持久的 delegation scope（root、child ID、角色、明确交接文件引用、独立输出目录），存在既有原生 session metadata/受控 storage domain，重启先恢复 scope 再开放工具。允许 read/glob/grep 的路径仅为已复制到本 child 目录的相关资料及该目录产物，write/edit 也限该目录；拒绝 symlink/绝对越界及个人 memory/history/notes 根，普通 child 的 tool schema 与执行 guard 同时限制。默认不开放 terminal/bash/run_code/plugin_manager、任意连接器和其他可绕过资源边界的工具。可以使用明确选择的只读 web 查询、受限文件工具与父级通信；需额外受限资源时由 root 核实并交接最小副本。需要任意 shell 或外部写动作的步骤回 root 在原工具审批和资源范围内执行；不通过模型声明升级 child 权限，也不把它冒充 OS 沙箱。研究/旅行/文档子任务可在此集合内持续推进，软件领域的复杂 shell 步骤由 root 或显式有资源授权的既有独立 Agent 执行。

observer 从宿主建立为 frozen-input one-shot research role，只给最小输入与父级回传，零文件/终端/网络/业务写工具；第一版正常观察由 root personal_context 完成，无需常驻 observer。role 由 trusted launch metadata 绑定，模型字符串不能升级；即使调用隐藏工具也被 guard 拒绝。S04 必须在真实 child 输入与 read/glob/grep/terminal/private memory 拒绝、允许相关资料、重启后 role 恢复上取证。maintenance 沿用已有 native fork 与冻结工具集，仅其内部具有受控记忆权限。

新增可选 `publish_artifact`：仅 root PA，path 必须在真实 workspace 内且无 symlink 越界，文件大小/类型受现有 media 限制；读取实际字节、hash，上传到固定 owner 私聊，不允许模型选择 owner/公开 audience。复用 gateway 已有认证 HTTP 通道与 media 存储，普通附件支持 caller Idempotency-Key 并验证相同 key 的 hash；返回稳定资源引用/hash/version/真实 receipt。修改通过 artifact ID+expected version 创建新内容版本并保留前版引用，返回最新引用；本地路径不作为 URL。对外发送仍经 PersonalActions 冻结具体版本、审核完整内容与复制，不绕过二次权限检查。未支持的格式外发明确失败，但私人已交付可打开。已上传资源按 IM 独立保存，执行环境丢失不影响其字节。

12 个 Skill 按包内领域方法合入 `assets/skills`，ongoing-work 合并现有约束；不覆盖用户 workspace 同名技能，不全文常驻，不绕过选择。默认 prompt 保持 `personalAgentDefaultInstructions` 导出，只描述真实 enabled 能力；角色片段按作用域消费。Heartbeat 指导合并语义，不改用户 HEARTBEAT 文件，不添加第二个 timer。

### 配置与选择接线

结构化 memory 复用现有 memory 工具和 memory_curation Feature；已迁移记录模式不会因关闭自动维护退回旧权威，工具单独选择仍按既有工具/Feature 独立规则。personal_context、personal_attention、publish_artifact 均为可选 root PA 工具，普通 Agent/child 不注册且执行层重复验证。新增 personal_proactivity Feature 默认 off，requires personal_context/personal_attention；新 PA 默认开启，旧 PA 保持旧选择（response_only）。关闭它停止未交办探索，显式查询/反馈仍可在工具已选择时调用；不影响 Task 的明确委托。服务模式/quiet hours/主题控制由 personal_attention settings 使用真实 owner 原话管理，返回当前设置及 revision；不新增空白设置页。

### Context lifecycle 与验证

Consumer：主 PA、受限 observer、Knowledge maintenance、事项 child、独立披露审核。Producer：可信 IM source/Task/runtime/受控记忆；权威分别仍在原 owner。数据输出包明确 data/source/certainty/coverage，记忆/关注/子结果不是 instruction/authorization。刷新点：source policy revision、memory revision、Task revision、attention revision、native status；取消/失效随生命周期持久保存。测试从新建默认/配置预览→真实 callable schemas→最终 provider request→工具回执→IM 用户结果取证；同时覆盖 disabled、maintenance combined、compaction、restart、child 最小上下文与反馈竞态。

## 契约层增量

- gateway/personal-agent.md：通用 PA、受控记忆/主动关注/产物/角色边界。
- gateway/agent-capabilities.md：新增可选能力及选择/迁移语义。
- gateway/task-graphs.md：execution 绑定、协调/取消与 waiting 不变量。
- im/personal-agent.md：聊天反馈、私人模式与成果交付。

## 风险与回退

最主要风险是遗忘表面成功但活跃上下文/旧回放仍使用；必须逐层回执并 fail closed，不凭源码断言已忘记。读权限与来源 revision 改变时重核，不让缓存成为授权。Task child 抑制须有真实结算通路，未知恢复协调；不得用一般 child 存在停止所有 doing。

新增 PA 功能按真实选择关闭，数据保留；已迁移 records 为唯一权威，关闭自动维护不能恢复旧文件双写。回退旧二进制须暂停已迁移 PA，保留 records 与备份，不把超长记录塞回两个短文件。无需外部连接的 IM 服务继续，未连接领域给诚实降级。正式合并/部署另行授权。

## 一次性部署迁移

见 [deployment-prompt.md](deployment-prompt.md)。显式副本迁移与验证在 M1；用户自定义默认指导/同名 Skill 不覆盖，启用策略由原配置和主人选择决定；本轮不操作生产。

## Runbook for Reviewer

| 服务 | 停止命令 | 启动命令 | 健康检查 |
|---|---|---|---|
| 本 unit 隔离 IM、Node、DSH、Web | `./scripts/e2e-down.sh`（仅当前 worktree） | `./scripts/e2e-up.sh --profile daily`（以脚本当前 help 为准） | `.e2e-daily.json` 对应 health 与固定账号登录 |

**Review 驱动方式**：真实模型与真实 IM；未增加客户端组件，API 使用客户端同一接口；建议编辑/采用/反馈、文件打开用真实浏览器走完整路径。原生 iOS 无专属交互或布局变化，不重复 iOS。

**验收前置**：读取 `docs/development/worktree-runtime.md` 与 `llm-integration.md`；使用已有隔离 profile 的 provider 配置，不复制输出秘密；网络/模型不可用标 blocked。外部日历/预订/购买没有真实账号则只验降级与确定性适配器，相应 live external 标 blocked，不影响 IM 核心验收。

## Milestones

| ID | 标题 | 依赖 | 并行组 | 范围 | 退出标准 |
|---|---|---|---|---|---|
| M1-memory | 记得且用对 | 无 | sequential | knowledge、memory feature、来源校验、相关 query、迁移、eval 入口 | [reviewer] M01–M12/S01/S02 的相关偏好、纠正、遗忘实际改变下一轮；[worker] 锁/revision/幂等/防复活/maintenance/非 PA/disabled/最终 Context/迁移重复及失败恢复测试，遗忘逐层证据 |
| M2-proactive | 看见且帮得上 | M1 | sequential | private attention、组合查询、来源验证、模式与通知反馈、IM action | [reviewer] P01–P14/I01–I06/U01–U04/S03 主动准备与静默/反馈可用；[worker] 分离 cursor、角色 guard、来源撤销、去重/版本/真实通知收据与重复点击测试，覆盖省略/错误 attention ID、静默期间普通私聊、明确提醒豁免、关闭 Feature 的旧调用、业务变更后旧卡与不同请求 key 的重复动作，真实浏览器反馈证据 |
| M3-delivery | 做得完且可控制 | M1、M2 | sequential | Task execution、native child、artifact、defaults/12 Skills、完整 eval | [reviewer] W01–W10/D01–D08/S04 与真实文件旅程；[worker] 真实 child 持续/失败/更正/取消/重启与附件 byte/权限/版本测试；58 场景均有执行适配和分类，多次核心真实重放与同模型旧基线比较，适用全量 CI |

测试资产落在现有 `evals/`，runner 用真实 IM 客户端接口和测试隔离 fixture；`actual-results.jsonl` 只记真实观察，每个场景 passed/failed/blocked/not_run，确定性成绩不冒充行为成绩。先 smoke M01/M02/M06/M09/P01–P04/I05/W01/W03/W04/W06/D08/U01/S03，再扩全量。核心至少 3 次独立重放；旧 HEAD 在单独隔离环境按相同模型/工具配置测，不能比较的能力给原因，不能生成假百分比。记录 model/tool calls、token、重复通知、错误记忆、响应阻塞与实际交付。
