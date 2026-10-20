# feat-623: PA 消息身份、参与关系与背景批次 — 技术方案

> 对齐: spec.md v1

## Changelog

## 现状分析

### 涉及范围

调研基线为 `origin/main` 的 `8330f0565`，加上未合入的 bugfix-621 PR #371（`bc59dfa7209f06642bda26aef78b7dfeba125004`）作为显式实施依赖。后续文档提交不改变该代码基线。

| 位置 | 当前事实与本次责任 |
|---|---|
| `apps/im-server/src/personal-agent.ts` | 认证绑定、来源权限、原始消息与观察事件；当前按会话把主人分为 owner_instruction/owner_fact，授权证据过滤主人私聊。本次改为事实投影和带上下文的主人原文证据。 |
| `apps/im-server/src/work.ts` | PA 查询合并主人和 PA 权限；info 的 is_member 可能代表主人，不能用它判断 PA 参与关系。 |
| `apps/im-server/src/messaging.ts`、`gateway.ts` | 已有群 mention/interaction_reply 触发元数据；复用同一解析，不新增模型可见 mentions。 |
| `packages/personal-assistant/src/personal-assistant.ts` | 可信准入结果目前写 personal_source_role，并对非主人逐条做输入检查；本次把观察背景与直接请求分开。 |
| `packages/personal-assistant/src/global-agent.ts` | 观察拉取逐条调用 receive；PA attention 目前绕过普通 needsAttention 群策略；控制命令在入 Inbox 前处理。bugfix-622 已把及时通知接到公开 steer。 |
| `packages/personal-assistant/src/inbox.ts` | SQLite 原消息去重、冻结分页、完整 tool/result 消费、wake watermark；本次新增独立背景通知状态，保留同一 Inbox。 |
| `packages/dsh-integration/src/personal-security.ts`、`global-mode.ts` | 固定身份/授权与工具指导，当前把其他聊天的主人原话一律当背景；改为解释身份、参与关系和上下文。 |
| `apps/im-server/src/personal-agent-defaults.ts` | 仅更新新建默认说明；不得覆盖已有 custom_prompt。固定协议说明由运行时维护。 |

### 既有约束

仅通过 DSH 公开 exports 接入，PA 不依赖 DSH；调度仍由 runtime 负责。沿用唯一 PA 主 session、现有来源授权和去重、原聊天回复、工具审批、原始时间/渠道、发送前复核、confirmed/unknown 结果。背景批次是 Inbox 通知节流，不是新任务引擎或用户 schedule。

### 可复用能力

- 用 `sourceAccess/sourceAllowed` 过滤可读范围；用真实 `conversation_participants` 中 PA 对应 agent user 判断参与身份。主人观察权限和历史参与记录不证明 PA 当前在场。
- 改 bugfix-621 的 `sourceRole` 为 owner 身份判断；保留其绑定 app、配置 agent、sender_source_id 与 owner_open_id 核验，以及真实目标 `ownerConversation`。首次来信绑定不变。
- 用既有 `needsAttention`、群提及/回复解析、Inbox 单条唯一键和持久消费；用 bugfix-622 的 `mode: steer` 处理直接提醒。
- 用既有 `session.status idle`、recover、stop 生命周期补发到期背景；只增加一个最近截止的本地 timer，时间与进度落在同一 SQLite。
- 不用 `pa_observation` 判断观察者：飞书主人与 PA 的直接聊天也通过这个传输入口。它只标识管道，不描述会话关系。

### 相关历史

feat-616 的双身份访问、披露审核和固定绑定保持。bugfix-621 尚未合入，实施必须先合入或在显式包含该提交的集成基线上进行，不自行批准其合并。bugfix-622 已合入，直接提醒继续及时 steer；背景通知另用空闲条件，不回退全局忙碌提醒修复。

## 架构总览

```mermaid
flowchart LR
  M[已授权的原始消息] --> S[IM 核实主人身份与 PA 参与关系]
  S --> I[同一个持久 Inbox]
  I --> P[参与会话: 既有触发策略]
  I --> O[观察会话: 十分钟背景截止]
  P --> N[及时 Inbox 系统提醒 / steer]
  O --> B[到期且空闲: 合并背景提醒]
  N --> A[同一 PA 主 session 主动 check/read]
  B --> A
  A --> R[原始消息 + 身份 + 参与关系]
```

消息入库不等于提醒，提醒不等于读入上下文，完整持久 tool/result 才消费消息。PA 直接来信的提醒可同时说明有累计背景，但不把背景正文自动塞进上下文。

## 关键决策

**只提供身份与参与事实，不在输入上判定“指令/事实”。** `sender.is_owner` 说明是谁，`delivery: participant | observer` 说明 PA 是否属于该聊天，`conversation_type` 沿用现有类型。群里主人向别人说话仍 is_owner=true，是否交给 PA 由原话与上下文决定。

**参与关系在准入时由 IM 核实。** Web 以实际 PA 成员行判断；既有外部 bot 会话按绑定 app/config_agent 与合法 shadow 关系确认 PA 接收，不能用 shadow 中代投影的主人身份或 owner-view is_member 推断。当前接入范围没有任意飞书他人私聊抓取。

**背景只在到期且空闲时单独提醒。** 忙碌时保留一个累计待办，不每十分钟插入一次模型上下文；主人直接请求仍在下一 step 前收到提醒。二者共用同一提交互斥，避免直接通知被背景的空闲等待阻塞。

**观察文本不是直接请求，不触发逐条请求审核或自动警告。** sourceAllowed、当前联系人访问规则仍执行；observer 原文作为不可信背景进入 Inbox，不调用逐条 input reviewer、不从它自动生成 peer warning。participant 的非主人输入保持原有检查与风险提示。所有实际对外披露仍经过既有 action review，未扩大任何发送授权。

**原始主人证据必须保留对话上下文。** 删除“只有主人私聊才是授权原文”的固定假设，也不把所有 is_owner=true 都变成授权。主 PA 与独立 reviewer 都要知道原会话、参与关系、发言对象和相关问答；已有授权可在别处延续，观察到的主人承诺不能自动授权 PA 代做。

## 接口与数据流

### 1. 可信事实和最小投影

`pa.source.admit` 在当前权限检查后返回 `is_owner`、`delivery`、`conversation_type`、`channel`、已有 policy_revision/actor_risk，移除 role。`is_owner` 复用 bugfix-621 的真实身份规则，外部 sender_source_id 不等于 bound owner_open_id 时为 false。`delivery` 不接受消息正文、调用方自报或模型填值。

Global receive 写入由准入结果覆盖的内部 metadata（`personal_is_owner`、`personal_delivery` 及既有 conversation_type/channel）；每次准入清除旧 personal_source_role，不允许旧 payload 重新覆盖可信结果。观察事件带既有群触发所需元数据：从存储原消息调用现有 `mentionedAgents` 与 interaction_reply 解析；合法外部 inbound 继续沿已认证 channel metadata 的提及/回复结果。不得创建新的 mentions 语义或模型输出字段。

PA `inbox.check` 仍为 sources 数组，每项只补 `conversation_type` 与 `delivery`；原 target/name/unread/requires_attention 保留。PA `inbox.read` 保留 target/messages/content/time/channel 结构，每条 sender 加 `is_owner`，每条消息加 `conversation_type` 和 `delivery`，移除 source_role。read 放在消息层是为了保留接收时事实，避免退群/入群前后未读混合时错误共用一个标记。check 的 delivery 取该 target 最新可信关系，仅作导航；逐条 read 是历史事实依据。不增加 participants 或 mentions；不清楚谈话对象时查询现有 conversations info/read。

示例（省略不相关字段）：

```json
{"sources":[{"target":"conversation:7","name":"与小王的聊天","unread":2,"requires_attention":false,"conversation_type":"direct","delivery":"observer"}]}
```

```json
{"target":"conversation:7","messages":[{"id":"m1","sender":{"id":"owner","type":"user","name":"主人","is_owner":true},"conversation_type":"direct","delivery":"observer","channel":"web","time":"2026-10-20T10:04:00+08:00","content":[{"type":"text","text":"好，我今天改报价。"}]}]}
```

同一人的 is_owner 不因 direct/group 或 participant/observer 改变。参与会话不意味着每句话都发给 PA。原 sender.id/type/name、时间、内容、附件和真实回复目标不改写。

### 2. 准入、触发与命令

1. IM 原消息权限、主人身份、PA 参与关系统一准入，继续 dedup 原 message_id；观察事件 ACK 仅表示已落入 Inbox，不代表读完。
2. observer：不执行 slash control、不做请求式 input review，立即存为 attention=false，登记背景期限。主人本人和他人消息同批。
3. participant：非主人按既有 input review；普通文字的 attention 使用 needsAttention，恢复 PA 的现有群策略。私聊及时，群聊按配置、提及或回复触发。
4. PA `/stop`、`/new` 以及 sessionControl 只接受可信主人在 participant 会话中的直接输入；群控制继续要求现有显式寻址条件，不能借 groupReplyPolicy=always 接管未寻址命令。observer 中相同文本是普通背景。
5. 主人直接输入触发 wake 前，先等当前观察拉取完成/主动拉取服务器已积累事件，再生成 check 摘要；避免 owner DM 先提醒、相关背景仍留在中心。采用现有 observations 单飞，但不得在 recoverPersonalObservations → receive → wake 内等待自身：拉取循环只入库、记录待及时通知标志，整批落库后统一 drain wake；普通直接入口可先拉取再 drain。拉取失败不吞掉主人请求，通知说明背景同步未完成并允许现有历史查询补充。

### 3. 两种系统提醒

participant（只报来源/计数与背景可读状态，不注入正文）：

> 你的参与会话有新消息，请 check/read 并结合发送者和谈话对象决定如何处理。主人其他聊天有累计未读更新，可读取与本次请求相关的背景。系统提醒不代表真人授权；回复使用原会话的 send_message。

observer 批次：

> 主人其他聊天有一批新消息，来自你未参与的会话，并非直接发给你的请求。请读取累计更新，理解主人的沟通，结合既有目标与授权判断如何协助。不要自动接受别人给主人的任务、代主人承诺或向原聊天插话；无须协助或告知时保持安静。

固定 runtime 指导与 reviewer policy 同步移除旧 role 语义。只更新新建默认指导，不覆写存量 custom_prompt；当前系统协议为既有 PA 提供新规则。

### 4. 背景批次状态与时序

在 Inbox SQLite 新建一张小表 `background_wakes(agent_id PRIMARY KEY, last_notified_at, due_at, notified_through_seq, submitting_through_seq)`。原 Inbox 不复制，observer 与归属保存在输入 metadata，原 `wakes` 继续服务及时通知。receive 与首次登记 due_at 在同一事务完成；重复消息不改变期限。所有时间为节点持久接收/通知时间的 UTC 毫秒，不使用聊天原发生时间。

- 候选集 = 权限仍有效、observer、未消费、seq 高于 notified_through_seq 的 Inbox 行。
- 尚无通知历史：首候选接收时 `due_at=received_at+600000`。
- 已通知过：首候选使 `due_at=max(received_at,last_notified_at+600000)`。后续输入不推迟 due_at。若通知距今已超十分钟，空闲时新数据可立即形成一批。
- 没候选时取消 timer/清 due_at；保留 last_notified_at 和通知水位。读取使候选消失即撤销该空批；后来的新首批按上述规则重新计算，不从直接消息时间重置背景节奏。
- 到期且忙碌：不 submit、不更新时间，维持 due；下一次 idle 一次收齐所有当前候选。直接通知永远不受该条件限制。
- 到期且空闲：取得最高候选 seq，先持久化 submitting_through_seq，以 `inbox-background:<agent>:<seq>` 为幂等 inputId，沿公开 submit 的 steer 入口发系统通知。steer 避免状态检查与提交之间已变忙时排成一轮独立 followup；这只是兜住正常事件竞态，不硬中断。成功 ACK 后原子更新 notified_through_seq、last_notified_at、清提交标记，再为期间新增候选登记下一期限。
- 未 ACK/进程重启：submitting_through_seq 存在时复用同一 inputId 重试；不扩成新的批次。没有提交标记的已消费消息不触发通知。运行时已接收但本地未 ACK 的重复 submit 沿原幂等语义恢复，不声称 exactly-once 模型执行。
- 通知成功只推进通知水位，不推进 fragments/consumed。新消息后续通知可引导再看尚未读完的旧消息；无新增时不靠十分钟定时器反复催读同一条。

GlobalAgent 维护最近 due_at 的一个 timer；启动/recover 从表恢复并重设，idle 事件尝试 drain，stop 清 timer。仅 observer 且有效的候选有 timer；多 PA 取最近截止，无候选不空轮询。source revoked/excluded 走现有 revokeSource 后重算候选；每次后台 drain 先完成来源恢复/核验，离线无法核验时等待连接，已过期恢复后立即尝试。等待到期或等待 idle 不使 NodeUpdater 永久 busy；仅提交/准入正在执行时计入 busy。

### 5. 授权与披露保持同一事实口径

IM 提供一个内部原消息事实投影，供 admit、authorization、source evidence 和 history read/search 共用；避免主 PA 看到新语义而 reviewer 继续使用私聊过滤。

- `authorization.owner_messages` 改为所有当前可访问、可信主人身份的原文，带 message/conversation ID、conversation_type、delivery、channel、sender 和 interaction_reply。保留原始问答所在会话的可验证上下文及实际发表 proposal，不把其他会话时间相邻的回答拼成确认。上下文来自既有 messages/conversations，不增加新的确认实体。
- `PersonalActions` 的 sources 同样提供可信身份与关系。独立 reviewer 不再按“其他聊天一律不是授权”拒绝，而是核对具体原话是不是给 PA、授权对象/范围和现在的实际受众。observer 原文只能作为背景或已获授权任务的新信息，不能仅凭 is_owner=true 升格为新授权。
- `ownerMessage`（来源设置工具使用）移除 source_role 检查，核实原始主人 + participant + 原文实际寻址：主人与 PA 私聊，或现有明确提及/interaction_reply 指向 PA 的共同群。返回带上下文证据；模型仍负责动作与原话一致。observer 引用不能直接改变来源设置。工具描述同步移除 canonical-DM-only 表述。
- 实际主人私聊免披露复审继续由 bugfix-621 的 ownerConversation/真实外部目标判断；不能用 incoming is_owner 或 conversation_type=direct 替代。群聊和他人私聊保持冻结 payload、真实受众、当前来源权限与独立 review。

### 6. 既有数据与升级

不清空 Inbox、会话或 Work。对尚未消费但缺少新事实的 PA Inbox 行，recover 通过同一服务端准入重新核实；已撤销的来源沿既有路径撤销。移除旧 role 投影，新事实持久化后恢复通知；原先 attention=1 的 observer 改为背景，原及时通知水位不复位。已成功及时通知过的旧行不再登记背景新通知，未通知旧行在首次恢复时开始十分钟计时。不修改已提交的 reads 快照或历史 tool/result，历史旧标签只作为旧记录，不继续作为当前授权规则。无需全历史重写或双写兼容层。

## 契约层增量 (delta-spec)

- `docs/specs/gateway/personal-agent.md` ← `specs/gateway/personal-agent.md`：事实身份、参与关系与背景时序。
- `docs/specs/gateway/global-agent.md` ← `specs/gateway/global-agent.md`：通用及时通知保留，明确 PA 观察批次例外。
- `docs/specs/im/personal-agent.md` ← `specs/im/personal-agent.md`：双向沟通不是自动交办，观察消息不自动触发 peer 警告。
- bugfix-621 的 external-channels 与主人私聊回归不重复写契约，不改其目标边界。

## 风险与回退

- 主人身份误投影会放大授权：所有读取/准入/审核复用同一可信函数，测试群与外部冒称；不从通知猜身份。
- 参与关系变化：read 保留逐条接收关系，当前访问每次重验；check 导航不能覆盖消息事实。
- timer/ACK 崩溃：持久期限与提交批次身份恢复，保留 Inbox 消费独立性。只做该必要恢复，不新增通用调度框架。
- 真实模型可能仍误判对话对象：用完整工具、实际动作与消息回执验收六组语义案例，不能以单看回复承诺替代。
- 回退为代码版本回退，保留新表不删除数据；旧版本可能恢复逐条通知的旧体验。升级不承诺抹去已经进入主上下文的旧标签。

## Runbook for Reviewer

本 unit 不改客户端。**Review 驱动方式**：端到端真栈，使用 Web 客户端同一登录、建聊天、发消息、查询聊天/Work API 驱动；后端、真实 DSH、真实模型与实际持久化不可替换。飞书用专用测试 Bot 与真实平台用户账号收发，读取平台消息核对真实到达。

| 服务 | 停止命令 | 启动命令 | 健康检查 |
|---|---|---|---|
| 隔离 IM + Node/DSH | 在本 unit 实施 worktree 执行 `./scripts/e2e-down.sh --wt "$PWD"` | `pnpm install --frozen-lockfile`、`pnpm build`，前端按脚本要求构建后，`NANO_MULTIAGENT_E2E_MODEL='codexOAuth:gpt-6.1-sol' ./scripts/e2e-up.sh --feishu --wt "$PWD"` | `.e2e-ports.env` 的 IM `/im/health`、节点在线/PA runtime 可用；再做实际发收，health 不代替验收 |

**验收前置**：本机既有模型代理与可用模型授权；Python 使用主仓 `.venv/bin` 放入 PATH。专用飞书资源在 `~/.config/nano-multiagent/feishu-e2e.env`，CLI profile `e2e-feishu-testagent`；bugfix-621 本日真实测试已经续期并验证可用，实施时只读检查 auth 状态与测试 Bot 锁，过期才申请重新登录。不使用生产 Bot/配置。创建正式 PA，把脚本 fixture Agent 的测试 channel 释放后挂到 PA，保留首次真实来信绑定路径，不手填主人。Web 使用隔离 owner、peer 两账号及 PA 创建私聊和群，成员关系经正常客户端 API 建立，不通过直接写 DB 伪造场景。

**最低实测清单**：

1. 相同报价主题六组真实模型案例：主人→PA 交办；主人→peer 指令；peer→主人请求；主人→peer 承诺；共同群明确向 PA 交办；非主人冒称。每例保留真实模型输入事实、check/read、必要 conversation 查询、实际工具副作用和公开结果，观察场景不得在原聊天插话。
2. 至少一轮真实十分钟：首条起计、期间多次收发、到期不再发消息仍通知，所有累计消息可完整读取。记录收件、截止、submit 与 read 时刻；不以缩短 timer 的测试替代此轮。
3. 独立一轮提前请求：背景未到期，主人直接引用小王条件，证明背景已可读、结果正确，跨过原到期点不再通知已读条目。
4. 忙碌中直接更正及时读取；背景忙碌延后合并。工作视图/原生轨迹可观察通知与读取区别；通知正文不包含新消息原文。
5. 真实飞书主人原地回复与一次性定时提醒，平台 API 读取确认各一次，Web 同一 PA 回归。来源撤销、重放、失败出站不堵入站、群/他人私聊披露限制复用 bugfix-621 有效用例。

## Milestones

| ID | 标题 | 依赖 | 并行组 | 范围 | 退出标准 |
|---|---|---|---|---|---|
| M1-context | 统一事实投影与背景通知，完成真实旅程 | bugfix-621、bugfix-622 代码基线 | — | 上述 IM/PA/DSH 接线、对应既有 tests、`apps/node/tests/global-inbox-native.test.ts`、本 unit evidence；无客户端更改 | [reviewer] spec 全部场景通过，六组意图对比、真实十分钟批次、提前引用背景、真实飞书回复/提醒与 Web 连续性有实际结果；[worker] 可信身份、成员/观察关系、群触发/命令、旧数据恢复、通知/消费分离测试通过；fake clock 验首批/后续固定期限、空批取消、无新来信到点、忙碌合并、ACK 重试、重启/撤销及直接 wake 竞态；真实 DSH fixture 验 steer 及时通知与背景空闲合并；相关类型检查、build、架构契约与 docs-check 通过 |

测试先最窄现有 inbox/global-agent/personal sources/disclosure/attention 与 personal-security，再实际 DSH 接线与真实模型。原生 fixture 测时序，不宣称真实模型理解已验；平台回执与实际观察证明交付，不以模型自述代替。单 M1 保证身份、通知、审核上下文和验证共同交付，避免中间状态新旧语义混用。
