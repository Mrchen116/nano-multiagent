# Personal Agent backend grounding and minimal design

基线：`nano-multiagent` `main`，commit `481467ac16f0eda4561fca5c8230050541600de9`。2026-10-16 阅读，初始 `git status --short` 为空。只读审计；未运行测试，未修改产品源码。已读 AGENTS.md、docs/README.md、change-workflow.md、change-design-author SKILL。以下“建议”均为 proposed，不是 current 行为。

## 结论

建议把“固定个人 Agent”建模为用户绑定的产品角色，执行复用现有 global Agent；不要发明第三种 work_mode 或第二套 loop。现有系统已具备跨聊天主上下文、Inbox、Heartbeat、原生 Cron、知识整理、任务图和权限审核。真正缺失的是唯一身份绑定、首次设置事务、个人入口投影，以及 owner 授权读取本人其他聊天的专用权限边界。

最重要的三个约束：
1. global != personal。当前所有 global Agent 都可以跨其有权访问的聊天工作，但没有哪个是“这个用户的唯一个人 Agent”。
2. owner != conversation member。个人 Agent 不能凭设备 owner_id 读用户全部 IM。尤其个人 Agent 固定 personal space，而用户加入公司的聊天处在 company space；若要协助这些聊天，必须单独设计受委托读取，不能直接放宽 canActorAccess。
3. task graph != scheduler。当前任务图明确只记录，不自动执行；主动推进应依赖用户授权、Heartbeat/Cron 和 Agent 工作策略，不能让 assignee/status 隐式获得执行授权。

## 当前代码地图

| 方面 | current 证据 | 已有能力 / 缺口 |
|---|---|---|
| 注册身份 | `apps/im-server/src/identity.ts:216-248` | 注册只创建真人 users，owner_id=id，personal_space_enabled=1、membership_status=none；没有个人 Agent 绑定 |
| 用户数据 | `apps/im-server/src/schema.sql:14-24` | 有 default_entry_node_id，无 personal_agent_id / role / canonical personal conversation |
| 首次设置 | `apps/im-server/src/onboarding.ts:26-68` | GET /onboarding 返回 owned nodes/agents/install；node setup 复用 Gateway RPC；无个人身份状态机 |
| Agent 数据 | `apps/im-server/src/schema.sql:54-86` | agent_profiles 全局 agent_id、owner_id、space_id、node_id、work_mode、features；没有用户唯一角色 |
| Agent 创建 | `apps/im-server/src/control.ts:160-444,656-697` | ConfigOperations durable receipts、fingerprints、recover、serialized(agent_id)，创建走既有节点 RPC；默认 single_thread；不保证每 owner 第一 Agent 唯一 |
| 创建配置 | `packages/personal-assistant/src/configuration.ts` | ConfigurationOperations 写前日志、pending/applied/rejected、并发链、冷恢复；应复用，不另造配置提交协议 |
| 配置协议 | `packages/product-contracts/src/configuration.ts:19-65`; `apps/im-server/src/control.ts:54-111` | canonical config 和 fingerprint 是 IM/Node 兼容边界，字段变化影响恢复；个人角色可先留在 IM 产品域而不进入 runtime fingerprint |
| 模式不可变 | `apps/im-server/src/control.ts:779`; `apps/im-server/src/gateway.ts:293-300`; `apps/node/src/configuration.ts:97-102` | work_mode 不可变；global workspace 也不可变。不能把旧 single_thread Agent 静默改 global |
| 节点注册 | `apps/im-server/src/gateway.ts:282-358` | 校验 owner/node 冲突，缺席 Agent 标 stale，未知 Agent 可从节点注册建立 profile；固定绑定必须覆盖 CLI/注册路径，而不能只改 Web 创建页 |
| 全局主上下文 | `packages/personal-assistant/src/global-agent.ts:21-101` | 一个 global:{agentId} 主 session，Inbox 唤醒是 system source；global /new 不按聊天重置；适合固定个人主脑 |
| 模型工具 | `packages/personal-assistant/src/global-agent.ts:112-195` | binding owner/agent 校验；Inbox/history 仅主 Agent；task_graph 等经产品调用；子 Agent 默认不能读全局 Inbox |
| 主动机制 | `packages/personal-assistant/src/heartbeat.ts:17-80`; `docs/specs/gateway/heartbeat-cron.md` | Node 本地调度，feature/subscription/availability/active hours 门槛，持久 pending intent、inputId 幂等；读取 workspace/.nanoassistant/HEARTBEAT.md；没有文件/任务就不运行 |
| Cron | `packages/dsh-integration/src/features/cron.ts`; `packages/personal-assistant/src/global-agent.ts:149-170` | 创建主 session 原生定时、重启恢复、执行证据区分 admission/completion/delivery；不要让 IM 成为另一调度源 |
| 任务图 | `apps/im-server/src/task-graphs.ts:189-207,356-360,438-470,717-748`; `packages/dsh-integration/src/features/task-graphs.ts:9-12` | fixed conversation、revision、request_key、assignee/status/result、list 过滤；明确“only when human asks to save a plan”“never run tasks”；当前无结构化 deadline/next_review 字段 |
| 聊天 ACL | `apps/im-server/src/messaging.ts:72-93`; `apps/im-server/src/conversation-access.ts`; `apps/im-server/src/identity.ts:42-69` | Gateway 验 agent owner+node+space，随后按 Agent 自己成员身份读写；公司 public 可读，写必须 member；个人 Agent 不继承真人权限 |
| 本人私聊 | `apps/im-server/src/messaging.ts:178-260,619-669` | 已有幂等 direct_key 和 user-Agent direct 创建；可复用做固定个人会话，不新增平行消息库 |
| 发送身份 | `apps/im-server/src/messaging.ts:37-49,619-669`; `docs/specs/gateway/global-agent.md` | Agent 有独立 agent: 身份；显式 send_message；本人 DM 特殊审核豁免不等于可代真人向其他人发消息 |
| Memory | `packages/personal-assistant/src/knowledge.ts`; `apps/node/src/configuration.ts:79-90` | 既有知识整理及用户/Agent workspace 路径；无需再造“个人 Agent memory 服务” |
| 设备交接 | `apps/im-server/src/identity.ts:833-890` | 整机转移可更新所有 agent owner/space/Agent user；固定个人身份与此现有机制冲突，必须有明确拦截或迁移流程 |

## 最小数据/API 建议

### 1. 单一权威绑定

建议一张 IM 产品表 `personal_agent_bindings`：user_id PRIMARY KEY、agent_id UNIQUE（预留稳定身份）、conversation_id UNIQUE nullable、provisioning_operation_id nullable、state（reserved/provisioning/ready/needs_attention）、created_at/updated_at。

- role 派生自该表；普通 agent_profiles 不再重复存一个可漂移的 is_personal。
- 必须校验真人用户、Agent owner 与 user owner 一致、Agent personal space、global mode。
- `node_id` 和 runtime 健康来自 profile/node，不复制到该表；ready 表示持久配置与会话完成，不表示设备当前在线。
- DB reservation 与 owner 级串行/唯一约束，不能只依赖当前 per-agent serialized。注册可 reserve；首次设备与模型就绪再 provision。
- 唯一性不等于全天可运行：尚未装机/节点离线显示 setup/offline 原因，禁止创建替代身份伪装 online。

### 2. 首次设置事务及 API

- 扩充 GET `/im/v1/onboarding`：personal_agent 对象 + setup_state；不再用 agents[0] 推断。
- GET `/im/v1/me/personal-agent`：identity、canonical conversation、derived availability、缺失步骤。
- POST `/im/v1/me/personal-agent/ensure`：选定 owned node、首次个性化字段、幂等 request key；服务器绑定 reserved agent ID，强制 global、personal space、受控默认能力；通过现有 ConfigOperations 创建，再幂等确保本人 direct conversation，最后 ready。
- ensure 重试查 provisioning operation，避免“节点已创建但 IM 未写绑定”产生第二 Agent。profile/绑定之间只在确认 applied 后完成；中途失败显示原 operation，允许恢复。
- 其他 Agent 创建仍用现有 endpoint，作为普通 specialist；不要允许客户端随意填写 role=personal。若产品要求“第一 Agent 必定个人”，服务器对无 ready 绑定用户拒绝或引导 specialist 创建，并覆盖节点注册路径的旧 Agent 导入场景。
- agent list/details 可投影 role/personal owner；无需把产品角色传进 DSH loop。

### 3. 主动目标与任务

第一版复用本人 canonical direct conversation 中的 task graphs，作为显式保存的目标/计划；复用 HEARTBEAT.md 的受控任务指令作为主动检查入口。使用现有 task_graph list(statuses,assignee) 查询已授权未完成目标，避免复制另一份任务真相。

需在产品契约明确区分：讨论中的建议、用户已保存的目标、已授权执行的动作、等待用户确认的动作。Heartbeat 可以检查/整理/给出建议；任何外发/敏感动作继续现有审批。任务标记 assignee 不是授权。

若要求可靠截止日期/下次跟进而非自然语言，应在 task graph 节点扩展可选 due_at / next_review_at（连同参数 schema、校验、索引/查询投影和兼容规则），不要把字段先塞进 description 再声称具备可靠调度。精确提醒仍绑定原生 Cron，任务 ID 作为关联而非第二调度器。

默认 Heartbeat prompt 现有“不要从历史推断旧任务”规则与“自动发现承诺”有语义冲突：需要明确仅个人角色可按已授权范围提取建议/检查已保存目标；不能改全体 Agent 默认。没有持久 HEARTBEAT 内容只开 features.heartbeat 不会发生主动工作。

### 4. IM 回复协助权限

最小安全版本：用户在某聊天选择消息→点“请个人助手帮我回复”→服务端以真人当前权限校验该消息与有限上下文→发送到本人个人会话，标注 source conversation/message IDs、发送者、时间、引用性质→个人 Agent 返回草稿。草稿回填 composer，由用户自己发送；不隐式以 Agent 账号加入源聊天，不把源消息变成 owner 指令。

如果产品要求“自动看我的 IM 并提醒/辅助回复”，必须增加受委托只读 API 和 grants，不能复用 Gateway owner_id 作授权：
- 用户明确 opt-in 的 conversation 集合（首版）或清晰 bounded scope；记录 read/draft 权限、创建及撤销时间。
- 每次读取重新验证真实 owner 当前账号/company/member 权限，与 grant 取交集；失权立即拒绝后续读取。
- 单独调用以 personal binding+当前 node 凭据认证，返回 source/provenance；不放宽普通 conversations API，不向 specialist/child 继承全部权限。
- 缓存/Inbox 撤销标记、投递前重验证、数据最小化需有明确契约；已进入模型历史的内容无法声称物理遗忘，至少禁止后续重新读与向失权来源外发。
- 只读权限不允许以真人发消息。后续如需代发必须独立 API、明确身份、目标、正文、幂等键与审核；不要在本次最小设计捆绑。

## 迁移/回滚风险

1. 老用户已有多个 Agent：当前没有 durable 首次设置 Agent 标记；created_at/rowid 只能作为候选，不能声称可靠地证明“原始第一个”。推荐用户确认候选；global+personal 候选可绑定，single_thread/company 候选不能原地转换。
2. 新建私有 global 个人 Agent 与旧聊天共存；不要迁移/混合原 specialist session、memory、任务图或历史 ACL。可以保留旧 Agent 不变，提供显式可审的资料导入。
3. 旧 company-only 账号：先开启 personal space 的适用迁移/设置流程，再创建个人 Agent；绝不能将既有 company Agent 自动改 private，反向也同样不行。
4. 整机交接：当前会迁移所有 Agent owner。绑定个人 Agent 的节点必须阻止普通整机 transfer，直到显式迁移/移除该运行绑定的流程可用；个人身份不能随硬件送给别人。不要静默清绑定使一人拥有多个 personal 身份。
5. 节点 config 手工移除 Agent 会使其 stale：保留用户绑定和修复入口，不自动从其他 Agent 随机替换。由于 current API 无通用删除 Agent 路由，不应只在 UI 隐藏删除就认为安全。
6. Node 注册与 config fingerprints：尽量把 personal role 保持在 IM；若确需传输新字段，必须双端 canonical 兼容和 pending receipt 恢复测试，否则旧操作 fingerprint 不匹配。
7. 回滚采用停止新 ensure/grants UI 与代理读取路由，保留 binding/Agent/原会话数据；不要删已创建身份、任务或 memory。“关闭主动能力”不等于删除用户保存的计划。
8. 节点离线不跑 Heartbeat/Cron，平台当前没有托管常驻执行承诺。必须在 personal 页面显示真实离线状态，避免宣称 24×7。

## 必须新增/扩展的验收测试

- 并发两个首次设置/不同 node 操作只产生一个 personal binding、一个 Agent、一个 canonical DM。
- 节点创建 applied 后 IM crash、RPC timeout、重复 ensure 均恢复原 operation，不重复创建。
- 在第二设备、手机或普通 /agents 路径创建 specialist 不夺走固定个人身份。
- 升级无 Agent、一 global、多 Agent、single_thread、company-only、stale/offline 等用户，均不静默混历史。
- 设备 transfer/注册缺席的 personal Agent 保持用户固定绑定和明确恢复状态。
- 私人 A 无法读私人 B；company suspension/离群/撤销 grant 后再次读取和缓存重发被拒；specialist 不能使用 personal delegation。
- 源 IM 的第三方指令/引用不是用户授权；read/draft 不授予 send；草稿发送人仍由 composer 的真人确定。
- Heartbeat 静默、忙时跳过、时区、去重、恢复、等待确认；task graph 状态变更不自动产生副作用。

测试入口复用：`apps/im-server/tests/onboarding.test.ts`, `control.test.ts`, `identity.test.ts`, `tenancy.test.ts`, `task-collaboration.test.ts`; PA global/inbox/heartbeat tests；现有 contract boundary tests。本文为静态证据，不以未运行测试宣称通过。

## 补充：主动能力真正生效的接线

前端当前实际首次 Agent 已是 global（`src/IM/frontend/src/features/onboarding/onboarding-page.tsx:61-70`），但明确关闭 heartbeat 与 cron_scheduling；现有 existingAgent 还使用 agents[0] 回退（:51），所以改为稳定 binding 仍必要。

个人 Agent 的首次设置应以一个可恢复 provisioning 单元完成以下条件，不能只把 checkbox 默认勾上：
1. 受控个人默认 config：global、heartbeat=true；若产品将定时列为基本能力，cron_scheduling=true 仅表示允许创建原生安排，不预创外发任务。保持 specialist 默认不变。
2. Node workspace 建立非空 `.nanoassistant/HEARTBEAT.md`，内容明确“检查本人已明确保存/关注且当前有权读取的未完成事项；检查是否需要有价值的提醒；没有就静默”。采用专门、幂等、仅缺失时播种的产品初始化步骤，并记录版本；不覆盖用户已有文件。现有 ConfigOperations 只写配置，不应假设它已经播种该文件。
3. 设置节律与可编辑 active_hours；例如30分钟和09:00–21:00是可讨论的产品默认，非现有承诺。`heartbeat-policy.ts:35-39` 在有时间窗口但没有时区时返回 false；UI需显示等待时区，不能用节点时区补猜。
4. `apps/node/src/main.ts:259-264` 将 store.ownerTimezone 注入 settings，按 globalProduct.heartbeatBinding 取得 global 主 session，并要求 runtime.available 与 relay/external availability。用户时区沿既有前台报告同步；跨时区沿当前已有规则。
5. `packages/dsh-integration/src/index.ts:261,443,451` 通过 heartbeat.subscription 通知 Node；必须验证配置 apply、冷启动、恢复都产生 subscription，而不只看数据库 features。
6. global Heartbeat 主 session 与本人 DM 是两个概念：前者 `global:{agentId}`；后者必须由 IM固定 binding 返回可核验的 owner conversation。应在 ready前幂等创建 DM，并通过产品上下文提供精确可用目标；模型不能只靠名字猜聊天。公开提醒仍显式 send_message，不把 global final 当消息。
7. 测试整个链：ready→合法时区+在线+idle+非空任务→实际 system wake→若有价值产生本人DM消息；无事不发。关开关、断连、忙、未知时区、文件空/不存在分别报告真实原因且不冒称主动正常运行。

## 补充：三种任务集合不能混为一谈

- “我负责”：已有 task graph assignee=user 本人，是责任关系；个人 Agent不因此得到聊天读/改权，也不自动变 assignee。
- “我关心”：可能是他人负责或我尚未承担的目标。首版由用户明确引用已有 graph/node 交办关注；只保存引用/关注意图，不复制任务正文和状态。若需要可见、可取消且可靠的跨会话关注列表，可加最小 subscriptions(user_id,graph_id,node_id,scope,created_at) 关系表，而不是第二套 task 数据库。
- “Agent能看/能改”：始终由源任务固定 conversation、space、当前资格/成员、Agent capabilities 决定；即使是本人负责或关心，也不能扩大授权。

首版零委托权限方案：只自动跟进本人和个人 Agent 共同参与的 canonical DM任务图；其他任务用用户转交的当前摘要作为输入，不称为自动同步。若要横跨公司IM/任务图持续跟进，读委托和任务查询必须走同一专用受限通道，取“用户当前权限 ∩ 关注scope ∩ grant”。写仍要求原Agent成员资格或单独明确的代操作授权，不能把只读委托顺带用于 apply/claim。

需要与用户单独对齐的实质权限问题（在现有UI问题答复后问一条即可）：希望“只在我主动选中消息/任务时协助”，还是“自动检查我授权的指定会话/任务”？不建议把全量IM作为默认；若用户明确要全量，再说明覆盖哪些私人/公司对话、历史读取范围、排除项、持续读取与撤销方式。当前“辅助回复”不足以推断该选择。
