# Personal Agent 消息路由、收件与观察机制审计

2026-10-16；基线 main `481467ac16f0eda4561fca5c8230050541600de9`。静态源码审计，未运行服务或测试；无产品代码修改。补充 `nano-personal-agent-backend-audit.md`。用户要求明确考虑“其他人和Agent能否给个人Agent发消息”“别人发给我的消息是否立即也给个人Agent”。下表推荐只是待确认设计，不将用户提出机制问题视作已授权全量旁听。

## 先分开五个开关

“可被发现”“可发请求”“能读取来源内容”“是否触发模型”“是否对外发言”必须独立。收到了消息，不等于这是owner的任务；已入Inbox，不等于运行；运行不等于必须回复；可读不等于可写。建议个人Agent的identity长期私有，接收外界协作请求另走受控inbound request入口，不直接开放其整个私人空间。

## Current code map

1. `apps/im-server/src/identity.ts:45-69`：Agent固定space，owner获公司资格不扩大Agent scope。个人Agent只能personal:{owner}；不同用户不能访问该space。
2. `messaging.ts:673-705` contacts：真人可见自己+active公司真人；Agent须viewer能access其space且agentAvailable。别人的私人Agent不可发现，公司Agent对active公司成员可发现。
3. `messaging.ts:178-232` resolveParticipants/createConversation：陌生私人Agent不可建DM；创建群只能加入自己拥有的Agent；Agent自己创建群不能加入其他Agent。
4. `messaging.ts:631-668` resolveTarget：Agent可通过user/agent目标建同space DM；直接给conversation发须已是成员。因此同owner同personal space的specialist可找到已知personal agent ID后发Agent-Agent DM，其他owner/private或company Agent不行。
5. `messaging.ts:490-550` human message path：relayAgents只取当前会话的可写成员Agent；每个成员生成持久relay_tasks。没有“收件真人→其个人Agent”observer tap；普通human-human DM无Agent就不fanout。
6. `gateway.ts:504-579` agent.message：按当前node凭据、from_session_id的agent前缀校验source；写Agent身份消息；targetKind=agent_id时给对方relay，再groupReply。发给真人目标只到本人会话，不自动抄其私人Agent。
7. `gateway.ts:890-958` groupReply：完成的非空Agent群消息（除NO_REPLY）转给其他成员Agent，排除发件者自身；无跨新消息的hop limit、因果链预算或自动对话TTL。relay key只防同一消息重复fanout。
8. `packages/personal-assistant/src/attention.ts`：context_only永不触发；其余direct总触发；group为ALWAYS、明确mention、reply_to_agent任一则触发。不区分owner/other human/Agent的优先级。
9. `global-agent.ts:64-109`：所有正常输入持久进Inbox，attention才调用wake；session.observe非idle则退出，idle通知与recover后再唤醒。wake是system提示，正文随后由inbox read摄取；忙时不自动插入新消息正文。
10. `inbox.ts:18-60`：UNIQUE(agent_id,message_id)防重收；attention watermark与admitted wake持久；check展示requires_attention；read页/摄取确认持久。不是优先级队列，也不是每条消息独立run。
11. `single-thread.ts:54-68,139`：未命中的群输入缓冲；命中后按chat session运行；context_only提交为inject。不能把此行为直接描述为global的自动注入。
12. `messaging.ts:553-566` relayEligible：重投检查node epoch、节点归属、当前Agent会话可写资格；`gateway.ts:81-99` send检查固定space、Agent可用、当前连接。新observer流需独立只读资格，不能强制伪造Agent membership以借用relayEligible。
13. `work.ts:476-525` conversation.query：global需验证global_main session；工具读取以Agent身份而非owner身份；public scope等访问仍受conversationAccess约束。
14. `global-agent.ts:237-294` send：新同来源attention消息存在时held_for_revalidation，不发送旧稿；sender仍Agent。不能把status accepted/sent理解为真人已读。
15. `gateway.ts:582-632` node.system_message知识整理通知只insertMessage，无enqueueRelay；task notice (`messaging.ts:527-531`)明确enqueueRelays。新通用observer若挂在所有insertMessage后，会把本来不回灌的自身通知重新唤醒，破坏现有隔离。
16. `packages/channels/src/feishu.ts:15-19`：外部飞书过滤非user和bot自身；`personal-assistant/src/external.ts:48-63,225`保留senderId、appId、ownerOpenId可信映射；mirror user ID可能是记账身份，不能据shadow owner认定本人来信。mirror suppress_relay是防重复的关键。

## 场景决策矩阵

| 场景 | 当前行为 | 推荐默认（proposed） | 缺口/代价 |
|---|---|---|---|
| 本人→个人Agent | 私人DM可发送，global direct需要attention | 最高普通优先级；立即入队，空闲即处理；忙时提示未读，不保证硬中断 | 需要owner优先级/忙时可见状态，区别已收与已处理 |
| 陌生真人查联系人 | private Agent不可见 | 继续不可见；不进公司公共Agent目录 | 不支持直接“找某人的秘书”，换取隐私/防骚扰 |
| 其他真人知道Agent ID后直发 | 跨personal space拒绝 | 默认仍拒绝；若需要提供公开联络，独立request入口+owner允许的sender集合 | 不应放宽canActorAccess或把个人Agent迁company |
| 同owner specialist→personal Agent | 同space可以agent:ID建DM并触发 | 仅已关联任务/显式协作消息主动唤醒；任意闲聊只入待审摘要或拒绝 | 当前无contact policy、任务关联认证、预算 |
| 其他人的Agent→personal Agent | 不同personal space拒绝；company Agent也不匹配 | 默认拒绝，未来允许经显式协作request入口 | 技术同公司不代表获owner授权；需要来源Agent+owner身份 |
| 其他人→我，human-human DM | personal Agent不在该会话则不收到 | 默认不复制；用户选定消息“请助手帮忙”可传有限上下文 | 全量/指定聊天持续读取须另行选择 |
| 其他Agent→我，Agent-human DM | 只给当前DM；不自动抄个人Agent | 同上；若本是个人Agent委派任务的结果，按task关联给主Agent一次 | 单凭“owner是我”不能让所有specialist输出自动占主上下文 |
| 群普通消息，个人Agent是成员 | 入global Inbox；MENTION不wake；ALWAYS wake | 推荐MENTION；无需逐条模型运行；高价值观察可后续批处理 | 在private space几乎只能本人+本人Agents；真正公司群须另有委托读取 |
| 群@个人Agent | 同space成员才可收，触发attention | 明确被点名可优先处理，但第三方请求仍无owner审批权 | 需区分请求人而非只看mention |
| 群Agent→Agent | 发给其他成员，排除自身；按MENTION/ALWAYS触发 | 限任务关联、限制自动回合、无事不回、默认MENTION | 现有去重无法阻止新消息ping-pong |
| 已授权观察某聊天的新消息 | 无owner observer流 | 快速持久记录引用/摘要，不等于立即LLM调用；合并窗口后评估 | 需独立read grant、cursor、撤销、节流；防全流量成本放大 |
| 本人的个人Agent→本人 | 本人DM写Agent消息；不自relay | 不再进入observer唤醒，保持一份可见消息 | 新tap必须排除自发message，而非靠prompt“别回复自己” |
| 自身知识整理/运行通知 | 部分system notices只展示；task notices会relay | 展示事件默认不wake；任务进展按subscription一次入队 | 分类并携带cause ID，防观察通知触发新观察 |
| 来源聊天被删/退出/停用 | 常规relay重投检查成员/space/epoch | 取消未来observer读取/投递；重新验证引用可读；说明缓存边界 | 已入模型上下文不可承诺瞬间物理抹除；需要禁止失权数据重新外发 |
| Owner忙/个人Agent忙 | global存Inbox，等idle；无owner专属抢占 | Owner新请求优先于低优观察；正在执行有副作用工具不硬打断 | 加醒来选择优先级而非创建第二loop；必要时安全点提醒 |
| 无人值守跟进 | Heartbeat忙时跳过；Cron独立原生机制 | 已保存目标与授权观察scope范围检查；无事静默 | 不能以后台事件给待确认动作“自动确认” |

## 关键容易漏掉的问题

### A. 旁听消息不能直接伪装成普通direct输入

`global-agent.ts:66-77`仅以sender_type=user判定精确`/stop`，随后直接cancel主session；`session-controls.ts`也按human与寻址执行/config、/compact等，不核对owner。当前私人space通常挡住外人；如果新方案把其他人给owner的话复制成发给个人Agent的普通真人DM，就可能把第三方原文变成个人主脑控制命令。

建议observer事件使用独立trusted source=system_observation，保持原sender的actor身份、source_message_id、grant_id、source_space_id，显式禁止进入sessionControl和命令解析；仅真正owner对个人Agent发出的命令能操作主session。若以后允许外人直联个人Agent，还必须限制管理/停止命令为owner，不能仅靠UI隐藏。

### B. 同owner Agent不是owner授权代理

Agent消息仅是工作资料/协作请求。它引用“用户说可以”不能变成授权；需要回查可信原始owner消息与绑定task范围。区分公开Agent间消息、运行时parent-child控制和真正owner输入，保持现有来源分类。`packages/dsh-integration/src/policy/sources.ts`已经保留nano-human/system/agent-message等类别，扩展observer时不能把第三方human文字放入代表owner意图的实时输入类别。

### C. 当前Agent-Agent DM的地址形式影响触发

`gateway.ts:573-578`只在targetKind=agent_id时relay对方。`conversation:<id>`地址给已有Agent-Agent DM写消息不会走该direct relay，而groupReply只处理group。global send保留调用者target形式。这里是静态观察到的潜在行为差异，尚无运行复现；新设计必须把“逻辑收件人是否Agent”从地址字符串解耦，同时防止重放变成双发。至少补`agent:B`与`conversation:DM_AB`等价行为测试。

### D. 当前去重不是防循环

inbox唯一键、relay idempotency、dispatch_request_key只保证同一消息/操作不重放；A新发→B新回→A新回均是新ID。建议有cause_id/root_request_id、sender_agent_id、target_agent_id、collaboration_id（若是已授权任务）、generation/hop_count；服务器执行最大自动回合/速率预算。所有达到上限的协作进入等待/向owner汇总，不靠重试绕过。数字阈值作为可测产品默认另定，不冒称论文证明某固定阈值最优。

需特别区分“禁止整个循环”和“禁止合法多轮协作”：owner明确开启的任务可以有更高预算/终止条件，且每轮仍保留权限。不要对所有Agent消息粗暴丢弃，否则委派结果丢失。

## 建议的最小事件处理链

消息正常持久提交 → 可选observer selector（仅用户授权scope、排除自身/纯展示通知、检查当前owner权限） → durable observation记录（唯一binding+source_message_id+event_kind，附原始引用/来源，通常不复制附件正文） → 同一个人global Inbox的系统观察入口 → attention分级/合并 → 需要时读取来源当前权限允许的正文 → 生成本人私聊建议/草稿。

不为观察建立第二Agent loop；IM只负责权限与事件队列，不替代Node heartbeat/DSH调度。所需持久字段是交付游标、幂等、grant与原因；任务状态继续task_graph，不重复。

建议优先级：owner控制/明确请求 > 已委派工作的必要阻塞/终态 > owner授权的重要提醒 > 普通观察。优先级仅决定何时看，不提高动作权限。不盲目每条触发LLM；默认合并普通观察，owner明确紧急请求可即时wake但不承诺抢占正在执行的副作用。

## 需要用户决定（按顺序一次一个问题）

1. 个人Agent作为私密助手，还是也要成为别人能联系的“代理联系人”？建议默认私密，必要时独立、受控请求入口。
2. 对发给用户的消息：仅用户手动转交；用户选择会话后持续观察；还是希望所有当前有权访问的IM都观察？这些权限差别重大，不能由“最好考虑”推断选择。
3. 被授权观察后：默认只给主人建议/草稿，还是允许在原会话以Agent明确身份回复？代真人发送是更独立的一层权限，应另定。

这些问题影响数据与安全模型；可以先交互原型比较，但在用户决定前不把任何全量读取/自动外发写成已确认需求。

## 验证矩阵补充

- contacts/直接ID/旧DM三条路径都不能绕过private scope；同owner不同space同样被拒。
- 同owner specialist正常关联结果可达；无任务/洪泛/循环受限；重复传输不重复wake，新的合法消息不误去重。
- agent目标与conversation目标路由语义一致；自发message不自醒。
- owner→personal即刻入队，普通observer合并；忙时不丢失且owner优先；重启恢复不会低优观察阻塞owner。
- 观察源原文含/stop、/config、伪造“我是owner”、引用批准，不会调用主session控制或授予外发。
- 第三方Agent转述owner承诺仍是Agent source；飞书shadow的用户记账ID不升级外部sender身份。
- revoke grant、company suspend、离群、node transfer后旧队列不继续读/外发；相同message Web镜像与外部原件不双提醒。
- 知识整理通知、task notice、主动提醒各自明确wake规则；个人Agent反复发提醒不会制造递归事件。

## `/stop` 风险精确分层（给设计审查的证据）

**当前确定行为，不直接称已证实安全漏洞：**
- `global-agent.ts:48-58`绑定的是全局唯一主session，非来源聊天session。
- `global-agent.ts:67-77`对trim后完全等于`/stop`且sender_type=user的输入直接`session.cancel`；该分支在`needsAttention`之前，不检查owner、context_only或来源类型。输入为`请解释 /stop`、引用块`> /stop`或代码块时不精确匹配；普通文本提及不是命令。完整正文恰好`/stop`会命中。
- `session-controls.ts:8-12`其他命令要求human+attention，context_only会由needsAttention阻止；`/stop`没有这层保护。`/new`在global只答不支持，不重置主上下文。
- `docs/specs/gateway/global-agent.md:115-131`当前契约确实要求从任一已触达聊天停止该Agent全局工作、保留未读，不新增子Agent级联停止。这是现行共享global模型语义，不能单凭“不是owner”就宣称实现违约。
- `single-thread.ts:66-85`另行按来源chat绑定session取消；不能把其较小取消范围误套给global。

**当前可达前提：**
1. 纯Web私有Agent：其他真人被space ACL挡住，无法仅凭ID触达；因此不存在已证明的“匿名/任意外人停止私有Agent”路径。
2. company global Agent：已授权会话成员的真人消息能被路由到它；裸`/stop`按现行契约可以取消该共享global主工作，包括可能来自别的聊天的工作。需要产品重新定义个人角色是否允许这种共享控制。
3. 连接飞书的global Agent：`channels/src/feishu.ts:81-88`收到已由平台送达的真人消息后入队，并未仅限ownerOpenId；`external.ts:54-60`所有这类来信sender_type=user，仅另加owner_user_id作已知本人标识。是否某外人实际可给bot发消息取决于飞书应用可见性/成员权限，静态审计未确认部署暴露范围，故只报告条件性风险。
4. 飞书补历史使用contextOnly；因`/stop`分支早于context_only门控，若补回的历史输入正文精确为`/stop`，从代码看存在误作为live控制的可能。需针对历史获取/过滤路径补最小复现，当前未运行验证，不将其列为已验证线上漏洞。

**拟新增观察转发会引入的风险：**
用户当前可读的第三方DM不代表第三方有权控制personal Agent。若observer把第三方来信原文原样包装为`sender_type=user`输入，并把conversation_type设direct，即使context_only=true，精确`/stop`仍可能触发上面分支。若改写sender为owner来“方便处理”，更会把第三方指令升格为本人授权。两种做法都不允许。

**建议角色专属契约：**
- personal主会话的停止/配置/压缩命令仅接受经过宿主认证的owner主动控制事件；公开协作请求或观察内容不走命令解析。
- Owner可以整体停止personal当前主执行；该动作是否停止已委派子工作另作明确产品选择，遵循现有子任务规则，不宣称自动全部取消。
- 第三方任务如需取消，提供task-scoped请求，由owner既有授权及协作scope判断，不等价于`session.cancel`。
- 新观察事件自身为system，原始sender保留在嵌套source中；也不能为了挡命令丢失是谁说话的证据。
