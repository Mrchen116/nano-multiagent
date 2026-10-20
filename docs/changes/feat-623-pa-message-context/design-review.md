# feat-623 Design Review

## Round 1

### Metadata

- reviewer: `/root/design_review_623`，独立于 spec/design author。
- reviewer target / validated_at: `10d91e8e55881165d98a871f80ef100a29a1e26a`
- executed_base: `8330f0565`；显式依赖另核 `bc59dfa7209f06642bda26aef78b7dfeba125004`（bugfix-621 / PR #371），未把它视为已经合入。
- review_mode: `full`
- mode_reason: Gate 2 首轮；覆盖首文档、完整设计、全部 delta 和唯一 milestone。
- started_at: `2026-10-20T11:11:20+08:00`（首次记录时钟；前置文档、源码阅读早于此点）
- completed_at: `2026-10-20T11:13:41+08:00`
- duration: 已计时部分 `141s`；前置阅读未计时，不将此数声称为完整审查耗时。
- 现场：独立 detached checkout，受审开始 clean；本轮仅新增本报告，不修改设计/产品代码、不提交。

### Verdict

**Issues Found — 0 CRITICAL / 3 WARNING**

身份、参与关系、观察背景与既有授权的区分方向成立，范围也保持克制；但背景提交竞态、持久序号及扩大证据范围后的发送失效规则尚未闭合。三个问题会直接影响已要求的忙碌合并、撤销后继续收件或正常交付，需修订设计后复审。

### Coverage 与证据

| 范围 | 独立核对及判断 |
|---|---|
| 用户要求与范围 | 核对 `spec.md` 全部五项 Requirement：Web/飞书主人身份、共同群寻址、观察双方不自动接受任务、十分钟首批/后续/忙碌/重启、提前背景与长消息消费、原渠道交付。未引入 mentions schema、摘要 Agent、可配置周期或生产部署。 |
| 实际组装入口 | `apps/node/src/main.ts:150` 将观察通知接到 `GlobalAgent.recoverPersonalObservations`，`:305` 实际构造 GlobalAgent，`:249` 在连接恢复时调用 recover；不是仅测试 fixture 存在的路径。`global-agent.ts:76` receive → `PersonalAssistant.admit` → Inbox → wake，`:134` 观察拉取仍逐条进入相同 receive。设计识别到单飞拉取内不得等待自身，且保留及时请求的 steer，覆盖了真实接线。 |
| 身份/关系与权限 | `apps/im-server/src/personal-agent.ts:35` 的 sourceAccess 合并主人和 PA 权限，确实不能把主人视角的成员身份当 PA 参与身份；PR #371 的 `feishuOwner/sourceRole/ownerConversation` 校验外部 app、配置 agent、绑定 owner 和真实目标。改为可信 is_owner 与 delivery，并继续使用 sourceAllowed、真实目标和固定主人绑定，职责归属正确。 |
| 请求和群触发 | 当前 `global-agent.ts:99` 的 PA attention 绕过 needsAttention，`attention.ts:4` 已有群配置/提及/回复逻辑，`session-controls.ts:9` 已有强制 mention_only 的控制寻址。设计复用它们，并对 observer 关闭 slash/input-review/peer warning，与需求一致；不需新意图分类器。 |
| Inbox 与通知 | `inbox.ts:84` 冻结 read 页面、`:171` 仅完整持久结果消费；设计保留此边界，单独持久截止和通知水位有必要。但新水位没有接入现有序号分配约束（R1-W2）。仅在 PA 层检查 idle 后用 steer 提交也不足以满足背景忙碌延期（R1-W1）。 |
| 授权、披露和实际发出 | `personal-actions.ts:112` 收集 source evidence，`:117` 获取 authorization，`:51` 在 review/commit 前重新验证。`personal-security.ts:25` 确有 canonical owner DM 固定假设；主 PA/reviewer 同步去除该假设是必要改动。但扩大 owner_messages 会影响现有全量 digest 失效判断，设计尚未处理（R1-W3）。 |
| 升级/恢复 | 新表独立、旧未消费行重新准入、保留旧成功通知水位、禁止覆写 custom_prompt，以及接入 recover/idle/stop，均覆盖了既有资料和生命周期。恢复提交应复用 inputId；设计正确没有声称 exactly-once 模型执行。 |
| Delta | 三份 delta 均指向正确 canonical area；MODIFIED 部分保留原有 Scenario，新增 observer 例外没有删除非 PA 的忙碌及时通知契约。另核 `docs/specs/gateway/global-agent.md:78` 未变更的“其他群及仅作背景的更新不阻塞发送”，它受 R1-W3 影响。无客户端变更，前端 prototype/must-match 不适用。 |
| Milestone / 验证资源 | 仅 `M1-context/.gitkeep`，没有事前伪填 tasks/progress；退出标准有单测、fake clock、真实 DSH、真实模型、真实十分钟和真实飞书回执，验证层次分明。核对 e2e-up/down 脚本、独立 Bot 锁、主仓 Python runtime 与测试 profile 文件存在；PR #371 的 `M1-fix/evidence/validation.md` 记录当天真实平台回复/提醒和同一 PA Web 回归。此轮没有重新登录、启动服务或发送测试消息，凭据当前有效性仍按 runbook 在实施时验证。 |

架构判断：IM 应继续持有可信身份、成员关系、权限与原始证据；PA 的 Inbox owner 管理接收、通知截止与消费；DSH integration 负责通过现有公开运行时入口接纳通知。单 Inbox 加一张背景表与一个 timer 是适当的增量，不需要另一套 scheduler。已有 `session.submit.onlyIfIdle` 可以直接解决背景提交边界，应优先复用；无需增加轮询或新锁层。单 M1 共同交付身份/审核语义也可避免中间版本失配。

### 历史问题闭环

首轮，无历史 issue 或 Author Resolution。

### Issues

#### R1-W1 — WARNING：背景提交使用 steer 兜底竞态，会在新任务已经开始后插入背景

- 位置：`design.md:119-121`；对应 spec“忙碌时合并”、gateway delta“忙碌与重启”。
- 证据：设计明确允许“状态检查与提交之间已变忙”时以 steer 进入下一 step。实际 `packages/dsh-integration/src/index.ts:580-597` 已在消息接纳边界实现 `onlyIfIdle`，同时检查 agent.status、nextTurn、nextStep；`heartbeat.ts:62` 已通过相同 RuntimePort 使用该能力。没有此条件时，`:592` 的 steer 正是向运行中工作追加下一步输入。
- 可重现场景：背景期限已到，PA 层观察 idle；在 RPC 接纳背景前，主人新任务、schedule 或其他合法输入已进入运行时。背景仍被 steer 接纳，在主人任务的下一 step 出现；这不符合“忙碌时不 submit、空闲后合并”，且单独保护 PA 两类 wake 的互斥不能覆盖其他运行时输入。
- 未修后果：十分钟批次会在正常并发时重新干扰主人当前工作，真实忙碌合并测试可能只覆盖提交前就 busy 的简单情形而漏过该路径。
- 需要收口：明确复用运行时的原子空闲接纳条件，并规定 `{accepted:false,busy:true}` 不是成功 ACK：不推进 last_notified_at/通知水位，保留待处理批次，在下一 idle 重试。保留原 inputId 恢复规则；补“PA 判空闲后、runtime 接纳前变忙”的验证。

#### R1-W2 — WARNING：新背景通知水位未纳入 Inbox 的序号不回退约束

- 位置：`design.md:113-124`，尤其候选 `seq > notified_through_seq`、来源 revoke 后重算。
- 证据：现有 `packages/personal-assistant/src/inbox.ts:35-38` 用 `max(max(inbox.seq), max(wakes.watermark))+1` 分配 seq，特意防止来源删除后复用已通知序号；`:41-50` 的 revokeSource 会实际删除 Inbox 行。设计新增独立的 `background_wakes.notified_through_seq/submitting_through_seq`，没有说明把它们加入该分配约束，也不再推进原及时 wakes。
- 可重现场景：只有一个 observer 来源 A，背景 seq=1 已通知；排除 A 删除该 Inbox 行，旧及时 wakes 仍为空。之后合法来源 B 的新背景会按现有分配器重新得到 seq=1，但背景通知水位仍为 1，候选筛选永远不会包含它。
- 独立核验：本轮以 SQLite 内存库执行现有分配 SQL，加设计所述独立水位/删除/候选过滤，输出 `new_seq=1, new_background_candidates=0`；无需假设崩溃或乱序。
- 未修后果：消息虽然保存可读，后续背景提醒会静默遗漏，违背撤销后其他有效更新仍可处理的要求。
- 需要收口：把“序号高于所有持久通知/在途身份水位、撤销来源后不复用”列为该表接入时的不变量，选择最小的统一分配方案，并加入“仅背景历史 → 删除最高来源 → 新来源收件”的测试。不应通过重置通知水位来修复，否则会破坏已有提交身份。

#### R1-W3 — WARNING：把所有主人聊天放进授权证据，会让无关背景来信使外发审核失效

- 位置：`design.md:128-133`，尤其 `authorization.owner_messages` 改为所有可访问主人原文；关联未修改的 `docs/specs/gateway/global-agent.md:78`。
- 证据：`apps/im-server/src/personal-actions.ts:62-63` 在 validate 中比较完整 `authorization.owner_messages` digest；`:139-141` 的 review-result 和后续 commit 都经过该验证。显式依赖 PR #371 中仍是相同逻辑。设计扩大这个数组，却只规定每条证据如何投影，未规定上述失效域如何变化。
- 可重现场景：PA 基于既有明确授权为 A 群准备并审核报价；审核尚未返回时，主人在仅供观察的 B 聊天说“好的”。新的 owner_messages 全量 digest 改变，合法报价在 review-result/commit 被 `owner_authorization_changed` 拒绝。B 的消息即使尚未到十分钟、未被 PA 读取，也会造成该结果。
- 未修后果：背景批次不打断模型的目的不能兑现到实际交付；主人正常聊天越活跃，跨聊天工作越容易反复重审。它也违反现有“其他群及仅作背景的更新不阻塞发送”契约。不能把问题解释为新的主人授权或继续沿用旧 DM-only 过滤。
- 需要收口：区分“给 reviewer 提供的完整可信上下文”和“使该次待发送操作必须重新复核的变化”，明确与目标会话更正、真实主人授权变化、来源撤销的原有约束如何共同生效；补“无关 observer 主人消息在审核期间到达，合法发送继续；相关更正仍失效”的验证。无需引入新的确认实体或语义分类服务。

### Recommendations

无额外可选建议。本轮仅列影响既定需求的三个集成缺口，不扩展产品范围。

### Author Resolutions

- R1-W1 — accepted。核对 `packages/dsh-integration/src/index.ts` 的 onlyIfIdle 接纳检查和 heartbeat 既有调用后，在 design §4 改为 onlyIfIdle=true；busy 不推进通知状态，保留身份等待 idle。新增检查与提交之间变忙的测试。
- R1-W2 — accepted。核对 Inbox receive 分配 SQL 与 revokeSource 删除行为，在 design §4 明确统一序号取 inbox、及时 wakes、背景 notified/submitting 四类最大值加一；新增仅背景来源删除后收件测试，不重置旧水位。
- R1-W3 — accepted。核对 PersonalActions.validate 的完整 owner_messages digest 后，在 design §5 将完整审核上下文与服务器生成的 guard_messages 分离；仅真实主人私聊/明确寻址的参与群原文进入新增授权失效域，保留目标新回复、来源权限及其余既有校验。补无关 observer 来信仍可发送、直接/目标更正仍复核的验证。

本轮不改变 spec 的用户要求、delta 或 M1 数量；修订落在 design 的可复用能力、§4/§5、runbook 第 5 项和 M1 worker 退出标准。

## Round 2

### Metadata

- reviewer: `/root/design_review_623`，沿用 R1 独立 reviewer。
- reviewer target / validated_at: `029cf9a92240fed7488917d7bb2b409345cc2271`
- executed_base: `8330f0565`；显式实施依赖仍为 bugfix-621 `bc59dfa7209f06642bda26aef78b7dfeba125004`。
- review_mode: `delta`
- mode_reason: R1-W1/W2 为局部收口；R1-W3 新增服务器内部 guard 证据投影，需复核它对 review/commit 失效规则和旧操作恢复的影响，不能只确认文字已改。未改变用户需求、模块职责、公开工具接口或 milestone 划分，沿用 R1 full 的其余覆盖。
- compared_range: `10d91e8e5..029cf9a92`
- started_at: `2026-10-20T11:15:16+08:00`
- completed_at: `2026-10-20T11:15:39+08:00`
- duration: `23s`（工具记录的核对区间，不含报告整理）。
- retained_from: Round 1；本轮 diff 只有 design 与审查报告，spec、三份 delta、M1 骨架及产品代码没有变化。

### Verdict

**Approved — 0 CRITICAL / 0 WARNING**

R1 三项问题均在设计层关闭。修订既保留完整事实供 reviewer 判断，又明确区分及时请求和背景通知的提交条件、消息序号与授权失效域，可以进入既定实施流程。该结论是设计门禁，不代表产品代码、真实十分钟批次或真实模型旅程已经验证通过。

### Coverage 与证据

- **背景接纳与恢复**：复核 `design.md:115-127` 和实际 `packages/dsh-integration/src/index.ts:73-79,580-597`。修订使用已有 onlyIfIdle，成功条件明确为 accepted/durable；busy 分支保留期限与身份、不推进通知水位，等待 idle；已接受后 ACK 丢失继续用 inputEvidence 查重。`input-evidence.ts` 会从队列插入或 user/message 识别 accepted，因此重试不会要求已有已接受消息再次通过空闲条件。M1 增加“PA 查 idle 后 runtime 先变忙”的真实接线验证要求。
- **序号不复用**：统一 max+1 纳入 Inbox、及时通知、背景已通知及背景在途四类水位。独立内存 SQLite 复核删除最高 Inbox 行后两种状态：`notified=1, submitting=null → new_seq=2`；`notified=0, submitting=4 → new_seq=5`，新行都进入背景候选。此为设计所选分配规则的验证，不是尚未编写实现的测试结果。
- **授权失效域**：复核 `design.md:133-138` 与 `personal-actions.ts:51-73,139-165`。guard 是服务器产生的真实主人私聊/显式寻址参与群原文集合，既不由主模型裁剪证据，也不把 observer 从完整 reviewer 上下文中删去；新 observer 原文不会改变 guard。直接更正仍改变 guard；目标主人已回复、当前来源权限、受众、策略和附件等仍由原验证保护。旧 prepared/allowed 缺 guard 必须重新 prepare/review，confirmed/unknown 不重发，未产生旧许可绕过。
- **验证与范围**：`design.md:175,181` 已补无关背景不使外发失效、真实更正仍失效以及上述两个时序/序号用例。R1 已核对的真实渠道资源与隔离 runbook 保留，不重跑与本次文档差异无关的服务。需求、delta 的消费者口径、客户端不变和唯一 M1 结构均 retained。

架构判断：修订复用既有 runtime 接纳参数和现有序号分配方式，guard 是 IM 所有的派生证据，不引入新审批服务、第二任务循环或语义分类器。新增规则有明确消费位置和最窄验证，未发现实质维护或运行复杂度问题。

### 历史问题闭环

| Issue | Author Resolution | 本轮证据与状态 |
|---|---|---|
| R1-W1 | onlyIfIdle=true；busy 保留待处理状态并等 idle | `design.md:122-124` 与 runtime submit/inputEvidence 契约一致；忙碌竞态进入 M1。**closed** |
| R1-W2 | 四类最大序号统一分配，不重置水位 | `design.md:115`；独立 SQLite 两组删除后分配验证均高于持久水位。**closed** |
| R1-W3 | 完整 owner_messages 与 guard_messages 分离 | `design.md:136-137` 明确替换旧全量 digest、保留目标及权限复核、拒绝旧无 guard 许可；runbook/M1 增加正反对照。**closed** |

### Issues

无新增问题，无未关闭的历史问题。

### Recommendations

无。

### Author Resolutions

R2 无新增 findings 或 recommendations；author 核对 R1-W1/W2/W3 闭环与实际差异，无实质异议。受审 spec/design/delta/M1 骨架在 R2 后未改；本段只记录门禁接受，不改变受审方案。Gate 2 完成，交给默认 change-orchestrator-simple 实施。
