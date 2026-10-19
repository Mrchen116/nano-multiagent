# PA 主动观察：owner 消息、历史与任务感知设计

状态：研究候选，非已通过设计；不修改 current spec 或产品实现。基线 `481467ac16f0eda4561fca5c8230050541600de9`，2026-10-16 静态代码核查。补充而不替代本unit的隐私与外部协作隔离研究。

## 1. 用户已确认的方向与未定细节

用户明确要求PA主动感知本人收到的人/Agent消息、查看聊天记录并主动协助，不接受“只有手动分享一条消息才开始”的替代方案。来源：Sentinel_24fff2efb1c08191a5c797bf29c47a68。此前研究中的“默认不观察、只手动转交”建议在本方向上已被用户否定，不能继续当默认。

本设计将自动观察与历史检索作为PA基本能力；手动“让助手关注”只是提高优先级和明确意图的补充。自动读取不等于自动对外回复/代发/修改他人任务，也不等于外部来信变成owner命令。

仍待产品定案：全部已加入群是否默认涵盖、首次历史扫描窗口、敏感会话排除、通知节律、跨空间组织限制。下面给推荐默认，明确不是用户逐项已确认。

## 2. current基础与实际缺口

- `apps/im-server/src/messaging.ts:317-345,348-398` 已有持久conversation_events及message.created，消息、Agent输出与system notice均可能经此处。不能把所有事件无区别重送为真人输入。
- `messaging.ts:534-550` 当前relay只给源会话的成员Agent；没有owner观察分支。PA不应为读owner消息被偷偷加进全部聊天。
- `messaging.ts:814-829` 本人已读只更新conversation_participants，没有持久read事件。PA读取不能调用此接口冒充用户已读。
- 当前消息GET支持按before_message_id分页（:837起）。未发现普通消息编辑/删除接口；新增观察事件规范可预留update/delete，但不能宣称现有源能产生它们。
- `task-graphs.ts:669-683` 在图事务内保存revision与少量通知；`task-notifications.ts`主要覆盖指派及paused/closed/in_review/done。通知气泡不是完整task变更日志。
- `messaging.ts:595-613` 解散群会批量关闭未完任务且不发task notice；须纳入观察事件，避免PA继续催已关闭任务。
- `personal-assistant/src/inbox.ts`有持久去重、摄取回执与watermark；`global-agent.ts:88-109`空闲才wake、重启recover。可复用持久执行机制，但不把观察事件直接送到现有`receive(RelayInput)`命令路径。
- `conversation-access.ts`与`identity.ts:45-69`已有真实账号/空间/成员ACL；当前Agent固定space。要使private PA观察owner公司聊天，应新增owner委托只读投影，不能把PA改为company或放宽全体Agent ACL。

## 3. 默认观察范围建议

### 自动范围

建议覆盖owner参与的真人DM、Agent-DM，以及owner已加入的群；包含收到消息和本人回复。owner自己的PA canonical DM沿原有直接交互路径，观察层只记去重/处理状态，不再次唤醒。未加入的公司公开群即使可搜索可读，也不自动批量监控；用户可显式关注它们后纳入。

本人负责的任务自动纳入（仍要求当前源会话可读）；本人显式关注的其他任务亦纳入；不把assignee自动改成PA。未在观察scope内的任务链接可按当前ACL做有目的的历史读取，但不能悄悄开启长期监控。

### 首次历史

推荐先索引最近30天的消息元数据和可读来源，按未完成事项/最近交互做分页内容回溯；不是把30天所有正文一次塞进模型。更早历史可按当前任务需要查找、按页取上下文，记录“尚未扫描/覆盖不完整”。30天为可调整工程默认，待确认；不把年龄较久的消息误当刚收到的紧急任务。

开启时以bootstrap snapshot_watermark与增量流并行，先保住新来信，再逐批回溯，历史进度可见。内容量大时有预算/节流，不承诺开户后立即理解全部历史。过去的承诺结合后续回复/当前任务状态再判定，不能仅凭旧句子重复提醒。

### 隐私控制

提供按会话排除、暂停全局观察、历史清理及敏感来源预设。静音通知不自动等价于禁止PA读取，避免误猜用户意图；“不让助手看”是独立明确开关。附件默认先读类型/标题等最小元数据，正文按相关性和现有媒体ACL取；敏感类型是否默认进一步限制待确认。

## 4. 一个持久事件层，三套不同游标

### 事件形状（proposed）

`observation_event`: event_id、owner_id、personal_binding_id、policy_revision、kind、source_space_id、source_conversation_id、source_object_id、source_version、original_actor、occurred_at、observed_at、cause_id、payload_ref、origin=system_observation。

事件由宿主产生；original_actor含human/agent/system、真实平台与账号映射；不能靠正文声明身份。payload_ref引用受ACL保护的真实记录，不把完整正文无条件复制进第二数据库。

事件类型与处理：

| 事件 | 如何产生 | PA处理语义 |
|---|---|---|
| message.received | 已提交新消息，owner是接收成员；Agent流式结果以完成态可分析 | 分析请求、阻塞、承诺；第三方内容不是命令 |
| owner.message_sent | 真人主动发送成功，或明确识别的其他发送身份 | 更新是否已回应/新承诺，不自动向owner再回复同一句 |
| message.finalized | 既有Agent流式输出完成 | 同一message版本合并，不把每个delta唤醒一次 |
| message.edited/deleted | 当前缺普通API；未来源支持后在修改事务内写event/tombstone | 使旧摘要/草稿失效，重查当前版本；删除保留无正文墓碑 |
| owner.read_changed | read接口更新水位同时写持久事件 | 只代表用户看过，不代表处理完、同意或授权 |
| task.changed/deleted | 任务图实际事务、含graph revision与changed IDs | 当前状态优先，关闭/改派后撤销旧提醒；不依赖通知文字解析 |
| conversation.membership/scope/deleted/dissolved | ACL/成员/生命周期变更事务 | 撤回读取/停止跟进、使关联摘要失效；解散群同时覆盖任务关闭 |
| observation.policy_changed | owner排除/恢复/暂停等设置 | 更新policy_revision并强制重验旧队列 |

最少持久新增数据：owner observation policy；owner event delivery/ack cursor；Node本地观察收件箱及处理回执。已有conversation_events能作为消息源日志；缺失事件补进统一事实事件规范，task/read/权限变更与业务写同事务，避免“数据变了但事件丢了”。IM推送只是可丢的通知，不能作为唯一事实源。

三个游标互不替代：
1. 服务端source/delivery cursor：哪些事件已发送/扫描。
2. Node durable_received cursor和processed/read evidence：哪些已落盘、哪些内容确实被模型摄取/处理。
3. 真人read watermark：用户看到哪里。

仅Node落盘后确认接收；模型处理失败不丢事件。不能用“已发WS”“LLM已启动”或人的已读水位替代处理完成。

## 5. owner委托历史API与权限

新增受限产品方法（名字候选）：`owner_observations.check/read/ack`、`owner_history.list/read/search`、`owner_tasks.list/get`。不是传owner access token给模型，也不是让现有conversations工具假冒owner。

每次调用须由ProductBridge提供可信绑定：personal_agent_id、owner_id、root/session/task scope、node epoch、policy revision。服务端验证这个Agent确为当前用户固定PA，node绑定有效，当前owner账号可用；scope只读。普通specialist、外部协作舱、任意child不能凭同owner使用这些API。

读取范围取交集：当前owner真实会话ACL ∩ 自动观察/明确关注scope ∩ 排除策略 ∩ 本次对象/查询范围。company源还要求当前company资格；private PA仅接收owner当前可读数据的私密投影，不取得company Agent身份。企业若另有不允许私人助手处理的政策，必须增加组织控制交集，不虚构现有产品已有此策略。

分页游标绑定owner、policy revision、query及snapshot watermark，重新请求仍检查实时ACL；授权减少使游标失效，不能用旧cursor继续读。metadata/search snippet/附件同样检查权限，不在错误中泄漏失权会话名。source链接在owner点击时重新鉴权。

历史读取是被动查询，不推进观察消费水位、不改用户已读、不把过去人类消息变成新授权。对当前工作引用旧owner语句只作背景，执行仍按当前有效意图与审批机制。

## 6. 同步与唤醒分离

### 接收

事件发生后可立即同步索引/引用并持久入观察Inbox；“立即感知”不应被实现成每条消息立即占用一次昂贵模型运行。运输层只做确定性分类、去重、过滤。第三方自称urgent不得获得控制级优先权。

### 分级

- P0：owner对PA的直接请求/控制，沿原有可信入口，优先于观察工作。
- P1：已授权跟进事项的真实阻塞/截止变化、已委派结果，较快检查。
- P2：普通新消息/本人回复，按会话短窗口合并后检查。
- P3：历史扫描/已读/非关键状态，空闲或Heartbeat批处理。

建议P2合并窗口10–30秒、每批有上限、低优批次有最长等待避免永远饥饿；数值待压测与产品确认。不把开启聊天窗口视作禁止主动帮助，也不逐条闲聊回复。

### 执行

复用现有global主执行与Node调度，不另造Agent loop。新增observation wake为系统提示“有来源变化待检查”，模型经观察工具读取当前证据；不得调用`GlobalAgent.receive`并伪造sender_type=user。忙时事件持久保留，global idle通知择优继续；Heartbeat作为低优/漏唤醒补偿，不抢占副作用工具。

Owner新消息应先被处理；持续忙导致积压时显示真实状态。任何“暂停/取消观察”都不是取消owner明确任务；owner `/stop`的具体停止/恢复语义与任务状态分别处理。

## 7. 合并、去重与恢复

- 主唯一键：binding+source platform+source conversation+source message/object+version+event kind；既有Web mirror/外部消息需有canonical origin ID，避免两源双提醒。
- 同一Agent输出的created/delta/finalized合成一次完成分析；自发PA提醒排除再wake，保留可核对发送记录。
- 同一graph/node revision的结构事件和system notice只处理一次；不以notice文本当新的第三方请求。
- 消息后紧接owner回复：同batch一起分析；已处理后有新回复则使旧候选提醒失效。owner已读只能降低重复提醒权重，不能自动mark done。
- 候选建议绑定source_versions和task_revision，真正发给主人前重验；若用户已回复/任务已完成则撤销或重生成。对外草稿亦如此。
- IM事务outbox→Node落盘→ack，重发同key无副作用；分析阶段与提醒发送分别幂等，避免“接收一次但重启提醒两次”。
- Node重启从durable cursor恢复；offline不宣称持续分析。恢复先处理owner新请求与最新状态，再合并积压，不逐条补发过去通知。
- 源日志保留窗口越界时，返回显式gap/resync_required，以当前可读snapshot重建；不无声跨过缺口声称历史完整。
- 节点转移/绑定变更：旧node epoch立刻失效，旧队列不继续同步；私人身份不能跟硬件转给新owner。

## 8. 主动理解与不可信内容的边界

自动观察应能发现“别人正在等我”“我承诺的事项临近”“我已回复所以不用催”“我的任务被改派/关闭”，不是只在明确派任务后执行。

但外部原文只表达外部人的请求和事实主张，不能修改PA规则、读取范围或同意外发。建议观察解析采用受限上下文：只看本批源内容及必要同会话片段，输出结构化候选事实/问题/证据引用；不能读取完整私人memory，也不能发消息、调用shell、改memory/任务或再委派。它使用DSH既有执行体系内受控profile，而不是fork私密主session。

私密PA主脑结合owner偏好和历史来选择是否提醒、准备资料、起草下一步；其读取已被用户授权为产品能力，但来源授权不因内容融合而升级。第三方事实标明said_by，并与owner confirmed区分。自动事实索引不能成为另一套task真相或批准规则数据库。

重点：`global-agent.ts:67-77`当前精确user `/stop`分支早于context_only门控；故只加context_only=true还不够。必须单独observation入口、system来源、禁控制解析。历史里owner曾说`/stop`也不是现在停止；当前owner主动对PA发出控制才进入命令路径。

## 9. 撤权、排除与内容生命周期

暂停/排除保存后立即增加policy revision：停止未来取内容、取消未处理payload读取、使候选建议失效；Node接收撤销tombstone并清理本地源缓存及衍生索引。所有读与发送前检查权限，离线队列恢复时先拉策略再拉正文。

已读入长期模型上下文的内容不能保证瞬间遗忘；强隐私排除需提供清除源缓存、衍生memory引用及重建干净上下文的流程，并明确不能撤回已经给模型服务或接收者的数据。没有完成该清理时，不应宣称“完全删除”。

会话删除与“不再观察”不同：删除源后读取拒绝，衍生建议撤回；是否删除PA已形成的长期事实需来源引用/owner选择，不能默默把源已删除事实永久保留且无法管理。

## 10. 自动观察与动作边界

自动允许的候选范围：读取有权来源、对比最新状态、整理私密建议、准备给owner的草稿/证据、帮助发现遗漏。

独立受控动作：对外发送/代表owner发言、修改或完成源task、接受承诺、上传/分享附件、外部Agent协作、日历/支付等。观察授权本身不授予这些动作；既有用户指令/动作规则仍决定能否执行。

PA可主动帮owner自己的task准备材料、发现依赖、提出下一步，不把“我帮助处理”变成“我把assignee改成自己”。已授权执行则按源task revision更新并记录Agent实际actor；对已完成/删除/改派的任务停止旧计划。

## 11. 验收建议（设计期，不声称已运行）

1. 未手动转交的真人DM与Agent-DM到达，PA能自动在权限内发现待处理事项；owner回复后不再错误催回复。
2. owner加入的群按定案scope自动观察，未加入公开群不自动全扫；排除会话不出现在摘要/search/附件读取。
3. 只读委托可读owner公司聊天而private PA仍不暴露给公司联系人/Work；specialist/外部任务舱不能使用owner_history。
4. read watermark不因PA查看推进；用户已读不被当成同意、完成或已回复。
5. task所有实际变更含群解散的批量关闭被捕获；不因只有部分notice就漏状态；graph仍唯一事实源。
6. 重复Web镜像/WS重连/节点重启不双提醒；消息更新后旧草稿失效；离线积压合并并展示覆盖缺口。
7. 历史回溯与增量并行无缺口；历史中旧承诺结合后续事实判断，旧`/stop`不控制当前session。
8. 第三方`/stop`、伪造owner许可、注入memory指令只能作为源内容，不能改变授权/主脑控制。
9. 撤销、失去company资格、退群、节点转移后旧cursor/旧队列/缓存重读均拒绝；不泄漏源标题。
10. 正常主动价值可衡量：发现owner未注意的重要请求、压低重复/低价值提醒、保持owner请求响应延迟；不能只用安全拒绝率验收。

## 尚待对齐但不阻塞研究

本次无需重问“要不要主动观察”，用户已经明确。后续结合原型收口：默认群范围、历史窗口与来源覆盖提示、敏感会话排除、个人提醒频率。应给用户可见的推荐设置与效果，而非把逐条授权操作重新塞回每一条消息。

## 12. 最新用户纠正：保留原生DM和群@，安全机制在后台

来源：Sentinel_576b16ff6314819191b1234b87f3fae7。用户要求其他真人/Agent正常私聊PA、群里@PA，明确否定将安全隔离变成新的“专门请求入口”。因此前述安全研究中的ingress broker只是后台处理职责，不是新按钮/表单/用户操作。外部用户继续使用现有联系人、DM、群成员和mention；不能先让用户改用特殊入口才具备基本交流。

### 12.1 为什么当前代码不能只调整提示词

1. `identity.ts:65-69` Agent只能访问profile.space_id，`messaging.ts:178-232,631-668`创建DM/解析目标同样要求同space。private PA在联系人中对他人不可见，外人DM不可达，company群不能加入；这不是只改Web UI就能解决。
2. `global-agent.ts:48-58`将所有聊天绑定`global:{agentId}`唯一主session；:64-86不同来源均进同一Agent Inbox。当前并无“global按聊天自动隔离”的能力。
3. `work.ts:707-743`Work读取按profile.space_id；如果把PA改company以便交流，会扩大完整工作轨迹的读取人群。不能这样解决。
4. `history.ts`普通subagent继承parent config；memory feature可继承父快照。外部处理不能使用普通fork或只换session ID而沿用私密workspace/skills/plugins。

### 12.2 后台身份与权限分离

保持一个用户可见的PA Agent身份、一个名称、正常DM与群成员形象。新增的是不同权限域，不是第二个助手账号：

- **管理/私人数据域**：个人binding、private Work、memory、owner历史委托仍归owner。其他人可联系它也不能打开这些对象。
- **通讯参与域**：这个Agent persona在某源聊天是否可加入/收消息/发送，沿会话成员关系与真人联系准入判断。company群必须owner仍有company资格且允许该PA参与；不把profile数据域改company。
- **执行域**：私密主scope、外部chat/task scope、观察分析scope分别由宿主选择；模型不能通过参数把自己提升到private主scope。

具体建议新增专用`communicationAccess(actor, conversation)`与contactability规则，现有canActorAccess用于私人资源的语义不整体放宽。所有消息创建/读写/附件/relayEligible/直接投递/WS订阅都必须明确使用相应权限：允许读源外部会话不允许读owner其他会话。禁止只改联系人或resolveTarget一处造成半通半漏。

默认联系范围推荐遵守既有真人目录资格：有效公司成员可找到已允许公司交流的PA并DM，公司内Agent亦须实际owner资格与受限协作范围；不顺带新开互联网匿名/跨组织联系。公司准入范围是否就是预期用户群仍要产品确认。个人身份默认可原生交流的方向已明确，不能退回“私有不可联系”作为完整方案。

### 12.3 完整路由矩阵（proposed）

| 原生交互 | 接收/读取资格 | 后台执行scope | 可回复目标与隐私边界 |
|---|---|---|---|
| owner→PA canonical DM | owner绑定+原DM ACL | private global main；可信owner control允许 | 默认回复本人DM；跨源资料只给owner，外发仍单独审核 |
| PA→owner DM（主动） | 同上；最新观察/任务证据 | private main | 主动提醒/草稿真实发给owner；排除再次观察自醒 |
| 外部human→PA DM | 正常contacts/DM建立，contactability+双方资格+会话成员 | fresh external scope，按DM复用受限上下文；无private主历史 | 自然在该DM回复，不强迫换入口；只含源DM资料/批准披露事实 |
| 外部Agent→PA DM | 同上+来源Agent与owner真实性+速率/循环约束 | external scope，消息仍Agent来源 | 原DM回复；不因对方也是Agent就获得owner命令权 |
| 群中@PA | PA已合法加入该群，sender可写，可信mention元数据 | 该群external scope，限定当前任务与必要群历史 | 在原群回复；不能把owner私密主上下文作为群上下文 |
| 群普通消息（PA成员） | 同群ACL | external Inbox context-only/批次，MENTION默认不逐条wake | 被@时可读该群上下文；主动发言须群策略，不能承诺ALWAYS |
| owner在群里@自己的PA | 同群ACL；sender可确认owner | 默认仍external群scope，避免直接把私密主上下文搬进群 | owner身份可表达任务意图，但公开群披露范围仍须明确；私密资料需通过后台批准投影 |
| owner其他DM/群收到人或Agent消息 | owner只读委托+当前源ACL；不要求PA成为成员 | observation scope→private main的证据摘要/主动计划 | 默认帮助owner；不自动在被观察的源会话发言，也不伪造加入 |
| owner在其他聊天回复 | 真实sender/代发身份、源ACL | observation更新状态 | 取消过期催促/草稿，不等同owner向PA交新命令 |
| PA主动发给外部人/Agent | 明确动作授权、目标/内容/当前可写资格 | 外部发送经统一egress，scope固定目标 | 使用同一PA身份原生DM/@；无发外权限时向owner请求具体决定，而非新增请求入口 |
| 外部请求需owner私密事实 | 外部scope发内部资料请求，不能直接查询private主scope | 后台owner审批/受限资料投影 | 允许后原DM/群自然收到批准回复；不暴露内部私密过程 |

对于owner在群中说“把我的资料发来”：不是自动把所有资料解释为群可见；系统结合目标、具体范围及审批规则处理。owner控制主PA的`/stop`建议限定本人canonical DM或显式owner控制面，群中的取消只针对该群任务；这是新的个人角色语义，需与当前共享global全局停止契约明确做delta，不暗改所有specialist行为。

### 12.4 实现选项与推荐

**选项A：所有输入继续进private global，用prompt和发送审核隔离。** 改动少，但模型已看到私密上下文，读工具禁用也不能阻止复述；不推荐作为安全底座。

**选项B：同一PA显示身份，宿主按scope绑定多个执行session。推荐。** 保留现有private global主session与主动能力；外部DM/群走独立受限session。它借鉴single_thread按conversation绑定的既有机制，但不复用其全部默认配置和final直接外发：配置必须从独立restricted profile生成，final交既有消息出口的审核/投影后再原会话投递。所有运行仍由DSH执行，Node/PA负责产品路由；不新增loop，也不绕过DSH公开exports。

**选项C：另建公开代理Agent账号。** 可以利用现有space，但会给用户两个联系人/两个身份并造成语义混乱，不作为默认；后台可以有运行身份，但前台必须保持原生单PA体验，且不能拿隐藏账号绕权限。

选项B的最小接缝：
- product-contracts SessionBinding增加宿主控制的execution_scope、source_conversation_id、capability_revision（字段名待设计），owner/private scope与external scope不可混用；不由模型自由传入。
- PA dispatcher先辨认真正owner canonical direct、正常外部chat、owner观察事件；private分支保留GlobalAgent，external分支使用专用受限session绑定，observer不能调用真人control分支。
- ProductBridge带可信scope到服务端；外部scope的conversations仅能当前源聊天/明确允许对象，无owner_history、private task、Work、memory工具。普通Agent_id/owner_id相同也不能绕过。
- DSH配置层避免global固定工具补回、parent配置/快照继承、owner/global skills/plugins挂载；独立workspace不等于沙箱，禁任意filesystem/shell/network等能力直至存在可验证隔离。
- IM保持一个Agent persona，多scope Work全部owner私有；第三方只见源聊天正常消息、必要状态，不见完整trace。
- 出口统一用实际source conversation与recipient检查；修复agent:B与conversation:DM_AB地址形式影响relay的现存静态差异，保证正常Agent DM多轮连贯并受预算控制。

这不是现有global“一Agent一主session”已经支持的配置开关，而是需要跨PA、product-contracts、DSH integration、IM通讯ACL的明确设计增量；可复用现有原语，但必须写完整测试与迁移契约。

### 12.5 增补验收

- B可用原联系人私聊A的PA、在合法群@它；全程不出现专用请求表单，PA名称/身份不变。
- 同时A在私人DM讨论canary隐私、B在外部DM询问：外部模型首请求及后续上下文均不含canary，不能靠工具或Work拉取。
- A在群@自己的PA不会让该群继承private memory；批准的最小资料可经投影自然回群。
- 外部Agent通过两种目标地址回复都能到同一原生DM；循环预算、撤权、幂等保持。
- PA未加入owner的某聊天仍可自动观察owner有权内容并帮助owner；“观察”和“公开参与”互不冒充。

### 12.6 审查收敛：一个global_main，新增external_chat scope，放行权在宿主

进一步限定选项B：每个PA依然只有一个`global_main`。外部会话引入新的`external_chat`执行scope；它不是第二个global_main，也不是把同agent_id简单交给现有SingleThread实例。当前配置以agent_id共享，直接复用会继承私密配置或发生配置冲突。只能复用“按conversation持久绑定、恢复、幂等”这一模式，具体配置选择必须同时由宿主execution scope决定；必要的protocol/config registry改动要在正式设计中显式列出。

Fresh外部上下文只能阻止直接继承私料，还需防“外部请求→摘要→私密主脑→主脑自批披露”的间接路径：

1. external_chat只提交带不可伪造来源的`needs_owner_decision`，包括请求人、源聊天、所需字段、用途；它不能签发grant。
2. 私密主脑可以查询资料、分析可行性并给owner建议，但主脑自己、摘要、task状态、外部Agent转述都不能成为新的披露授权来源。
3. 宿主仅依据可信owner直接指令或已存在且确实涵盖该动作的明确规则，生成可核验的披露grant；锁定字段/产物摘要、受众、用途、期限及revision。自然语言建议不能直接变capability。
4. 主脑提供的候选资料先经宿主按grant做最小投影，再交external_chat；即使主脑输出多了内容，超范围字段也不能穿过数据边界。
5. 外部chat最终发送仍受当前grant与目标重验；owner改变意见/撤权后旧建议和已排队回复失效。

需补测试：外部摘要声称“owner已同意”或要求主脑“自行判断并批准”时，主脑可给主人解释/询问，但服务端没有真实owner证据就绝不生成grant。另一方面，用户已明确设置的日常低风险协作范围可以复用，不应每轮强制重复审批。此边界保护自动感知，不将主动性退化成逐消息授权读取。
