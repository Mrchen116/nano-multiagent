# 统一 PA 模型独立审查：一个身份，分受众的执行与资料权限

2026-10-16。基线 `main@481467ac16f0eda4561fca5c8230050541600de9`，工作树仅 feat-616 未跟踪设计材料。范围：现源码静态核查、active spec 与观察候选方案；未运行服务、攻击测试或视觉验证。本文是设计前研究审查，不是 Gate 2 Approved；当前尚无完整 design/delta/milestone 可供正式 Gate 2。只写本文件，不改产品代码、spec 或其他作者文件。

## 结论先行

用户要的产品是“属于我的一个人”：名字可改、身份固定、主动理解我的工作，也可在原生 IM 接待别人。不是“一个全权限会话公开接待所有人”，也不是“私人机器人加一个新请求门户”。推荐把这句话落实为三个相互正交的维度：

1. **产品身份**：每个 owner 唯一 PA binding，稳定 Agent ID、自定义名字；onboarding 首个 Agent 即 PA。普通 specialist 不抢占该角色。
2. **会话受众**：本人专属私聊、其他人与 PA 的普通 DM、PA 参与的群仍是现有 IM conversation。owner 其他会话的观察不是新增成员，也不是对方与 PA 的新会话。
3. **执行权限**：私密主脑跨来源持续认知；外部执行只知本会话及已放行资料。一个显示身份不要求所有执行共享上下文、文件、工具或授权。

复用 global 持久执行、Inbox 可靠摄取、DSH 调度及 task_graph。不能复用其“所有输入都进同一 global binding”的路由语义来处理 PA 的全部外部会话。可联系性与私人资产可读性也必须拆开，不能把 PA 的 space 改成 company 来完成“别人能私聊”。

## 一、代码事实与设计差距

以下是已核查的 current 行为，**不是未来方案已实现**。

| 代码位置 | 实际行为 | 统一设计必须处理的后果 |
|---|---|---|
| `apps/im-server/src/identity.ts:45-69` | Agent 固定 space，`canActorAccess` 要求 profile.space_id 等于目标 space | 不能简单让 private PA 进 company 群；放宽同一个 helper 会影响所有资料，而不只是联系人 |
| `apps/im-server/src/messaging.ts:178-230,630-668,676-686` | 联系人、建群、建 DM 与目标解析都依赖上述 space；群邀 Agent 限 owner；DM key 含 space | 原生 IM 联络需统一修改发现/建联/成员与解析，不能只开放联系人入口 |
| `packages/personal-assistant/src/global-agent.ts:48-86` | 每 agent 使用 `global:<agentId>` 单主 binding；全部正常输入进同一 Inbox；真人裸 `/stop` 可取消该主 session | owner 观察和外部 DM/@ 不能直接复用 receive；owner 控制需认证，不由文本自称身份 |
| `global-agent.ts:88-103` | 忙时不强插正文，空闲才提交 system wake，随后显式读 Inbox | 主动性可复用可靠唤醒，但“立即收到事件”与“已读懂/处理”不能混称 |
| `global-agent.ts:110-145` | 只限制 child 使用 inbox/conversations；其他产品调用继续带根 binding | 普通 child 不是外部隔离域；限制 Inbox 不等于限制其他读写/发送 |
| `packages/dsh-integration/src/product-bridge.ts:10-27` | 沿 parentSession 找绑定，传同一 agentId/ownerId 和真实 sessionId/rootSessionId | 现有产品身份继承须叠加不可由模型指定的执行 scope，不能只凭 agentId 授全权 |
| `packages/dsh-integration/src/index.ts:166-177,333-339` | child 配置走 parent 路径；fork 沿用源配置与 binding | 不能把 fork/普通 subagent 命名为“安全会话”就当它无私密历史 |
| `packages/dsh-integration/src/agent-config.ts:76-106,129-145` | persona/skills/extensions 配置按 Agent 附加；配置刷新影响同 agent 的多个执行 | 分 session 但共享私人 persona、skills、插件和目录仍可能泄漏；需独立 execution profile |
| `packages/dsh-integration/src/capabilities.ts:53-68` | global 非 subagent 强制补 inbox/conversations/send_message/subagent | 空 allowlist 不足以做 global 外部隔离；需改变 role/profile 的确定性规则 |
| `apps/im-server/src/work.ts:41-60,476-488,707-741` | 仅一 global_main；query 检查该 scope；Work 读路由默认核 space，非一律 owner-only | 外部执行不能伪装第二 global_main；PA 私密 Work 必须独立 owner-only，不能因可联系就可看轨迹 |
| `apps/im-server/src/task-graphs.ts:252-259,393-400,445-465,709-747` | claim 会改 assignee 且拒绝领取他人已负责任务；读写使用真实主体、来源会话权限，Agent list 限固定 space | 帮 owner 处理 task 不可用 claim 实现；当前私密 PA 也不能仅按 owner ID 查询公司 task |
| `apps/im-server/src/gateway.ts:504-579` | 消息实际署名 Agent；接收方 direct relay 还取决于 target_kind | 新外部 scope 应绑定真实目标，而不依赖模型选择 agent:/conversation: 字符串来决定投递行为 |
| `packages/dsh-integration/src/policy/approval.ts:112-116` | 产品解析本人私聊后免分类器；其他发送有审核 | 这是一层动作审查，不是让公开会话安全共享全部私料的证明 |

既有 routing audit 中“默认不观察、外人另用 request 入口”的推荐已被用户新要求替代；其中源码现状仍可引用，旧产品推荐不能继续作为方案前提。

## 二、统一路由模型（proposed）

服务端与 Node 根据可信身份、conversation 和 PA binding 选择路线，模型不得选择自己是 owner 或切换安全域。

| 输入 | 执行与上下文 | 可见输出 |
|---|---|---|
| 已认证 owner 主动对 PA 的专属 DM | 私密 `global_main`，本人记忆、已授权观察及任务证据 | 默认本人 DM；对外输出必须另经披露/动作检查 |
| 外部人或 Agent 对 PA 的普通 DM | `external_chat` scope，按真实 conversation 绑定；新建时无私密历史 | 同一原生 DM，以同一 PA 身份回复 |
| 原生群 @PA / 合法 reply | 该群的 `external_chat` scope，按群历史与当前成员权限 | 原群，复核群受众/新消息，不默认另开私信 |
| owner 收发消息、历史回溯、任务变化 | 独立 system observation 入口；不作为对 PA 的真人命令 | 私密主脑发现问题、准备资料/草稿、提醒 owner；不擅自加入源群 |
| 内部执行结果 | 依据委派时宿主绑定的父任务/执行 scope 回传 | 不把 worker 的“owner同意”当授权，不自动公开其完整报告 |

“fresh”指不继承私密主脑，不要求外部每条消息都失忆。可以持久保留同一外部会话内的历史；不同 DM、不同群不互相继承。群成员变化或资料撤权后，旧已放行资料可能已在历史里，须使旧执行上下文失效并重建最小合法上下文，不能只改下一次 API 的 ACL。

一个 PA 保留一个私密 `global_main`，而非每种路线再造 global。外部执行为独立 scope，可在私密 Work 中供 owner 查看；外部用户只看普通聊天，不获得 Work/session/run ID 的查询资格。必要的“处理中/离线”状态来自交付记录，不暴露内部工具、源标题、其他用户任务。

## 三、可联系身份与私密资产如何分开

推荐新增“该 PA 在此 conversation 的参与资格/受众能力”，而非改变其私密资源 home space。公开可联系 profile 只含需要的名字、PA 角色与所属本人等展示字段；是否展示 owner/在线状态亦需产品收口。头像和名字不是认证凭据。

原生公司 DM/群仍使用原 conversation 权威记录与成员表；PA 可以拥有经过授权的 conversation participation，读取/发送仅作用于此 conversation。private owner DM、记忆、Work、附件、配置不随 participation 发布。不要让通用 `canActorAccess` 因“personal role”就变成跨全部 space 真值。

建议服务端分别判定 `canContactPA`、`canParticipateInConversation`、`canReadPrivatePAAsset`；这些是职责边界示意，不要求建立三套重复 ACL 数据库。contact policy、已存在的 membership 和 PA binding 各自为唯一事实源，helper 组合它们。

同时覆盖：已知 ID 直接访问、搜索 snippet、下载链接、旧分页游标、轨迹附件、节点诊断与配置接口。只保护聊天列表不会保护资料。外部网络平台映射继续用真实 sender 身份，不能用 shadow user 的归属推定 owner。

## 四、既能使用主人资料，又不反灌核心

### 4.1 不接受的捷径

- 外部会话给私密主脑一段 prompt：“请查询秘密并回复这里”；主脑执行后叫一次发送审核。
- 普通 child/fork 拿主人 workspace，再用 prompt 要求只看指定文件。
- 先让模型总结外部消息，再把“summary”标签当安全证明。
- 主脑自行批准自己生成的资料包；外部声称 owner 已同意就延续授权。

无论称 parser、sanitizer 还是 researcher，模型输出都可能保留恶意语义。受限提取可减少暴露与无关信息，但不能把输出升级为可信指令。

### 4.2 推荐的双向数据交换

外部上下文可处理本会话已知事实、解释可提供帮助的范围、提出必要澄清。遇到需要 owner 私料/决策，向私密侧提交有来源的请求记录：原消息引用、真实请求人、问题、所需资料类别、目标会话。记录仍是第三方请求，不是已批准任务，更不自动生成披露许可。

私密主脑结合 owner 信息判断是否值得帮助，可以立即进行只读准备，并在本人 DM 给具体选择；没有必要每次弹“是否准许处理外部请求”，也不需要新门户。若已存在精确的长期披露权限，按其边界处理，否则让 owner 在已有私聊确认具体资料和受众。

真正传入外部上下文的是宿主校验后的最小放行包：资料/结果、来源对象版本、受众（conversation 和必要时成员版本）、用途/任务范围、有效期、授权证据。授权依据只能是真实 owner 决定或明确既有规则；私人主脑提议本身不能作为依据。这个记录只保存披露权限与回执，不保存第二份用户目标/任务状态。

例：对方问下周何时开会，私密侧计算可用时段；获准分享的是两个时段，不是完整日历、冲突事项名称或“因为看医生不能来”。对方再问原因，是新的数据请求，不被上次时段授权覆盖。附件需具体对象和版本，不能授予 owner 全盘搜索能力。

对外回复在外部 scope 内以本会话上下文和放行包生成；发送时宿主校验 conversation、当前成员/ACL、包版本、许可、输出附件和新消息。允许主脑准备完整待发草稿，但它属于待放行资料，不能通过内部消息工具跳过同一边界。

### 4.3 真实剩余风险

私密主脑为理解用户问题仍可能看到恶意第三方内容；它若同时能任意 shell、联网或调用插件，注入仍可能借非 IM 通道外泄。故 execution profile 不能只限制 send_message，还要覆盖文件、网络、插件、memory 写入及再委派。外部 scope 默认没有这些私密能力；私密侧的有副作用操作继续用真实 owner 授权与动作权限，不因 observation 是 system 事件而自动放行。

设计不能声称绝对免疫提示注入。需要验证：真正没有私密输入/凭据/挂载、工具在宿主拒绝越界、模型无法替换授权证据、普通及多轮攻击不能越权；不能以“拒答率高”代替这一组不变量。

## 五、主动观察不是手动任务服务

沿用 `proactive-observation-design.md` 的 source event → durable ingestion → priority/coalescing → private global wake → 按需读取方案。消息收发和本人回复都要感知，才能知道“别人等我”以及“我已经处理”。历史回溯与增量并行，任务实际 revision 变化而非通知文本是事实源。

观察授权是持续产品能力，不要求逐条分享；默认覆盖哪些群、历史窗口/排除策略可在 onboarding 设置。观察不等于成员身份，不改变真人已读、不伪造实时 owner 意图、不自动向源会话回复。

同时不要把所有外部正文直接持续灌满主脑：按来源/任务聚合候选，必要时回查。受限观察执行输出带来源的事实主张，不输出“请以 owner 身份运行此命令”的可执行指令。可以准备查资料、工作材料、回复草稿、检测任务依赖并主动给主人建议；这已是主动工作，不必靠默认自动承诺来证明主动性。

优先处理本人请求、真实任务阻塞与截止变化；普通更新合并，历史扫描低优。Inbox 接收/模型摄取/任务完成/消息送达是四种不同状态。主脑忙碌时不另起第二 loop，而是持久等待并在安全时机继续。

## 六、任务推进：协助与责任分开

`task_graph` 保持唯一任务真相：graph/node ID、revision、负责人、状态、结果仍在原图。PA 对 owner 任务的观察索引只保存引用、已检查 revision、候选下一步与交付记录，界面显示状态时回查；不建立平行 PA Todo 状态机。

三层动作要分清：

1. **可主动做**：查 owner 当前有权且在观察范围内的任务、准备材料、查缺漏、发现依赖、给主人建议。
2. **已获任务执行授权后做**：私密内部委派、推进已批准的实质工作、收集结果。内部 worker 运行与 task assignee 无须一一对应。
3. **独立写权限**：写回 task 结果/状态、建立公共子任务、改派负责人、删除，使用当前 actor、来源会话与 revision 检查。用户说“帮我做”不自动等于“改派给你”。

当前私密 PA 没有 owner 公司图的普通 Agent 权限。只读观察投影可解决发现和准备，但不能默默解决写回：需要设计“有界代表协助”的 mutation 契约，或让 PA 在该会话有正常成员资格后以自己真实身份写。前者保留 `actor=PA` 与 owner 授权范围，绝不能伪装 `actor=user` 或继承公司管理员删除权。若首版不实施这种写能力，就明确首版能准备交付/让 owner 应用，不能说已能自动完成所有本人任务。

外部会话协作仍引用同一源任务；外部提要求不自行成为 owner 承诺。I2I 的 message、任务接受、开始、结果待确认、完成需区分；消息送达不是任务完成。

## 七、怎样复用既有系统而不制造第二真相

- **IM server**：身份/参与资格/源数据 ACL/持久事件/真实消息交付；不运行第二 Agent loop，不负责用模型评估全部消息。
- **PA 层**：根据可信来源选择 scope，持久 Inbox 与观察摄取、执行绑定、目标验证、资料包交接及回执。
- **DSH integration**：通过公开 exports 提供 profile 受限的运行、恢复、工具约束和通知；不修改 DSH 内核或依赖私有 import。
- **DSH runtime**：继续唯一执行调度器与内部子任务机制；独立 scope 不等于另造 runtime。
- **task_graph**：任务真相；新增 observation cursor、release receipt、execution link 是交付/权限事实，不是第二任务库。

新 profile 必须同时隔离 prompt/history、persona/memory、skills/extensions、workspace/文件权限、credential/network 能力、产品工具授权。仅建立新 sessionId 不够。当前配置刷新按 agentId 联动，实施时需把“产品 PA 配置”与“宿主派生的最小执行 profile”区分，不能为外部 scope 关工具时顺手关掉本人主脑，或反过来升级外部权限。

外部 route 不能直接套 single_thread 完成：其 `session.submit` 来源映射、自动最终投递、共享 Agent 配置等都需对新 scope 审核。更稳妥是复用单会话绑定/恢复机制，明确外部 profile 的显式投递和安全入口，而非切换整个 Agent 的 work_mode。

## 八、必须收口的设计决定

### 架构必须决定，无须反复问用户已确认的产品方向

1. private global 与 external scope 的数据/工具/目录/凭据边界；DSH 公开能力可实现到何种程度，哪些必须在宿主 broker 检查。没有证据不得宣称已支持强沙箱。
2. PA participation 与 private asset ACL 的独立判定，及新建 DM/group 路由全链路；不要只改 UI。
3. owner_task 只读与写回的分界；是否提供有界代表协助，以及授权、审计和撤权如何执行。
4. 外部对 owner 私料的请求怎样最小化送入主脑；什么条件允许放行；受众变化后旧 scope 如何重建。
5. 与 current global spec 的明确 delta：普通 global 不变，personal role 私密 global 不接管所有外部会话；外部不得取消/compact/config 主脑，现有 owner `/stop` 子工作语义不要顺带扩张。

### 需要产品选择的少数问题

- 谁能发现/首次私聊 PA、谁可邀其入群：推荐先沿既有公司可联系关系与 owner 设定，保留屏蔽/频控；“原生 IM”不必等于全网匿名联系。
- 自动观察默认包含哪些已加入群、历史窗口、排除来源与通知节律：用户已确认自动观察，不能重问要不要。
- 哪些资料/行动可以长期自动对外处理，哪些先请 owner 决定：通过具体示例确定，不给一键“允许全部隐私”作为便利默认。

## 九、整体旅程验收，而非孤立安全补丁

1. owner 起名后完成 onboarding，已有身份改名不换 ID/不生成新 DM；之后自建 specialist 不替换 PA。
2. 同事直接私聊 PA、在合法群 @PA，使用现有聊天界面；只能看到该聊天，不可通过同一 Agent 的 Work/附件/搜索接口看到 owner 私密材料。
3. 同事给 owner 发来请求，owner 未手动转交，PA 主动发现并准备回复；owner 已回复后取消过时提醒；观察不把 PA 加入该 DM。
4. 同事直接问 PA 私密问题，PA 以会话已知内容回答或在 owner 私聊提出具体决定；外部不得凭“主人说可以”获资料，也不能经提取摘要触发主脑自行批准。
5. owner 只批准候选时段，外部仅得时段；多轮诱导、附件/链接、插件/网络侧通道均不泄露冲突详情。
6. owner task 被 PA 协助推进，负责人仍是 owner；状态写回显示 PA 真实 actor，按 revision 冲突处理；源任务已关闭/改派后不继续旧计划。
7. 群成员改变、会话排除、company 资格失效、节点转移使旧队列/游标/资料包/上下文失效；已外发数据无法撤回须明确。
8. I2I 对话按因果链/协作范围预算终止，重复投递幂等；新消息循环不能只靠 message_id 去重；预算限制不能丢合法任务结果。
9. PA 本人新请求优先于外部洪泛；外部裸 `/stop` 和观察历史 `/stop` 不取消私密主脑；断线恢复不重复提醒或伪报完成。
10. 同时测主动价值与安全边界：漏发现的重要承诺、重复打扰、本人请求延迟，以及私料泄露/越权副作用。不能用全部拒绝换取“安全通过”。

## 审查结论

推荐方案方向可成立，但“一个 PA + 几种不同 prompt”不足以实施。最需要设计作者一次收口的是**可信路由、可联系身份/资产 ACL、执行 profile、资料放行、owner task 写权限**这五个相互关联的契约。它们应进入同一 design 的数据流和 delta，而不是在原型每出现一个反例就增添一个页面开关。

本文没有确认 DSH 已提供满足上述限制的所有公开 sandbox/profile 能力，也没有证明现系统存在可被任意外人触达的私料泄漏漏洞；指出的是 current 单 global/固定 space 模型与已确认 PA 需求之间必须补齐的架构边界。
