# feat-665 Design Review

## Round 1

### Metadata

- reviewer_target: `/root/design_review`（独立 reviewer；未参与受审设计编写）
- review_mode: `full`
- mode_reason: 首轮 Gate 2，完整覆盖需求输入、当前产品组装、设计、delta-spec、迁移与三个 milestone；同时执行 `agent-context-review` 的 Design Review 模式。
- baseline: `main@bed9c40ae5eb63a88cd46c99e7d5b4ec45f1d7c0`。相对附件基线 `eddaf52ba3bc8276787e86dce43ec999f88d9341` 仅新增本 unit 首文档提交，产品代码一致。
- started_at: `2026-10-26T18:07:46+08:00`（报告定稿阶段；前序取证开始时刻未单独采集）
- completed_at: `2026-10-26T18:11:04+08:00`
- duration: 报告定稿阶段 198 秒；全轮取证耗时未采集，不作估计。
- reviewed_scope: `spec.md`、`design.md`、`specs/**`、`deployment-prompt.md`、M1/M2/M3 `.gitkeep`、`input/GENERAL_PA_BLUEPRINT.md` 与 `input/LOCAL_CODING_AGENT_PROMPT.md`；另读取用户包 README、工具/UX/验收资料与场景定义。
- changes: 仅创建本报告；未修改设计、实现或 current specs，未提交，未启动或操作生产。

### Verdict

**Issues Found — 0 CRITICAL / 4 WARNING。**

核心职责拆分和复用方向成立，但子执行的私人资源边界、主动通知的执行层入口及旧交互的业务版本绑定尚未闭合；delta 还保留了一条与目标行为冲突的 current 契约。上述问题会影响实施及验收判定，应在 Gate 2 放行前修订。

### Coverage 与证据

| 范围 | 独立核对与判断 |
|---|---|
| 用户范围及来源可信度 | 两份保留附件与解压包要求一致：通用 PA、M1/M2/M3、12 Skills、58 场景、真实 IM/模型、旧基线比较。设计没有将附件自检当产品成绩，也没有扩大 merge/deploy、生产测试、交易或真实表单授权。 |
| 当前组装与依赖 | 已核 `SPEC.md`、Gateway/IM PA 与 Task current specs、能力 current spec。`index.ts:235-249` 真实创建入口接入配置/审批/历史；`agent-config.ts:102-135` 注册工具、Feature、Persona 和角色范围；`global-agent.ts:410-519` 接产品调用；`personal-agent.ts` 认证 binding 与 owner 原话。方案应继续由 integration 持有 DSH 对象、IM 持有私人产品数据、PA 持有路由投递，不应让 IM 或 PA import DSH。 |
| M1 记忆 | `knowledge/files.ts:49-69` 确有两个小文件、1375/2200 限额和首个 substring 替换；`memory-curation.ts:11-30` 确为 compaction 序号快照。扩展受控记录并保留短投影有明确必要性，文件级原子事务适合本次规模；没有必要另建向量库或维护 daemon。新 revision、幂等、维护读前写冲突和非 PA 保留路径已写入设计及退出标准。 |
| 遗忘与公开 API | 锁定的 `dsh-agent-context@0.3.0-rc.5` 根 export 公开 `commitRollover`、`selectRolloverRange`、`NotesStore`、history 读取；公开 `ContextRolloverEngine.compactNow` 支持 idle maintenance，`compactRegion` 限完整 paired conversation。故并非必须 patch DSH 的不可实现设计。`lib/rollover.js` 同时有 pairing、open-turn 和 shrink 检查；设计以 pending/unavailable 阻止消费作为失败语义是必要约束，尚不能据此宣称遗忘真实通过。 |
| M2 读取与主动性 | 私人候选放 IM、受控 memory 留节点、组合查询由 integration 汇总，避免把私人候选做第二套 Task。已有 `ownerMessage`、来源 union、policy revision、十分钟批次和主 Inbox 摄取可复用。查询游标与 ack 分离、部分读取不授完整收据、Task 当前状态重查、snooze 用原 Schedule 都有明确设计；通知入口仍有 R1-W2。 |
| M3 执行与产物 | 锁定 DSH 公共 subagent seam 确有 continuable start/send/interrupt/catalog，现有 `descendants.ts`、Task driver 和持久 Work 为可复用入口。按每条真实 child 状态抑制对应 Task，而非任意 child 抑制全部 doing，方向正确。`media.ts:124-141` 普通上传生成随机 key，语音才使用 caller key，扩展普通附件幂等有现状依据；固定 owner 私聊、真实字节/hash/version、外发复用 PersonalActions 是最窄合理新增面。 |
| Context lifecycle | 从来源/owner → memory/source 查询 → projection/实际工具输出 → root/child/maintenance 消费 → revision/撤销/遗忘 → rollover/restart 逐段审查。memory/combined maintenance 的冻结工具与读前写证据在 `knowledge/runtime.ts:50-77,140-146,250-307` 有真实落点；普通 child 资源继承问题见 R1-W1。模型必填身份由宿主派生、source/certainty/coverage 与实际回执分层合理。 |
| 交互与 UX | 新方案复用现有聊天、ComposeMessage、ToAssistant，无新页面/布局，避免重型工作台合理。当前 `Interactions.record/prepare` 和 `interactive-card.tsx` 的源码可证消息 supersede 与单次请求重试幂等；不能据此证明业务版本反馈闭合，见 R1-W3。本轮未启动浏览器或看实际渲染，故不作视觉/真实旅程通过结论；M2/M3 已要求真实浏览器检查，修订后仍须完成。 |
| delta-spec | 四个目标路径均为正确 canonical area，ADDED 消费者视角基本清楚；但 Memory 生命周期确实修改 current 既有断言，不能只追加新 Requirement，见 R1-W4。 |
| milestone 与测试 | 三个骨架仅 `.gitkeep`，符合设计阶段要求；顺序切片有退出标准，涵盖 disabled、combined、竞态、重启、真实 context 和资源字节。`scripts/e2e-up.sh` 确有 daily profile；现有 `evals/README.md` 可承接可复用场景/runner，运行产物与产品测试需按既有规则组织。58 场景编号分配与附件一致；多次核心重放、同模型旧基线、passed/failed/blocked/not_run 与外部连接缺失分开，证据要求合理。 |
| 迁移与回退 | `deployment-prompt.md` 已明确授权时机、只迁 PA、停维护后备份、相同 source hash 跳过、冲突不覆盖、自定义/空 prompt/Skill 保留、records 单权威、旧程序回退先暂停。功能/失败/重复迁移在隔离环境完成；生产只做有限只读结果核对，无生产功能测试或额外重启演练。设计阶段可接受，实际迁移命令及隔离证据仍是实现交付条件。 |

**架构判断：** 本轮不建议增加第二套执行引擎、通用连接平台或额外审查 Gate。records 事务、IM attention 与既有 Task execution 引用各有不同 owner，当前边界划分足以支持目标。问题主要在这些边界对模型/用户反馈的实际约束尚未写全，而不是模块数量不够。

### 历史问题闭环

首轮，无历史问题。

### Issues

#### R1-W1 — 普通任务 child 的文件读取面仍能取得全量私人记忆

- severity: **WARNING**；evidence: **CONFIRMED（设计缺口与当前继承事实），未运行攻击或真实模型**。
- 位置：`design.md:50,68,86,98`；对应附件 S04 与 `spec.md`「身份与最小上下文」。
- Context Surface：child System Prompt、工具选择与 workspace 文件可读范围。
- expected：简单研究 child 只取得相关 handoff；无关私人事实既不进入其输入，也不因默认继承的受控资源读取面而可得。
- observed：设计只禁止 `personal_*`、`memory` 私人读取及代表发送，未说明 `read/glob/grep` 和通用执行工具如何处理共享 workspace 的 `.nanoassistant/memory/{records.json,USER.md,MEMORY.md}`。当前 `index.ts:243-246` 从父配置组装 child，`workflow/engine.ts:104-106` 普通路径直接返回 parent；锁定 DSH `childSessionMeta`（公开包 `lib/index.js:454-479`）继承父 cwd。`KnowledgeFiles` 将私人文件放在该 cwd 下（`files.ts:49`）。仅 spawn 代替 fork 和删除 memory 工具不能撤掉这些实际可读文件。
- impact：即使最终 child 初始请求没有敏感事实，它也能通过普通文件工具重新读取；S04 的「敏感信息未出现在 child 输入/可读资源范围」不能由现方案兑现。随后 child 回传、notes 与产物会扩大私人内容的传播面。
- recommendation：明确可信 child role 的默认配置及文件资源边界，覆盖普通 read/glob/grep 与可执行工具，而非只列 PA 工具名；为普通研究使用最小工具集、受控读取及任务文件交接即可，不要求新增 OS 沙箱。需要任意 shell 的执行角色应明确实际保证与额外边界，不能沿用“不可读私人资源”的承诺。将允许相关任务资料、拒绝受控个人记忆读取及 restart 后角色恢复写入 S04 验证。

#### R1-W2 — 可选 attention ID 不能保证主动私聊执行静默与去重策略

- severity: **WARNING**；evidence: **CONFIRMED（接口设计缺口）；模型实际遗漏的频率未验证**。
- 位置：`design.md:76-80,94`；对应 P02/P05/P08/P09。
- Context Surface：`send_message` schema/调用意图、服务模式及真实投递回执。
- expected：主动探索的候选投递必经模式、静默时间、主题、最新状态和通知去重；主人直接回复与其明确 schedule 有可信的豁免依据。
- observed：设计说 `send_message`“可携带” attention ID/revision，并把后续检查描述为候选投递。未定义不带 ID 的主动发送如何进入同一检查，也未定义“用户直接请求/明确 schedule”豁免如何由宿主识别。真实当前 owner 私聊路径在 `personal-assistant.ts:126-140` 直接 `agent.message`；`send_message` 是 Global 固定工具，不会随 personal_proactivity 关闭而消失。
- impact：模型把观察结果写成普通 `send_message`，就可能不经过候选静默/去重/主题控制；Feature 关闭后的历史主动指导也可能继续利用此路径。仅要求模型主动填 ID，无法实现设计承诺的服务端约束。
- recommendation：收口私人投递的必经入口和可信分类。明确主动结果必须绑定有效 item/revision；无绑定的普通 owner 投递如何证明属于直接请求/明确提醒/已委托 Task 的结果，以及未知类别如何返回可行动状态。复用既有来源与 operation 身份，不需新审批流程。验收应包含省略/错误 attention ID、静默期间普通发送、明确提醒豁免及关闭 Feature 后旧调用。

#### R1-W3 — 旧卡的 source message 尚未绑定被用户确认的业务 revision

- severity: **WARNING**；evidence: **CONFIRMED（设计链路未定义）；未声称现产品已发生重复交易**。
- 位置：`design.md:58,76-80`；`specs/im/personal-agent.md`「交互与附件」；对应 U01/U02。
- Context Surface：已发布提案、ToAssistant 回传、业务工具 expected_revision/idempotency_key。
- expected：宿主知道用户点的是哪个提案的哪一版条件；重复点击或模型重新查询后，不能把旧确认重新解释成对最新版业务条件的确认。
- observed：现有 `Interactions.prepare`（`interactions.ts:112-141`）固化 source message 与提交状态，幂等按一次 caller key；过期只看 `superseded_by/read_only`（`:25-30`），由显式发布 supersedes 消息更新（`:77-81`）。设计仅说反馈传“最新 item revision”与模型幂等键，没有定义发布 message → attention/proposal ID + revision + action 的宿主持久绑定，也没定义业务 revision 变化时如何让旧消息失效。现有前端一次成功后清除 pending key（`interactive-card.tsx:123-144`），其重试保护不等于跨提交/设备的业务动作幂等。
- impact：用户点 revision 1 的旧建议，PA 先查询取得 revision 2，再传“最新 revision”可能成功执行用户未确认的新条件；不同提交产生不同请求 key，也不能仅靠 IM attempt 幂等证明一次逻辑动作。
- recommendation：复用已有 published message/source interaction 数据，保存可信的业务对象、发布 revision、动作/载荷关联；反馈执行时校验的是“原提交关联的 revision”，不能由模型替换成刚读到的当前值。业务幂等以被确认的提案/动作身份稳定去重，失效可复用 supersedes 或现有错误状态。明确普通文字反馈的目标解析及 owner 证据路径；无需新增前端组件或万能批准工具。

#### R1-W4 — delta 未修改 current 的 compaction-only Memory 快照契约

- severity: **WARNING**；evidence: **CONFIRMED**。
- 位置：`specs/gateway/agent-capabilities.md` 全文仅 ADDED；`design.md:68`；canonical `docs/specs/gateway/agent-capabilities.md:392-398`。
- expected：完成 delta 归并后，current 唯一契约能区分 PA 的 revision 即时刷新、普通 child 最小上下文、维护 fork 与非 PA 的旧行为。
- observed：canonical 已明确「Memory 注入在首次请求惰性读取，当前会话内保持快照，原生 fork 继承快照，压缩完成后再读取最新内容」，新设计要求 PA 每个 model boundary 检查 revision、不等 compaction。仅追加“通用能力遵守选择与知识归属”不会替换或限定旧断言。
- impact：实施者/最终 verifier 会面对同时有效的相反生命周期规范；后续维护容易继续按旧 compaction 缓存恢复 PA 行为。新 ADDED memory Requirement 不能代替对原断言的明确变更。
- recommendation：增加正确锚定的 MODIFIED Requirement，按 delta 规则保留未改变的 Scenario，明确 PA / 非 PA、root / task child / maintenance 的适用条件；保留禁用和后台计数等不变语义。同步核对涉及角色继承的 current 描述，但不扩大改写无关契约。

### Recommendations

无额外非阻断建议。修订集中关闭上述四个问题即可，不要求扩展模块或测试平台。

### Evidence limits

本轮为设计审查：所有源码事实来自当前 checkout 与其锁定依赖；附件仅用于需求和场景覆盖。未执行实现测试、模型请求、浏览器交互、迁移或生产操作。公开 API 存在只支持可行性判断，不证明将来实现的安全、遗忘、持续执行或行为成功率。前端渲染及相关最终 Context 必须在已安排的隔离实施验收取得真实证据。

### Author Resolutions（R1）

- R1-W1 accepted：已核 DSH childSessionMeta 继承 cwd。design M3 改为宿主持久 delegation scope、最小文件副本和默认工具执行 guard；所有文件工具只可达该 child 目录，默认撤 terminal/run_code/plugin/任意外部写；需要这些步骤回 root 原审批执行。区别任务 spawn 与可信 maintenance fork，明确重启恢复和 S04 验证。
- R1-W2 accepted：design M2 取消自愿绑定，所有 owner-private 发送必经分类；普通回复豁免只基于宿主 live Inbox/request、真实 Schedule 授权来源或 canonical Task 责任结果。无证明且无 attention 返回 requires_attention，关闭 Feature 仍拦历史调用；加入对应反例验证。
- R1-W3 accepted：design 交互段补发布 message 与 item/revision/action 的同事务关联；反馈取原发布版，不接受模型替换；业务幂等基于 proposal/action 身份，跨 caller key 去重，旧卡随业务版本失效。自然文字继续原 ownerMessage 解析路径。
- R1-W4 accepted：capabilities delta 加 MODIFIED 原 Requirement，完整保留两个原 Scenario、后台计数与维护前缀语义，明确 PA revision/child 与非 PA snapshot 的边界。

以上为实质修订，交独立 reviewer 自行确定 R2 范围；未开始产品编码。

## Round 2

### Metadata

- reviewer_target: `/root/design_review`（同一独立 reviewer）
- review_mode: `full`
- mode_reason: 虽由 R1 四项问题触发，但修订实质收紧了 child 执行边界与共享发送入口，不能只以文字消歧 closure 放行；复核其对 root/child/maintenance、普通回复/主动结果、交互状态及配置/退出标准的影响，并重新确认整体需求与职责仍一致。
- baseline: `main@bed9c40ae5eb63a88cd46c99e7d5b4ec45f1d7c0`，产品代码未变化。
- started_at: `2026-10-26T18:13:27+08:00`
- completed_at: `2026-10-26T18:15:48+08:00`
- duration: `141 seconds`
- reviewed_scope: R1 全范围，重点核对修订后 `design.md:58,78,86-90`、M2 退出标准、`specs/gateway/agent-capabilities.md` MODIFIED 部分与 Author Resolutions。

### Verdict

**Approved — 0 CRITICAL / 0 WARNING。R1-W1、R1-W2、R1-W3、R1-W4 均 closed。**

本轮批准设计进入实施；不代表产品功能、模型行为或浏览器验收已经通过。

### Coverage 与证据

- **需求、现状与整体架构：** 重新对照本轮完整 `design.md` 与 R1 已读原始输入。通用 PA、独立长期事项、IM 主入口、配置保留、唯一 Task/Knowledge 权威和不 merge/deploy/生产测试均保持。没有引入新执行引擎、OS 沙箱或独立维护服务。当前代码、依赖及附件未变化；R1 对当前组装、公开 DSH API、记录事务、媒体/Task 复用和迁移的源码证据仍有效，`retained_from: Round 1`，理由是对应设计与产品代码未改变。
- **职责与最小方案：** child 资源控制落在 integration 的可信 scope、工具 schema 与执行 guard，IM 不取得 DSH 对象；通知分类与可信业务反馈落在既有产品发送/交互链。已有 `KnowledgeRuntime` 的 `tools.guard`、实际路径验证及 storage domain（`knowledge/runtime.ts:49-66`），`descendants.ts:21,47` 的持久 domain 均为可复用 seam。新 child 文件目录用于最小资料/产物交接，不复制 Task 状态；额外执行步骤仍由原 root/独立 Agent 责任处理，无模型自升权接口。
- **Agent Context Review / Design Review：** 已复核来源→可信派生→schema/工具执行→child 消费→恢复。最小输入与资源权限同时约束，角色先持久恢复再开放工具；发送豁免以当前 live request、真实 schedule 来源或本人 canonical Task/result 为据，不以模型 reason 或旧 owner 原话自证；交互按已发布原版本恢复，模型不能刷新 expected_revision 偷换原选择。memory 版本刷新、maintenance 冻结证据、遗忘 fence 与 root 原工具权限仍按 R1 已核方案实施。
- **delta：** MODIFIED 正确锚定 current `self-evolution 创建的 Skill 跨前台 terminal 仍完成配置调和`。以本轮脚本比较该 Requirement 的两个既有 Scenario，结果为字节一致；保留原调和与后台计数语义，并区分 PA revision / 非 PA compaction snapshot / task child / maintenance。其余 delta 的用户行为承诺与修订后的 guard 一致。
- **milestone、UX 与验证：** M1/M2/M3 依赖与范围保持；M2 新增省略/错误 attention ID、静默普通发送、明确提醒豁免、Feature 关闭旧调用、旧卡及不同 key 重复动作的反例；S04 明确实际 child 输入、文件/终端拒绝、相关资料允许与重启恢复证据。既有聊天渲染、草稿采用不发送、真实文件可打开等验收仍保留，未新增前端组件。实际浏览器和模型取证限制与 R1 相同，未将代码静态阅读当作体验通过。
- **迁移及回退：** 本轮没有改变 records 单权威、显式旧数据迁移、custom/空 prompt 保留或生产边界。`deployment-prompt.md` 仍具适用条件、备份/跳过/失败恢复与有限生产只读核对，`retained_from: Round 1`；无需因本轮 guard 修订新增迁移或重启演练。

### 历史问题闭环

| Issue | Author Resolution | 本轮独立证据与判断 | 状态 |
|---|---|---|---|
| R1-W1 | 持久 delegation scope、最小副本、文件工具限定 child 目录，默认撤销通用执行/插件/任意外部写，额外步骤回 root | `design.md:86-90` 已明确 spawn 不等于隔离、普通 child 与 maintenance 的可信角色区别、schema 与 guard 双约束、路径越界拒绝及重启先恢复 scope。S04 的正反测试进入明确验证要求；既有 public tool guard/storage seam 支持该方案。没有再用仅移除 memory 工具冒充资源隔离。 | closed |
| R1-W2 | 所有 owner-private 发送必经分类；无可信普通回复证据且无 attention 则拒绝 | `design.md:78` 明确包括原快路径，attention 对主动结果必填；当前 request/schedule/Task 证据由宿主认定，模型 type/reason/旧原话不产生豁免；无绑定返回 requires_attention、关闭 Feature 后仍拦。M2 退出标准覆盖绕过入口与合法提醒两面，普通已交办工作仍保留原授权。 | closed |
| R1-W3 | 发布 message 与 item/revision/action 同事务保存，原发布版本校验，跨 caller key 业务去重 | `design.md:58` 明确可信关联、旧版随业务版本失效及不得替换为最新 expected_revision；自然文字反馈另走 ownerMessage。M2 反例覆盖更新后旧卡和不同请求 key，未再把 attempt 幂等等同业务幂等。 | closed |
| R1-W4 | 增加 MODIFIED，保留原 Scenario/计数/维护前缀 | 本轮读取 delta 与 canonical，脚本确认原两个 Scenario 字节一致。新正文明确 PA 即时 revision 刷新、不等待压缩、普通 child 最小上下文、可信 maintenance 与非 PA 原快照行为，以及禁用和工具独立选择。 | closed |

### Issues

无新增或未关闭 CRITICAL / WARNING。

### Recommendations

无额外建议；按当前退出标准实施和验证即可。

### Evidence limits

本轮仅复核设计可实施性与契约闭合，未修改代码、未运行模型/浏览器或启动服务。子执行文件边界、跨重启 role 恢复、来源分类、旧交互状态与遗忘效果须由实施后的实际 guard、最终 provider 输入及产品事实证明；这些是已有 milestone 的验收责任，不是本轮新增 Gate。
