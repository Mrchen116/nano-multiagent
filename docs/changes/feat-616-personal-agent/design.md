# feat-616: 每位用户的个人助手 — 技术方案

> 对齐: spec.md；设计稿，Gate 1 已按自主设计授权收口、Gate 2 R1 Issues Found，正在修订，不可据此开工产品代码。
> 基线: main / origin/main / 实时远端 main 均为 481467ac16f0eda4561fca5c8230050541600de9（2026-10-16 17:02 UTC 核对）。工作树仅本 unit 未跟踪材料，无已有产品代码修改。

## Changelog

- R1 修订：闭合设备交接、委托权限、非 IM 执行、撤源生命周期、通知及联系控制；未解决视觉/DeepSeek 资源，不宣称 Gate 2 通过。

## 现状分析

### 涉及范围

- IM `apps/im-server/src/{onboarding,control,identity,messaging,conversation-access,gateway,work,trajectory,media,task-graphs,task-notifications,db}.ts` 与 `schema.sql`：身份/配置、会话资格、持久消息与任务、节点传输、Work 和附件访问。
- `packages/product-contracts/src/`：运行绑定、输入来源和权限域的产品词汇，保持不 import DSH。
- `packages/personal-assistant/src/{global-agent,inbox,store,session-controls}.ts` 及产品组装入口：单 global 接入、可靠摄取、执行恢复、命令路由与发送。
- `packages/dsh-integration/src/{index,agent-config,capabilities,product-bridge}.ts`、审批和 product tool 集成：运行域配置、工具约束、宿主绑定。`apps/node` 仍只经 integration/client 管理进程。
- Web `src/IM/frontend/src/features/{onboarding,chat,settings/agents}/`、app 导航及 API：起名、固定入口、私聊草稿/来源/观察控制和 PA 管理身份。

### 既有约束

遵守 AGENTS.md/SPEC.md：DSH 是唯一运行时，只使用已声明公开 exports；不恢复 Python kernel，不把 PA loop 搬进 IM，不新增内核 HTTP。PA→Channels/product-contracts；IM/Channels 不 import DSH。private Agent 的空间资格不能因外部可联系而整体改为 company。

基线 `GlobalAgent.receive` 先解析 user `/stop` 再入 Inbox；只加 context_only 无法隔离外部控制。`ProductBridge` 根据 parent 找 root binding；普通 fork/child 继承配置而非天然最小权限。`capabilities.ts` 对 global main 强补消息/委派工具；空 allowlist 不是 deny-all。以上均由现文件和 [统一审查](research/unified-pa-review.md) 交叉核对。

### 可复用能力

| 能力 | 用/改/不用及理由 |
|---|---|
| configuration operation + profile_version | 用：新增 PA 的首次创建继续走可恢复配置操作；唯一 binding 在服务端事务里收口，不能靠 UI 防重复 |
| private/global session 与 Inbox | 改：保留 owner 私密主 session、可靠摄取及 idle wake；不再把 personal-role 外部输入汇入同一 Inbox |
| conversation_events | 改：复用持久事件，并补业务事务内的 task/member/policy 事件；WS 仅通知，不作事实源 |
| task_graph 与 revision | 用：唯一目标、负责人和结果真相；不新建 PA Todo 数据库，不用 claim 表示协助 |
| 会话 ACL / ownerAccount / node epoch | 用并组合：单独判通讯参与资格与私密资产资格，不让通用 canActorAccess 对 PA 恒真 |
| single_thread binding/recovery | 部分复用：按外部 conversation 保留上下文；不能沿用其共享 persona/config 和自动投递直接宣布隔离完成 |
| 普通 DSH child/fork | 私密获授权工作可用；外部/观察域不用 fork，必须 fresh profile 且无私人继承 |
| message approval / delivery receipts | 改：保留动作审批与真实送达状态，新增绑定受众/版本的资料放行；模型判断不替代强制 ACL |

### 相关历史

feat-615 是当前 main 合并点；当前首次配置及安装链路以 agents-nodes 为准。feat-584/587 已约定任务按会话资格、revision、负责人管理；本 unit 不废除这些边界。bugfix-611 的全局发送前复核保留。feat-583/589 的 Work 主/子轨迹保持，PA 新增 owner-only 限定而普通公司 Agent Work 不退化。历史研究中的“逐条分享才观察/另建请求门户”建议已被用户否定，不能实施。

## 架构总览

一个稳定 PA persona，三个宿主确定的执行域：

1. owner_private：唯一 private global_main；本人直接输入、私密长期认知、已授权工作。
2. external_chat：每个真实 DM/群及 audience revision 的独立受限 fresh session；仅本聊天及已放行资料。
3. observation：按来源批次受限解析，产生带出处的候选事实，不能执行第三方指令；私密主脑决定何时准备建议。

输入流为 IM 持久事实 → Node durable ingestion → 可信路由 → DSH profile。输出流为模型提议 → PA 宿主目标/版本/授权校验 → IM 当前 ACL/真实投递。任何模型参数均不能选择 owner_id、profile 或权限提升。外部执行与观察执行不是新 Agent 账号，也不是另一个 runtime。

## 关键决策

**身份、通讯资格和私人资料权限分离。** IM `personal_agent_bindings` 以 owner 唯一、agent 唯一，保存 canonical owner DM、binding revision 和当前节点 epoch；profile 的 personal role 为服务端派生。普通 profile 更新不能自封 personal。通讯参与使用现有 conversation membership 加 PA contact policy；私人 Work、memory、配置和 owner history 仅 owner/正确私密运行域可访问。不改变 company 普通 Agent 规则。PA 的私人资产边界由 binding.owner_id 判定而非 profile.space_id 共享推导；新建沿当前合法 defaultSpace（包括仅公司资格账号），不要求先开启个人空间，也不因仅公司空间而公开 PA Work/配置。既有 private PA 不为了可联系而改 space；公司资格变化后重核账号/联系资格，不把旧 company 外部联系权限永久保留。

**默认策略在产品启用时明示，不由配置静默授予。** 自动观察本人已参与 DM/群与本人任务，近 30 天逐步回溯，显式排除优先，恢复时合并最新状态；同公司有效身份可 DM，owner 决定入群。onboarding 明确说明持续观察/模型处理的来源范围，用户确认开启后才启动；之后无需逐条分享，并可暂停/排除/清理。入口采用 A，自定义名字固定导航。此处是用户自主设计授权下的作者决定，非伪称用户逐项原话。

**执行域使用宿主可信 binding，受限域 deny-by-default。** 扩展 SessionBinding：scopeKind、personalBindingId、scopeRevision、sourceConversationId（external）、audienceRevision、policyRevision。DSH integration 从宿主配置派生 profile，不接受工具参数改写。受限域禁 shell、通用文件/网络、插件、skills、memory、配置和再委派；模型 provider 传输由宿主维持但不暴露凭据。只开放特定产品读取、结构化候选输出及同会话发送提议工具；宿主再次校验。锁定 DSH 的公开 root Agent/preset 支持不传 parent/seed 的 fresh 配置；公开 tools restrict 与单调 guard 支持拒绝未授权工具，persona complete + suppressRuntimeContext 防默认人设继承。另须从公共 host 禁用 agent-instructions，仅在 private preset 显式挂载，防 $DSH_HOME/AGENTS.md 和 cwd 指令被注入受限域首步历史；受限运行根无私人文件。公开 sandbox 仅 file effects，不能称网络/进程/凭据沙箱；此处依赖工具/配置不暴露这些能力及宿主 broker 强制检查。取证详见 research/execution-isolation-feasibility.md（已核对 19 个锁定公开 npm 包的 integrity 与源码；未运行）。

**productAgentId 与 executionProfileId 分离，禁止配置串域。** 增加宿主派生的 ExecutionProfileId，preset key、ConfigurationScopes、history override、ModelPolicy、knowledge/workspace/cron 按 profile 访问，不再同 agentId 找首项或覆写全部。owner 配置更新只派生新不可变 profile 快照，受限 ceiling 不随私人 feature/插件开启而扩大；模型/公开名字可明确同步。fresh root 不设 native parentSession，工作关系用产品因果链接记录。恢复校完整 profile/role/policy/audience/node epoch，否则不 resume 旧上下文。

**移走宿主 root 的私人贡献，并强制工具执行上限。** owner global extensions、project instructions、memory/skills/cron/heartbeat 仅挂有权限 private/ordinary preset；root 只留受审公共运行时服务。新增精确版本公开 agent-instructions 依赖，不能 import transitive private 实现。受限配置显式 features=false、knowledge=false、skills roots=[]，cwd 为本次空执行目录；禁 root 自动发现 owner 指令。tools.restrict 不过滤 scope-local 工具，run_code 又绕普通 restriction，因此受限始终 presentAs(native) + immutable tools.guard 拒绝所有非允许工具、run_code和内部通信，再由 broker 验操作/目标。restricted approval 不允许外部 interactive 同意或 unattended fallback 扩权；其拒绝不能被 Auto 分类器覆盖。若尚不能证明 root contribution 清单，拒绝启用受限执行，不能降级为共享 owner profile。

**私密与外部之间只传有来源请求及最小放行资料。** 外部 request 记录包含真实 actor、source message/version、目的和目标，不是授权或第二任务。私密侧可读准备；没有精确既有授权时在本人 DM 请求具体确认。release 绑定 owner 决定、资料对象/版本或精确输出、conversation、audience revision、用途、期限和撤销状态。不得由主脑自批、外部伪造同意或子 Agent 回复建立许可。

**私密主脑的自动观察工作也不得借非 IM 工具外泄。** observation/external 域无通用网络与文件工具，但 private 主脑可能组合私料和第三方材料；不能把 web_search/read 类名视作永远安全。PA 私密执行的外发包括 URL/query、上传、插件参数、shell 网络命令，均须绑定 owner 当前明确动作或有界规则，不能由 system wake/历史 owner 语句/第三方摘要建立许可。无人值守且缺少可核对 grant 时拒绝或回本人确认，即使既有 NanoApproval 将工具标为 safe/unattended allow 也不可覆盖该 PA egress gate。允许的本机只读准备与本人私聊建议无需逐项审批；通用公司 Agent 既有规则不变。此边界防私料经“只读搜索”传出，不能仅保护 send_message。

**task_graph 唯一真相，新增有界代表协助写回。** 只读 owner_tasks 使用 owner 当前源 ACL 和观察范围；写回必须有本人给定的 task ID、动作及范围授权，保留 actor=PA/authorized_by=owner，不伪装真人。默认不 claim、不改 assignee。当前 PA 不在源会话时，有界协助写入是独立 delegated-mutation 路径：以 owner 当前写资格为上限并保留 PA actor，不偷偷将 PA 加入源会话；已有成员 PA 仍不能因成员身份越过 owner 批准的范围。结果/状态更新使用当前 graph revision 和现有合法状态检查；改派、删除及扩大范围另取授权。不借 owner 管理员身份获得删除权。

**自动同步与模型唤醒分开。** 消息、本人回复、任务变更即时持久同步；模型合并处理，owner 直接请求最高优先。普通消息建议 20 秒合并、单批 50 个引用、每源最多 5 分钟待检查；这是工程预算，可由压测调整，不是安全保证。历史分页低优，重启/忙碌/离线可恢复，显示真实覆盖而非“已理解全部”。

**撤权须使上下文失效，不能只改下一次 API。** policy/member/node epoch 变化撤销游标、未发送候选和旧 release；受影响外部 scope 重建。排除/清理先暂停受影响执行准入，失效旧执行与受控派生索引，再重建允许的上下文。清理范围是 PA 管理的观察副本，非所有磁盘历史的物理删除；下述生命周期明确保留物与恢复边界。

**单 M1 端到端实施。** 身份/路由/ACL/受限执行/观察/界面互相依赖；按数据库、API、UI拆 milestone 不能独立交付且容易出现半通半漏。不机械拆 worker；实施 owner 在一个 unit worktree 集成，独立门禁另派。

### R1 收口：节点驻留与同身份恢复

首个 PA 私密文件/事件写入前，IM 和本机分别持久登记 node 的 PA residency（owner、binding、epoch、历史驻留事实）；两端握手确认后才准入 PA 执行。该标记不随断开、暂停、删除缓存或目录改名清除。跨 owner device prepare/commit/recover 任一步发现任一标记或未知状态即拒绝，事务不部分转移 Agent；本机在写新 owner/token 前和每次启动再核，不能先转服务端再依赖本机清理。已有未登记运行目录/身份不匹配须停止并要求同 owner 核对，不能推断为空设备。普通无 PA 节点交接仍原行为。

本期不实现可验证整机擦除/跨 owner 迁移。用户提示“这台电脑保存个人助手私密资料，暂不支持整体转交”；停止或目录改名不是擦除。原 owner 可在原节点重连，或在新在线节点通过 owner 管理操作恢复同一个 PA 身份：事务递增 binding/node epoch，撤销旧节点运行凭据，旧端离线回归先校 epoch 并停止；新节点重新观察当前授权来源，旧本地记忆/Work 不自动复制。不能从新节点上报另建第二 PA，也不以旧节点仍有文件为可继续运行的许可。

### R1 收口：自动能力与明确委派执行

三个 PA 域仍负责理解、准备、同会话沟通与受控动作；另增加 owner 批准的 `authorized_task` 执行用途（不是第二 PA 或默认第四个常驻脑）。PA 自动工作不直接装配通用 read/shell/run_code、任意扩展或不受控自进化。自动可做的真实工作包括观察与检索当前允许源、合并承诺、起草附件/回复、准备任务结果、申请结构化搜索/产品写入，并由宿主批准后实际执行。PA 可用专业能力执行写代码、操作文件与复杂工作；普通专业 Agent 的独立使用保持现状。

两种执行明确区分：

1. 可结构化中介的能力：新增 host action candidate，包含 owner/binding/execution、具体工具与规范化全部参数、接收服务/目标、外传字段及来源、内容 hash、用途、expires、policy/audience/object revision、idempotency key。本人确认界面显示这些事实，认证 owner `POST /im/v1/personal-agent/actions/{id}/approve` 用 expected_revision 确认，不能由模型、第三方或历史短回复签发。宿主 async pre-execute 读取并验证 grant，绑定原生 `exec.token` 和完整不可变参数；同步 tools.guard 在所有 pre-execute/人工审批之后用宿主闭包中的 permit 再设单调拒绝。最终 broker 发出网络/产品请求前原子消费/重验 grant，参数改变、撤销、token 不符均拒绝。普通 NanoApproval 允许只是必要条件之一，safe/skip/unattended 不跳过该 guard。未知结果仅查询同一 operation，不重新外发。外部系统已接受后的撤销不能追回。
2. 无法由参数完整界定效果的 shell/run_code/任意插件：不得把命令 hash 当作精确外传保证，不进入上述自动 broker 许可。PA 在本人 DM 准备独立任务提案，列目标、选定专业能力/节点、准确输入附件与摘要、所需工具/工作区、预期网络服务和残余风险；本期固定由 PA 自己的 productAgentId 承载 authorized_task fresh root；“专业”指 owner 选定、宿主版本化的能力配置，不派给普通公司 Agent 的既有账号/共享会话。owner 明确批准后 fresh task profile 仅收到选定任务包，不 fork PA/审批/记忆，不继承持续观察权限。结果只存 owner-only Work/产物视图，不自动写任务或公开发言。工具动作继续现有工具审批，child 不能自行扩大任务包/目标或获得 PA source API。若同 OS 广权限工具可读其他文件或联网，此模式不宣称强隔离或精确信息流；确认必须明示这一实际风险，用户可拒绝或选择独立干净节点。没有可接受的节点/授权时保留提案，不静默放权。恢复、child/workflow 均继承 task 的上限和撤销 epoch，不能升回 private。

provider 模型请求是启用时明示的资料处理，仍只组装该域允许输入；不能把 provider 正常调用扩展成可任意发 URL、query 或日志。任何新外部工具若未实现完整 broker 或显式任务路径，则保持不可用并如实提示。M1 验证同时证明受控搜索/任务成果有用，以及无 grant 的 web/query/plugin/shell/child 均未产生出站，不能以全部拒绝冒充完成。

### R1 收口：撤源、缓存清理与残余历史

PA 自动知识写入只经 provenance-aware host writer；禁用现有通用 memory_curation/self-evolution 对 PA 自动资料的无来源写入。可复用知识文件序列化，新增每片索引与内容 hash；读取只从当前 policy 的允许片段构造，不直接全量注入 MEMORY.md/USER.md。所有从受限观察、主脑、审批 reviewer、知识维护、workflow/child、摘要压缩、导出及本人建议形成的输出都登记 execution lineage；整次上下文无法逐片分清时保守标记为依赖其所有输入源。未知来源派生内容整项隔离，不猜测安全。

`POST /im/v1/personal-agent/cleanup` 创建幂等 operation（policy_revision、affected source IDs、mode=exclude/all_observation）；`GET .../cleanup/{id}` 返回 pending/retiring/rebuilding/complete/failed 和真实进度。IM 同事务提升 policy epoch、停旧许可与准入并记事件；Node 落盘 operation 后停止相关 main/children/reviewer/知识运行，废弃其 resume/checkpoint 引用和待发候选，撤旧 grants，清除 PA 控制的缓存与派生片段并重建允许的知识。只有重建成功且服务端确认新 epoch 才允许新上下文；离线/崩溃/未知回执继续同 operation，不能靠点击宣布完成。排除单源可以保留其他源的持久摄取，但模型处理等待重建安全点。

锁定 DSH 原生 session 日志为 append-only，没有公开逐条 redact/delete；`dispose`、压缩、新会话不等于删除。旧 runtime/history、workspace chat_history 导出、审批 checkpoint 和备份可仍留在磁盘，原聊天/任务/已发消息及 owner 可查的历史 Work 保留。它们属于展示历史，不得经旧 resume、KnowledgeRuntime.batchHistory、普通 read/shell、审批文件工具或新 source API 重新进入 PA 自动上下文。宿主复核 epoch+provenance 并只提供过滤后的 history view；保留的 owner DM 中带旧源 lineage 的建议/引文同样屏蔽模型重读，不能借“本人私聊”重新注入。新输入明确包含被排除内容时作为新的直接输入标记，不暗中恢复旧源持续观察。

清理 UI 明确“PA 观察缓存已清理、旧上下文已停用”，不声称磁盘全部抹除；模型服务/收件人已接收资料无法撤回。广权限独立任务仍有本机残留读取风险，须按前段显式说明；本期不把文件工具约束冒称 OS 安全沙箱。M1 覆盖源→记忆/摘要/建议→排除→重启/child/审批/导出/旧 DM 的完整再注入负向链。

### R1 收口：联系控制与任务通知

contact policy 保存 blocked_actor_ids 与 blocked_conversation_ids（稳定服务端身份，不按显示名），只阻断该目标触达/发送及其待办执行，不删除历史。owner 设置内提供阻止与解除、离线未生效及 revision 冲突；提交同事务提升 policy，取消该目标候选、许可与 scope，下一次消息/relay/投递再验。解除后新消息可触达，不自动重放屏蔽期请求、不恢复旧许可。禁止他人 DM 和群屏蔽各自明确，避免一个群屏蔽意外成为对人全局屏蔽。PA 入群确认另有具体 group/audience grant，contact 可用不等于可自行入群。

任务结果/状态写回不额外以 owner 身份发聊天消息，但现有“待确认/完成”系统通知保留且随任务事务提交。确认页展示源群、当前受众、改动内容及系统通知，结果页展示真实通知/任务回执；任何受众变化必须重新确认。不能显示“不会给群里发消息”。

## 接口与数据流

### 持久模型与迁移

IM 新增最小事实：personal_agent_bindings；pa_policies（version、enabled、excluded conversations、历史覆盖和 contact policy）；pa_source_events（单调 seq、kind、object/version、actor、source、occurred_at，仅受控引用）；pa_deliveries（binding/epoch/cursor）；pa_releases/pa_action_grants（授权证据与受众/对象版本/用途/期限/撤销；owner confirmation API 绑定 candidate hash+expected revision，保存真实 authenticated owner actor，非模型提供的 approved=true）；必要 execution link。不得存另一份 task 状态。

协议增加 ExecutionBinding={executionId,productAgentId,ownerId,profileId,role,policyRevision,audience?:{conversationId,epoch},observationBatchId?}，由 Node 持久宿主绑定提供，不允许模型自报。Node configuration/main 负责派生与恢复 profile；integration initialize/configuration.apply/session.ensure 以 profile key 装配。

Node 新增 observation inbox、durable_received/processed cursor、候选及投递幂等键、scope bindings/profile revisions、PA residency、action permits/cleanup operations/provenance index；现有 SQLite 迁移机制执行 additive schema，旧 role 缺省 specialist。既有用户无 PA 时显示设置引导，不任选第一个 Agent 静默改角色；新建 PA 后原 Agent 保持。唯一索引处理并发创建，配置 apply 尚未确认不得显示 PA 就绪；重试复用 operation id。用户退出/失去资格禁用绑定，不把身份迁给新 node owner。

### 对外联系人投影

PA contacts/list/search 使用严格投影：agent_id、自定义 display_name、personal role、现目录已可见的 owner 身份及粗粒度可联系/离线状态。不得复用完整 Agent profile 响应；外部不返回 custom_prompt、workspace、skills/plugins、模型配置、private conversation/session/run ID 或工作摘要。建 DM、群成员添加、message read/write、media download、relayEligible、直接投递和 WS 订阅统一执行 communicationAccess，Work/config/trajectory 与 skills/commands 能力发现则执行 privateAssetAccess；外部发现只给 external 域公开操作，绝不枚举私人配置。对已知 ID 的直接 API 同样检查，不以联系人列表不可见代替。

### 用户 API（目标契约）

- GET /im/v1/personal-agent：仅本人，返回 binding/公开名称/canonical DM/状态/观察覆盖，不返回 secret。
- POST /im/v1/personal-agent：本人创建，使用 request_key 与现有配置 operation；重复返回同一结果，pending 可恢复。名称验证与既有 Agent 一致。
- PATCH /im/v1/personal-agent/policy：本人+expected_revision，保存暂停、排除和 contact policy，同事务写 revoke event；冲突不覆盖。
- GET /im/v1/personal-agent/sources：本人当前可读来源与覆盖/排除状态，分页。搜索及错误不泄漏失权来源名。
- POST /im/v1/personal-agent/releases：本人对精确候选确认；服务端核候选版本、受众和当前权限，返回不含凭据的 release id。模型不可调用 owner HTTP 身份。
- POST /im/v1/personal-agent/task-actions：本人对 task_id、graph_revision、source/audience/policy revision、系统通知受众、允许操作/结果 patch hash 的候选确认；服务端验证 owner 当前写资格并生成一次性 grant。重复确认幂等，实际应用时再核权限/revision；撤销或使用后不得复用。禁止 model 自行签发。
- 既有 Agent rename/config API 继续处理名称与模型，PA role 不可普通 PATCH 修改；普通 Agent 删除入口不得删除固定 PA；可暂停观察或断开节点，显示恢复原 PA 的入口而非无痕重建身份。本 unit 不新增销毁 PA 私人历史的独立产品操作；账号删除继续原有明确确认契约。

### Node/产品方法（目标契约）

`pa.observations.check/read/ack`、`pa.history.list/search/read`、`pa.tasks.list/get`、`pa.tasks.apply`、`pa.releases.request/read` 经现有 authenticated gateway request/response 传输，不另开服务端口。每次请求带宿主 binding/epoch/scope revision；IM 按当前真实 owner 资格及该方法允许 scope 校验。外部仅 `pa.external.read` 和同会话 send proposal；观察域仅本批源读取和结构化结果提交。普通 specialist 或 child 无法借 owner_id 参数调用。

所有读范围 = owner 当前 ACL ∩ 本次批准的观察策略 ∩ 查询目标；附件、snippet、分页 cursor 同样受控。cursor 绑定 owner/binding/policy/query/snapshot；权限变小旧 cursor 拒绝。读取不调用真人 read API、不产生本人已读、不赋予执行授权。

### 私密 Work 投影

保留一个 global_main；external_chat、observation 与 authorized_task 是独立 root execution kind，以产品 cause/关联工作链接到 PA，不伪装第二个 global_main 或 native child。Work schema/query/trajectory 类型增加这三种 scope，均仅 owner 可查；页面明确“外部会话处理/观察分析/专业任务执行”及真实来源，外部聊天不获得 run/session ID。普通全局 Agent 与 child 的导航和统计保持，不能因新增 scope 导致查询重复累计或把接收回执算成完成。

### 路由与控制

| 输入 | 域与处理 | 输出边界 |
|---|---|---|
| 真实 owner → canonical PA DM | owner_private；可走原有当前控制命令 | 本人 DM；外发单独授权 |
| 外部 human/agent → PA DM | external_chat；同 conversation/audience，输入明确 external | 仅源 DM；无 private Work 查询 |
| 合法群 @PA/回复 PA | external_chat；当前群成员/提及规则 | 仅源群；不用新门户 |
| 本人其他收发/任务/历史 | observation system ingress，禁控制解析 | 候选给私密主脑；不自动加入源会话 |
| 内部工作结果 | 宿主 parent/scope 归属 | 结果不是授权，不默认外发 |

PA 私密 Inbox 只接 owner 当前 direct input、可信系统通知和正确子执行结果。owner 在群中 @PA 也按群受众处理，不把群发言升级成读取全私料的通道。外部 `/stop` 最多停止该 external scope；不控制 private main。旧 owner 历史文字只作背景。普通非 personal global 保持原跨聊天语义。

### 授权与撤权并发

release/grant 状态为 pending→approved→consumed/revoked/expired；仅 owner authenticated confirmation 或已核实的精确既有规则可进入 approved。受众/对象/来源 policy revision 在最终消息写入或 task mutation 同事务重验。跨 Node/IM 的发送先预留幂等 operation，再在 IM 最终提交时 compare-and-check revision；撤销先提交者胜，未知回执查询原 operation，不能重复消费许可。非 IM 的线性化点为权威 store 接受 operation 预留/消费：此前已提交撤销则拒绝；之后动作可能已开始，不能保证可追回。网络与数据库不是跨互联网原子事务，超时保留 unknown 并只查原 operation。单次批准仅授精确输出/patch；有界长期规则必须由 owner 在产品规则功能中另行明确创建，本 unit 不自动新增长期规则。对同会话既知事实的普通回复不需私人资料 release，但仍受目标、受众、最新消息与动作审批检查。

### 观察可靠性

消息完成、本人发送、已读、task revision、群解散/成员变更、策略修改与业务写同事务入事件；流式输出 finalized 后分析，delta 不逐条唤醒。现无普通 message edit/delete API，不为本 unit 顺带新增编辑产品；未来提供时必须产对应事件，当前源删除/群生命周期仍纳入。

增量以 snapshot watermark 启动并行历史分页，Node 落盘后 ack，processed 只有实际摄取后推进；WS 丢包从持久 cursor 补取。幂等键覆盖 source canonical ID/object version/kind，PA 自己的提醒不重新唤醒自己。候选发出前重读最新任务/本人回复；旧请求已处理则撤销。保留窗口越界返回 gap/resync_required。offline 不宣称分析中，恢复先检查权限和最新状态，再合并积压。

### 候选事实与记忆

复用私密 knowledge/memory 能力，不新增平行 task 状态。观察候选始终携带 source object/version、真实 said_by、时间与 asserted/owner_confirmed 区分；第三方内容、模型总结、旧 owner 消息均不能写成新的授权规则。自动记忆更新只能保存有来源的事实候选，不能修改系统规则、profile ceiling、release/grant 或已确认 owner 决定。新增 PA provenance index 记录 source object/version → candidate/memory fragment/output/execution/export/approval evidence；索引不复制任务状态。无可靠逐源 lineage 的旧记忆不能自动迁入 PA 自动知识库，整项隔离并由仍有权的原始来源重新形成。受限观察域本身无 memory 写工具，private curation 也要通过此 provenance 边界，不能由通用 safe-memory 或 shell 路径绕过。

### 发送、任务和 I2I

公开回复只允许本 conversation 事实及有效 release，实际目标由 binding 决定，不信任模型 target。群受众改变、来源版本变化、许可撤销或新消息使审批失效。当前发送复核保留；结果区分 prepared/sending/confirmed/unknown/failed。unknown 用同 idempotency key 查询/重试，不能重发新消息假定成功。

任务写入始终校 owner grant + owner 当前源会话可写资格 + graph revision；PA 成员资格绝不是 owner 资格的替代。还须核任务工具开关、scope、source/audience/policy revision，操作记录真实 PA。无 grant 只能回 owner 草稿与建议；grant 不允许 claim/改派/删除的隐式升级。I2I 使用 cause chain、父协作授权、最大 hop/turn 预算、每身份配额及去重；预算耗尽给主人报告待决定，合法已开始任务结果仍可提交但不得触发新一轮无限委派。来信送达、接单、执行、结果待确认、完成是不同事实。

### 独立任务的身份与返回资料信任

首版 authorized_task 固定 productAgentId=PA、ownerId=binding.owner、独立 executionProfileId 与 purpose，专业能力仅为同 owner 可选择的配置快照，不把 private 包发送给普通公司共享 Agent。候选页显示“执行者：你的 PA · 专业任务”，能力版本、实际节点、输入与仅本人可见的结果。所有 Work/session/native trajectory/产物/media/WS/查询/已知 ID/关联导航按 PA privateAssetAccess；恢复前校 binding/profile/policy epoch。不能因某能力配置来自普通公司 Agent 就继承其 product id、共享 Work 或配置监听器。普通专业 Agent 工作仍原共享规则，未获这份任务包。

广权限任务无法证明实际只读取批准输入，所以其正文结果、产物、错误、进度、child/workflow/reviewer 输出全部标记 unknown/tainted；不以初始输入包或执行模型自报覆盖。宿主仅把固定状态、执行 ID 和“结果待你查看”的无正文提示交给 PA，内容在 owner-only Work 由人查看，不进入 private Inbox、owner DM 正文、自动观察、memory、审核历史或后续任务工具。具有可证明输入集合的受控 broker 结果才可带可靠 lineage 自动进入相应域。

owner 可从隔离结果视图明确选中具体文字/文件，查看准确内容及“作为新的本人输入提供给 PA”说明后提交新输入；服务器记录 owner 选择、bytes/version 与新来源事实。拒绝/未选择时正文继续隔离；不能用自然语言短同意或任务执行批准代替这次选择。此操作不恢复已排除源的持续观察，后续资料也不自动获准。W11 增加 S 已排除但残留磁盘、包 A 执行返回 S 的测试，断言仅人可看，主脑/知识/审批/本人DM摄取均无 S；显式新选择另测。

## 前端原型

原型：[prototype.html](prototype.html)。基于用户自主设计授权，收敛为 A 固定导航 + 四关系的连续旅程，已补齐首次创建、历史覆盖、外部私料确认及撤权恢复的可交互状态，46 项 jsdom 交互断言通过；详见 [原型补全记录](research/prototype-completion.md)。视觉未验证。不得把功能清单宣称为已通过体验验收。

用户目标：先找到自己的 PA，再辨认本人/外部受众与建议来源；从私聊读明“为什么需要我决定”，查看具体草稿/任务，确认后才外发或写回。PC 复用现聊天列表/消息区和右侧编辑面板；窄屏同一动作进入全宽面板，关闭回原聊天并保留草稿，返回不误发送。观察暂停/排除在 PA 设置，聊天顶栏持续显示 paused/offline/backfill 状态；不能用在线绿点表示历史已读完。

### 现有 UX grounding

| 当前入口 | 依据 | 增量 |
|---|---|---|
| onboarding-page / agents create | 源码与 agents-nodes current spec；实际画面未验证 | 首个创建固定 PA 角色、可起名、观察说明；失败可恢复且不重复创建 |
| chat-workspace-page 与导航 | 源码/既有原型模拟；实际布局未验证 | A 固定自定义名字入口；PA 名称+角色身份，不新增外部请求门户 |
| task graph 与 agent Work | current spec + 源码；实际画面未验证 | 私聊来源跳转原任务、保持负责人；PA Work 仅 owner |

### 原型对齐契约

| 区域/状态 | 级别 | 产品入口 | viewport/状态 | 投影 |
|---|---|---|---|---|
| 唯一 PA、起名/改名及固定入口 | must-match | onboarding / 固定主导航与专属私聊 | 1440、768、390px；长名字/空白/重复提交/断线 | M1 R1 / W1 |
| 主动建议来源、草稿审核、任务引用 | must-match | owner PA DM / 编辑面板 | 同宽度；来源失权/已回复/任务更新/取消返回 | M1 R2 / W2 |
| 原生外部 DM / 群 @ 与身份/受众 | must-match | 现有 DM/群 | 同宽度；无授权/等待本人/许可过期 | M1 R3 / W3 |
| 观察暂停/排除/历史覆盖 | must-match | PA 设置与私聊状态 | 同宽度；离线/补读/清理未完成 | M1 R4 / W4 |
| 精确服务动作与广权限专业任务确认、隔离结果选择 | must-match | owner PA DM / 同一编辑面板 | 三宽度；拒绝/取消/参数变化/换节点/离线/未知回执/新输入选择 | M1 R6 / W10、W13 |
| 联系屏蔽与解除后新请求 | must-match | PA 设置 / 原生 DM群 | 三宽度；取消/离线/策略冲突/旧请求撤销/新请求重建 | M1 R4 / W12 |
| 间距、平台图标、面板断点 | may-adapt | Web responsive | 不改变上述层级、关闭/返回与草稿保持语义 | W1–W4 |
| 原生 iOS 新导航 | out-of-scope（按本次 Web 请求） | 原生仍普通聊天 | 必须回归已有聊天/API；不声称 Web 缩窄图即 iOS 设计 | R5 |

### 原型走查

无成功的实际渲染/代表性截图，当前产品画面对照也未完成。此前 shell Chromium socket/升级启动失败、云浏览器与 shell 端口隔离；clipboard→terminal 路线曾被拒且授权后同调用重试仍被 frame policy 拒绝，不能绕行重试。本设计明确视觉未验证，不将 DOM/CSS 阅读冒充观察结果。需允许且可用的实际浏览器路径完成走查，或用户明确调整验收范围；在此之前 Gate 2 阻塞。

## 契约层增量 (delta-spec)

- IM 新 `personal-agent.md`：身份、原生联络、观察控制、私人资产；canonical 归并时登记到 im/spec.md。
- IM `agents-nodes.md`：首次 PA 创建与固定模式、目录公共投影；修改受影响条目并完整保留普通 Agent 场景。
- IM `auth-tenancy.md`：固定空间仍成立，限定 PA 观察/通讯资格与私人资产之间的例外，不放宽普通主体 ACL。
- IM `agent-work.md`：修改“聊天沟通与全局工作轨迹分开呈现”，完整保留普通 Agent 场景并限定 PA owner-only。
- IM `task-graphs.md`：有界代表协助，新增仅限 PA 的 owner 委托路径，不改负责人或普通主体 ACL。
- Gateway `global-agent.md`：修改跨聊天认知、信号接收和控制命令的适用范围，完整保留普通 global 场景。
- IM `conversations-messages.md`：PA 入群由 owner 明确确认，普通加入规则不变。
- Gateway `task-graphs.md`：委托任务及 PA 加群例外；`agent-capabilities.md`：按域配置/继承/Auto ceiling 及私密能力发现。
- Gateway 新 `personal-agent.md`：域路由、观察摄取、资料放行、任务协助及恢复；canonical 归并时登记到 gateway/spec.md。

所有 delta 均为目标草案，不能提前覆盖 current。

## 风险与回退

最高风险是 profile 的漏继承与空间 ACL 放宽；需负向测试遍历工具/附件/轨迹/已知 ID/cursor，不只测聊天输出。逻辑隔离不宣称 OS 沙箱；公开 DSH 能力无法落实时先阻塞对应功能，不能悄悄放权。观察可能误判承诺、反复打扰或降低本人响应：用合成真实旅程衡量漏报/重复/延迟，不能以“全拒绝”换安全。

schema additive，可禁用 PA feature、停止 observation/external admission 并保留 owner 历史及原任务；不将外部 context 合回 private，也不删未知用户数据。回退期间显示未处理状态，不伪报运行。旧客户端若不能辨认 personal role 则保留普通 DM 可用、不给其新增管理操作。

## Runbook for Reviewer

常驻服务为本 unit 隔离 IM 与 Node/DSH；Web 可使用已构建静态客户端。遵循 docs/development/worktree-runtime.md，禁用主机端口/身份/config，真实启动以脚本为准（文档中旧 Python 手工 IM 启动段与现 TypeScript 入口不一致，不使用旧手工段）。

| 服务 | 停止 | 启动 | 健康检查 |
|---|---|---|---|
| IM + Node/DSH | ./scripts/e2e-down.sh --wt "$WT_ROOT" | pnpm install --frozen-lockfile && pnpm build && npm --prefix src/IM/frontend ci && npm --prefix src/IM/frontend run build && ./scripts/e2e-up.sh --wt "$WT_ROOT" | source "$WT_ROOT/.e2e-ports.env"；curl -fsS "$IM_URL/openapi.json"；pnpm pa status --config "$WT_ROOT/.gateway-config.yaml" |
| 可选 Web Vite | 记录本次 PID 并只停止它；确认端口释放 | 在 frontend 目录，加载 VITE_IM_PROXY_TARGET，以 free-ports.sh 分配端口执行 npm run dev -- --host 127.0.0.1 --port "$VITE_PORT" --strictPort | 实际浏览器登录该隔离栈并核对受审版本 |

运行前将 WT_ROOT 设为最终 unit worktree 的真实绝对路径，并在该目录执行；Python 辅助依赖按 pyproject 的 dev 组安装到本次云端隔离环境，不能读取用户本机配置。Vite PID 与端口由启动者记录并负责清理。

Review 驱动方式：端到端真栈，必须真驱动 Web 新手创建、PA 入口/改名、本人私聊草稿/观察控制、外部 DM/群 @、任务写回与撤权；API 不代替 UI。独立 static reviewer 执行 code-review+verifier；独立 product reviewer 检查真实用户结果。

验收前置：隔离 owner/peer/company/nonmember 测试身份及测试 Agent 可由本次测试栈创建，使用合成隐私数据；不访问用户生产聊天。DeepSeek 模型必须经安全方式配置到云端隔离环境并核实真实请求/响应与产品送达，目前未配置。浏览器需同隔离栈可达且正式允许，目前未落实。原生 iOS 构建/真实设备未作为已完成资源；若范围扩大需先补相应原型和资源。以上必要资源未落实前 Gate 2 不能 Approved。

## Milestones

| ID | 标题 | 依赖 | 并行组 | 范围 | 退出标准 |
|---|---|---|---|---|---|
| M1-personal-agent | 完整 PA 纵向旅程 | Gate 1 + Gate 2 | 无 | 上述 IM/contracts/PA/DSH/Web 路径及测试；不动生产配置/密钥 | [reviewer] R1 唯一首 PA、命名与入口兑现原型且恢复不重复；R2 自动发现未手动转交请求、本人回复后不重复催、任务责任保持；R3 原生 DM/群 @ 可用且私料受众可辨认、放行精确；R4 暂停/排除/撤权/离线恢复真实且不泄漏；R5 普通 Agent/已有 channel/task/Web与iOS普通聊天兼容；R6 用户能区分精确外发与广权限任务，取消/改范围/检查回执，并明确选择隔离结果是否重新提供给 PA。[worker] W1–W4 各 must-match 对应真实浏览器证据与独立体验判定；W5 可信路由/所有工具拒绝/审批伪造/撤权 race/重复恢复/游标缺口负向测试，含实际模型请求/历史/tool result 的 owner canary 缺席、AGENTS/扩展 listener、非空最小 allowlist 仍禁 run_code、配置热更新/HMR/冷恢复不串域；W6 任务 revision/授权/actor 不变式；W7 DeepSeek 真链路同时证明主动价值及攻击边界；W9 PA residency 两端交接拒绝/重试/恢复、同 owner 新节点旧 epoch 拒绝；W10 非 IM broker 参数/撤销/重复与独立专业任务的真实有效结果；W11 源→记忆/摘要/建议/审批/child/export→排除→重启再注入负向链及清理回执；W12 联系屏蔽/解除→新请求/unknown与真实任务系统通知受众；W13 新增授权/隔离结果must-match真实UI与身份/Work/媒体/WS私密投影负向测试。W8 最窄测试后跑当前 CI 等价全量，保留 commit/command/result/evidence，未经验证不归档。 |
