# Design Review: feat-554

## Round 1

### Metadata

- reviewer: `/root/design_review`
- review_mode: `full`
- mode_reason: 首轮独立审查；完整检查现状、设计决策、首文档全部约束、8 份 delta-spec、原型、runbook 和 M1，并从实际组装入口追生产调用链。
- started_at: `2026-09-13T01:52:13+08:00`
- completed_at: `2026-09-13T01:57:00+08:00`
- duration: `4m 47s`
- baseline: `main`，设计声明基线 `eb4da2815`；工作区有大量既有 dirty/untracked 内容，仅本报告由 reviewer 写入。没有启动真实产品服务，没有将原型视为后端实现证据。

### Verdict

Issues Found — **2 CRITICAL / 1 WARNING**。

聊天成员读取、个人管理归属、登录可读完整 Work 三条规则能够成立；复用现有 IM、Gateway 和轨迹存储的方向合理。进入实施前须补齐 Gateway 实际使用的 HTTP/WS 数据边界，并解决普通聊天上传仍生成公开地址的问题。原型批准状态也需与本轮新定的确认语义一致。

### Issues

- **[R1-C1][CRITICAL] [设计“消息与卡片路由”“建议接口与数据承接”，design.md:95、121、132] “沿用既有受信任入口”不足以承接真实 Gateway HTTP 路径，成员切换会破坏跨账号图片和 shadow。** 生产组装 `src/personal_assistant/gateway/composition.py:661-693` 将同一个真人 IM token provider 交给 shadow 同步及图片下载；`shadow_sync.py:205-224` 向普通 messages POST 代记外部用户身份，`:465-471` 向同一入口写 `sender.type=agent`；`reply_images.py:319-348` 以管理者 Bearer 上传 Agent 图片，`image_attachments.py:135-145` 也以该 Bearer 下载附件。IM 的普通消息、shadow terminal 和 images 入口仅依赖 `current_user`，不存在设计暗示的独立 Gateway HTTP 主体（`src/IM/api/routes/messages.py:428-448、521-532`，`message_images.py:46-64、96-105`）。此外，实际 WS 配置边界仍要求 `conversation.owner_id == gateway owner`（`src/IM/infra/repositories/config_boundaries.py:49-56`），仅改变用户流收件人不会修好它。**不改的后果：** B 与 A 的 Agent 私聊时，A 的 Gateway 上传/读取图片被成员校验拒绝；把普通 POST sender 一律改为 token 本人又会把 shadow Agent 回复改成人或拒绝，保留任意 sender 则允许群成员冒充；C 的 Agent 在 A 建的群上报配置边界仍失败。请明确浏览器与 Gateway 对消息、shadow、图片读写、配置边界等入口的调用身份与授权依据、真实生产落点及协议增量；Gateway 操作依据应能证明 node/Agent/聊天关系，不能通过把管理者加入别人的聊天或放开浏览器原聊天 GET 来补救。不要求新增通用权限引擎，也不要求某一种具体实现。

- **[R1-C2][CRITICAL] [决策 1 / 图片 delta / 既有功能承接，design.md:47、64、121、163] 只改受保护 Agent 图片遗漏了正在使用的普通聊天上传链。** 从实际 composer 的 `src/IM/frontend/src/features/chat/components/message-pane.tsx:697` 到 `attachments/use-attachment-upload.ts:25-35`，浏览器上传仍走无 conversation_id 的 `/im/v1/uploads`。该路由返回 `/im/uploads/<随机文件名>`（`src/IM/api/routes/messages.py:391-419`），`src/IM/app.py:446-448` 用未鉴权 StaticFiles 公开返回字节。unit 只有“Agent 新托管图片”的 MODIFIED，且保留不迁移旧公开附件的例外；没有决定升级后普通新上传如何归属于聊天、如何读取。**不改的后果：** 新群中刚上传的文件/图片一旦地址出现在完整 Work，非成员可直接取得原附件，与 spec Q8 的“聊天附件…按成员关系可见”（spec.md:59）及“未加入的群不可读取”（:171-173）相抵；换掉 `message_images` 的 owner 检查无法覆盖这个真实入口。请补齐本次新增普通上传的成员归属/读取方案、前端及 Gateway 消费闭合与最窄 delta；明确旧公开附件的承接边界，不能把“旧公开上传不追溯”默认为升级后继续产生公开聊天附件。这里不要求隐藏 Work 中已记录的正文或图像数据。

- **[R1-W1][WARNING] [原型对齐契约“批准卡操作和处理结果”，design.md:99-101、183] must-match 原型仍把提交等同生效，并拒绝离线提交。** 设计和 `specs/im/gateway-relay.md` 已拍定持久 `submitted`、确认后 `resolved`、节点离线可提交等待确认；但 `prototype.html:217` 中任意 `perm` 都显示“已处理”，`:233` 的 approve 分支在线立即设置 `perm`，离线直接提示“暂时无法提交决定”。**不改的后果：** 前端 worker/产品验收同时面对相反的 must-match 状态，可能继续使用“HTTP 接收即已处理”的反馈，无法辨认真正尚未确认的操作。更新示例状态及中英文反馈即可，不要求原型执行真实工具或模拟完整传输可靠性。

### Recommendations

- **[R1-R1]** 把 `design.md:89` 的“创建者不可被移除，沿用当前群治理约束”改成明确的本次补齐规则或准确说明现状。路由 `web_im.py:580-598`、service `web_im_service.py:187-199`、repo `conversations.py:588-613` 均无 creator 保护；UI `group-settings.tsx:234` 目前只允许移除 Agent，并非服务端已实施该约束。目标规则本身已明确，因此未单独升级成阻断项。
- **[R1-R2]** 将 `specs/gateway/routing-delivery.md:14` 的 `global-agent.md` 链接改为可解析的 canonical 路径；unit 内不存在该文件。链接不会改变已经明确的 global 模式决策。
- **[R1-R3]** 迁移审计中说明真人 owner/creator 校验只适用于需要承接真人可见性的记录；已知的 Agent-Agent creator 或随机旧 owner 不必强行对应真人。`design.md:131` 的概括与 `specs/im/conversations-messages.md:91-95` 保留此类旧关系的细则应读起来一致；以已明确的细则执行可避免自动补入新的真人。

### Coverage

以下行号均为本轮送审快照；`D` 表示 design.md，`S` 表示 spec.md，`Δ` 表示 unit 的 specs 目录。核实方式为只读静态追踪、canonical 原条目比对、原型状态/动作阅读和运行手册命令对照。没有用作者报告的浏览器或模型通过结果替代本轮设计判断。

审查 inventory 包含：现状表全部 9 条与跨包约束、补充的实际依赖与 UX 前提；编号决策 1–2 和补充章节全部有架构意义的决定；首文档 8 项 Requirement、18 项验收 Scenario、6 段用户场景、Q1–Q8、范围/非目标；8 份 delta 的全部 20 个 ADDED/MODIFIED/REMOVED 条目；唯一 M1、原型契约及 runbook。

### 核实台账：现状断言与生产落点

| 原子 | 本轮核实动作及证据 | 结论 |
|---|---|---|
| C01 账号与设备/Agent 归属（D15） | 从 `IM.app:449-458` 的正式路由注册到 `api/deps.py:52-76` 仓库；`infra/db.py:55-99` 的 profile/node owner 字段、`repositories/users.py:73-87` 的真人 owner=user id；`agents.py:451、553` 保留 owner profile 查询 | 成立；一人多 node 无需组织模型 |
| C02 多方成员已有稳定存储（D16） | `infra/db.py:125-131` 复合主键；`conversations.py:89-99、618-650、775-795` 解析稳定 user/agent Actor | 成立；不能把 prototype 的 human kind 直接作为 API Actor |
| C03 聊天 HTTP 现为 owner 范围（D17） | 正式 `app.py:454-456` → `web_im.py:195-208、424-434、497-508` → `deps.py:94-105` → `conversations.py:472-495`；messages/image GET 分别在 `messages.py:595-604`、`message_images.py:19-25、105` | 成立；原型不是另一套生产路径 |
| C04 用户实时流按成员、注释称 owner（D18） | `app.py:319-336、507-530` → `user_stream.py:189-203、275-301` → `events.py:220-226、268-291`；实时队列当下冻结收件人，D91 要求发送时复核正是必要增量 | 成立；owner 文档/注释与成员 SQL drift 已识别 |
| C05 跨 Gateway 群 relay 已存在（D19） | `messages.py:483-507` → `web_im_service.py:636-645` 传真实 group type → `relay_service.py:284-296` 每 Agent 取 node；每节点独立 push | 成立，不需新调度服务 |
| C06 Agent 查询已有成员范围（D20） | `app.py:378-392` → `ws/gateway/runtime.py:162-176` → `application/work_conversations.py:48-65、151-172`；node、root session、成员快照和后续页当前关系均检查 | 成立，Work GET 公开无需改变 Inbox/Agent 读取 |
| C07 全局 Work GET 现按 owner（D21） | `app.py:452` → `agent_work.py:13-18、22-85`；`AgentWorkRepository.session:52-61`、items `:393-414`、turns `:416-477` 约束 root/session；数据非 mock | 成立；全局模式门槛是本次需补的目标校验，不能只删共享 helper 的 owner |
| C08 pin/mute/unread 现为共享字段（D22） | `db.py:35-53`；`conversations.py:419-454` 共享 PATCH；`messages.py:393-409、480-488、1052-1055` 共享计数/已读/占位回滚 | 成立；放到 participant 能自然表达个人状态 |
| C09 建群与聊天 UI 可复用（D23） | `frontend/src/app/router.tsx:11-13、40-67`、`chat-workspace-page.tsx:1324-1330` 生产挂载；`new-group-modal.tsx:15-21、84-85` 当前只收 AgentRow | 成立；新人类选择须加入当前界面数据源 |
| C10 IM 不执行内核、Gateway 只经 SDK（D25） | `SPEC.md:85、93-99、117-120`；实际 IM app 只组装 IM 仓库与 WS 服务，Gateway composition 持有 kernel 并交 IMConnectionManager | 成立；方案没有新增反向 import |
| C11 公开资料与完整配置应分开（D79-81） | `users.py:41-43` 内部 select 含 password_hash；`agents.py:258-275、553` 现配置返回/owner校验；D117-118 改用显式最小字段 | 成立；目录是有必要的输出投影，不是复制权限系统 |
| C12 卡片原节点推断有歧义（D99） | `messages.py:677-699` 空 content 解析；`relay_service.py:411-412` 选首个 Agent；`EventBridge:409-444` 已存 request；正式 `app.py:348-358` 组装到 GatewayExecution | 成立；修到原请求的真实目标是必要的 |
| C13 决定现投递通道可复用（D99-101） | `ws/gateway/control.py:85-120` 发送 response；Gateway `composition.py:282、1193` → `ws/im_connection.py:180-201、1537-1545` → kernel.submit_permission_decision；不是过时注释所说独立 HTTP 内核 | 成立；持久 submitted/retry 是明确的新职责，不能误认为已有内存发送可靠 |
| C14 Gateway 已有独立受信任 HTTP 入口（D95/132 的隐含前提） | `composition.py:661-693` → shadow/reply_images/image_attachments 的同一真人 token → IM 的 current_user HTTP 入口；另 config boundary 还校验 conversation owner | 不成立，R1-C1 |
| C15 受保护图片代表全部聊天上传（D47/64/121 的覆盖前提） | composer → `use-attachment-upload.ts:25-35` → `messages.py:391-419` → `app.py:446-448`；普通新上传仍是公开 StaticFiles | 不完整，R1-C2 |
| C16 现有 Work 实时依赖用户事件（D107） | `agent-work-panel.tsx:84-98` 主/子 infinite query 与 `agent.work.updated` 失效；`ws/gateway/work.py` 使用 owner 用户事件；没有给所有用户广播 node 配置的现有必要性 | 成立；可见页轮询覆盖新非 owner 读者 |
| C17 现有语言与导航（D161/169） | `i18n/index.ts:7-20、41-46`，`app/shell/user-menu.tsx:60-63`，`features/me/me-page.tsx:3、41、132-146`；原型有独立语言字典和持久键 | 成立，产品沿用 im_lang，原型不得覆盖产品偏好 |
| C18 创建者不可移除现状（D89） | route/service/repo 删除链没有 creator 检查，UI removable 只看 Agent（见 R1-R1） | 目标明确，现状措辞需校正 |

### 核实台账：全部设计决定与接口闭合

| 原子 | 四问结果与证据 |
|---|---|
| D01 编号决策 1，聊天成员 / Work 登录（D43-50） | 已拍定；Q8（S57-59）直接驱动，不与配置 owner 冲突；原聊天 GET 继续校验与 Work 原记录不遮盖可并存。Gateway/附件完整路径欠缺见 C1/C2。 |
| D02 编号决策 2，个人列表（D52-56） | 已拍定；S81“只…自己参与”覆盖；发现目录与聊天历史分开，无“全部聊天”入口或组织切换。 |
| D03 联系人目录和公开资料（D77-81、117-118） | 最小字段/搜索/分页/Actor 身份明确，有 Q4 与 S87-94 驱动；仅复用 UserRepository/WebIMService，小查询没有假想多态层。 |
| D04 direct/group/fork 与 creator（D87） | 群显式 type，direct_key 对联系人普通私聊唯一，fork/旧会话不合并；`conversations.py:111-120` 当前靠人数与第一参与者，目标差异明确，Δ修改并发 Scenario 避免新旧冲突。 |
| D05 群治理/成员生命周期（D89-91） | 哪些人可加谁、删除谁、谁解散、历史加入/退出规则均已拍定；成员变更失效提示仅 ID、重连 sync 以及 live/replay 当前成员依据闭合，不扩出角色表。creator 旧行为表述见 R1-R1。 |
| D06 用户个人偏好与已读（D85、122-123、128） | participant 保存个人状态；首次消息/占位与回滚、显式 read 边界、并发新消息、个人响应不群播写明；S202 授权设计确定个人状态，无不必要第二套消息存储。 |
| D07 消息真实身份/跨节点/纯人会话（D95-97） | sender/token、Agent/node、无 Agent 不 relay 的目标明确，实际 `relay_service.py:273-282` 有 fallback 待去除；跨包已有路由可复用。Gateway 与 browser 共用 HTTP 的关键分界尚未拍定，C1。 |
| D08 批准绑定/幂等/迟到确认（D99-101） | 绑定 conversation/message/request/agent/node/run，pending→submitted→resolved，持久重试同一 request，所有真人成员全选项可用；S153-161 驱动，不新增人员授权。原型状态矛盾 W1。 |
| D09 Work GET 与轮询（D103-109） | root/session 验证保留、只全局、只登录读；3 秒可见轮询/隐藏暂停/重返刷新及失败反馈明确；S175-184 与当前主子轨迹存储吻合。 |
| D10 HTTP 响应与管理接口（D113-126） | 401/404/400/403 定义、配置保持 owner、联系人独立公开、read 新接口方向清楚；不把 server 授权交给 owner_id 客户端字段；Gateway 的真实消费者缺口 C1。 |
| D11 数据承接与回退（D129-133） | ID/历史/管理归属保留，原 owner 个性状态映射、其他成员初始化、旧 direct_key 不猜、备份副本审计与配套旧版本 DB 回退均拍定；无双写长期兼容层；已知 Agent-only 关系需按细则理解（R1-R3）。 |
| D12 现有能力及中英文（D159-163） | user 明示原功能保留；current spec 为回归基准，原型未绘制不等于删除；新增字符串入既有资源，语言切换不翻译输入/原记录、不清空草稿，无另造 i18n。 |

### 核实台账：首文档 Requirements 与全部验收 Scenario

| Requirement 原子 | 约束原句 / 设计对应 |
|---|---|
| S-R1 无 Gateway 联系人（S85） | “无需 Gateway 即可注册登录并查找联系人”；D79、117-118 沿用注册并加目录。 |
| S-R2 跨账号人际私聊（S96） | “跨账号私聊并持久回看”；D87、95-97、119-121 和个人流复用。 |
| S-R3 一人多 Gateway（S104） | “管理多个 Gateway 及其 Agent”；D68、79、125 保留管理归属，不加一人一机约束。 |
| S-R4 他人 Agent 私聊（S120） | “直接私聊其他人管理的 Agent”；D79、87、97 明确可用，HTTP资源路径 C1 待补。 |
| S-R5 混合群（S128） | “多人与不同 Gateway 上的 Agent”；D89、95-97 每 Agent 真实路由，C1 配置边界路径须补。 |
| S-R6 分模式批准（S146） | “不新增人员权限配置”；D99-101 全选项与幂等绑定。 |
| S-R7 私聊/群隔离与完整 Work（S163） | “聊天按成员可见，全局…详情完整可见”；D45-50、105-109；普通新上传范围 C2 不闭合。 |
| S-R8 既有数据和能力（S186） | “升级后保留”；D129-133、159-163；shadow/图片保持需解决 C1。 |

| Scenario 原子（S 行号） | 核实覆盖 / 可观察结果 |
|---|---|
| S01 无设备用户开始沟通（87） | D79、117；联系人可辨真人/Agent，注册无 Gateway 前置；prototype 小李资料/新聊天。 |
| S02 没有匹配联系人（92） | D117 名称/ID 查询与原型空态；不创建错误对象。 |
| S03 两账号实时沟通（98） | D87 稳定 direct_key、D95 token sender、D65/91 成员流与 sync；同一会话持久历史。 |
| S04 同一人绑两设备（106） | D125/174 沿用 node owner 与设备列表；runbook A1/A2 同账号。 |
| S05 非管理者不能写配置（110） | D68、79、125 owner 接口保留，公开资料不含完整配置。 |
| S06 单设备离线（115） | D97 每 Agent node 独立、D107 状态更新、runbook C1 重启；不伪造完成。 |
| S07 跨归属 Agent 交办（122） | D79、87、97；文本主链可成立，图片/配置边界执行 C1。 |
| S08 建混合项目群（130） | D87 显式 group、89 加真人和自有 Agent；prototype 选择器按当前 owner 筛 Agent。 |
| S09 不同成员共同交办（135） | D95-97 真实 sender、既有 relay/触发；正式回复广播当前成员。 |
| S10 改群名和成员（141） | D89-91 权限、加入前历史、退出后停止、当前连接失效和恢复均明确。 |
| S11 全局不弹批准卡（148） | D101 global 无卡，D206 不重做 global 工作机制；原型 Atlas/Iris 无工具批准卡。 |
| S12 非 owner 处理单 Thread 卡（153） | D99-101 全选项均可用，配置权不扩大；prototype 共享 request 示例，W1 状态差异待校正。 |
| S13 多人处理一张卡（159） | D99 同记录原子 pending→submitted，后续不覆盖，D101 同 request 重试；不重复执行。 |
| S14 未参与者不能读私聊（165） | D47/49 成员 GET 和 protected images；Work 不扩大原聊天读取；C1 机器使用与人查看要拆清。 |
| S15 未加入群不能读历史/实时/附件（171） | D47、91 覆盖历史/事件；普通新上传公开地址遗漏 C2。 |
| S16 Work 完整查看（175） | D48、66、105-107 主/子/root及轮询；明确不遮盖已记录的他聊内容。 |
| S17 Work 链接不授予聊天访问（181） | D49、109 独立成员检查，不代理附件；新普通上传字节旁路 C2。 |
| S18 老用户继续使用（188） | D129-133 保 ID/消息/成员/管理归属，D159-163 current回归；runbook 数据副本演练不连生产。 |

### 核实台账：用户场景、澄清、范围与非目标

| 原子 | 本轮逐条核实 |
|---|---|
| 场景 1 无机器也能成为同事（S71） | D79 目录和既有 auth；没有绑设备 gating，prototype li 无设备还能聊天/建群。 |
| 场景 2 多机器、多管理者和离线（S73） | D68、97、125；runbook 明确 A 两个/C一个/B零个；原型设备信息只是样例，不能证明路由。 |
| 场景 3 跨 owner Agent 私聊（S75） | D47、79、87、105 一致；C1 为实际响应能力闭合缺口。 |
| 场景 4 项目群共同做事（S77） | D89 群治理和 D97 触发/分发覆盖，没有要求配置组织或一套新协作工作机制。 |
| 场景 5 分模式批准（S79） | D99-101 原请求唯一决定及全选项符合；W1 仅原型表现不一致。 |
| 场景 6 聊天私有、Work 完整（S81） | D45-50、105-109 明确例外，C2 为附件实施覆盖缺口。 |
| Q1 简单起步、不确认团队资产 | D25、81、207 没有引入团队所有权/角色体系。 |
| Q2 一个人多机、Agent 随 Gateway 管理 | D68、79、89、125 保持配置 owner；人可无 Gateway，Agent 由管理者入群。 |
| Q3 global 无卡 / single thread 人人可按 | D101 包含长期允许选项，不将配置 owner 套入卡片；D99 首个有效决定是满足不重复执行的设计选择。 |
| Q4 其他用户可直接私聊 Agent | D79/87 无好友申请、无逐人授权，公开目录不开放旧聊天。 |
| Q5 聊天按参与关系、机主本地数据非承诺范围 | D47、49 聊天入口成员规则；没有提出本地模型记忆隔离。C1 必须闭合服务调用而非恢复管理者聊天特权。 |
| Q6 范围收口 | D77-133、M1 从账号/联系人到群/Work/迁移全覆盖，不添加独立任务看板。 |
| Q7 错误“全部聊天公开”已撤回 | D45、54 显式撤回，全局列表未引入。 |
| Q8 全局 Work 完整，原聊天和附件按成员 | D45-50、105-109 不遮盖 Work；新普通上传缺口 C2。 |
| 在范围（S196） | 8 requirement 与 18 Scenario 均有落点；当前不能闭合的具体生产路径只计 C1/C2。 |
| 非目标（S197） | 没有组织部门/团队资产/角色表/逐人授权/任务看板；SQLite participant 承接使用权未变成权限引擎。 |
| 不引入来源过滤、模型记忆隔离、全部聊天（S198） | Work 完整记录原样投影；不增加来源权限追踪，不替用户扩大机主隔离承诺。 |

### 核实台账：全部 delta-spec 条目

所有 MODIFIED 标题都确实存在于指定 canonical 文件；本轮逐一比较旧 Scenario 标题集合，没有发现 MODIFIED 静默遗漏旧 Scenario。REMOVED 标题也全部存在，替代条目承接原情形并显式改变访问规则。THEN 主要描述 API 消费者可观察响应或用户结果；沿用的 Gateway 未知 Agent LookupError 属于已有调用者可观察错误，不误报为内部实现断言。

| delta 原子 | canonical 锚与核实结果 |
|---|---|
| Δ01 IM auth REMOVED owner 全隔离 | `docs/specs/im/auth-tenancy.md:30-50` 原标题准确；被 Δ02 替换，不并存矛盾。 |
| Δ02 IM auth ADDED 登录/成员/管理归属 | 旧 4 情形分别承接无 token、token 身份、原跨租非成员拒绝、metrics；新增同群跨账号；与 D113-126 对齐。 |
| Δ03 IM agents REMOVED owner 用户流 | canonical `agents-nodes.md:334-363` 标题精确；5 个旧情形由 Δ04 承接。 |
| Δ04 IM agents ADDED 成员用户流 | token/resume/sync/断网/切账号均保留并换成员语义；与 `events.py:268-291` 和 D91 对齐。 |
| Δ05 IM agents ADDED 联系人与管理分开 | 真正新增目录，配置 existing owner 接口仍在；包含无 Gateway、多 Gateway、离线，不误把配置整体公开。 |
| Δ06 IM conversations REMOVED Agent 私聊 owner 可读 | canonical `conversations-messages.md:61-74` 精确；由 Δ10 改写明确撤回 owner 特权。 |
| Δ07 IM conversations REMOVED owner 群治理 | canonical `conversations-messages.md:255-294` 精确；由 Δ11 承接全部 8 种原情形。 |
| Δ08 IM conversations MODIFIED 托管 Agent 图片 | canonical `:14-29` 同名，3 Scenario 完整；owner→成员符合 Q8；普通浏览器新上传不在本条，缺口 C2。 |
| Δ09 IM conversations MODIFIED 消息字段/分页 | canonical `:31-59` 同名，原 6 Scenario 保留；并发改为普通 direct 唯一、群/fork 独立，新增 sender 防冒充/纯人/显式 group；C1 需补具体 Gateway 例外协议。 |
| Δ10 IM conversations ADDED Agent 私聊不授予 owner 可见 | 原投递回执、随机归属旧私聊两情形保留并改变访问语义；旧可见会话由迁移承接，不自动给新聊天加 owner。 |
| Δ11 IM conversations ADDED 成员群治理 | 原 8 Scenario 的增/重/空/404/改名/Actor/移除/解散都在；增加跨账号及移除后 UI收敛；未静默删原治理功能。 |
| Δ12 IM conversations ADDED 个人偏好和已读 | 现无同名个人状态条目；D128 的独立 pin/mute、消息 read 边界及迁移均有可观察 Scenario。 |
| Δ13 IM work MODIFIED 聊天/全局轨迹分开 | canonical `agent-work.md:12-26` 原 3 Scenario 均在，追加完整内容/原聊天权限、非 owner 更新；执行明细原 requirement `:28-50` 继续保留。 |
| Δ14 IM relay REMOVED owner 配置边界流 | canonical `gateway-relay.md:51-65` 同名；由 Δ17 取代，事件仍不含完整配置。 |
| Δ15 IM relay MODIFIED 工具授权随消息 | canonical `gateway-relay.md:198-210` 原 2 Scenario 保留，增加多人卡、幂等/离线、global无卡；D99-101 目标明确，原型 W1。 |
| Δ16 IM relay MODIFIED relay/流式幂等 | canonical `gateway-relay.md:67-85` 原 3 Scenario 保留，global Inbox completed含义保留；新增多节点独立投递，与真实 `messages.py:489-507` 对应。 |
| Δ17 IM relay ADDED 成员配置边界流 | 原在线和重连两情形完整承接；仅浏览器收件变化，真实 Gateway boundary 入站 owner 假设须一并处理（C1）。 |
| Δ18 IM UX ADDED 导航/i18n承接 | 没有替换现有交互 requirement；两新增 Scenario明确在协作入口沿用导航和语言、保留消息附件能力；D161 和真实 i18n入口一致。 |
| Δ19 Gateway routing MODIFIED 四步路由 | canonical `gateway/routing-delivery.md` 同名，原 8 Scenario 全部保留；新增跨账号同群真实输入；relative global-agent 链接 R1-R2。 |
| Δ20 Gateway relay MODIFIED 授权标识 | canonical `gateway/relay-protocol.md` 同名，旧允许/拒绝两个 Scenario保留，增加原请求幂等返回；消费者仍是 IM/用户，无跨包内部符号断言。 |

### 核实台账：M1、原型和运行前置

| 原子 | 本轮核实动作及结论 |
|---|---|
| M1 单垂直交付（D195-199） | 唯一 M1 覆盖用户进入→联系人→聊天/群→Agent执行→Work/批准→旧数据，没有横切前后端 milestones；不存在并行范围相撞；`.gitkeep` 空骨架符合设计期职责。 |
| M1 退出标准两轨 | reviewer R1–R6 + S 全18 Scenario；worker W1–W4 具体含权限分界、正确执行、build、三账号多node、迁移和语言回归；不是只有类型定义/单测步骤。C1/C2修订后需投影对应端到端验收。 |
| 原型 R1 联系人、R2群、R3消息 | 静态读 `prototype.html:202、214-218、226-233`：假身份/数据可解释多人、跨node和空结果；D155、188明确不是产品结果。 |
| 原型 R4 批准 | 共享 perm 跨身份可见，但在 `:217、233` 与 submitted/confirmed 新规则冲突，W1。 |
| 原型 R5 Work/原聊天 | `:223-224、227、233` 主/子展示完整记录，source 点击独立检查成员；不新增来源遮盖。 |
| 原型 R6 配置和设备 | `:220-225` 非 owner没有写配置入口，三身份分别2/0/1台；不存在团队/角色设置。 |
| 原型语言、may-adapt/out-of-scope | `:29-199、209-213、233` 独立 lang持久、t词典、切换saveDraft；原文不翻译；附件/注册/绑机未执行明确标示，D159禁止据此删除产品能力。 |
| Runbook 组装/模型/隔离 | 比对 `config/e2e/gateway.yaml:18-38、47-57` 两Agent/web channel/本机代理；`scripts/e2e-up.sh:184-225、252-258、375-382` 重写node/workspace、主IM路径和导出端口；额外 A2/C1 独立 cwd、node、workspace、同隔离 IM。没有启动生产。 |
| Runbook 重启与清理 | `--main-config` 是实际脚本选项；主栈e2e-down，额外PID显式kill/wait；说明e2e-up重置DB、保DB重启保持JWT和cwd；前端构建/真实模型/浏览器不同context/双模式要求具备。 |
| Runbook 迁移 | 独立旧DB与备份、副本、ID/成员/图片/Work/历史对比，失败清理明确；不要求 reviewer直读生产DB；Agent-only审计解释建议见R1-R3。 |
| 整体可读性/一致性 | 两个编号决策与关系图可解释核心读取规则，补充节提供worker边界；标题/对齐/branch/空Changelog/引用齐全。没有将未实现前端或静态prototype宣称成真实多人IM。 |

### 架构进攻

| 角度 | 攻击对象与实际核实 | 结论 / 长远代价 |
|---|---|---|
| 一·归属 | 成员查询与个人状态放 IM会话仓库；人/Agent公开目录放IM；node到执行路由与原权限broker留Gateway；Work存储原位；从 `IM.app.py`、deps、Gateway composition 追组装 | 分层方向合理，无 IM→kernel 或 Gateway→IM import。**C1**：若把“真人成员”和“机器为Agent服务”混作同一入口判断，未来每种图片/通知/边界都会反复补 owner特例，既破坏协作又复发越权；应在本轮明确现有双消费者边界。 |
| 二·该不该存在 | 删除新公开资料投影会迫使目录直接暴露含配置/密码字段的数据，不能删；删除 participant个人状态会共享用户偏好，不能删；删除direct_key唯一约束会并发造多份普通私聊；没有抽象工厂/策略引擎 | 新增数据和薄投影有当前场景依据。持久批准状态服务一次有效决定及可靠确认，有实际产品需求；不需为未来组织/权限做接缝。 |
| 三·深还是浅 | 仓库成员查询统一聊天/图片检查，既有 EventRepository/replay、RelayService每Agent路由、AgentWorkRepository主子结构和i18n复用；公开资料仅一个窄响应形态 | 没有发现必须拆新服务才能更简洁的点；“复用”必须覆盖当前生产消费者。**C1/C2**的漏链不能通过再造一套旁路聊天/文件系统解决，否则两套HTTP/WS行为会持续分叉。 |
| 四·治本还是补丁 | 个人状态从共享字段迁移、普通direct唯一、原批准目标绑定都修事实归属；Work仅开GET而不加遮盖；检查普通上传StaticFiles及Gateway owner校验 | 主要设计治本。**C2**：仅在Work按钮或图片组件隐藏链接会留下可直接请求的公开字节，持有地址仍可读；必须明确资源归属/服务读取边界，不能用前端隐藏替代。原型W1要改状态，不增加传输模拟框架。 |

本轮未发现要求增加组织权限管理、过滤 Work 或重写 Agent 工作机制的理由。请作者修订 C1/C2，并使 W1 的原型与目标状态一致后交回同一 reviewer 复审；复审深度由实际 delta 决定。

### Author Resolutions

以下为作者对 R1 的修订记录，不改变上方审查原文或结论。

| Finding | 处理 | 修订与验证 |
|---|---|---|
| R1-C1 | 接受 | design.md 明确 Gateway HTTP 的现有真人 token 缺口，新增绑定当前 WS 注册连接的内存运行凭据，收口 messages、shadow、附件读写的机器调用范围；浏览器仍按真人身份和成员关系操作，管理接口仍按 owner。配置边界写入改为受信任 node、Agent 归属、Agent 成员及消息锚校验。IM auth／relay 和 Gateway relay delta 同步，runbook 增加跨 owner 图片输入输出、配置边界、重连失效及 shadow 验证。凭据不是持久角色体系，也不把管理者加进别人的聊天。 |
| R1-C2 | 接受 | design.md 与 conversations-messages delta 将普通文件纳入现有资源快照和会话关联存储：上传指定 conversation_id，浏览器及 Gateway 通过鉴权读取，fork／再引用不能只凭 URL 获得资源。旧 IM 公开上传按已有消息引用建立关联，旧地址改为成员鉴权别名，撤回“不迁移旧公开附件”例外；无关联旧文件保留但不公开读取。runbook 加入新旧图片／文件、原始 URL、Work 链接、fork 及 DB＋存储目录迁移回退验证。 |
| R1-W1 | 接受 | prototype.html 将提交与确认分开；离线可提交并等待，恢复在线后模拟节点确认再标记已处理，保留原处理人和决定。中英文状态均补齐。实际浏览器验证了离线提交、跨身份同一决定、英文等待状态、恢复确认及在线长期允许两阶段反馈；原型脚本语法通过。 |
| R1-R1 | 接受 | 群创建者不可被移除改写为本次补齐的服务端规则，明确当前 UI 只删除 Agent、现有服务端尚无此保护。 |
| R1-R2 | 接受 | routing-delivery delta 的 global-agent 链接改为 canonical 相对路径；本 unit Markdown 链接检查通过。 |
| R1-R3 | 接受 | design.md 与 runbook 的旧数据审计区分需承接真人可见性的记录、Agent-only 会话和随机旧 owner；不把后两类强行映射或补入真人。 |

本次同步检查了所有 MODIFIED／REMOVED requirement 的 canonical 标题锚及 ADDED 标题无重复，均通过。全仓 docs-check 仍受两处既有研究索引链接影响；本 unit 链接无新增失败。上述均为设计／原型验证，尚未执行真实多人 IM 实现或迁移。

## Round 2

### Metadata

- reviewer: /root/design_review
- review_mode: full
- mode_reason: R1 修订新增了 WS 注册连接绑定的 HTTP 机器身份，并把普通新旧上传纳入受保护资源；这改变跨包共享接口、鉴权和迁移边界，不能仅核对旧 finding 的文字关闭。
- started_at: 2026-09-13T02:11:08+08:00
- completed_at: 2026-09-13T02:20:21+08:00
- duration: 9m13s

### Verdict

Issues Found — 0 CRITICAL / 1 WARNING

R1 的六项意见均有实质修订；新增的运行凭据和统一附件方案方向成立。本轮只发现一处会阻断实际 shadow 镜像的调用身份衔接，R2-W1 修订前不建议进入实施。未发现需要增加角色、组织权限、Work 遮盖或重写 Agent 机制的理由。

### 历史问题闭环

| 历史项 | Author Resolution | 本轮独立核实 | 状态 |
|---|---|---|---|
| R1-C1 | 接受；补机器 HTTP 主体和配置边界校验 | design.md:106–123 明确当前注册连接凭据、限定数据入口、Agent/node/成员检查和浏览器本人发言；IM/Gateway relay delta 同步。重新追 composition、shadow、图片消费者和 GatewaySessions。原先把真人 JWT 当成机器身份的缺口已正面解决；shadow 的身份前置还需 R2-W1。 | closed；新衔接问题单列 |
| R1-C2 | 接受；普通新旧上传按会话保护 | design.md:125–134 覆盖普通上传、鉴权 fetch、合法关联/fork、旧公开 URL 别名、孤立文件、存储备份回退；conversations-messages delta:165 起承接可观察结果，明确撤回 canonical 旧公开文件例外。 | closed |
| R1-W1 | 接受；原型区分提交和确认 | prototype.html:218–220、236：点击先写 submitted，确认模拟器仅在线时延迟变 resolved；离线可提交、恢复在线再确认，状态和处理人跨身份共享，新增等待文案有英文。原型仍明确不证明真实执行。 | closed |
| R1-R1 | 接受；创建者保护改为新增规则 | design.md:92 明确当前 UI 只移除 Agent、服务端无 creator 保护，并把新目标与现状分开；与 conversations.py:588 起和现有 GroupSettings 对应。 | closed |
| R1-R2 | 接受；修 canonical 链接 | routing-delivery delta 的 global-agent 链接解析到 docs/specs/gateway/global-agent.md，保留原四步路由的八个 Scenario。 | closed |
| R1-R3 | 接受；分类旧 Agent-only/随机 owner | design.md:164 和 runbook 迁移段明确保留实际 Agent 成员及旧身份，不强制映射或补入真人；仍仅对已有真人访问权做可证明承接。 | closed |

### Issues

- **[R2-W1][WARNING] 人与 Gateway 的调用身份 / design.md:112：shadow 的身份查询也在被整体替换的同一个 client 上，新凭据不能完成它的前置。** 当前正式 wiring 在 personal_assistant/gateway/composition.py:672–689 创建带 durable saga 的 IMShadowConversationSync；shadow_sync.py:133–151 用同一 token 和 HTTP client 先执行身份查询，:600 请求 /im/v1/me，:622 请求 /im/v1/nodes，:163–168 再以认证得到的 owner 恢复旧 saga。设计给 shadow_sync 注入运行凭据，却在 :111 明确禁止它访问账号/管理入口；仅写“登录、绑定和个人配置客户端仍用 owner JWT”没有覆盖这个混合消费者。现有 node.register ACK 只有 node_id（IM/ws/gateway/sessions.py:380–383），新设计也只新增 token，不能假定已返回替代身份事实。**不改的坏事：** 按当前文字直接替换 provider 后，每次启动或 token 变化的镜像都会在写消息前被拒，durable 重试也会重复同一失败；worker 若为了恢复功能自行放开机器 token 的 /me、/nodes 或直接信任本地 owner，又会改变刚确定的身份边界。请明确 shadow 的受信任身份来源及其 client/provider 与机器数据请求的分工，保持旧 owner 恢复校验；保留独立 owner JWT 身份查询是足够小的解法，不需扩大机器凭据范围。

### Recommendations

无新增建议。不要为本项引入身份服务、人员角色或通用 token 策略框架。

### Coverage

本轮完整读取当前 spec、design、八份 delta、prototype、runbook、R1 和 Author Resolutions；重新枚举全部承重原子。HEAD 仍为 eb4da2815，正式源代码未随本次文档修订变化。本轮核实沿正式 app/deps/路由和 Gateway composition 追踪，结合自己在 R1 已读取且仍相同的实现；未把原型操作或作者模型探针当作产品实现证据。

完整 inventory：现状表 12 条、跨包红线及补充 UX/依赖前提；编号决策 1–2 和全部补充设计决定；spec 的 8 个 Requirement、18 个验收 Scenario、6 段用户场景、Q1–Q8、3 条范围/非目标；八份 delta 的全部 24 个 ADDED/MODIFIED/REMOVED 条目；唯一 M1 和全部原型对齐项、运行前置；四个架构进攻角度。下文 D 指本轮 design.md，S 指 spec.md，Δ 指本 unit specs；源文件简称按所列包路径理解。

### 核实台账：现状断言与正式调用路径

| 原子 | 实际核实和证据 | 判断 |
|---|---|---|
| C01 账号/node/profile 个人归属 | IM/app.py:449–458 正式路由→api/deps.py:52–76；infra/db.py:55–99 的 owner 字段、repositories/users.py:73–87 的真人 owner。 | 一人多节点已有数据模型，成立。 |
| C02 多方成员稳定存储 | infra/db.py:125–131 复合主键；conversations.py:89–99、618–650、775–795 解析真实 user/agent Actor。 | 可复用成员查询，human 仅目录 kind。 |
| C03 聊天 HTTP 现 owner 过滤 | app.py:454–456→web_im.py:195–208、424–434、497–508→conversations.py:472–495；messages.py:595–604、message_images.py:19–25。 | 前提成立，成员替换落在真实路径。 |
| C04 实时流/replay 当前成员 | app.py:319–336、507–530→user_stream.py:189–203、275–301→events.py:220–226、268–291；发送队列当前缓存收件人。 | D94 的发送时复核与重连 sync 是必要增量；现状注释 drift 已说明。 |
| C05 群按各 Agent node 分发 | messages.py:483–507→web_im_service.py:636–645→relay_service.py:284–296。 | 不是只有测试使用的实现；纯人 fallback 的删除边界已说明。 |
| C06 Agent 查询成员聊天 | Gateway runtime.py:162–176→work_conversations.py:48–65、151–172 的 node/root/member 查询。 | Work 公开不扩大 Agent Inbox，成立。 |
| C07 Work GET owner 门槛及主子存储 | app.py:452→agent_work.py:13–18、22–85；repositories/agent_work.py:52–61、393–477。 | GET 与写共用 helper 要区分，D138 明确只放开全局 GET。 |
| C08 共享 pin/mute/unread | infra/db.py:35–53、conversations.py:419–454 的共享字段；既有消息插入/回滚计数由消息仓库维护。 | 迁至 participant 有真实多人需求。 |
| C09 现有建群/聊天入口 | frontend app/router.tsx:40–67→chat-workspace-page.tsx:1324–1330；new-group-modal.tsx:15–21、84–85 当前接 AgentRow。 | 扩展既有选择器，不需重造聊天页。 |
| C10 HTTP 消费者共用真人 token | composition.py:659–694→shadow_sync.py:133–151、reply_images.py:326–341、image_attachments.py:136–145；IM current_user 依赖。 | D24 的新增现状断言正确；两种 token 边界合理，R2-W1 是未拆完的身份前置。 |
| C11 普通上传公开 | message-pane→use-attachment-upload.ts:25–35→messages.py:391–419→app.py:446–448 StaticFiles。 | D25 如实识别，普通新旧资源都已进入目标。 |
| C12 config boundary 额外 owner 检查 | GatewayExecution→config_boundaries.py:49–76 当前同时比对 conversation owner、profile/node 和成员。 | D26 如实识别；D121 去掉错误的 conversation owner 等式，保留锚点/Agent 约束。 |
| C13 IM/Gateway/kernel 依赖方向 | SPEC.md:85、93–99、117–120；IM app 组装 IM 仓库/WS，Gateway composition 持有 SDK kernel。 | 无新跨包 import 或 IM 执行内核。 |
| C14 公开资料需独立投影 | users.py:41–43 含 password_hash 的内部选择；agents.py:258–275、553 为完整 owner 配置。 | D82/150 的窄公开字段有必要，不公开整个配置响应。 |
| C15 原卡片目标推断不够 | messages.py:677–699 空 content→relay_service.py:411–412 的首 Agent；EventBridge:409–444 存请求。 | D102 绑定原执行是正确落点。 |
| C16 权限回送实际生产 wiring | GatewayControl:85–120；composition.py:282、1193→im_connection.py:180–201、1537–1545→kernel 提交。 | 可复用原 broker；submitted 持久重试是新增职责，非现有能力。 |
| C17 WS 注册已有节点信任锚 | sessions.py:251–274 验证 node 与 durable owner，:339–350 连接记录，:378–383 替换当前连接及 ACK；runtime 对注册连接授权。 | 运行凭据可自然绑定这个生命周期；不需要新的持久凭据资产。 |
| C18 创建者保护现状 | conversations.py:588–613 无 creator 检查；GroupSettings 只提供 Agent removal。 | D92 已校正为本次新增约束。 |
| C19 Work 更新/公开在线信息 | agent-work-panel.tsx:84–98 通过 owner 用户事件使 query 失效；node 状态事件保持个人发送。 | D140 的可见页轮询解决非 owner 更新，不需广播配置。 |
| C20 导航和语言 | i18n/index.ts:7–20、41–46；UserMenu:60–63、MePage:132–146；sidebar/new-group/work panel 的真实挂载同 C09/C19。 | D194–210 六行 UX grounding 可复用，原型独立语言键合理。 |

### 核实台账：全部设计决定

| 原子 | 四问结果、依据及边界 |
|---|---|
| D01 决策 1：聊天成员 / Work 登录 | S Q8 和“Work 链接不授予原聊天访问权”直接驱动；D48–53、129–142 分开原记录与来源资源，规则已拍定、无冲突。 |
| D02 决策 2：个人聊天列表 | S 用户场景 6“只…自己参与”；D57–59 撤回全部聊天入口，目录发现不会开放别人的聊天。 |
| D03 公开目录/配置分开 | D82–84、123、150–151 给出登录真人/非 stale Agent、稳定身份、最小字段、搜索排序分页；S 联系人 Requirement 驱动，不是新 ACL。 |
| D04 显式 group、普通 direct 唯一、fork 独立 | D90 指定 Actor、本人创建者、direct_key 唯一事务、旧数据不猜 fork；canonical 并发 Scenario 在 Δ 同步修改，不会新旧要求并存。 |
| D05 群治理与成员生命周期 | D92–94 拍定加真人/自有 Agent、改名、移除非 creator、退出/解散、历史可见、失效仅 ID、同步和发送时复核；满足 S 群变更。 |
| D06 个人状态/已读边界 | D88、161–164 的 participant 权威、单调 message 边界、重复/占位/回滚、并发消息及个人响应不共享；S 设计交接授权确定该行为，无第二套消息真相。 |
| D07 真实 sender、纯人/跨节点 | D98–100、118 分离本人发言和节点 Agent 发言，复用每 Agent relay；无 Agent 不制造兜底任务；S 无 Gateway/跨归属/离线场景均有依据。 |
| D08 卡片目标与状态 | D102–104 持久原执行身份、pending→submitted→resolved、同 request 重试及不复活终结请求；全现有选项对真人成员开放。原型已对齐，未引入长期授权人员分类。 |
| D09 两类调用凭据 | D108–123 的作用域、内存生命周期、node/Agent/成员、外部来源、同 IM 附凭据全部明确；S Q5 与跨归属图文要求驱动。混合 shadow 身份查询缺口仅 R2-W1。 |
| D10 统一聊天资源 | D127–134 明确扩展现有存储/关联，普通 uploads 带 conversation、浏览器 fetch/blob、Agent 机器身份、合法关联/fork、旧 alias 和孤立文件；支持 S 既有附件及访问边界，不另造并行文件系统。 |
| D11 Work GET 和可见页轮询 | D138–142 保留 root/session、仅全局登录读取、owner 写校验；3 秒刷新/隐藏暂停/失败重试都有调用者，S 完整且持续查看驱动。 |
| D12 HTTP 状态与接口职责 | D145–159 确定 401/404/400/403、联系人/聊天/read/config/Work 输入输出；owner_id 展示不能当授权来源；新机器接口不扩展到管理 API。 |
| D13 迁移和回退 | D132–134、161–166 保 ID/归属/历史、分类旧身份、个人状态初始化、原字节/关联、DB+目录备份和版本配套回退；无双写、未凭空为 Agent-only 加真人。 |
| D14 原功能和语言承接 | D194–198 把 current IM 和受影响现有测试作为回归基线；沿用 im_lang/en/zh，新增文案、切换不改正文/草稿；S 既有数据能力及用户中英文要求驱动。 |
| D15 原型与真验收边界 | D209–224 的 must-match/may-adapt/out-of-scope 以及实施真栈说明区分设计示意与真实模型/Gateway/迁移；没有把原型功能缺席当成删功能授权。 |

### 核实台账：spec Requirements 与全部验收 Scenario

| Requirement | 约束原句与覆盖 |
|---|---|
| S-R1 | “用户无需 Gateway 即可注册登录并查找联系人”：D82、150–151，auth 不改。 |
| S-R2 | “人与人可以跨账号私聊并持久回看”：D90、98–100、161 与成员流。 |
| S-R3 | “一个人可以管理多个 Gateway 及其 Agent”：D71、123、158 和 runbook A1/A2。 |
| S-R4 | “用户可以直接私聊其他人管理的 Agent”：D82、90、100、118–120，管理者不被自动加入。 |
| S-R5 | “多人与不同 Gateway 上的 Agent 可以在同一群协作”：D92–104、121 的真实 node/成员/锚点。 |
| S-R6 | “工具批准遵循工作模式且不新增人员权限配置”：D102–104 全选项和唯一决定。 |
| S-R7 | “聊天按成员可见，全局 Agent Work 详情完整可见”：D48–53、127–142，普通附件缺口已补。 |
| S-R8 | “既有使用数据和工作能力在升级后保留”：D132–134、161–166、194–198；shadow 需 R2-W1 才闭合。 |

| Scenario | 本轮核实结果 |
|---|---|
| S01 无 Gateway 开始沟通 | D82/150 目录和原型小李无设备，runbook B 无 Gateway；注册不受节点限制。 |
| S02 无匹配联系人 | D150 名字/ID 查询与 prototype 空态，空结果不会指向错误对象。 |
| S03 两账号实时沟通 | D90 普通 direct 唯一、D98 token sender、D94 当前成员流/恢复，持久回看同一会话。 |
| S04 同一人两设备 | 既有 nodes owner 没有单机唯一约束；D158、runbook A1/A2 同账号。 |
| S05 不改他人配置 | D71、123、158 保留 owner，公开资料只读；卡片不调用配置页 owner 资格。 |
| S06 单设备离线 | D100 各 Agent/node 分发，D140 可见页更新；卡片 submitted 不伪造成完成。 |
| S07 跨归属 Agent 交办 | D90/100 文本主链与 D118–120 图文机器入口闭合；不要求 owner 入对方私聊。 |
| S08 建混合群 | D90 显式 group、D92 各 owner 加自身 Agent；原型按身份筛选 Agent。 |
| S09 不同成员共同交办 | D98–100 的真实 sender、原触发/relay、成员广播；不按原发起者拆聊天。 |
| S10 群名/成员变化 | D92–94 明确新旧历史、移除/重加和解散；退出后不能以缓存收件人继续获取内容。 |
| S11 全局无批准卡 | D104 保留自动授权/主动沟通，无卡；Gateway global-agent no delta。 |
| S12 非 owner 操作单 Thread 卡 | D102–104 全现有选项可用；prototype:220/236 共享决定和处理人。 |
| S13 多人同卡 | D102 原子提交、D104 相同 request 重试，resolved 依真实 Gateway；不重复执行。 |
| S14 非成员私聊不可读 | D51/117–120 人/机器判定不同，A 真人 JWT 不因管理 Agent 获得 B 私聊。 |
| S15 未加入群不可读/收件/附件 | D94 当前成员、D127–134 新旧普通文件和图片保护；直接 URL 不绕过。 |
| S16 Work 完整 | D138–140 主子/root/轮询；记录中他聊正文不遮盖，无来源追踪。 |
| S17 Work 链接 | D133/142 已有记录保留，原聊天资源独立判定；不携带访问凭据。 |
| S18 旧用户继续 | D161–166 保身份/历史、D132–134 原文件哈希/关系/回退；R2-W1 是仍需修的旧 shadow 能力承接。 |

### 核实台账：用户场景、澄清与范围

| 原子 | 本轮核实 |
|---|---|
| 用户场景 1 无机器同事 | D82/150 的登录目录、纯人私聊，prototype 无设备用户仍能建群。 |
| 用户场景 2 多设备/多管理者 | D100/158、runbook 三个节点由 A/A/C 管理；不把一人和 Gateway 绑成一对一。 |
| 用户场景 3 私聊他人 Agent | D90/118–120 让 Agent 参与且机主不参与；D138 保留全局 Work 完整性。 |
| 用户场景 4 群共同做事 | D92–104 包含多人输入、现有提及和治理；配置边界 D121 处理实际跨 owner 场景。 |
| 用户场景 5 分模式批准 | D104 global 无卡、single_thread 全选项、一次决定，不额外分配批准角色。 |
| 用户场景 6 聊天私有/Work 完整 | D48–59、127–142；原聊天链接及附件归属与记录展示分开。 |
| Q1 简单起步 | D28、84 没有团队资产/角色/组织服务；未把 Q1 的旧推荐当确认。 |
| Q2 Gateway/Agent 随个人管理 | D71、92、158；成员交办权与配置 owner 分开，人无需 Gateway。 |
| Q3 global 无卡、single_thread 谁都能按 | D104 包含长期允许，prototype 三个选项都按共享状态操作。 |
| Q4 任意用户私聊 Agent | D82/90 无逐人授权/好友申请，不开放对象原有聊天。 |
| Q5 成员可见，机器管理员本地数据除外 | D51、113、117–120 保留两边界，机器 token 不发给浏览器，也不声称隔离本地运行数据。 |
| Q6 首期范围 | D82–166 包含账号/联系人/聊天/群/设备/批准/读取/迁移，不扩张独立任务产品。 |
| Q7 错误全部聊天公开已撤回 | D48/57 明确撤回；没有全部聊天导航，原型“全部”是本人会话类别。 |
| Q8 Work 全详情、聊天/附件仍私有 | D48–53、127–142 直接覆盖；普通历史附件也不再保留公开服务。 |
| 范围内条目 | 上述 8 Requirement/18 Scenario 都有落点；仅 shadow 前置 R2-W1 会破坏既有数据交付。 |
| 组织/角色/任务看板/重写机制非目标 | 没有上述新增模块；两类调用 token 是既有消费者必要边界，非人员权限体系。 |
| 不做来源过滤/模型隔离/全部聊天 | 没有新投影遮盖或 Agent 记忆隔离；Work 只开读取，配置归属保留。 |

### 核实台账：全部 24 个 delta-spec 条目

本轮对全部 MODIFIED/REMOVED 标题与对应 canonical 文件逐一匹配，并比对 MODIFIED 原 Scenario 标题集合，无遗漏；REMOVED 的旧情形由对应替代条目承接。IM spec Purpose 的 owner 隔离摘要归并更新已在 D 契约层说明。THEN 使用消费者能看到的响应/状态，不要求调用某个内部类或测试桩。表内 source 均为 docs/specs/ 相应 area。

| 原子 | canonical 锚与本轮核实 |
|---|---|
| Δ01 auth REMOVED 数据面 owner 隔离 | im/auth-tenancy.md:30 同名原条目存在，Δ02 明确替代访问规则。 |
| Δ02 auth ADDED 登录/成员/管理归属 | 无 token、token 主体、原非成员拒绝、metrics 四旧情形保留；新增同群、限定机器凭据引用，无宽泛 owner 代理。 |
| Δ03 agents REMOVED owner 用户流 | im/agents-nodes.md:334 原标题精确，被 Δ04 取代。 |
| Δ04 agents ADDED 当前成员事件 | 原五种握手/resume/sync/断网/切号情形保留；个人配置/node 仍 owner；D94 当前成员发送/恢复一致。 |
| Δ05 agents ADDED 登录目录 | 新接口，无现有完整配置契约被暗改；公开身份、多设备、离线可观察。 |
| Δ06 conversations REMOVED Agent 私聊 owner 访问 | im/conversations-messages.md:61 原条目精确，Δ10 承接投递回执和旧随机 owner 情形。 |
| Δ07 conversations REMOVED owner 群治理 | canonical:255 原条目精确，Δ11 保留八个原治理情形。 |
| Δ08 conversations MODIFIED Agent 保护图片 | canonical:14 三原 Scenario 保留；明确由 Δ13 接管旧公开上传，撤回原不追溯例外。 |
| Δ09 conversations MODIFIED 消息字段/分页 | canonical:31 六原 Scenario 保留并按普通 direct 唯一改写并发；新增本人 sender、纯人无 Gateway、显式 group，与 D90/98 对齐。 |
| Δ10 conversations ADDED Agent 私聊不授予 owner 查看 | 回执 ID 不给聊天权限；旧随机归属保 ID、实际成员，不强加真人，符合修订后的迁移分类。 |
| Δ11 conversations ADDED 成员群治理 | 增/重/空/404/改名/Actor/移除/解散全部承接，新增跨账号和移除后界面收敛；创建者保护目标明确。 |
| Δ12 conversations ADDED 个人偏好/已读 | 独立 pin/mute、个人已读与并发未见消息、原用户状态迁移均可观察，未出现内部字段调用断言。 |
| Δ13 conversations ADDED IM 托管聊天附件 | 新普通文件上传、旧 URL 成员关系、合法 fork/非法引用均覆盖 D127–134；与 Δ08 不再保留相反的旧公开例外。 |
| Δ14 Work MODIFIED 聊天和全局工作分开 | im/agent-work.md:12 原三 Scenario 保留；新增完整记录/来源保护/非 owner 持续更新，主子明细原契约不删。 |
| Δ15 relay REMOVED owner 配置边界流 | im/gateway-relay.md:51 原条目准确，由 Δ19 改为成员事件。 |
| Δ16 relay MODIFIED Gateway 实际边界/ACK | canonical:30 同名原三个 Scenario 全保留，新增跨 owner 群；D121 明确 node/profile/Agent member/锚点，不能再以 conversation owner 等式拒绝合法群。 |
| Δ17 relay MODIFIED 工具授权持久下发 | canonical:198 原历史标识/无标识兼容仍在，新增多人、离线唯一决定与 global 无卡；原型 R1-W1 已对齐。 |
| Δ18 relay MODIFIED 中继/流式幂等 | canonical:67 原三个 Scenario 保留，global Inbox completed 与无预建气泡不变；新增多节点独立交付。 |
| Δ19 relay ADDED 成员配置边界流 | 两原在线/replay 情形保留；精简浏览器字段、持久事件、恢复窗口不变，符合 D94/121。 |
| Δ20 relay ADDED Gateway HTTP 运行凭据 | 新机器数据接口范围、跨归属图片、失效/错 node、shadow 归因、管理 API 拒绝均有结果；支持 D108–123，但 shadow 身份前置 R2-W1 尚未闭合。 |
| Δ21 UX ADDED 导航/语言 | 真正并行新增协作入口和双语承接；不替换 current 的附件、消息菜单、草稿和移动端行为。 |
| Δ22 Gateway routing MODIFIED 四步路由 | gateway/routing-delivery.md:100 同名八原 Scenario 全在；新增跨真人输入，global canonical 链接已正确；不改既有全局运行机制。 |
| Δ23 Gateway relay MODIFIED 授权标识 | gateway/relay-protocol.md 同名原允许/拒绝两 Scenario 全在；新增原执行/幂等反馈，与 D102–104 一致。 |
| Δ24 Gateway relay ADDED 运行凭据 | 注册 ACK→图片/镜像、重连现取、外部主路径不阻塞均可被 Gateway/IM 消费者验证；需 R2-W1 补清前置身份查询。 |

### 核实台账：M1、原型与运行前置

| 原子 | 核实及判断 |
|---|---|
| 唯一 M1 | D226–232 单一完整协作切片，涵盖 IM/Gateway/前端/迁移；无横切 milestone 或并行范围冲突；实际 M1-collaborative-im/.gitkeep 空骨架符合设计期职责。 |
| reviewer 退出轨 | R1–R6 对应联系人、建群、路由、批准、Work、配置；覆盖 S 全 18 Scenario，加跨归属图片/配置边界/普通新旧附件/fork，产出为真实可用而非组件完成。 |
| worker 退出轨 | W1 人/机器/owner/Work、卡片幂等；W2 build 和桌面/手机对照；W3 三账号节点、旧 DB+文件演练、shadow/失效凭据；W4 双语和受影响旧功能，均有可判定退出条件。 |
| 原型联系人/建群/消息 | prototype 的 direct、create-group、send、contact 选择等动作对应 D must-match 前三项；身份条是演示，未误当登录实现。 |
| 原型批准 | prototype:218–220/236 已有 pending/submitted/resolved 和离线恢复模拟，满足第四项的多人共享结果；浏览器验证由作者记录，本 reviewer 只使用脚本作为交互设计证据。 |
| 原型 Work/来源/配置设备 | work/source/agent-tab/account 按示例身份呈现完整主子详情、来源成员结果和配置 owner，符合第五/六项；未以原型认定真实后端授权。 |
| 原型双语 | language 动作持久 feat554_prototype_lang；新增等待状态和处理人重绘；D 指定正式沿用 im_lang，切换保存草稿。 |
| may-adapt 和 out-of-scope | 字体/间距可按设计系统；演示条/固定回复不进产品；附件/注册/绑定只是原型未展开，正式仍保留，界限清楚。 |
| 真栈前置/runbook | 独立 UNIT_ROOT/RUNTIME_ROOT、e2e-up/down、A 两节点/B零/C一、不同 workspace/node/state、单 Thread/manual/global、无 Feishu；真实问答验证模型就绪，无生产 :8011。 |
| 重启和恢复 | C1 owned PID 重启/日志，完整新栈与保留 DB 的 IM 重启分开；保留 IM_PORT/JWT_SECRET/cwd，清理 owned 进程，足以下游照用。 |
| 迁移演练 | 旧副本含真人 owner 非成员、Agent-only/random owner、fork/shadow、公开上传和受保护图片/Work；一致性备份+两目录哈希/关系+配套回退，不动生产原库。 |

### 整体判断与架构进攻

总览以人/聊天成员/Work/个人管理/多 Gateway 串起规则，补充段给出各消费者；上层仍能看懂方向。接口数据流除 R2-W1 外已经闭合，风险及回退指向实际 DB/文件/连接状态，没有临时兼容分支或原型冒充验收。

| 角度 | 实际攻击对象与证据 | 结论 / 长远代价 |
|---|---|---|
| 一·归属 | 对照 IM app/deps、Gateway composition、GatewaySessions：真人成员/资源关系由 IM 仓库校验，机器凭据留当前 WS 连接，Gateway 仅传数据；kernel 仍由 SDK 调用。 | 所属层合理，无反向 import。R2-W1 属于一个既有 client 混合身份和数据职责的真实缺口；若把 /me 管理事实也放入机器作用域，会逐渐扩出 owner 代理权限，需在当前调用边界明确拆开。 |
| 二·该不该存在 | 对运行 token、目录、participant 状态、direct_key、批准 submitted、资源关联分别做删除测试：同 owner JWT 无法分辨浏览器与 Agent、公开完整配置会泄漏字段、共享偏好互相影响、普通 direct 并发重复、离线确认无承接、fork 附件丢失或旁路。 | 每项有本次可观察场景驱动；单一内存连接凭据无手工授权面，资源仍扩展既有存储，没有为了未来多态新造工厂/策略/角色框架。 |
| 三·深还是浅 | 独立搜索 PA 的 /im/v1 HTTP 消费者，复核 shadow/reply_images/image_attachments、bootstrap/config clients；复用既有 relay、WorkRepository、EventRepository 和资源文件存储。 | 未发现需要另建聊天/调度/文件服务的理由。搜索揭示 shadow 仍含 /me、/nodes 前置（R2-W1）；拆清两个 provider 可以就近解决，不需要抽象成通用权限 SDK。 |
| 四·治本还是补丁 | 检查 D132 删除公开 StaticFiles、旧 alias 受成员保护、合法 fork 目标关联；D121 修 conversation owner 错等式；D94 当前成员发流；D104 原请求幂等；迁移配套 DB+字节。 | 都在真实权威边界修正，未仅隐藏按钮/链接或给管理者加隐式成员。Work 不造过滤层。R2-W1 应保留既有受信身份校验，不用信任本地旧 owner 或放宽所有机器访问掩盖失败。 |

本轮不要求实施或真实服务运行。请作者补清 R2-W1 的身份前置分工后交回同一 reviewer；后续检查深度根据实际修订决定。

### Author Resolutions

| Finding | 处理 | 修订与验证 |
|---|---|---|
| R2-W1 | 接受 | design.md 明确 composition 向 shadow_sync 注入两种 provider，身份前置以独立 owner JWT client 查询 `/me`、`/nodes`，保留真实 owner、node 归属及旧 saga recover_owner 校验；后续数据 client 才使用运行凭据。身份缓存仍依据 owner JWT，运行凭据轮换不替代它；失败保留 durable 待同步，不信任本地旧 owner 或放宽机器 token。Gateway relay delta 增加身份／数据分别认证的可观察场景，runbook 增加旧 owner 恢复、两类凭据轮换及失败恢复验证。已对照 shadow_sync.py 的正式调用链，尚未执行实现或真实同步。 |

本次不改变产品权限、运行凭据作用域、注册 ACK 格式、聊天／附件规则或原型交互，仅补清既有混合消费者的身份前置；交回 reviewer 判断闭合情况。

## Round 3

### Metadata

- reviewer: /root/design_review
- review_mode: delta
- mode_reason: 修订仅为已有 shadow 混合消费者明确身份查询与机器数据请求的 client/provider 分工，以及直接对应的 delta Scenario 和验收补充；没有改变 R2 已核定的凭据作用域、注册协议、聊天/Work/附件规则、迁移方案或 milestone。
- started_at: 2026-09-13T02:22:19+08:00
- completed_at: 2026-09-13T02:23:29+08:00
- duration: 1m10s

### Verdict

Approved — 0 CRITICAL / 0 WARNING

R2-W1 已关闭。本轮范围内无新增问题；结合仍有效的 R2 完整审查，设计具备进入 change-orchestrator 实施的条件。本结论是设计批准，不代表多人 IM、真实镜像或迁移已经实现或验收。

### 历史问题闭环

| 历史项 | Author Resolution | 本轮核实 | 状态 |
|---|---|---|---|
| R2-W1 | 接受；shadow 同时接收两类 provider，身份前置使用 owner JWT，数据使用运行凭据 | design.md:112–113 明确 /me、/nodes 的独立 owner JWT client、真实 owner 和 node 校验、旧 saga recover_owner、基于 owner JWT 的缓存，以及独立数据 client 的运行凭据；失败保留待同步，禁止本地 owner 或真人数据降级。与 shadow_sync.py:133–168、591–638 的真实前置及 account.py:113–122、nodes.py:150–163 的认证入口相符；当前 node.register ACK 不需添加另一套身份返回。 | closed |

### Coverage

- changed atoms：R2 台账 D09 的 shadow 调用身份分工、D13 的旧 owner 恢复前置、Δ24 新增 Scenario、M1 W3 对应 runbook 补充。
- 波及链：composition 注入 → owner JWT 身份查询及缓存 → 节点归属/旧 saga 恢复 → 运行凭据数据 client → 失败保留及后续重试。
- retained_from: Round 2 — 其余现状、决策、spec 约束、delta 条目、M1、原型和运行前置均未改变；源代码仍无本 unit 修改，运行 token 的边界和所有产品规则没有扩大。本轮不重抄完整台账，也不以原型或作者报告的检查代替实现验证。

### 本轮重查证据

| 原子 | 直接核实与结论 |
|---|---|
| 两类 client/provider 的边界 | design.md:112–113 明确 shadow 同时接收 owner JWT 与运行凭据，且 Authorization 不复用。composition.py:659–694 是真实注入点；shadow_sync.py:133–151 原混合 client 的两个前置现在都有明确身份来源，worker 无需猜是否放开机器 /me、/nodes。 |
| 身份缓存与轮换 | shadow_sync.py:591–612 现按 token 缓存解析 owner；新设计指定该 token 是 owner JWT。运行凭据轮换只影响数据请求、身份 provider 刷新影响原身份缓存，各自语义明确。 |
| 真实 owner 与旧 saga 承接 | shadow_sync.py:163–168 的 recover_owner 依认证结果，:614–638 校验对应 node；D113 保留这些检查，不以配置旧 owner 代替。账户 GET 使用 current_user，节点列表依 user.owner_id；设计与现有管理边界一致。 |
| 写入/失败/重试 | shadow_sync.py:450–479 Agent 输出、:338–368 调和请求属于运行凭据数据调用；:248–252 原锚点失败转 PendingError，:526–577 恢复沿持久来源重试。D112–113 明确失败保持 durable、重试现取凭据、禁止用真人 JWT 代写，不再是重复被拒的死路。 |
| Gateway delta | specs/gateway/relay-protocol.md:38–41 新“shadow 身份校验与镜像数据分别认证”位于 R2 已新增的运行凭据 Requirement 内；canonical 仍无同名 Requirement，无旧 Scenario 被删。THEN 写实际 HTTP 身份、原恢复结果及失败行为，没有以内部函数被调用作为验收。 |
| runbook / M1 W3 | reviewer-runbook.md:94 加入旧配置 owner 与认证 owner 不同的 saga、两种凭据分别刷新、身份失败/恢复、机器管理请求仍拒；与 D113 和 Δ Scenario 一致，复用 M1 既有 shadow 回归范围，无需另拆 milestone 或真实第三方消息。 |

### 受影响的架构进攻

| 角度 | 本轮核实与结论 |
|---|---|
| 一·归属 | 身份事实仍来自 IM 的既有账号/node 入口，机器数据资格仍由 IM 当前注册连接和 Agent 成员判断；Gateway 组合两个消费者，没有把聊天授权交给本地配置，也未扩大 owner JWT 或机器 token 权力。 |
| 二/三·存在必要性与深度 | 两个 Authorization 边界属于同一流程中实际存在的两类请求；删掉区分就会复发 R2-W1。设计只要求两类 provider/client，不要求新接口工厂、权限 SDK 或身份服务，复杂度集中在当前 composition/shadow 而非另造间接层。 |
| 四·治本 | 修正混合 client 的实际调用，而不是给机器 token 开放管理 API、信任旧本地 owner 或以真人 JWT 重试机器写入；保留旧 saga 恢复和持久重试，没有新增需日后偿还的兼容旁路。 |

### Issues

无。

### Recommendations

无。可以结束设计审查循环，进入实施及既定真实验收。

### Author follow-up after Round 3

用户以原 IM 截图指出多聊天生成 Skill 遗漏，继而明确 single_thread 能力须保留、global Agent 聊天蒸馏尚未设计，并要求逐项检查其他原功能。spec v4 Q9 记录原话；此前三个 Round 的结论仅对应当时版本，以下修订交回同一 reviewer 复审。

- 对照 sidebar、MessagePane、ChatWorkspace、Agent 管理、UserMenu／MePage／账号设备 current 代码形成 design 承接矩阵与 R7；原型补多选蒸馏、消息菜单／fork／过程、slash、草稿、聊天管理和旧管理入口。深层管理表单／RPC 在原型只示意，正式 IM 必须复用原能力。
- 单 Thread 蒸馏保留 source/execution owner 管理边界，来源聊天使用成员检查，保留两种 Skill scope、preflight、Gateway 本机解析、成功后独立固定节点聊天与预填；global Agent 模式不参与此流程。
- 补清跨 owner slash 的真实消费者：成员专用 commands 投影复用已有 config/capability RPC，不公开完整配置；头部／@／fork 状态使用公开 Agent 状态。相关 UX delta 保留原 Scenario 后增加新场景；runbook 同步真实验收。
- 原型主旅程与双语桌面／手机布局通过；原 IM 四组相关前端测试 42 项通过。未实施、未部署多人 IM，也未在此原型真实生成 Skill。

## Round 4

### Metadata

- reviewer: `/root/design_review`（与前三轮相同）
- review_mode: `full`
- mode_reason: Q9 明确补充既有 IM 功能承接范围，且新增成员 commands 接口改变原 config/capabilities 的聊天消费者；重新核对全部五类承重原子及四个架构角度。本轮报告落盘前作者接受并修订了两项实际发现，已在本轮复核，不要求为已闭合问题再开空转轮次。
- started_at: `2026-09-13T10:54:25+08:00`
- completed_at: `2026-09-13T11:07:42+08:00`
- duration: 13m17s

### Verdict

Approved — 0 CRITICAL / 0 WARNING（未解决）

Q9 所要求的原 IM 入口和关键流程已有可实施的承接；本轮发现的 Skill 候选身份丢失及特殊聊天误复用均已修正。可以进入 change-orchestrator 实施。此结论只批准设计，不代表多人后端、真实蒸馏、迁移或完整产品旅程已经实现、验收或部署。

### 历史问题闭环与本轮已解决发现

| 项目 | 本轮核实 | 状态 |
|---|---|---|
| R1-C1 人／Gateway HTTP 主体混用 | design.md:110–126 保留连接绑定运行凭据、有限数据入口和 WS 配置边界校验；Q9 commands 为真人成员窄投影，不放开管理 config/capabilities，也不把 Gateway owner 加入来源聊天。 | closed |
| R1-C2 普通新旧上传公开 | design.md:130–137、conversations-messages delta 的资源 Requirement 仍覆盖普通新上传、历史公开别名、浏览器 blob、Gateway、合法 fork 和原字节迁移回退；补回附件入口没有恢复 StaticFiles。 | closed |
| R1-W1 批准状态与离线不一致 | design.md:104–106 保留 submitted／resolved 区分和原请求重试；prototype.html:370–373、407 提交后等待模拟节点确认，离线可提交。补回移除成员后，未决定且 Agent 已离群的卡不再给新决定按钮，历史不删除。 | closed |
| R1-R1 创建者保护现状 | design.md:94 正确区分“当前服务端没有保护”与“本次补齐”；与 conversations.py:588–613 相符，不再误称既有保证。 | closed |
| R1-R2 canonical 链接 | Gateway routing delta 指向 canonical global-agent；新 Q9 条目未改变此链接。 | closed |
| R1-R3 Agent-only／随机 owner 审计 | design.md:180–183 仍分类保留 Agent-only、真实旧成员与随机旧 owner，不能将所有 creator 强行变真人；与 conversations.py:693–733 的来源解析分工一致。 | closed |
| R2-W1 shadow 身份前置断裂 | design.md:114–115 保留独立 owner JWT 与运行凭据 provider/client；/me、/nodes、旧 saga recover_owner 和缓存仍使用 owner JWT，后续数据才使用运行凭据。Q9 不改此链。 | closed |
| R4-W1 成员 Skill 投影丢失去重身份 | 初稿只返回 name/description；slash-candidates.ts:101–133 会将所有无 location 的同名候选合成一行，丢失原不同来源及说明；测试 :107–135 和 canonical agents-nodes.md:418–422 明确保留同名异位置。作者已在 design.md:153–157 定义不泄漏路径的 skill_key，按 node＋实际 location 的域隔离 HMAC 生成，旧无 location 按 node＋name 退化；前端按 key 聚合 fromAgents，异 key 保持独立行，普通选中文本不变。UX delta 增加观察场景，agents-nodes delta 完整 MODIFIED 原 runtime 能力 Requirement，只改受影响的 SlashPicker 语义，管理能力 location/source_group 保留；runbook:117 增加回归。 | closed in Round 4 before report |
| R4-W2 联系人发消息误复用 fork／蒸馏聊天 | 初稿 direct(id) 查找任意同对成员两人聊天；branchMessage／prefillDistill 又将特殊聊天置于列表首部，后续从资料发消息会进入它，违背 design 的 direct_key=NULL。当前 prototype.html:320、366 分别标 purpose=fork/distill，:405 的普通私聊查找排除 purpose 并恢复该会话的独立草稿；重命名的普通私聊仍可复用。仅修原型匹配规则，无后端实现宣称。 | closed in Round 4 before report |

### Coverage

本轮逐条读取 spec v4、design、8 份 delta、prototype、runbook、前三轮报告及新增 Author follow-up，并核对 M1 空骨架。现状以当前源码和实际入口 wiring 为证；源码无本 unit 实现修改，因此既已独立追通的调用链仍可用于本轮完整判断。新增旧功能承接逐项追前端入口、服务端消费者与 canonical，不以作者的 42 项测试、截图或浏览器通过陈述替代设计判断。

完整台账包含：12 条现状表断言及 9 条既有能力／消费者断言；2 个编号决策和 16 个承重补充决策；8 Requirements、18 Scenario、6 用户场景、Q1–Q9、3 项范围／非目标；全部 27 个 delta 条目；唯一 M1、两轨退出、原型对齐与运行前置。下表中的 D/S 行号分别指当前 design.md/spec.md；源码短路径均相对仓库，IM 前端路径均位于 src/IM/frontend/src。

### 核实台账：现状与真实消费者

| 原子 | 实际核实及结论 |
|---|---|
| C01 账号／节点／Agent 个人管理 | src/IM/app.py:449–458 注册实际路由；api/deps.py:52–76、94–105 注入仓库；infra/db.py:55–99、125–131 保留 owner 与成员两类事实，users.py:73–87 创建真人 owner=id。D17 没有假设人机一对一。 |
| C02 已存在多方成员存储 | ConversationRepository 的 conversations.py:89–99、618–650、775–795 实际写 Actor 稳定身份与 participants；不需替换聊天存储才能跨账号。 |
| C03 聊天 HTTP 仍按 owner | web_im.py:195–208、424–434、497–508 经 owner helper；messages.py:595–604 和 message_images.py:19–25 同边界。D19 改真实用户路径，不只改 UI。 |
| C04 实时流已有成员依据但有缓存 | events.py:220–226 保存 members 为收件人，:268–291 replay 联结当前 members；user_stream.py:189–203、275–301 的缓存与广播须按 D96 收敛。app.py:319–336、507–530 确认该 registry 在实际 wiring 中。 |
| C05 已有逐 Agent 节点 relay | messages.py:483–507 → web_im_service.py:636–645 → relay_service.py:284–296；每个 Agent 解析 node。:273–282 的无 Agent fallback 是 D102 要移除的实际分支。 |
| C06 Agent 自查聊天的范围 | work_conversations.py:48–65、151–172 校验 node、global_main 与 Agent member；运行入口委托此查询。D22/102 保留，不因人的 Work 开放扩大 Agent Inbox。 |
| C07 Work GET 与轨迹存储 | routes/agent_work.py:13–18 的 owner helper 被 GET :22–85 和写入口 :95 起共用；infra/repositories/agent_work.py:52–61、393–477 保存 root、items、turns。D141 明确只放开 GET，root/session 检查保留。 |
| C08 偏好目前共享 | infra/db.py:35–53 会话列、conversations.py:419–454 PATCH 为会话字段；消息首次插入／占位回滚改变原未读。D178 迁到 participant 及显式读边界，不能只改响应字段。 |
| C09 原界面主要面向自有 Agent | new-group-modal.tsx:15–21、84–85 Agent 列表，chat-workspace-page.tsx:1324–1330 传自有候选；成员扩展的修改点真实。 |
| C10 Gateway HTTP 使用真人 provider | personal_assistant/gateway/composition.py:659–694；shadow_sync.py:133–151、reply_images.py:326–341、image fetch :136–145 使用此 provider。D26 正确承认现状，未伪称机器认证已存在。 |
| C11 普通上传真实公开 | MessagePane → use-attachment-upload.ts:25–35 → messages.py:391–419；src/IM/app.py:446–448 挂载 StaticFiles。D27/130–137 正面覆盖上传、读取及旧 URL。 |
| C12 配置边界另有 owner 条件 | config_boundaries.py:49–76 同时检查 profile/node、conversation owner、成员和锚；D124 只去掉阻断跨 owner 的 conversation owner 相等条件，其余仍保留。 |
| C13 侧栏蒸馏入口与流程 | conversation-sidebar.tsx:156、184–236、287 分别是底部、选行、右键；distill-selection.ts:7–11 是 idle＋明确来源；chat-workspace-page.tsx:1008–1028 preflight、1055–1069 成功后新聊天预填。D149–151 补模式限定，保留两 scope 与成功后再建聊天。 |
| C14 蒸馏真实 owner 消费者 | web_im.py:244–344 当前依次 source chat owner、source Agent owner、execution owner、Gateway prompt、固定节点聊天；conversations.py:693–705、722–733 的 source 解析不会任取多 Agent 群第一人。D151 只将来源聊天读改成员，两个 Agent 管理资格保留，IM 不读 JSONL。 |
| C15 Slash 从管理信息组装 | chat-workspace-page.tsx:217、233、409–469 用自有 Agents/nodes＋live config/capabilities；agents.py:425–495 是实际 RPC 入口。D153 的成员 projection 必要，不能把 owner API 整体公开。slash-candidates.ts:90–95 enabled 语义、:101–133 去重语义由新投影承接，R4-W1 已关闭。 |
| C16 消息菜单与 fork 消费者 | message-pane.tsx:1207–1223 要求完成、direct、kernel 锚和在线，:1490–1540、1712 提供工具栏／菜单／移动入口；web_im.py:353–417、web_im_service.py:341–560 是原 fork 主链。chat-workspace-page.tsx:508、541–563 用自有列表推在线是跨 owner 的实际错误前提，D159 已替换为公开状态。 |
| C17 既有聊天管理 | direct-conversation-menu.tsx:64–90 提供改名及可选配置；group-settings 的 :247、258、326 分别移除、配置、解散。D94、159 保留原入口并区分共享标题／个人偏好，明确新增真人退出及创建者保护。 |
| C18 Agent 创建与真实分区 | agents-list.tsx:57、agents-rail.tsx:52、nodes-page.tsx:323 为创建入口；agent-detail-page.tsx:1640–1676 挂 Work／Skills／Channels，Overview／Sessions 当前占位，:1739 起完整配置、:1776/1814 Heartbeat/Cron、:2000 起保存／放弃。D224/228 明确复用完整管理页面，原型少字段不构成删功能。 |
| C19 账号／设备／Policies／退出 | UserMenu:157、167、181、217；MePage:53、88、116、132、169；AccountPage:178/200 显示名及默认节点，NodesPage:265/284 别名与诊断。路由 :40–67 与 MePage:8–11 证实 Notifications 设置已移除，D213 没有误造通知页面。 |
| C20 语言、草稿、消息富交互 | i18n/index.ts:7–20、41–46 使用 im_lang；UserMenu:60–63、MePage:132–146 为实际切换入口。MessagePane 原分页、附件、文本选择及 fork 仍由原组件承担；D211/222–226 要求保留草稿编辑状态和正文，不把原型 text-only 展示当组件替代。 |
| C21 公开联系人必须窄化 | users 内部数据含 password_hash，agents.py:258–275、553 可携完整配置；D126/167 只投影可登录真人及非 stale Agent，排除 shadow/system，资料和管理 API 分开。新 commands 同样不返回路径／workspace／原错误体。 |

### 核实台账：决策

| 原子 | 完整性、自洽性及依据 |
|---|---|
| D01 编号决策 1（D48–55） | S59、181–190 同时要求完整 Work 和原聊天成员检查；两类读入口及链接行为独立，未添加 Work 来源过滤。 |
| D02 编号决策 2（D57–61） | S59/205 撤回全部聊天；普通列表按本人参与，联系人新聊天不授予已有聊天访问，导航没有组织切换。 |
| D03 联系人／owner 配置（D82–86、126、167–168） | 当前管理响应不能直接公开（C21）；目录字段、对象资格、查找／空态／分页和管理动作都已限定，S93–100、116–132 有驱动。 |
| D04 direct／group 身份（D92、151） | Actor user/agent 与公开 kind/human 不混；普通对人唯一 direct_key、group/fork/distill NULL、旧会话不猜 key。并发唯一约束明确，R4-W2 的原型矛盾已关闭。 |
| D05 群治理（D94） | 谁能添加谁、移除谁、创建者退出／解散、新增成员历史都拍定；与 S83、147–150 一致，无角色层。 |
| D06 成员失效及恢复（D96） | 旧成员只接 ID 失效，当前成员决定正文与 replay，恢复先 sync；缓存清除涵盖正文／附件及 commands，离线移除闭合。 |
| D07 个人状态（D90、178–180） | participant 状态、首插未读、幂等／占位回滚、显式读边界和并发新消息均明确；个人结果不广播成共享快照，S209 授权该设计。 |
| D08 发送者及跨 Gateway（D100–102） | 人 sender 取 JWT，Agent 输出使用运行主体；每 Agent 真 node，纯人不 fallback，全局自动收件仍是 Agent 成员范围，和原 relay 分工相符。 |
| D09 批准卡（D104–106） | 原 conversation/message/request/agent/node/run 绑定，pending→submitted 原子决定，真实确认才 resolved；离线／重启同请求重试与不存在请求边界明确；所有原选项开放给真人成员，符合 S159–167。 |
| D10 运行凭据（D110–126） | 注册 ACK 发内存 token，服务端当前连接解析身份，断开／替换／重启失效；指定数据入口范围，管理保 owner。GatewaySessions 当前 node 注册/ACK 及 composition 可承接，不增持久角色。 |
| D11 shadow 身份与数据（D114–115、182） | 身份前置与旧 recover_owner 保留，runtime provider 只负责数据；shadow_sync.py:591–638、163–168、450–479、526–577 的实际消费者分别有出路，失败 durable 等待而非 owner 旁路。 |
| D12 附件统一（D130–137） | 上传 conversation、下载 blob、机器 agent_id、合法引用/fork、旧 aliases 与孤立文件、哈希／备份／回退都有来源和出口；不保公开文件旁路，也不扩大到外站副本。 |
| D13 Work 与公开在线状态（D141–145） | 仅 global GET/root/session，非 owner 可见页 3 秒轮询、后台暂停恢复刷新，失败重试；不广播完整节点配置。链接仍原接口，S181–190 闭合。 |
| D14 单 Thread 蒸馏（D149–151） | 用户 Q9 明确模式边界；source chat member、source/execution owner 且 single_thread/同 node；保 agent/global Skill 写入范围、Gateway preflight 与 prompt，先成功后建独立执行聊天，失败没有空会话。 |
| D15 成员 commands（D153–157） | 权限、输入聊天、真实 Agent/node、复用 RPC、enabled 判定、逐 Agent 状态/命令描述、部分失败与缓存边界均明确；新增 skill_key 保留同名异源，管理 location 不公开给成员。没有为了 slash 引入新 Gateway 协议或配置权限。 |
| D16 原消息操作资格（D159） | 头部/@/fork 使用聊天成员＋公开 Agent 状态，fork 仍完成 direct/合法锚/在线且源按成员；私聊共享改名仍可用。没有把“可看 Agent”变成任意旧聊天 fork。 |
| D17 旧数据与回退（D180–183） | ID/历史/成员/管理 owner 保持，旧个人状态只映射真实原人，其他成员独立初始化；随机 owner/Agent-only 分类，无法解释停止。DB＋资源配套恢复，无长期双写兼容。 |
| D18 既有能力／原型边界（D209–258） | Q9 每项有入口与关键操作资格矩阵；深层当前页面继续复用，原型只示意的范围、may-adapt、must-match、out-of-scope 都明确。未以原型覆盖字段替换现有完整表单。 |

### 核实台账：首文档全部验收

| Requirement | 原句与对应设计 |
|---|---|
| S-R1（S91） | “无需 Gateway 即可注册登录并查找联系人” → D84/126/167，无绑机前置。 |
| S-R2（S102） | “跨账号私聊并持久回看” → D92/96/100/170，稳定普通聊天及成员历史。 |
| S-R3（S110） | “一个人可以管理多个 Gateway 及其 Agent” → D73/84/175，一人多节点保原管理关系。 |
| S-R4（S126） | “直接私聊其他人管理的 Agent” → D84/92/100–124/153–159，文本、图片、slash、状态/fork 的实际消费者均覆盖。 |
| S-R5（S134） | “多人与不同 Gateway 上的 Agent 可以在同一群协作” → D94–106/124，混合成员、逐节点执行、共同控制。 |
| S-R6（S152） | “工具批准遵循工作模式且不新增人员权限配置” → D104–106，所有旧选项、原请求唯一决定。 |
| S-R7（S169） | “聊天按成员可见，全局 Agent Work 详情完整可见” → D50–55/130–145，所有聊天入口与已记录 Work 的规则不同。 |
| S-R8（S192） | “既有使用数据和工作能力在升级后保留” → D180–183/215–228/272；Q9 清单逐项复用原行为，global 蒸馏不冒充已设计。 |

| Scenario | 对应可观察落点 |
|---|---|
| S01 无 Gateway 的用户开始沟通（S93） | D84/167；原型小李无节点仍有联系人和新聊天；runbook B 账号无 Gateway。 |
| S02 没有匹配联系人（S98） | D167 查询、原型联系人空态；不创建错误对象。 |
| S03 两个账号实时沟通（S104） | D92 direct 唯一、D96 当前成员流、D100 sender，持久回看和刷新保持。 |
| S04 同一人绑定多台设备（S112） | D175/225 保原 Nodes 管理；runbook A1/A2 同账号、独立 node/workspace。 |
| S05 协作者不能修改他人配置（S116） | D73/113/153–157 保 owner 管理 API；member commands 窄投影不返回完整 config。 |
| S06 单台设备离线（S121） | D102 独立逐 Agent relay，D143/159 公开在线状态；批准 submitted 不伪报完成。 |
| S07 跨管理归属交办（S128） | D100–126 Gateway 数据主体与图文回复、D153–159 旧聊天操作可用，不需把管理者加为成员。 |
| S08 建混合成员群（S136） | D92/94 显式 group、真人与自己的 Agent 选择；prototype 新群/邀请同规则。 |
| S09 不同成员共同交办（S141） | D100–102 真实 sender＋既有触发/relay，不只认可 owner；当前成员收回复。 |
| S10 群成员／群名变更（S147） | D94–96 增删/改名/解散/退出和重连收敛；prototype memberPanel、removeMember、dissolve 分支一致。 |
| S11 global 无卡（S154） | D106 保自动审批/主动沟通，不新增卡或绕开原授权判断；prototype global 示例进入 Work。 |
| S12 single_thread 任意成员操作（S159） | D104–106 包括长期允许，配置仍 owner；原型三个选项均可用，提交/确认两阶段。 |
| S13 同卡多人操作（S165） | D104 原子首决定、D106 同请求重试，后续读实际状态；不重复执行另一轮。 |
| S14 未参与者不能读私聊（S171） | D52/120/130–135 所有原聊天、附件入口；Agent owner 无特权。 |
| S15 未入群不可读（S177） | D94–96 当前成员历史／实时及附件；ID-only 失效不泄正文。 |
| S16 完整 Work（S181） | D53/141–143 主轨迹＋关联子执行完整，只向登录 global GET 开放并持续刷新。 |
| S17 Work 链接不给原聊天资格（S187） | D54/134–145 原地址独立授权，Work 不代理资源字节；已记录内容原样可见。 |
| S18 原用户继续使用（S194） | D180–183 旧身份/历史/个人状态承接；D219–226 逐项覆盖 S199 的蒸馏、复制/fork、slash/skills、草稿、附件、聊天管理、Agent新建及分区、账号/设备/Policies/退出和双语；下文原型台账核各入口，D272/runbook R7 要求正式回归。 |

### 核实台账：用户场景、澄清与范围

| 原子 | 核实结果 |
|---|---|
| 用户场景 1（S77） | 无机器注册、找人、私聊、入群和空结果均由 D84/94/167 与原 auth 承接，不绑 Gateway gating。 |
| 用户场景 2（S79） | 一人两机与另一管理者、设备离线互不阻断由 D73/102/143/175 承接，无一对一约束。 |
| 用户场景 3（S81） | 他人 Agent 私聊由 D84/92/110–124 支持；管理者仅能看完整 global Work，不能借 owner 读取聊天。 |
| 用户场景 4（S83） | 混合项目群、共同交办与既有触发、改名/增减/解散由 D94–106 支持；不重写 group reply policy。 |
| 用户场景 5（S85） | 两模式及共同批准由 D104–106 支持；长效选项未被偷偷限制到管理者。 |
| 用户场景 6（S87） | D50–55/130–145 完整 Work 与原聊天隔离；D180–183 旧关系承接，没有来源权限子系统。 |
| Q1（S22–25） | D30/86 不把未接受的团队共有资产当需求，没有组织／角色引擎。 |
| Q2（S27–30） | D73/94 保原 owner 管理，各管理者带自己的 Agent 入群，人无需机器。 |
| Q3（S32–35） | D106 全部现有卡片选项对真人成员开放；首个有效决定是满足 S165–167 的设计选择，未伪称单独用户拍板。 |
| Q4（S37–40） | D84 普通联系人直接找他人 Agent，无好友申请或逐人许可。 |
| Q5（S42–45） | D52/54/116 产品聊天按参与，不保证对机器管理员隐藏本地运行数据；没有新增本地隔离。 |
| Q6（S47–50） | D84–183 覆盖用户协作完整主链，M1 端到端；不另造任务看板。 |
| Q7（S52–55） | D50/59 撤回全部聊天解读，原型“全部”只对本人会话分类。 |
| Q8（S57–59） | D50–55 明确已记录他聊内容不遮盖，原聊天／附件链接独立鉴权；新 commands 只服务该聊天成员。 |
| Q9（S61–65） | D149–159 与 D219–228 分别拍定单 Thread蒸馏和旧功能承接；agent/global scope 区别于 work_mode，global 聊天蒸馏无新增承诺。 |
| 在范围（S203） | 8 Requirements、18 Scenario、6 场景均有上表落点，原型和实现范围分开，R7 承接新增清单。 |
| 非目标（S204） | 无组织部门、团队资产、权限表、逐人配置、任务看板；Gateway token 和 member projection 处理当前真实消费者，不是新人员授权体系。 |
| 禁止扩大项（S205） | 无 Work 来源追踪／遮盖／模型记忆隔离／全部聊天；管理 owner 继续有效。 |

### 核实台账：全部 delta-spec

独立脚本检查全部 27 条：MODIFIED／REMOVED 标题精确命中各自 canonical，ADDED 没有同名旧 Requirement，全部 MODIFIED 原 Scenario 标题集合均保留。随后逐条核对含义与消费者，不能只靠标题检查：新投影、机器 token、完整 Work 和成员授权分别落在最窄 area；THEN 是用户或接口消费者可观察结果。Q9 新增的 runtime 能力 MODIFIED 与 canonical 对比，仅改变一个受影响的 SlashPicker 承接条款，没有删去模型、features、路径分组或兼容行为。

| 原子 | canonical 锚及核实 |
|---|---|
| Δ01 auth REMOVED 数据面 owner 全隔离 | auth-tenancy.md:30–50 原 Requirement；Δ02 承接并明确改读规则，不双重并存。 |
| Δ02 auth ADDED 登录／成员／管理归属 | 无 token、token身份、非成员、metrics 原4情形保留，跨账号同群新增；与 D163/170/175 一致。 |
| Δ03 agents MODIFIED runtime 能力在线解析 | canonical agents-nodes.md 的同名 Requirement，7原 Scenario 全在；管理 location/source_group 留存、成员 SlashPicker 用 opaque skill_key，R4-W1 的 canonical 冲突关闭。 |
| Δ04 agents REMOVED owner 用户流 | canonical :334–363 原标题准确；由 Δ05 替换访问规则。 |
| Δ05 agents ADDED 当前成员用户流 | 原 token/resume/sync/断网/切账号五情形完整；节点/个人配置事件仍 owner，不全部公开。 |
| Δ06 agents ADDED 联系人与管理分开 | 新目录平行于管理API，无设备、多设备、公开资料字段与配置保留均可观察。 |
| Δ07 conversations REMOVED 同 owner Agent 私聊可读 | canonical conversations-messages.md:61–74；Δ11 明确撤回管理者特权并保旧实际成员。 |
| Δ08 conversations REMOVED owner 群治理 | canonical :255–294；Δ12 承接原八情形并改成员治理，无静默删除。 |
| Δ09 conversations MODIFIED Agent 托管图片 | canonical :14–29 原3情形完整；旧公开图片例外改为引用同 area 新资源 Requirement，与 D130–137 一致。 |
| Δ10 conversations MODIFIED 消息字段／游标 | canonical :31–59 原6情形保留；并发改普通direct复用、group/fork独立，附sender、纯人、显式group；原 run_state/page union保留。 |
| Δ11 conversations ADDED Agent 私聊无 owner 特权 | 投递记录和随机旧归属原情形都承接，Work记录不授权原聊天，Agent-only无强行真人迁移。 |
| Δ12 conversations ADDED 成员群治理 | 增加、重复、空请求、非成员、改名、Actor user_id、移除、解散原8情形完整，加跨账号和失效收敛；creator不可移除明确。 |
| Δ13 conversations ADDED 个人偏好／已读 | pin/mute、个人读边界和迁移各有观察场景；不改其他成员的状态。 |
| Δ14 conversations ADDED 托管附件成员读取 | 普通新旧附件、原地址、引用/fork旁路与独立关联均覆盖；不是仅隐藏Work按钮。 |
| Δ15 Work MODIFIED 聊天／全局轨迹分开 | canonical agent-work.md:12–26 原3情形完整，增加完整记录/链接/非owner持续查看；原执行明细 Requirement仍保留。 |
| Δ16 IM relay REMOVED owner配置边界用户流 | canonical gateway-relay.md:51–65 原标题；Δ20 替换当前成员收件，不改完整config为公开事件。 |
| Δ17 IM relay MODIFIED boundary durable ACK | 原持久化/重复/错误三情形保留；新增跨owner群真实node＋Agent成员身份，不再依赖conversation owner。 |
| Δ18 IM relay MODIFIED 授权标识持久化 | 原有授权/旧无标识两情形保留，增加所有选项、多人/离线/真实确认、global无卡；与D104–106一致。 |
| Δ19 IM relay MODIFIED 幂等／回执 | 原中继幂等、流式去重、回执推进保留；新逐节点独立投递，global Inbox完成含义未改。 |
| Δ20 IM relay ADDED 成员配置边界流 | 原在线和重连两情形完整；当前成员收到展示字段，Gateway写入的来源校验另由Δ17承接。 |
| Δ21 IM relay ADDED 机器HTTP凭据 | 非管理者聊天图像、断开失效/节点绑定、shadow代记、不能进管理入口均有消费者结果；与 D110–126 闭合。 |
| Δ22 UX MODIFIED 历史蒸馏选择 | 原5 Scenario完整：同Gateway锁、prompt格式、缺能力、prompt失败、普通侧栏；新增两scope与模式/管理资格边界，未以global scope误开global工作模式蒸馏。 |
| Δ23 UX MODIFIED slash发现与填写 | 原单聊/new、群/new、按Agent effort三个Scenario完整；新增跨owner候选/部分失败/缓存清理和同名异源不丢；执行文本原机制不变。 |
| Δ24 UX ADDED 导航／语言承接 | 新协作入口采用原导航和i18n，已有消息/附件继续可用；没有用新条目覆盖或删除旧页面能力。 |
| Δ25 Gateway routing MODIFIED 四步路由 | canonical同名原8 Scenario全部在，新增同群跨账号真实输入；global-agent链接指向canonical，未重写全局工作机制。 |
| Δ26 Gateway relay MODIFIED 授权决策中继 | 旧允许/拒绝两Scenario保留，新增原执行绑定和重复/过期请求不再执行；消费者仍是IM与用户。 |
| Δ27 Gateway relay ADDED 当前连接数据凭据 | 注册后HTTP、shadow双身份、连接恢复三Scenario；身份和数据分别认证不扩大owner JWT或runtime token，失败留durable待同步。 |

### 核实台账：M1、原型与实施前置

| 原子 | 核实证据与结论 |
|---|---|
| M1 唯一垂直交付 | D264–268 单M1，实际目录仅 .gitkeep；多人进入→聊天→跨节点执行→卡片/Work→旧数据完整交付，不横切数据库/API/前端多个M，也无并行文件交集。 |
| M1 reviewer退出 | D268 R1–R6＋全部18 Scenario；D272明确追加R7，runbook:92/117包含真实单Thread两scope/失败不建聊天、非owner slash/@/fork及同名候选。不存在“只能验原型”或漏Q9的退出条件。 |
| M1 worker退出 | D268 W1主体/成员/owner/Work分界和幂等，W2构建/双viewport，W3三账号三节点和迁移，W4既有能力；D272补相关旧组件回归。不是仅测试类型/函数步骤。 |
| 原型联系人／群／消息 | 静态读 sidebar、openModal、direct、create-group、send 及种子身份，确认只列本人聊天、可找人/Agent、只添自己的Agent、显式群语义与设备标识；演示固定响应不作真实路由证据。 |
| 原型批准与成员变更 | permission、approve、settlePermission 当前submitted→模拟确认；离线等待；移除Agent后不接新决定，已提交/已结束历史保留。D104–106 must-match闭合。 |
| 原型Work／配置 | Work主轨迹、子执行与source各自入口；source独立检查当前聊天成员，非owner无可写config；没有全部聊天导航或Work来源遮盖。 |
| 原型多聊天Skill | 底部/右键 enterDistill、distillReason、distillDialog、prefillDistill保留多选、source owner/同node/single、execution选择、两scope、preflight失败、预填不自动发送；purpose防普通私聊误复用。实际JSONL/写入明确是示例，D151+runbook承担正式链路。 |
| 原型类型筛选 | sidebar保留Agent网络分类、人/Agent/群；无网络样例显示空态，不移除原会话类型。 |
| 原型消息／聊天菜单 | openMessageMenu、copyMessage、branchMessage、message trace、memberPanel、removeMember与重命名/解散分支保留入口和当前操作资格；移动长按入口可见于事件绑定。原复杂Markdown/复制代码/附件依D223复用原组件，未要求示例HTML重做它们。 |
| 原型slash／草稿 | renderSlash仅示意静态候选及预填；drafts按身份＋聊天，saveDraft在切换中使用，direct恢复普通聊天草稿。D153–157与D222明确正式完整动态候选/键盘/effort/编辑状态不能按示例缩减。 |
| 原型Agent创建／管理 | Agent列表“新建”、本人节点、legacy管理分区及字段提示保留Config/Channels/Skills等入口；D224/228要求完整原表单，Overview/Sessions当前占位不扩实施。 |
| 原型账号／设备／Policies／退出 | 桌面用户菜单及手机我的，账号默认设备、设备管理/诊断、Policies、退出各有入口；深层实际执行仍由原页面，D225/runbook:92要求回归。 |
| 原型语言／边界 | 新入口英文字典、独立原型语言key、切语言saveDraft，正文/prompt原文保留；D211正式复用im_lang。D243–258精确区分入口资格must-match、视觉may-adapt、演示和完整后台out-of-scope。 |
| runbook拓扑／真实模型 | 核对 config/e2e/gateway.yaml 的两个Agent/webchannel与脚本真实选项；scripts/e2e-up.sh:184–225、252–258、375–382 重写隔离身份/workspace并导出端口。A两个、B零个、C一个，single/global都有；模型要求真问答，不把health或作者小探针当旅程。 |
| runbook起停／恢复 | --main-config为真实选项，额外Gateway独立cwd/node/workspace/PID；e2e-down清主栈，额外PID终止和wait；保DB重启与重置脚本区别明确，JWT及运行数据保持；无生产IM/第三方发信要求。 |
| runbook数据／资源／shadow | :94–117要求新旧附件原URL、图文跨owner、合法fork、配置边界、凭据失效、shadow两provider/旧owner恢复；DB和存储副本一起迁移回退。与D130–137/180–183闭合，未要求对真实生产数据试写。 |
| 整体可读性与分层 | D32关系图和两个编号决策先讲读规则，后节展开实际消费者；Changelog、对齐、branch声明、风险、代码/原型边界与运行命令齐。current specs保持未实施事实，M1骨架为空符合设计阶段。 |

### 架构进攻

| 角度 | 实际攻击与证据 | 结论及具体代价判断 |
|---|---|---|
| 一·职责归属 | 从IM app/deps/路由追会话仓库、事件和relay；从Gateway composition追shadow/附件和SDK。成员授权与窄commands投影在IM，节点实际能力/JSONL路径解析在Gateway，内核执行仍经agent.sdk；核对SPEC的IM不调用内核及产品包不互import边界。 | 新增责任自然归属现有层，没有反向依赖。若把source transcript移到IM读或放开完整配置会重生部署机路径/owner特例，现设计明确禁止；无需新执行服务。 |
| 二·新增层删除测试 | 逐项尝试删direct_key、participant状态、member查询、public contacts/commands、连接运行凭据、附件关联及持久批准状态：会分别造成并发多私聊、偏好互扰、读入口分歧、曝光管理数据、机器/人混用、地址旁路或重启丢决定。skill_key解决原实际去重消费者，而非为未来扩展建工厂。 | 每项都有当前需求或真实调用链驱动；没有角色SDK、策略引擎、身份服务或能力快照表。HMAC仅给现有去重需要的不透明标识，不引入持久映射表和同步维护税。 |
| 三·深度与复用 | 独立追原distill选择/preflight/RPC，原slash enabled/去重构建器，fork服务、UserMenu/Me/管理页和旧事件/relay/Work存储；新增投影集中隐藏config/capabilities差异，前端只收安全候选。 | R4-W1表明“只删字段”会让浅投影丢契约；现已保留需要的身份而不泄路径。其余用原页面/组件/RPC，未按prototype重造第二套简版IM；否则两套入口长期功能漂移的代价真实，D228已明确避免。 |
| 四·治本而非旁路 | 机器身份按当前连接建信任边界，普通上传撤StaticFiles，owner→member落服务端；distill先成功后建聊天，普通direct与特殊会话分开；Work本身不遮盖而链接独立授权。 | R4-W2已用会话用途修复误复用，未靠标题或列表次序补丁。无“让owner代读/让token进管理API/前端隐藏附件”的权宜路径；没有遗留需未来补权限框架的已知债。 |

### Issues

无未解决项。本轮两项实际发现 R4-W1、R4-W2 在报告落盘前已由作者修订并完成独立闭环，完整证据见本轮问题表；不将原型演示不足、实施步骤未展开或M1目录为空误报为设计缺陷。

### Recommendations

无新增建议。可以结束本轮设计审查循环，按M1、R7和runbook实施及验收；实现阶段保留本轮明确的旧功能回归范围。

### Author follow-up after Round 4

用户截图指出手机上下同时出现聊天／Agents 主导航。此前原型 CSS 在手机仍显示 .topbar，且用通用 detail 隐藏底栏，和原 AppShell 的桌面／手机分工不符；前次布局检查遗漏此问题。作者现已修正手机隐藏整个桌面顶栏、仅具体聊天隐藏底栏，Agent 资料与“我的”保留底栏，并统一 768px 分界、内容高度、抽屉偏移与安全区。design 的 AppShell grounding 与 runbook 同步；实际 Chromium 的五种宽度导航／高度断言和截图检查通过，原 AppShell 5 项测试通过。待同一 reviewer 对本次修订独立复审；先前接口与数据流设计未变。

## Round 5

### Metadata

- reviewer: `/root/design_review`
- review_mode: `delta`
- mode_reason: 本次是有界的原型响应式导航和布局语义修正；不改变成员／管理者边界、API、数据流或 milestone。逐项核实被修订的 AppShell grounding、原型显隐／断点／高度、语言入口和导航验收。用户随后新增的 Agent 页标签及设备 Heartbeat 反馈仍在作者修订中，不属于这次已完成的导航修订。
- started_at: `2026-09-13T22:01:35+08:00`
- completed_at: `2026-09-13T22:04:46+08:00`
- duration: 3m11s

### Verdict

Approved — 0 CRITICAL / 0 WARNING

移动导航修订可以接受。本轮结论只覆盖下列导航增量；不表示尚在处理的 Agent 标签／Heartbeat 反馈已关闭，也不表示真实产品已实现或验收。

### 历史问题闭环

| 历史项 | 本轮核实 | 状态 |
|---|---|---|
| 用户指出移动端上下重复主导航；Round 4 未发现此遗漏 | 当前 AppShell 源码确实只在非手机渲染顶栏，只在非具体聊天的手机页面渲染底栏。原型曾保留手机顶栏、又按通用 detail 隐藏底栏，与它不符。当前 prototype.html:13 已隐藏整个手机 topbar，:305 只在 detail 且 nav=chat 时设置 conversation-detail；Agent 资料／我的不再因 detail 丢底栏。design.md:235/241 和 runbook:119 同步。Round 4 对原型导航承接的判断在这一点上有遗漏，本轮明确纠正，历史正文不回写。 | closed |

### Coverage

- changed atoms：Round 4 的 C19/C20（实际 AppShell 与语言入口）、D18（原型承接边界）、M1 原型导航及 runbook 回归。
- 波及链：手机断点 → desktop topbar／mobile bottomnav → 列表与具体聊天状态 → 可用高度与抽屉／安全区 → 返回和“我的”语言入口。
- retained_from: Round 4 — 其余接口、成员／owner／Work规则、运行凭据、附件、蒸馏、commands及其27条delta与M1数据流没有因导航修订改变；本轮不重抄完整台账。新的 Agent 页标签／Heartbeat 反馈不引用这一继承声明视为已验收，待其明确修订后另核。
- 未运行真实 IM／Gateway，不以作者的 Chromium 断言、截图或原 AppShell 测试通过陈述替代以下独立源码核对。

### 本轮重查证据

| 原子 | 独立核实与结论 |
|---|---|
| 原导航真实判定 | src/IM/frontend/src/app/shell/app-shell.tsx:21–24 用 useIsMobile 与 /chat/:conversationId 匹配；:39–62 只在 !isMobile 渲染整个顶栏，:64–95 只在手机且非具体聊天渲染三项底栏。settings/agents 的列表／详情与 /me 不属于该会话路由，不能用任意 detail 状态隐藏导航。 |
| 断点 | hooks/use-is-mobile.ts:3–12 定义 <768px，样式 global.css 多处沿用 max-width:767px。prototype.html:13/15/17 的移动CSS、:31/407/410 的初始／导航／重置／身份切换均使用767/768，主导航显隐没有760–767分歧；剩余子执行自动滚动的旧数字见非阻断建议。 |
| 具体聊天与返回 | prototype.html:305 的 conversation-detail 仅为 detail && nav==='chat'；:407 的 chat/direct/source 进入具体聊天，back 将 detail=false，nav 到Agent及account不会有conversation-detail。:13 仅该类隐藏底栏。与canonical web-chat-ux.md:461–464 的进入聊天隐藏、返回列表恢复一致。 |
| 可用高度 | 原型桌面高度34px演示条＋48px顶栏＋layout(100dvh−82px)闭合；手机列表为36px演示条＋layout(100dvh−92px−safe)＋56px底栏及safe，具体聊天为36px演示条＋layout(100dvh−36px)。没有继续扣除已隐藏的48px顶栏，Agent与我的的内容高度仍预留底栏。 |
| 抽屉／输入安全区 | prototype.html:13 抽屉从36px演示条之后开始，聊天composer保留底部safe-area，列表底栏高度和padding包含同一safe-area。canonical具体聊天要求输入区安全留白，实际global.css:5203–5204也在conversation composer保留它；设计没有将演示条当正式产品导航。 |
| 语言入口可达 | 原MePage:132–151的语言区存在；原型:383 account()调用languageControl，:305底栏“我的”指向account，:407导航强制account进入内容，且其不触发conversation-detail。手机隐藏桌面UserMenu之后仍能进入语言设置；language动作仍saveDraft、持久化并重绘。 |
| 设计与验收 | design.md:10、235、241正确写明两个布局及详情差异；reviewer-runbook.md:119覆盖390/767/768、列表／Agent资料／我的／具体聊天／返回、残余空白／底栏遮挡和语言入口。已有UX delta“沿用现有导航”及canonical移动具体聊天Scenario足以覆盖，不需要新增相互重叠的导航Requirement。 |

### 受影响的架构进攻

| 角度 | 核实与结论 |
|---|---|
| 一·归属 | 导航显隐仍属于AppShell／原型外壳；具体聊天状态只提供是否隐藏底栏的依据，没让各Agent管理页分别维护第二套主导航。与实际源码分层一致。 |
| 三·深度与复用 | 修订沿用原AppShell的mobile＋conversation判定，通用detail仅负责列表／内容切换；不以全局隐藏所有详情底栏掩盖重复导航。没有新增导航组件体系或权限判断，后续实现可保留原AppShell。 |
| 四·治本 | 同步删除手机顶栏并修正可用高度、底栏条件和抽屉偏移，未只隐藏Chat／Agents文字留下48px空栏；修正针对实际布局原因，不产生新页面补偏移的维护债。 |

### Issues

无。

### Recommendations

- [R5-R1] prototype.html:407 的 child 自动滚动仍使用 `innerWidth<=760`。它不控制导航显隐，不阻断本轮修订；后续修改该原型时可统一为 `innerWidth<768`，避免761–767px手机宽度下子执行展开后不自动滚到详情。无需为此另起审查循环。

### Author Resolutions after Round 5

- R5-R1 已接受并修正为 `innerWidth<768`。
- 用户继续指出 Agent 六分区与 Nodes Heartbeat 缺失。作者按原页面实际 bundle 和当前组件补回管理者原分区／空态／双语，节点管理改为独立完整卡片页，展示计数、连接状态、ID／版本、别名保存、Heartbeat／最近错误及在线指定节点创建入口。非管理者公开资料与 Work 规则不变；运行快照为示例，不宣称实际后端动作已实现。
- design 承接矩阵和 runbook 已同步，相关浏览器旅程及原 NodesPage 4 项测试通过。请求对该增量独立复审，保留历史报告。

## Round 6

### Metadata

- reviewer: `/root/design_review`
- review_mode: `delta`
- mode_reason: 对上一轮明确留待修订的 Agent 分区和 Nodes Heartbeat 做有界复审，并关闭 R5-R1。改动是既有管理入口、原空态、节点快照及操作的原型承接，没有改共享接口、权限、数据流或实施拆分；检查相应真实消费者、管理与公开入口差异及手机导航影响。
- started_at: `2026-09-13T22:09:55+08:00`
- completed_at: `2026-09-13T22:13:05+08:00`
- duration: 3m10s

### Verdict

Approved — 0 CRITICAL / 0 WARNING

本次 Agent 分区及 Nodes Heartbeat 承接已闭合，R5-R1 也已关闭。结合 Round 4 仍有效的接口／数据设计及 Round 5 的导航修订，当前设计具备实施条件；本轮没有新增阻塞。原型中的节点心跳、别名和管理表单仍是示例，不代表真实后端或产品验收已完成。

### 历史问题闭环

| 历史项 | 本轮核实 | 状态 |
|---|---|---|
| R5-R1 子执行滚动旧断点 | prototype.html:471 的 child 分支已使用 innerWidth<768；独立检索不再存在760/761旧分界，未改变节点导航或执行行为。 | closed |
| 用户指出 Agent 六分区缺失 | 原 agent-detail-page.tsx:1635–1678 明确包含 Work（仅global）/Overview/Config/Channels/Skills/Sessions，并保留Overview/Sessions占位。当前prototype.html:425–431按管理者/模式构建同顺序标签与原空态，:18允许标签换行，双语标签与原字典一致。Round 4虽然识别出原占位实现，却未发现原型省略这两个入口；入口不可因内容是占位而消失，本次明确修正。 | closed |
| 用户指出设备页 Heartbeat 缺失 | 原nodes-page.tsx:284–300展示last_heartbeat_at、version和last_error，:65–129接收节点状态事件。当前prototype.html:439–447以独立nodesPage呈现完整节点卡片和心跳，而非原legacy缩略弹层；design.md:227明确它是连接快照，不是Agent定时任务。 | closed |

### Coverage

- changed atoms：Round 4 C18/C19、D18、原型Agent与账号／设备承接；Round 5的节点页手机导航波及链和R5-R1。
- 波及链：原Agent详情分区与字典 → 管理者/非管理者、global/single_thread的标签与内容；个人设备入口 → 节点快照及保存 → 在线指定节点创建 → 手机底栏及返回。
- retained_from: Round 4 与 Round 5 — 成员/owner/Work边界、运行凭据、附件、commands、蒸馏及其delta、M1数据流没有改变，导航仍只在具体聊天隐藏底栏。本轮只重查上述明确增量，不重新背书作者的浏览器或测试结果。
- 取证来自当前源码、canonical、设计和原型静态控制流；不连接用户提供的59770旧IM、不启动服务、不执行节点管理或Agent任务。源码src/tests没有本次修改。

### 本轮重查证据

| 原子 | 独立核实与结论 |
|---|---|
| Agent管理页真实分区 | src/IM/frontend/src/features/settings/agents/agent-detail-page.tsx:1639–1646逐项列出六分区，Work由work_mode=global控制；:1665–1678分别接Work、Skill统计、Overview占位、Channels及Sessions占位。新原型没有把Overview当公开资料，也没有实现原来未设计的Sessions。 |
| 管理／公开内容分工 | prototype.html:425–431将owner标签与公开标签分开：管理者完整原分区，非管理者仅资料与global Work；settings/channels/skills/占位内容均受owner分支约束，Work仍只global。与design.md:226及spec Q2/Q8一致，不因补页面放开管理配置或他人聊天。 |
| 单Thread和标签状态 | 原型:429仅global加入Work；:471选择自有single_thread进入settings、非管理者进入资料；agent-tab保持所选状态。原组件:1285默认config，single_thread未被导向不存在的Work；标签aria-pressed由当前agentTab计算。 |
| 双语与空态 | 独立读取i18n/en.json、zh.json的agents.detail.sections：Work/工作、Overview/概览、Config/配置、Channels/通道、Skills/技能、Sessions/会话及两条空态原文。prototype的sectionLabels和t映射一致；两占位内容采用原含义，不把“没有内容”误呈现为加载失败。 |
| 手机分区与外壳 | prototype.html:18增加subtabs flex-wrap，:333仍只有nav=chat且detail时设置conversation-detail；Agent列表/资料不隐藏手机底栏，补回六标签未恢复手机桌面顶栏。沿用Round 5实际AppShell依据。 |
| Nodes真实数据源与字段 | nodes-page.tsx:39–42调用listNodes；im-settings-api.ts:75起指向现有nodes接口；IM routes/nodes.py:133–163返回node_id、owner、node_name、status、last_heartbeat_at、agent_count、version、alias、last_error等。新design:227明确继续用真实查询与WS；原型nodeProfiles固定时间只作示例。 |
| Heartbeat与定时任务区分 | nodes-page.tsx:287–288将last_heartbeat_at格式化为时间，:294–300只在有last_error时显示错误；canonical agents-nodes.md:473–486以node.register/node.heartbeat及超时状态事件定义连接心跳。Agent的HEARTBEAT.md／定时任务为另一既有入口，新设计没有混为任务配置或改变执行机制。 |
| 实时恢复与管理边界 | nodes-page.tsx:65–129接node.status_changed并更新status、心跳、错误，恢复时invalidate，保留编辑草稿；canonical规定仅owner收完整节点状态。design:227及runbook:121明确复用这些现有行为，与公开联系人窄在线状态的分工不冲突。 |
| 节点列表和快照呈现 | 原nodes-page.tsx:163–208为四项计数，:234–258为名称/ID/状态/Agent数/版本，:265–301为别名/实时快照。prototype.html:439–447逐项有对应，离线示例保留末次heartbeat并显示连接错误，无设备账号有空态。固定示例未被当成正式统计实现。 |
| 别名保存 | 原nodes-page.tsx:55–62判断dirty，:131–143保存并刷新节点/Agent设备标签查询，:306–335显示状态和保存操作。原型:444/471/474提供独立节点输入、dirty提示、合法值保存及已保存反馈；保存只改当前账号所示节点的示例alias。正式页面完整查询/保存行为由D227/229继续承接，未要求照原型DOM重写数据层。 |
| 指定在线节点创建 | 原nodes-page.tsx:319–326只在online呈现/settings/nodes/{id}/agents/new；canonical agents-nodes.md:201–208要求绑定owner＋在线节点。原型:444按钮携data-node，:471存createNode，:460新建表单将该在线节点选中；无节点和离线节点不冒出可创建入口，后台仍按既有创建流程。 |
| 独立节点页面与返回 | 原型:333为nodesPage路由分支，:334在nodes不绘侧栏，:471的设备管理入口进入nav=nodes、detail=true。:442返回“我的”，底栏把nodes高亮到account但不隐藏；与原NodesPage:170–181移动返回/me和AppShell非聊天保留底栏一致。 |
| 设计／M1／runbook投影 | D226–229明确完整原管理分区、原空态、节点快照与真实查询/WS复用；D263仍将入口和操作资格列must-match。runbook:121补逐分区、single_thread无Work、双语、节点字段、别名、指定节点、离线末次心跳和WS更新，纳入既有R7/W4。 |
| canonical增量范围 | 本次恢复现有页面入口和既有节点状态契约，不改变config、channel或node API；现有UX delta的原能力承接与canonical节点心跳/创建规则可直接用于验收，无需新增重复Requirement或重写Gateway协议。 |

### 受影响的架构进攻

| 角度 | 核实与结论 |
|---|---|
| 一·归属 | Agent分区留在原Agent详情，节点连接诊断留在Nodes；Heartbeat时间来自节点状态，不借用Agent任务调度。公开Work/资料与个人管理继续分离，没有因补入口造成跨层或权限倒置。 |
| 二／三·必要性与复用 | 原型独立nodesPage让现有完整卡片及操作可被评审，正式产品仍复用现有NodesPage/listNodes/updateNode/user stream；六标签直接对应原组件，不新增通用页面引擎、第二套管理API或节点监控存储。 |
| 四·治本 | 补回被缩略弹层遗漏的设备快照与创建/保存链，而非仅加一个“Heartbeat”文本；占位页恢复入口而不虚构已实现的功能。新设计明确原型固定时间不可替代真实WS快照，避免实施时把示例当监控数据。 |

### Issues

无。

### Recommendations

无新增建议。R5-R1与本轮两项用户反馈已闭合，可以继续实施阶段；保留R7/W4中的原页面逐项回归要求。

### Author follow-up after Round 6

用户要求列清新增／重新设计与原有做法，并在原型中提醒。作者增加仅供评审的“改动说明”及 19 项清单；页面和弹窗按功能来源标记新增／调整／沿用原有，独立标明简化示意。清单首段明确本 HTML 独立绘制、正式产品不据此重做原页面；标注可关闭，操作不重绘底层表单，已验证未保存输入保留。design 增加分类范围与验证记录。未改产品行为、接口、数据流或权限规则；请求同一 reviewer 核对分类与标注是否准确、不将简化示意误当目标设计。

## Round 7

### Metadata

- reviewer: `/root/design_review`
- review_mode: `delta`
- mode_reason: 用户要求说明哪些新增／调整／沿用；实际增量为原型评审清单、页面/弹窗标注及显隐工具。逐项核对19项分类与既有实现/已批准设计，检查标注映射、简化示意和表单保留；不重审未变化的产品API、权限和数据流。
- started_at: `2026-09-13T22:32:41+08:00`
- completed_at: `2026-09-13T22:36:06+08:00`
- duration: 3m25s

### Verdict

Approved — 0 CRITICAL / 0 WARNING

19项来源分类及原型标注与当前设计一致，能够区分正式增量、既有能力与示例绘制范围。本轮不增加正式IM的说明条或提示层，也不扩大“沿用”区域的重做范围。当前设计仍具备实施条件。

### 历史与本轮校正

| 项目 | 本轮核实 | 状态 |
|---|---|---|
| Round 6 已关闭的管理分区与Nodes反馈 | 新标注把原Overview/Sessions明确列为既有空态，Config/Channels/Skills列为沿用且简化示意，Nodes及Heartbeat列为原页面和示例数值；没有撤掉上一轮恢复的入口。 | closed |
| R7-R1 批准说明避免把submitted称为已生效 | 本轮初始reviewEntries.approvals中文写“首个已提交决定生效”，会混淆既定两阶段状态；作者在报告前改为“首个提交的决定锁定，设备确认后更新结果”，英文同步。当前文本与design.md:106–108的submitted/permission_resolved分工一致；卡片实际模拟状态未改。 | closed before report |

### Coverage

- changed atoms：Round 4 D18及原型边界，Round 5/6原页面承接的解释层，19项reviewEntries与页面/弹窗映射。
- 波及链：用户查看改动说明 → 新增/调整/沿用分类 → 当前页对应标注 → 独立简化标记 → 关闭标注但保留清单与底层未保存表单。
- retained_from: Round 4、Round 5、Round 6 — 成员/owner/Work、机器凭据、附件、commands、蒸馏、27条产品delta、M1及原导航/管理页规则均未因本轮标注改变；相应既有源码证据继续有效。这里的“沿用”描述功能和页面来源，不表示所有后台消费者零改动，design.md:213明确仍要适配成员与数据读取。
- 独立检查当前reviewEntries得到19项：new=3、changed=6、kept=10；每项如下表核对，没有以作者的浏览器通过陈述代替分类核实。

### 分类逐项核实

| key／分类 | 核实证据与结论 |
|---|---|
| contacts／新增 | 原ConversationSidebar:66–109只有既有建群入口，:20–27的direct-user筛选尚未启用；新联系人搜索与人际私聊入口由design:86/169及spec Q4/Q6驱动。不是宣称原消息组件首次存在。 |
| public_profile／新增 | 原AgentDetail使用管理配置数据，原agents接口owner约束；新公开简介/管理者/设备窄投影和管理表单分开（D86/128）。明确新增“他人Agent公开资料”，未把原管理页标成新增。 |
| work_link／新增 | 独立检索现有chat前端未见“查看Work”或view=work消息链接；原型新增消息回复到Work入口，用户Q9原话也明确认可该入口。分类对象是链接，非整个Work功能。 |
| directory／调整 | 原Agents列表/rail存在，数据原为自有Agent；新可发现同IM Agent并区分“我的”（D86、公开目录接口）。标为范围调整而非新造列表准确。 |
| chatlist／调整 | conversation-sidebar.tsx:83–100已有搜索/过滤，:139–150呈现原类型；本次成员范围及人际分类变化明确。原网络分类仍保留，未把整个列表当新设计。 |
| group／调整 | 原new-group-modal和group-settings已有Agent群与治理入口；本次加入真人、跨账号/节点及退出规则（D94–98）。保留群基础，只调整协作规则。 |
| approvals／调整 | 原卡片与原选项存在，新的共同操作/真实请求绑定属于D106–108增量；本轮校正后说明首决定锁定、节点确认后更新，global仍无卡。 |
| work／调整＋简化示意 | 原AgentWorkPanel和主子轨迹存在，目标放开登录global GET并保原聊天检查；说明明确轨迹/排版只是示意，不把画出的样例作为原Work替换设计。 |
| preferences／调整 | 当前DB会话字段共享pin/mute/unread；D180–184改为每人独立。文本说明功能原有、归属改变，与实际差异一致。 |
| chat_base／沿用＋简化示意 | MessagePane原消息/附件/复制/fork/draft/slash/inline trace均已独立核对；D155–161、原矩阵仍要求适配真实成员消费者。标注说复用原组件且示例未展开，不宣称后台无需修改或示例等于完整组件。 |
| distill／沿用 | 原侧栏选择、同Gateway和两种Skill scope存在，D151–153/Q9限定single_thread及原管理资格；说明明确global Agent蒸馏未设计，不误当新增功能或已支持全局模式。 |
| settings／沿用＋简化示意 | 原Agent完整config表单继续使用，当前简版不得替换；与D242/245及原agent-detail配置区一致。 |
| channels／沿用＋简化示意 | 原AgentChannelsPanel有真实连接/凭据/诊断功能；当前标注限定仅展示入口，不能据此删除原内容。 |
| skills／沿用＋简化示意 | 原Skill选择与AgentSkillsUsagePanel存在，示例列表/计数明确为样例；没有宣称生成或统计真实结果。 |
| placeholders／沿用 | 原agent-detail-page.tsx:1669–1678有Overview/Sessions占位；标注保原入口和提示，准确解释为何该页暂时没有业务内容。 |
| nodes／沿用 | 原NodesPage的完整字段、last_heartbeat_at、alias保存、在线节点创建已在R6追到真实查询/WS；标注指出当前数值演示，未将连接心跳说成新增任务调度。 |
| account／沿用＋简化示意 | 原UserMenu/Me/Account/Nodes/Policies/登录退出均存在，标注范围覆盖语言与设备绑定，并强调这里未完整展开；没有增设账号/权限体系。 |
| create_agent／沿用＋简化示意 | 原在线所属节点创建、workspace和模式流程存在；标注明确完整原表单复用、本示例不执行创建，和原型入口边界一致。 |
| navigation／沿用 | 原AppShell桌面顶栏、手机底栏/Me及具体聊天隐藏已在R5核实；标注没有将修正后的布局当新导航方案，也没有恢复已撤回的重复导航。 |

### 标注映射及交互边界

| 原子 | 实际核实与结论 |
|---|---|
| 来源分类与示例程度正交 | prototype.html:333–358的kind决定新增/调整/沿用，simple独立决定“简化示意”。Work是调整但可简化，Config是沿用但可简化；不会把“独立画过”错误等同“正式全部重做”。 |
| 页面与标签映射 | :360–375按chat/group/human、Agent所选标签及owner、nodes/account选择条目；自有settings/channels/skills/占位和他人公开资料不混。消息Work链接单独标新增，卡片单独标调整。 |
| 弹窗映射 | :499–504将新聊天标contacts、建群/邀请/解散标group、distill标沿用；绑定/退出/account、创建、复制/fork、legacy管理分区映射到各自来源，不把所有弹窗统称新设计。 |
| 关闭标注不关闭清单 | CSS :21仅隐藏#app及非change-guide弹窗的注释；说明面板自身明确排除。:377–379按同一reviewEntries生成19项清单，关闭页面标注后仍可读取全部分类。 |
| 表单保留 | :528 change-guide只saveDraft并renderModal，不重绘#app；:532 review-toggle仅改showReviewNotes和body class后return；不调用render/renderReviewNotes或重建原表单。关闭说明只清overlay，原页面未保存input仍在。这个保证不被扩大为所有既有modal切换都会保留表单。 |
| 仅供评审 | D213/221/223及说明面板首尾明确HTML独立绘制，正式产品复用沿用区域；身份条、离线开关、固定回复和评审标注均不进入IM。被撤回的常驻同步提示/会话数/重复导航没有因分类再成为需求。 |
| 双语与设计投影 | 每个reviewEntry title/body和reviewKinds均有中英文；reviewText随当前language选择，页面和说明共用同一来源。D215–219三类范围与19项对应，原承接矩阵及must-match继续管正式结果；本轮无需新增产品delta或后端接口。 |

### 受影响的架构进攻

| 角度 | 核实与结论 |
|---|---|
| 一·归属 | 来源说明放独立原型的reviewEntries/评审层，正式IM和管理页面不承担解释开发过程的责任；不会把implementation信息塞进正式用户流程。 |
| 二／三·必要性与复用 | 用户明确要求“列清并在原型提醒”；同一19项数据同时生成完整清单和页面/弹窗标注，避免各处复制说明后漂移。未引入通用文档系统、权限层或新导航架构。 |
| 四·治本 | 解释的是具体功能来源与简化程度，明确原页完整复用；不是用一句“原功能都还在”掩盖示例与目标差别。标注开关直接改CSS可见性，避免为评审开关重建表单。 |

### Issues

无。

### Recommendations

无未解决建议。已在报告前消除批准说明的两阶段歧义；可结束本次解释层复审，实施仍以正式设计与既有能力承接矩阵为准。


## Round 8

### Metadata

- reviewer: /root/design_review（沿用原 reviewer）
- review_mode: full
- mode_reason: 用户要求对当前整体方案判断能否开发；R4 后数轮补回原功能、导航及设置层级，局部结论不足以替代一次整合后的完整判断。本轮重查五类承重原子与四个架构角度，复用已经独立追通、当前源码未变化的调用链，并重新核实关键入口和新 UI 承接；不只关闭最新样式反馈。
- started_at: 2026-09-13T22:58:45+08:00
- completed_at: 2026-09-13T23:09:25+08:00
- duration: 10m40s

### Verdict

Approved — 0 CRITICAL / 0 WARNING（未解决）

当前完整方案可以交给 change-orchestrator，按唯一 M1 开发。联系人、多人群、跨 Gateway 消息与附件、批准决定、聊天与 Work 的不同读取规则及旧数据承接均有具体落点；原 IM 能力现在由逐项矩阵和原页面复用要求承接，不能再把独立原型的字段子集当成重做范围。本轮未发现必须再补设计才能实施的具体问题。

这是设计批准，不是实现、真实模型旅程、迁移演练或部署通过。本轮只读产品源码与设计产物，没有启动产品服务或执行产品旅程；作者的 Chromium、原基线测试和模型探针记录只分别支持原型/原代码/调用前置，不被提升为多人产品已经完成的证据。

### 历史问题与用户反馈闭环

| 项目 | 当前直接证据与结论 |
|---|---|
| R1-C1 人与机器混用 | design:110–128 保留当前注册连接运行凭据及有限数据入口；真人 JWT 仍只有本人身份。composition.py:659–694 的真实共享 provider 正是实施要拆的入口；未恢复 owner 代理所有聊天。closed。 |
| R1-C2 普通及历史上传公开 | design:130–139 覆盖 uploads、浏览器鉴权 blob、Gateway、合法 fork、历史别名和 DB/原字节配套回退；app.py:446–448 的公开 StaticFiles 明确撤除。closed。 |
| R1-W1／R7-R1 批准两阶段 | design:104–108 保留 submitted 后真实确认才 resolved；prototype 的 approvals 标注明确“首个提交的决定锁定，设备确认后更新结果”，approve/settlePermission 仍为两阶段且离线等待。closed。 |
| R1-R1 创建者保护 | design:96 明说当前服务端没有 creator 保护，本次补齐；conversations.py:588–613 的删除语句无此校验，现状没有再次失真。closed。 |
| R1-R2 链接 | routing-delivery delta 的 global-agent 链接仍指向 canonical，当前路径可解析。closed。 |
| R1-R3 旧 Agent-only／随机 owner | design:182–185 区分实际真人旧访问、Agent-only、随机 owner；不强行把 Agent creator 或所有 Agent owner 加为真人成员。closed。 |
| R2-W1 shadow 身份前置 | design:116–117 明确 owner JWT 独立 client 查询 /me、/nodes，保留身份缓存及 recover_owner；运行凭据 client 只做数据。shadow_sync.py:591–638 的真实前置与失败恢复未被省掉。closed。 |
| R4-W1 Skill 去重 | design:155–159 明确 opaque skill_key、node＋location、无 location 退化、fromAgents 聚合和异 key 同名保留；两个对应 delta 仍保留管理 location/source_group。closed。 |
| R4-W2 普通私聊误复用 | prototype:543 的 direct 排除 purpose；branchMessage/prefillDistill 仍分别赋 fork/distill，返回普通私聊读取独立 drafts。design:94/153 明确特殊会话无 direct_key。closed。 |
| R5-R1 断点及重复导航 | prototype 所有相关分界为 767/768，child 分支也用 innerWidth<768；AppShell:21–24/39–64 的原导航规则与 design:268 一致。只有具体聊天隐藏手机底栏。closed。 |
| R6 Agent 六分区与 Nodes | prototype agentPage 保留管理者六分区、single_thread 无 Work、Overview/Sessions 原空态；nodesPage:492–500 有计数、ID、别名、连接 Heartbeat、版本、错误及在线节点创建。design:250–251 与 runbook:121 要求原页面真实功能继续回归。closed。 |
| R7 来源分类与简化说明 | prototype reviewEntries:337–357 仍为 3 新增、6 调整、10 沿用；simple 单独说明示意程度，说明开关只改 class。design:213–223 禁止按示例删原功能，评审标注不进入产品。closed。 |
| 最新 UserMenu／Me 反馈 | design:231–237、273、288–289 与 prototype:334–335/501–514 一致：原菜单图标、桌面 EN 分隔 中、手机分段语言、纵向独立设置行、退出分组，设备明细在 Nodes。作者本轮进一步将这些已确认形态设为 must-match；未保存表单不应因评审标注开关重建。closed。 |

### Coverage

完整读取当前 spec v4、design、8 份 delta、runbook、原型主要渲染及事件处理、历史 Round 与 resolutions；核对 M1 骨架、current canonical 和真实源码。检查时 checkout 为 main，HEAD 基线 eb4da2815，src/tests 没有本 unit 产品实现修改；保留其他 dirty/untracked 内容。

本轮台账逐项覆盖：12 条现状表断言及 10 条旧能力/消费者断言；2 个编号决策及 18 个补充承重决策；8 Requirements、18 Scenario、6 用户场景、Q1–Q9、3 范围/非目标项；27 个 delta 条目；唯一 M1、原型契约和实施前置。下文 design/spec 行号指当前 unit 文件；源码短路径相对仓库，未写前缀的 IM 源码在 src/IM，前端组件在 src/IM/frontend/src。

### 核实台账：现状与真实入口

| 原子 | 核实动作、证据与结论 |
|---|---|
| C01 账号、Gateway、Agent 个人归属 | app.py:449–458 注册实际 routers，api/deps.py:52–76/94–105 注入真实仓库；db.py:55–99 与 users.py:73–87 保留 owner，真人创建 owner=id。多节点 owner 无人机一对一前提。 |
| C02 多方成员可复用 | conversations.py:89–99/618–650/775–795 按稳定 users/Actor 写入和读取 participants；db.py:125–131 成员表可表达跨账号。design:20/94 复用这条路径。 |
| C03 聊天 HTTP 现为 owner | web_im.py:195–208/424–434/497–508、messages.py:595–604、message_images.py:19–25 都是实际 owner 入口；成员改动覆盖这些 HTTP，非仅侧栏。 |
| C04 当前事件成员查询与缓存 | app.py:319–336 组装 EventRepository→notify→pump，events.py:269–302 的 replay 联结当前成员，user_stream.py:189–203 先缓存 recipients。design:98 要求投递时重验，修到实际泵而非只改重放 SQL。 |
| C05 多 Agent relay 已存在 | messages.py:483–507→WebIMService:636–645→relay_service.py:284–296 每 Agent 解析 node；:273–282 的纯人兜底是真实待改分支。design:104 明确纯人只持久化/广播。 |
| C06 Agent 自动查询范围 | work_conversations.py:48–65/151–172 查 profile.node、global_main session、Agent member；design:24/104 不因人的 Work GET 开放而扩大 Agent Inbox。 |
| C07 Work 存储与 owner 门槛 | routes/agent_work.py:13–18 helper 被 :22–85 GET 使用，写操作亦复用；work repository:52–61/393–477 检查根与 sessions、投影 turns/items。design:143 只移除 GET owner，保留目标与 session 约束。 |
| C08 偏好是会话共享列 | db.py:35–53、conversations.py:419–454 PATCH 为会话级；design:180 将权威改为 participant，保留插入/占位回滚语义和显式读边界，不只在 UI 分两份。 |
| C09 建群目前只选自有 Agent | new-group-modal.tsx:15–21/84–85 与 ChatWorkspace:1324–1330 的参数真实只含 Agent；design:94–96 扩展真人和本人 Agent，显式 group。 |
| C10 Gateway HTTP 当前真人 token | personal_assistant/gateway/composition.py:659–694 把 token_getter 注入 shadow 和 image fetch；reply_images.py:326–341 同消费。design:112–117 承认并改变此实际 wiring。 |
| C11 普通上传实际公开 | use-attachment-upload.ts:25–35→messages.py:391–419→app.py:446–448 StaticFiles；design:132–139 覆盖创建、访问、旧地址和文件承接。 |
| C12 配置边界有额外 owner 阻断 | config_boundaries.py:49–76 查询 conversation.owner、锚点、Agent member/node；WS 注册层另校验 node owner（sessions.py:251–274）。design:126 删除前者跨 owner 限制，保留真实节点/归属/锚点，不把配置公开。 |
| C13 侧栏及蒸馏入口 | conversation-sidebar.tsx 的底部、选行和右键（:156/184–236/287），distill-selection.ts:7–11，ChatWorkspace:1008–1028/1055–1069 是实际选择→preflight→预填主链；design:151–153 保留。 |
| C14 蒸馏 owner 消费者 | web_im.py:244–344 依次读 source chat、source profile、execution profile，成功 RPC 后才建固定 node 聊天；conversations.py:693–733 的 source 解析不会任取多 Agent 群第一项。成员变化只放开 source chat，两个 Agent owner 和模式限制仍清楚。 |
| C15 Slash 的管理信息依赖 | ChatWorkspace:409–469 从自有 Agent live config/capabilities 取候选；slash-candidates.ts:90–95 的 enabled 与 :101–133 location 去重是实际消费者。design:155–159 的成员投影和 key 保留它需要的信息，不公开完整 config。 |
| C16 消息菜单/fork | MessagePane:1207–1223 完成/direct/kernel 锚/online 资格，:1490–1540/1712 原动作入口；web_im.py:353–417→WebIMService:341–560 为服务路径。ChatWorkspace:508/541–563 的自有列表状态改由公开状态承接，原操作资格继续有效。 |
| C17 聊天元数据与群治理 | direct-conversation-menu:64–90 改名/配置；group-settings:247/258/326 移除/配置/解散。design:96/161 明确共享标题、个人偏好、创建者保护及退出，原入口未消失。 |
| C18 Agent 创建与六分区 | agent-detail-page:1640–1678 原六项/两个空态、:1739 起完整配置/Heartbeat/Cron、:2000 保存；agents-list:57、agents-rail:52、nodes-page:323 的创建入口保留。design:250 不以原型删字段。 |
| C19 Nodes 快照与操作 | nodes-page:39–42 query、65–129 WS 更新、131–143 别名保存、284–301 last_heartbeat_at/version/error、319–326 在线指定节点创建；routes/nodes.py:133–163 返回 owner 节点字段。Heartbeat 确是连接时间戳，非 Agent 定时任务。 |
| C20 账号/策略/语言/退出 | UserMenu:157/167/181/190–220 是账号/设备/策略/语言/退出，MePage:88/116/132–185 为独立行/分段语言/退出；AccountPage:178/200 为显示名/默认节点。router:31–77 连到真实页面，Notifications 旧入口确已移除。 |
| C21 草稿、富消息及公开投影 | i18n/index.ts:7–20/41–46 使用 im_lang；MessagePane 保留分页、富消息、附件和原输入行为。users/password_hash 与 agents 管理响应不能公开，design:128/171–172 限定目录，:245–252 列出完整回归而非新实现证明。 |
| C22 响应式与设置层级 | AppShell:21–24/39–64 仅桌面 topbar，mobile 具体聊天隐藏 bottomnav；use-is-mobile.ts:4 为 768。UserMenu:190–214 原文字分隔语言、MePage:132–170 原分段控件；当前 prototype 的 render/account/languageControl 与 design:268/273/288 对应，不再双主导航或设置混放。 |

### 核实台账：决策

| 原子 | 完整、自洽、必要性及落点 |
|---|---|
| D01 编号决策 1 | design:50–57 与 Q8：聊天 member，global Work 登录完整读，原聊天/附件链接重新检查；没有 Work 来源遮盖。 |
| D02 编号决策 2 | design:59–63 与 Q7/Q8：侧栏仅本人参与，联系人发现不等于浏览旧聊天；没有“全部聊天”产品入口。 |
| D03 目录与管理分离 | design:84–88/128/171–172：可登录真人/非 stale Agent，稳定 user_id、名字/ID 查询、固定排序分页、空态，owner 仅辨认；原管理 API 不公开。 |
| D04 direct/group 身份 | design:94/153：Actor user/agent，不混 kind=human；普通 pair 唯一 direct_key，group/fork/distill NULL，事务/唯一约束处理并发，旧无证据不回填。 |
| D05 群治理 | design:96 拍定添加真人/自己 Agent、移除非创建者、退出/创建者解散和新增成员历史；无额外角色表。 |
| D06 成员失效 | design:98/159：原成员只收 ID 失效、送达时当前成员、恢复先 sync，移出清正文/附件/commands；在线和离线链闭合。 |
| D07 个人偏好/已读 | design:92/180–184：状态归 participant，首插/重传/占位回滚、单调 message 边界和并发新消息保留；个人结果不广播成共享状态。 |
| D08 sender 与 relay | design:102–104：真人由 JWT，机器由节点运行主体；逐 Agent 真 node，纯人不兜底，全局自动收件范围不变。 |
| D09 批准请求 | design:106–108：原六元执行身份、原子 pending→submitted、记录决定者、真实确认 resolved、离线/重启同请求重试、已终结不生新工具；所有原选项可由真人成员使用。 |
| D10 运行凭据 | design:112–128；sessions.py:251–274/339–383 存在 owner 注册、当前连接和 ACK。内存不可猜 token、替换/断开/重启失效及允许入口都拍定，禁止走账号/配置/人流。 |
| D11 shadow 双身份 | design:116–117/186 对应 shadow_sync.py:591–638/163–168 的真实 owner 校验、缓存与旧 saga 恢复；数据独立 client，身份失败 durable 保留，不降级本地 owner。 |
| D12 附件统一 | design:132–139：新上传 conversation、browser blob、Gateway agent_id、合法引用/fork、旧 alias/孤立文件及原字节备份回退均有消费出口；不把 URL 当授权。 |
| D13 Work/公开状态刷新 | design:143–147：global GET、root/session 校验、非 owner 可见页轮询/隐藏暂停/恢复刷新/失败重试；链接独立授权，完整 node 配置不广播。 |
| D14 原 single_thread 蒸馏 | design:151–153：source chat member，source/execution 均 owner+single_thread+同 node，两 Skill scope，Gateway preflight/prompt 后才建固定 node 独立会话；失败不造空聊天。 |
| D15 成员 commands | design:155–159：member→真实 node 的原 config/cap RPC→窄响应；enabled/逐 Agent 完整描述/skill_key/部分不可用/账号会话缓存与失效清楚，GET 不改配置，无新 Gateway 协议。 |
| D16 原消息资格 | design:161：公开在线供头部/@/fork，fork 仍完成 direct/合法锚/原 node，source member；私聊改名仍改该聊天共享标题。 |
| D17 一次性旧数据承接 | design:182–187：旧 ID/实际成员/归属不改写，旧 owner 个人状态保真，Agent-only/随机 owner 分类，不明确则停；DB/原存储与旧版本配套回退，无长期双写。 |
| D18 原能力完整保留 | design:227–253：8 行能力矩阵与 current spec/原实现共同约束，覆盖聊天/Skill/管理/账号；原型缩略内容不是功能替换清单。 |
| D19 来源解释层 | design:211–223、prototype reviewEntries：19 项复用一份说明生成清单/页注，simple 与新增分类独立，关闭不重建表单；只供评审，不给正式产品加过程提示。 |
| D20 设置与导航形态 | design:231–237/268/273/288–289：独立设置行、语言与退出分区、Nodes 详情，原菜单图标/桌面文字/手机分段为 must-match；只余字号间距可适配，不让 worker 猜是否整页重画。 |

### 核实台账：首文档要求

| Requirement | 原文要求与设计承接 |
|---|---|
| SR1 | “无需 Gateway 即可注册登录并查找联系人”→design:84–88/171–172，原 auth 与 B 无设备流程。 |
| SR2 | “跨账号私聊并持久回看”→design:94/98/102/173–175，稳定 pair、本人 sender、成员持久历史。 |
| SR3 | “一个人可以管理多个 Gateway 及其 Agent”→design:75/112/179/251，不新增一对一或共同资产。 |
| SR4 | “直接私聊其他人管理的 Agent”→design:86/94/112–126/155–161，图文、旧候选与 fork 也有可用路径。 |
| SR5 | “同一群协作”→design:96–108/126，混合群/真实多节点/当前成员交付。 |
| SR6 | “遵循工作模式且不新增人员权限配置”→design:106–108，global 无卡、single_thread 所有选项及一次实际决定。 |
| SR7 | “聊天按成员可见，全局 Agent Work 详情完整可见”→design:52–57/132–147，两类读与链接分开。 |
| SR8 | “既有使用数据和工作能力在升级后保留”→design:182–187/241–253/305，数据副本演练与逐项旧能力，不把全局聊天蒸馏算承接。 |

| Scenario（按 spec 顺序） | 可观察结果的设计落点 |
|---|---|
| S01 无 Gateway 开始沟通 | 联系人目录及已有注册登录不绑机，runbook B 零节点。 |
| S02 无匹配联系人 | design:171 名字/ID 搜索与原型空态不产生错误聊天。 |
| S03 两账号实时沟通 | direct 唯一、JWT sender、member stream、持久历史和重新登录。 |
| S04 同人两设备 | 保留 owner Nodes 页，runbook A1/A2 独立 node/config/workspace。 |
| S05 不可修改别人配置 | 原 owner 管理 API 与新公开目录/commands 分离；非 owner 无可写页。 |
| S06 一台离线 | 每 Agent 独立 relay、公开状态，未执行不显示完成，批准待确认。 |
| S07 跨管理归属交办 | member 私聊＋机器数据身份，Agent owner 无须入会话；图文/命令/fork 承接。 |
| S08 混合项目群 | 显式 group，成员真人及各自管理 Agent，跨账号/node 不拒绝。 |
| S09 不同成员共同交办 | 真实 sender、原触发策略/逐节点执行，当前成员正式交付与历史。 |
| S10 群名/成员变化 | design:96–98 改名、添加、移除、退出、创建者解散及在线/重连失效。 |
| S11 global 无卡 | 保原自动审批/主动沟通，不加工具卡或越过原判断。 |
| S12 single_thread 成员任意选项 | design:108 包括长期允许，操作不转成 config 管理权。 |
| S13 同卡多人操作 | design:106–108 原子首决定、submitted 与确认分开、原请求持久重试不重复执行。 |
| S14 未参与者不可读私聊 | 聊天/历史/图片/普通新旧附件一并 member，Agent owner 无特权。 |
| S15 未入群不可读 | 当前 member 检查覆盖读取/发送/事件，ID-only 失效不泄正文。 |
| S16 完整 Work | 登录 global 主/子执行记录完整、无来源遮盖，非 owner 持续刷新。 |
| S17 Work 不授予原链接资格 | 原聊天与资源处理器自己鉴权，Work 不代理源字节或传凭证。 |
| S18 原用户继续使用 | design:182–187 旧数据，245–252 蒸馏/复制/fork/slash/草稿/附件/群管理/Agent/账号/语言；M1 R7/W4 与 runbook 验真，原型只示意。 |

### 核实台账：用户意图与范围

| 原子 | 覆盖/不冲突/不越界 |
|---|---|
| 用户场景 1 无机器同事 | 原 auth＋contacts＋纯人聊天/混合群，无绑定前置，空态明确。 |
| 用户场景 2 一人多机 | 沿用 owner 多节点，与他人的 Agent 可协作；离线隔离保留。 |
| 用户场景 3 找 Agent | 普通联系人私聊稳定，owner 只能看已记录 global Work，不可看原私聊。 |
| 用户场景 4 项目合作 | 保既有触发、全体人输入和多 Gateway 交付；群治理无新角色。 |
| 用户场景 5 共同审批 | 原两模式，所有真人可按卡片各选项，正确请求只生效一次。 |
| 用户场景 6 聊天/Work | 成员聊天与完整 Work 分开，旧数据不丢，无来源跟踪框架。 |
| Q1 简单权限 | 未接受的团队共有 Agent 不变成需求；运行凭据是现有机器消费者边界，不是人员角色。 |
| Q2 个人管理共同用 | Gateway/Agent 原管理者、各自带入群、无 Gateway 的人也参与。 |
| Q3 单 Thread 谁都可按 | design:108 没把长期选项偷偷缩回 owner；首决定是实现同卡唯一结果所需设计。 |
| Q4 可直接私聊 Agent | 无好友申请/逐人授权，目录发现与独立新私聊。 |
| Q5 原聊天不可看 | member 控制产品访问，不新承诺隔离机器管理员本地数据。 |
| Q6 首期闭环 | 注册、目录、三类聊天、多节点、卡片与可见性全在 M1；不另造任务看板。 |
| Q7 撤回误读 | 原型“全部”仅当前人的会话分类，全部聊天公开方案未回流。 |
| Q8 Work 详情例外 | 保留已记录其他聊天内容，不遮盖；源聊天/受保护链接仍独立检查。 |
| Q9 原有功能 | 单 Thread 多聊天 Skill 两 scope 与原 IM 全矩阵保留；global 聊天蒸馏未扩范围。 |
| 在范围 | 8 Requirements/18 Scenario 在上表各有落点，新增与原能力承接共同进入退出标准。 |
| 非目标 | 没有组织部门/团队资产/角色表/逐人配置/独立任务板，未重写原 Agent 工作机制。 |
| 禁止扩大 | 不加来源权限追踪/遮盖/模型记忆隔离/全部聊天；owner 管理归属仍有效。 |

### 核实台账：全部 delta-spec

重新执行只读 canonical 对照：全部 27 条的 MODIFIED/REMOVED 标题准确命中目标；全部 MODIFIED 的原 Scenario 标题完整保留。逐条阅读全文核语义，保留原 Scenario 的含义与必要变更相容，THEN 对准用户或 HTTP/WS 消费者可观察结果；不把标题脚本当语义审查。各 target 保持最窄 area，current canonical 本轮未被目标覆盖。

| 原子 | 锚与核实 |
|---|---|
| Δ01 auth REMOVED owner 数据全隔离 | canonical auth-tenancy 同名条目由 Δ02 替换，无并存双规则。 |
| Δ02 auth ADDED 登录/member/owner | 无 token、token 身份、列表/非成员、metrics 原情形承接；新增同群真人，机器入口另限范围。 |
| Δ03 agents MODIFIED runtime capabilities | 7 个原 Scenario 均保留；管理 features/model/reasoning/location/source_group 不删，仅成员 SlashPicker 使用 opaque key。 |
| Δ04 agents REMOVED owner 用户流 | canonical 旧标题精确，由 Δ05 承接成员规则。 |
| Δ05 agents ADDED member 用户流 | 原 token/resume/sync/断网/切账号 5 情形完整，个人 node/config 仍 owner。 |
| Δ06 agents ADDED 目录/管理 | 新公开目录独立管理 GET，含无设备、多设备、公开资料和非 owner 不可写。 |
| Δ07 conversations REMOVED 同 owner Agent 私聊 | 旧投递记录授予真人读取的特例撤除，由 Δ11 接住实际成员及旧身份。 |
| Δ08 conversations REMOVED owner 群治理 | 旧八情形由 Δ12 完整承接，修改访问规则不丢原动作。 |
| Δ09 conversations MODIFIED Agent 图片 | 原持久回看/地址不授权/fork 3 情形仍在，旧公开例外改指 Δ14。 |
| Δ10 conversations MODIFIED 字段/游标 | 原六情形、typed union、run_state 保留；普通 direct 并发复用、特殊独立，新增本人 sender/纯人/显式 group。 |
| Δ11 conversations ADDED Agent 私聊无 owner 特权 | receipt ID 不授权、随机旧 owner 复用且不推断真人成员；Work 记录不受此删减。 |
| Δ12 conversations ADDED member 群治理 | 原增员/幂等/空请求/越界/改名/user_id/移除/解散全在，新增真人与自己 Agent、创建者保护/重连失效。 |
| Δ13 conversations ADDED 个人状态 | pin/mute、已读并发边界和原状态迁移可观察，其他成员状态不变。 |
| Δ14 conversations ADDED 普通新旧附件 | 上传、历史原字节/旧 URL、引用不能洗权限、合法 fork 独立关联；与资源设计一致。 |
| Δ15 Work MODIFIED 分开呈现 | 原三情形完整，扩登录者主/子轨迹、来源内容不遮盖/链接独立/非 owner 持续更新。 |
| Δ16 IM relay REMOVED owner boundary 流 | 旧条由 Δ20 承接成员事件，不保 owner 原聊天特权。 |
| Δ17 IM relay MODIFIED durable boundary | 原持久 ACK/重复/错误三情形完整，跨 owner 群用 node/Agent/member/锚点；旧同归属情形未扩大为一般 owner 旁路。 |
| Δ18 IM relay MODIFIED 授权标识 | 原允许标识/旧无标识保留，新增全选项/同卡唯一/离线确认/global 无卡。 |
| Δ19 IM relay MODIFIED 幂等/回执 | 原中继/流式/回执三情形保留，多节点独立投递；global Inbox completed 不冒充主 Agent 完成。 |
| Δ20 IM relay ADDED member boundary 流 | 原在线与恢复两情形承接，最小展示 payload、replay/去重不变，原完整 config 不广播。 |
| Δ21 IM relay ADDED 机器 HTTP | 非 owner 聊天图像、运行 token 失效/伪造 node、shadow 外部身份、管理请求拒绝均有观察结果。 |
| Δ22 UX MODIFIED 蒸馏 | 原五 Scenario 与 prompt 格式/固定节点/失败不建聊天保留，新增两 Skill scope 与 source/execution 管理和模式界限。 |
| Δ23 UX MODIFIED slash | 原单聊/群 new、per-Agent effort 完整 levels 保留；新增跨 owner 候选、部分失败、缓存清理与同名异源。 |
| Δ24 UX ADDED 导航/语言 | 新协作入口复用旧导航/消息/附件，切语言保留编辑、刷新记住；未覆盖删除其余 UX requirements。 |
| Δ25 Gateway routing MODIFIED 四步路由 | 原八 Scenario 完整，跨账号输入仍真实 sender/原聊天上下文；global canonical 链接正确，不新建全局路由机制。 |
| Δ26 Gateway relay MODIFIED 授权中继 | 原允许/拒绝标识保留，新原执行绑定/幂等/终结不复活，响应回同聊天。 |
| Δ27 Gateway relay ADDED 当前连接凭据 | 注册 ACK、shadow 双身份、持久重连三情形闭合；token 不进外站/模型/日志，身份失败不做数据旁路。 |

### 核实台账：M1、原型与实施条件

| 原子 | 证据与判断 |
|---|---|
| M1 唯一垂直切片 | design:295–301 一项 collaborative-im，目录只有 .gitkeep；从登录/成员聊天到 Gateway 执行/Work/旧数据端到端，无横切 M 或并行文件争用。空骨架是设计阶段正常状态。 |
| Reviewer 退出 | design:301 的 R1–R6/18 Scenario 加 :305 R7 逐项旧能力；runbook:88–96/117–123 有真实三账号、跨节点批准、资源、两 scope、非 owner slash/@/fork 与旧页面。不会只验原型。 |
| Worker 退出 | design:301/305 的 W1 各身份/幂等、W2 build/双端原型、W3 隔离栈/迁移、W4 i18n 与旧功能；设置 must-match 已投 W2/W4，均是可判断的结果。 |
| 原型联系人/群 | sidebar/member selection/direct/create-group 明确 member 列表、可找人/Agent、自己 Agent 入群和 group 类型；purpose 保护普通私聊。刷新演示重置明示，不冒充后端持久化。 |
| 原型消息/卡片/Work | send/permission/approve/settlePermission/source/child 对应固定回复、原请求两阶段、global 无卡、完整 Work 和 source member 判断；演示不验证真实 node 或工具副作用。 |
| 原型蒸馏/菜单/草稿 | enterDistill/distillReason/prefillDistill、branchMessage/renderSlash、saveDraft 保留入口/模式/资格/两 scope/预填/独立草稿；深层 JSONL、动态命令与富消息由 design:151–161/245–249 和原组件承接。 |
| 原型管理/Nodes | agentPage 原六分区/空态和 nodesPage 独立明细已对应当前源码；真实创建、config、channels、skill usage、WS 心跳/别名保存由原页面，示例固定数值不是新数据源。 |
| 原型设置/语言/响应式 | userPopover:335 与 account:501–514 分清菜单和 Me 行层级；languageControl:334、language 事件和 im_lang 正式契约分开；手机仅底栏、具体聊天无底栏、桌面仅 topbar，768 分界一致。 |
| 原型来源/对齐级别 | reviewEntries 与 design:215–223 三类相符，simple 是展示深度；design:277–291 分清 must-match、may-adapt、原型 out-of-scope。全量原页面仍须可用，“没画全”不是放弃验收。 |
| 运行拓扑/模型 | runbook:5–11 A 两节点/B 无节点/C 一节点、两模式、独立身份/目录；e2e-up.sh:184–225 真实重写 node/workspace，:252–258/375–382 启动并导出隔离端口/JWT；--main-config 实际存在。真实问答才证明模型就绪。 |
| 起停/恢复前置 | runbook:14–85/98–113 给可执行隔离栈、额外 Gateway PID 和重启；明确 e2e-up 重置 DB 不可充保数据重启，复用 IM cwd/port/secret。无需生产服务或第三方发信。 |
| 资源/shadow/迁移回退 | runbook:94–96/117–127 覆盖图文跨 owner、token 换代、shadow /me /nodes/旧 owner 及双 client、旧 DB+两目录哈希和关系审计、Agent-only/fork；退出清自有 PID/端口。 |
| 整体可读性与阶段 | 两条首要读规则和关系图在前，后续按联系人/群/执行/身份/附件/旧消费者组织；branch 声明、风险、原型/实施范围、回退和运行命令完整。design 状态明确尚未实施，current spec 未被目标冒写。 |

### 架构进攻

| 角度 | 本轮实际攻击与结论 |
|---|---|
| 一·归属 | 从 app/deps 正向核对成员仓库、事件泵、relay/Work/config 边界，再从 Gateway composition 核对 shadow/图片与 SDK；授权和窄投影在 IM，能力和 JSONL 在 Gateway，执行仍经 agent.sdk。没有产品包互 import 或 IM 读本机 Gateway workspace 的隐含反向依赖。把这些职责移到浏览器/IM 文件系统会复发跨账号和跨机器错误，当前明确避免。 |
| 二·删除测试 | 逐个删 direct_key、participant 状态、统一 member 查询、窄 contacts/commands、运行凭据、附件关联、durable submitted：分别会留下并发多私聊、偏好互扰、入口授权分歧、管理数据曝光、人机主体混用、旧 URL 旁路、重启丢决定。这些均有已存在消费者/用户要求，不是未来权限体系。skill_key 不加表，说明层共用 19 项数据，不造通用框架。 |
| 三·深度与复用 | 实际比对原 distill preflight/RPC、slash enabled/去重、fork、六分区、Nodes、UserMenu/Me/i18n，以及原 event/relay/Work 存储。新增投影隐藏管理数据但保完整候选语义；正式 UI 复用原组件、完整字段和行为。若把缩略 prototype 实现成第二套页面，会持续遗漏原能力；当前矩阵、来源说明与 must-match 已正面阻止此维护成本。 |
| 四·治本而非补丁 | member 规则落所有 HTTP/WS/资源入口，运行主体修实际 provider 而非让 owner 旁路，旧 uploads 撤公开服务，特殊聊天按用途不按标题猜，Work 原内容与链接分别处理。导航直接沿用实际 AppShell 分界，Me/Nodes 分工明确，没有用隐藏按钮或文案遮住设计缺口，也没有留待未来角色系统偿还的已知债。 |

### Issues

无未解决项。本轮作者对旧 UX grounding 和设置对齐级别的收紧已纳入当前复核，没有发现新的实质冲突；未将字体间距偏好、原型不模拟全部后台、M1 尚无任务细节或尚未跑实施旅程当作设计缺陷。

### Recommendations

无新增建议。可以结束设计审查循环，按当前 design、27 条 delta、能力承接矩阵、M1 R1–R7/W1–W4 和 runbook 进入开发；真实产品结果在实施后验收。


## Round 9

### Metadata

- reviewer: /root/design_review（继续使用原 reviewer）
- review_mode: full
- mode_reason: Q10 新增交付约束，改变存量资源接口承诺、目标 schema 初始化及 M1/部署验收分工；且当前 HEAD 已发生变化。本轮整体核对原约束与新部署边界，深入追迁移所涉持久消费者，未变化项复用 Round 8 的实际源码证据。当前精简版 skill 允许相同证据复用，不以重复表格代替覆盖。
- started_at: 2026-09-13T23:21:33+08:00
- completed_at: 2026-09-13T23:26:59+08:00
- duration: 5m26s

### Verdict

Issues Found — 0 CRITICAL / 1 WARNING

Q10 的 Markdown 交付、部署时离线转换、目标格式运行和无本次兼容分支，当前设计与真实存储消费者自洽；不需要改回应用迁移程序。唯一未解决项是独立基线核对发现的蒸馏 Skill scope 漂移：当前已合入的 builtin 指令与仍在使用的 IM/Gateway/tool 契约不一致，而送审设计尚未将其列为明确修复项。它直接影响 Q9/M1 必须保留的 global 范围，故本轮暂不批准。

本轮仅审文档和实际源码，没有创建迁移脚本、fixture、产品实现，没有启动服务、执行迁移或验证模型旅程。正式旧数据保真由获授权部署 agent 执行，不能由本轮报告提前宣布通过。

### Coverage 与基线

已读取当前 change-design-reviewer/SKILL.md 及 references/report.md，spec v5、design 当前数据/资源/初始化/M1 与旧能力段、完整 migration-prompt.md、conversations-messages delta、runbook 及历史报告。其余 7 份 delta 的语义与 Round 8 一致；重新对全部 27 条做 canonical 标题和 MODIFIED 原 Scenario 保留检查，通过；本次文档相对链接可解析。

checkout 仍为 main，当前 HEAD 为 94338a2a7d2e01b7868648895e6cfdcf0f6c53f4，保留现有 dirty/untracked。相对 Round 8 基线 eb4da2815，IM、Gateway、内核 Python/TS 和测试没有变化；变化存在于 bundled Skills Markdown，不能笼统说“全部 src 未变”。独立查看 conversation-skill-distiller 的 diff，发现下文 R9-W1。

| 完整范围 | 本轮证据与结论 |
|---|---|
| 现状 C01–C07、C09–C10、C12、C14–C22 | retained_from: Round 8 对应 C 行；上述执行代码与 canonical 未变。账号/member、真实 HTTP/WS 组装、per-Agent relay、Work、机器主体、config 边界、fork、UI/Nodes/i18n 的事实仍成立。本轮复查 app.py:282–294 的实际启动及资源注入，确认新数据改动在真实路径。 |
| 现状 C08/C11 | 本轮重追 db.py 的建表、initialize_schema 及旧共享偏好补列，Conversation/Message 的实际旧列消费者，普通上传/StaticFiles 与私有 images。新目标明说移除旧列依赖和公开服务，见下表。 |
| 现状 C13 原蒸馏能力 | 入口/preflight/prompt/RPC 代码未变，但 bundled Skill 新指令已漂移；不能继续直接继承“原实现完整可复用”的全链结论。R9-W1 明确只影响 scope 指令这一点。 |
| 决策 D01–D11、D13、D15–D16、D19–D20 | retained_from: Round 8 相同 D 行，当前规定未改变：member/Work/owner 三边界、目录、群、真实 sender、卡片、连接 token/shadow、commands、原操作资格、评审标注及设置形态保持。无需为 Q10 增加人员权限或新的执行模块。 |
| 决策 D04/D07/D12/D17/D18 | 普通 direct、个人状态、附件和旧数据的目标行为保留，但旧行初始化/转换主体改为部署 agent，运行时不读旧格式；完整复核见迁移表。旧能力矩阵仍生效，D18 的 builtin scope 前提存在 R9-W1。 |
| 决策 D14 单 Thread 蒸馏 | source/execution owner+single_thread+同 node、agent/global 两 scope、prompt 后建聊天不变；当前 builtin 与这条决定不相容，需显式承接修复，不改设计选定的两个 scope。 |
| 8 Requirements、18 Scenario | SR1–SR7、S01–S17 全部目标与 Round 8 表一致。SR8/S18 仍保留旧身份/历史/能力，仅 WHEN 增加“部署 agent 按迁移文档完成旧数据转换”；M1 用目标格式历史回看，正式转换保真后移到部署验收，阶段没有混写。 |
| 6 用户场景、Q1–Q9 | 原意图保持：一人多机、无机协作、他人 Agent 私聊、混合群、所有真人可按 single_thread 原卡片选项、global Work 完整而源聊天不可读、单 Thread 原功能完整保留；Q10 没改变这些访问或执行规则。 |
| Q10 与范围/非目标 | spec:67–69/210 明确只交 Markdown、部署时转换、无本次迁移/回填/双写/旧字段/旧 URL 分支。原三项范围/非目标仍与 Round 8 对应；不扩大为删除无关历史兼容或重做 shadow。 |
| Δ01–Δ12、Δ15–Δ27 | 标题/原 Scenario 对照通过；语义仍见 Round 8 对应 Δ 行，尤其 images 的既有受保护接口保留、global Inbox completed 含义、shadow 双身份、slash/distill 两范围均未改。Δ09 所引用的附件规则现在由新部署转换承接。 |
| Δ13 个人状态、Δ14 普通新旧附件 | conversations-messages:160–178 明确部署 agent 转换、新资源历史回看、旧独立 uploads URL 不再服务；没有残留旧 alias 必须可用承诺。与 Q10、design:137–142、迁移文档一致。 |
| M1、原型与验收前置 | 仍唯一垂直 M1，骨架只有 .gitkeep，原型未改；must-match 和 R1–R7/W1–W4 原产品行为不删。M1:304、runbook:88/94/123 明确产品验收与正式存量转换分工，迁移 Markdown 在 PR 前按最终 schema 校准。 |

### 本轮深入核实：转换与目标格式的数据链

| 改变的原子 | 实际源码/消费者证据 | 设计闭合判断 |
|---|---|---|
| 初始化只能生成目标结构 | app.py:282–286 的 lifespan 必经 initialize_schema；db.py:365–390 执行 _SCHEMA_SQL 与 _migrate_conversations_metadata，:471–481 会自动补回三列。 | design:183–185 同时要求删除目标 schema 三个共享列及现有补列分支，明确旧库先离线转换；不是只改 CREATE TABLE 后启动又加回。无须为无关历史初始化做范围外清理。 |
| 当前读写不能再依赖旧列 | conversations.py:137–139/313–315 插入、:409/465–479 SELECT/排序、:440 PATCH、:663–665 转模型，messages.py:393–409/480–488/606/1055 更新 unread。 | design:183 明确所有读写使用 participant；migration:30–36 转旧 owner 值、其他成员默认、drop 列及旧事件个人字段。实施 fixture 使用目标列即可暴露遗漏 SQL，不需要旧格式 fallback。 |
| 旧成员与稳定身份 | users.py:73–87 真人 owner=id；conversations owner/member 本来是两份事实，Agent-only/随机旧 owner 是已核实例。 | migration:27–32 保 ID/原成员/owner 来源，只有能证明旧真人可见性才补成员，无法解释停止；direct_key 全 NULL 不猜旧 fork/distill。没有自动把 Agent owner 加到他人聊天。 |
| 新普通附件与旧公开文件不同 | messages.py:391–419 生成绝对 /im/uploads URL；app.py:446–448 公开 StaticFiles。 | design:137–142、migration:44–52 从本 IM 绝对/相对地址匹配原文件，写新资源/聊天关联并改历史引用；新程序删旧服务，不留 alias/redirect。独立旧书签失效在 spec/delta 中明确，原聊天内仍回看同一字节。 |
| 保留现用 protected images | app.py:292–294 注入 message-images 目录；message_images.py:25–28 当前稳定 images URL，:71–108 原字节 hash/source-key，:132–175 fork 建目标独立关联并共用不可变文件。 | migration:40 保原 images ID/URL/字节/fork；扩展同一资源存储只承接普通文件，不将现用 images 接口误删成旧公开地址兼容。 |
| 多聊天引用不是全员授权 | 原 protected copy_references 以 source conversation 解析，再给 target 独立 row；正常消息资源必须校验 source 可读。 | migration:45–48 按每个既有来源/合法 fork 建关联、逐聊天新 URL；Work 只引用原来源、不额外建全员关联。新消息的合法引用校验仍由 design:139 保留。 |
| IM 持久记录不只 messages | db.py:133–157 有 attachments/tool_calls/thinking/background_returns/reply_process，events.py:199–214/269–302 重放 payload_json；Work repository 保持 session/turn/item 记录。 | migration:36/47 明确消息、过程、事件、Work、待投递的仍消费引用一起转换，事件 ID/顺序/投递状态不变；不靠新程序识别旧事件补偿。 |
| Gateway shadow/回复持久引用 | shadow_sync.py:331–372/443–470 从存储内容重新投影和补写；reply_images.py:336–365 可复用按 conversation 保存的 im_receipts；shadow_saga.py:954–988 的稳定 ID 来自自然键/执行序号。 | migration:11/17/19/47 保自然幂等/输出身份和状态，改同资源 URL；现有受保护 images receipt 不须改地址。shadow 身份校验/离线补写是正常能力，不被 Q10 当迁移代码删除。 |
| Inbox receipt 与内容摘要 | global_inbox.py:54–80 有 entries/receipts/cursors/consumed_parts/work_events；:1174–1185 保存 page 与 content_digest，:1209–1243 按摘要证明提交并更新消费状态。 | migration:47 要同步改 Inbox/receipt 与 Session 工具结果，依实际契约重算摘要/校验但保调用配对和已消费状态，:63 验无重复；覆盖只改消息 URL 会导致旧引用回流或摘要不一致的真实风险。未要求重编号 parts/receipts 或重新消费。 |
| Session 与连续上下文 | agent/core/session/transcript.py:138–146/189/248–274 从 JSONL 恢复、读取及 fork 消息；已有工具结果可继续进入模型。 | migration:47 明确上下文/工具结果对应链接，不删自然历史或改变工具事实/调用配对；部署离线核对文件，不向 IM 增加读 Gateway JSONL 的产品依赖。 |
| 批准/执行切换 | EventBridge:409–444 的旧 pending 数据与 messages:1116–1221 持久请求目前未必带新六元身份；运行 token 本来只存在新连接。 | migration:17 要先把进行中执行/待批/投递/配置边界确认到终态，不靠猜节点或重放试副作用；:62–63 重新注册 token、保消费状态并验证不重复。没有要求新程序猜旧请求目标。 |
| 停写/备份/副本/切换 | IM app lifespan 持 DB，Gateway 多个 SQLite/上下文各有写入者，global_inbox.py:50 明确 WAL。 | migration:15–19 先定位真实 cwd/config、停止所有写入者、同窗 SQLite/WAL/两附件目录/Gateway 状态备份；:56–65 副本核对/隔离验真后用同规则正式转换、协调全部 Gateway，不混跑兼容窗口。 |
| 回退与完成状态 | 换 URL 不只改 IM DB，Gateway 内容与消费状态也受影响。 | migration:69 同批 IM/文件/Gateway/旧版本恢复；开放写入后先保全新数据再制定回退合并，不能旧快照覆盖。:71 由部署 agent 提供实际结果，本次不声称成功。 |
| 实施交付与目标 fixture | design:188/304、runbook:123 区分未来 schema 定稿与正式旧库事实。 | PR 前核 migration Markdown 和真实初始化/字段/资源 API；开发用目标格式消息/附件/fork 检正常行为，不写迁移生成 fixture。正式演练/转换归部署是 Q10 的交付约束，并非偷减旧数据保留目标。 |

### 历史问题闭环

| 原 issue | 本轮变化与证据 | 状态 |
|---|---|---|
| R1-C1 / R2-W1 | 运行 token 和 shadow 双 client 保持 design:113–130；migration:11/62 不把“去兼容”误解成删除正常 owner 身份前置或改回真人代机器。 | closed |
| R1-C2 | 原安全问题仍由新旧附件 member 读取解决；R8 的旧 alias 解法被 Q10 明确替换为部署改引用，新版本没有公开旁路，migration:44–52/61 完整接住。 | closed，解决方式依 Q10 更新 |
| R1-R1 / R1-R3 | 创建者保护目标不变；migration:27–34 保实际成员/Agent-only/随机 owner 及个人状态，未强行真人化。 | closed |
| R1-W1 / R7-R1 | pending/submitted/resolved 及原型两阶段未改；迁移先处理旧 pending 终态，不让新 token 重放工具。 | closed |
| R1-R2 / R4-W1 / R4-W2 / R5-R1 / R6 / R7 UI 标注 | canonical 链接、skill_key、特殊聊天用途、768 断点、原六分区/Nodes/设置及说明层未变；Round 8 的相应证据未失效。 | closed |
| Round 8 完整批准的边界 | Q10 对 schema/旧 URL/部署阶段的新决定不能沿用 R8 的旧解法措辞；本轮已重新核对。另当前 bundled Skill 改动产生新漂移，不能拿 R8 对旧基线的批准覆盖。 | 新边界见本轮；R9-W1 未解决 |

### 架构判断

| 角度 | 本轮结论 |
|---|---|
| 职责与依赖方向 | 一次性旧库转换归部署 agent，应用只接目标 schema；IM/Gateway 正常职责不变。迁移手册涉及 Gateway JSONL 不等于 IM 产品可读取 Gateway 文件，没有反向 import 或新迁移服务。 |
| 新层必要性 | Q10 主动删除本次迁移程序、启动回填、旧 URL alias、双写/fallback，没有再用“兼容服务”包装它们。受保护资源关联、member 状态、durable 队列是新产品正常能力，有现成消费者，不能一起删。 |
| 复用与维护成本 | 保现用 images 身份、正常 shadow 与原 Skills/tool/RPC；部署文档按最终 schema 校准，避免产品永远维护旧版本分支。跨存储引用和摘要核对由真实持久消费需要，不是通用迁移框架。R9-W1 要纠正一个实际指令值，不应扩成三种 scope/别名兼容。 |
| 是否正面解决问题 | 旧 URL 字节服务直接退役并改已有引用，旧偏好列从真实读写及初始化一同移走，停写和同批回退覆盖多存储。没有只藏入口、只改消息不改重放、或用重新执行工具猜状态的补丁路径。 |

### Issues

- **[R9-W1][WARNING] 当前 builtin 蒸馏 scope 已漂移，设计尚未明确修复这条真实消费者。**
  - 位置：design.md:18 的代码基线及 :154–156“生成 Skill 沿用现有工作流”、:248 承接矩阵、:304/308 的 M1 R7/W4；当前 bundled Skill 不再符合这里假设的 agent/global 原链。
  - 证据：当前 HEAD 94338a2a7 中 src/personal_assistant/builtin_skills/conversation-skill-distiller/SKILL.md:12 将 target_scope 写成 agent 或 pa，:18 又要求原样传 skill_manage；src/IM/api/routes/web_im.py:72 的输入、src/personal_assistant/gateway/distill_prompt.py:41/139–149 的校验及生成 prompt、src/agent/platform/tools/builtins/skill_manage.py:234–237 的 enum 都仍是 agent/global。实际前台 Gateway 启动经 process_lifecycle.py:154→:39–46→builtin_skills/bootstrap.py:93–137 将 bundled Skill 同步到运行根，不是闲置文档。
  - 不修后果：用户按既有 UI 选择 global，拿到合法 target_scope: global 后，模型读取的 Skill 却将它归为无效输入；若照 Skill 转成 pa 调工具，schema 又拒绝。不能假设模型总会自行消解此冲突。这里未运行模型，不宣称已经复现某种随机回复，但契约冲突是确定的。
  - 最小修正：在设计现状明确记录新基线漂移，并将 builtin 输入说明校正为既有 agent/global 列为 M1 原能力恢复项；runbook 要验证两种实际写入范围与工具结果。可在实施时改这一处 Skill，保持现有前端 scope、Gateway RPC、tool enum 和本次迁移方案不变，不新增 pa alias 或旧版本兼容。
  - 作者已确认该证据，表示将在本轮报告后修订设计/runbook，再交复核；本报告写入时该修订尚未落盘，故仍为 open。

### Recommendations

无额外建议。Q10 无需另造迁移代码或通用框架；将上述一项原能力漂移明确纳入实施后，可做有界复审收口。

### Author Resolutions

- **R9-W1 — accepted。** 已独立核实当前 `94338a2a7` bundled Skill 第 12 行为 `agent/pa`，IM 输入、Gateway prompt 与工具 enum 仍为 `agent/global`。修订 design 的现状基线、既有聊天消费者及 M1 R7/W4，明确实施时校正该 builtin；修订 reviewer-runbook，要求在实际运行根检查同步结果，并对两 scope 分别发送预填 prompt、核对工具成功与真实目录写入。保持现有 API／RPC／tool enum 和迁移方案，不增加别名。当前仅修订设计与验收要求，未修改产品源码或声称实际蒸馏已经通过；交原 reviewer 复核设计闭合。


## Round 10

### Metadata

- reviewer: /root/design_review
- review_mode: delta
- mode_reason: 初始按 R9-W1 闭环核对；追新增真实 global 写入步骤时，发现实际用户级共享 Skill 根不随测试 workspace 隔离，影响本次 runbook 起停和收尾，因此在同轮扩为有界 delta。没有需求、产品接口或迁移规则变化，不重做全量台账。
- started_at: 2026-09-13T23:28:52+08:00
- completed_at: 2026-09-13T23:31:26+08:00
- duration: 2m34s

### Verdict

Issues Found — 0 CRITICAL / 1 WARNING

R9-W1 已在设计层关闭；还需补清新增真实 Skill 写入旅程对本机共享 Skill 根的前置和收尾。产品架构、Q10 迁移方案无需调整。

### 历史问题闭环

| 历史项 | Author Resolution 与独立核实 | 状态 |
|---|---|---|
| R9-W1 | design:18 明确新基线与 bundled Skill 漂移；:156 明确 M1 把输入校正为 agent/global，保持现有前端/RPC/tool enum，不加 pa 别名；:310 将 builtin 纳入 M1 范围及 R7/W4，要求实际发送、工具成功和正确目录。runbook:94 检查运行根同步后的 builtin 并验证两个实际 scope。原源码冲突尚待实施，但设计已明确处理，不再让 worker 猜。 | closed（设计层） |

### Coverage 与本轮证据

retained_from: Round 9 — Q1–Q10、spec/delta、原型、migration-prompt、成员/机器/Work/附件目标与全量源码证据均未变化；本轮只重查 design 的现状与蒸馏/M1 段、runbook 新增真实写入及其实际运行根。

| Changed atom / 波及链 | 核实结果 |
|---|---|
| scope 修正 | IM web_im.py:72、Gateway distill_prompt.py:41/139–149、skill_manage.py:234–237 仍为 agent/global；design:156 的最小修订正确，没改原 scope 语义。 |
| 验收深入到实际写入 | runbook:92–94 区分预填不自动发送与后续验收者手动发送，核工具结果/实际目录/另一个 scope 无误写。这能验证 R9 的实际消费者；不把模型创建成功提前宣称为事实。 |
| Agent 与 global 写根并非同样隔离 | src/personal_assistant/product.py:56–60 将 PA_SKILL_SEARCH_ROOTS[0] 定为 ~/.nanoassistant/skills，:512–518 传入真实 build_kernel；agent/core/skills/root_resolver.py:28–40 的 global writer 直接用该根，workspace 只控制 Agent 根。 |
| 启动已会写共享根 | process_lifecycle.py:154 在 build runtime 前调用 builtin 安装；builtin_skills/bootstrap.py:16/93–137 默认同步到同一用户根，逐个替换 package 声明的 builtin 目录。它不是只读候选扫描。 |
| 当前收尾缺口 | runbook:17–40/58–80 分别创建 RUNTIME_ROOT/workspace 并启动 Gateway，:127 只清 PID/端口/运行产物；没有记录共享根既有内容、同步覆盖的 builtin，也没有限定并清除本次实际新建的 global Skill。只说“隔离 workspace”不能覆盖这条真实写路径。 |

### 受影响的架构判断

真实产品的 global 根由 PA 产品层传给内核，职责自然，继续复用，不应为了本次验收新加根配置或兼容 scope。需要修的是验证环境与产物归属说明：同机多个测试 Gateway 可以共享用户级根，若把它当作每个 RUNTIME_ROOT 下的私有目录，就会把测试文件和 builtin 同步影响留给日常运行。用明确根、冲突检查、同步记录和本次项收尾即可，不需要通用隔离框架。

### Issues

- **[R10-W1][WARNING] 新增真实 global Skill 写入未交代共享运行根的影响及收尾。**
  - 位置：reviewer-runbook.md:17–40/58–84 的 Gateway 启动、:94 的实际两 scope 创建、:127 的清理。
  - 证据：上述 product.py→build_kernel→root_resolver 的 global 写根固定为当前用户 ~/.nanoassistant/skills；builtin bootstrap 也会在 Gateway 启动时同步覆盖该根中 package 声明的目录。三个同物理机器测试 Gateway 不会因 node_id/workspace 不同而得到三个 global 根。
  - 不修后果：按文档完成验收后，测试 global Skill 留在日常可发现目录；启动测试版本还会改变日常使用的 builtin 内容，而现有清理只停止进程/清运行目录，没有记录这些变更。此处是确定的实际文件写路径，不是推测模型可能越界。
  - 最小修正：在运行前核对实际 global 根，明确同机共享；两次创建使用本轮独立测试名并确认原本不存在，记录实际新建路径，退出只清本轮创建项。同时说明启动同步 builtin 的影响，对相关原有内容做记录并明确本轮保留/恢复收尾，不无记录覆盖日常根。已有独立验证环境可直接使用；不要求新增产品配置、pa alias 或通用隔离框架。
  - 作者已确认此事实并表示报告后补充文档，当前受审版本尚未包含修订，故 open。

### Recommendations

无额外建议。本轮仍只审设计，没有启动 Gateway、写入任何 Skill 或运行模型；补齐这个有界验收前置即可继续闭环。

### Author Resolutions

- **R10-W1 — accepted。** 已核实 PA global writer 与启动 builtin 同步共用运行用户的 `~/.nanoassistant/skills`。design 的蒸馏段明确同机同用户共享根；runbook 在任何启动命令前要求核对实际根、唯一测试名及无同名项，记录 builtin 原有状态／快照／哈希，日常 Gateway 正在共用时改用现成独立测试环境。退出先停本轮进程，再只清本轮新建测试 Skill，按记录恢复本轮同步的 builtin，不覆盖其他写入、不删除整个根；失败同样收尾。没有修改产品根解析或新增隔离框架，未真实写入任何 Skill。交原 reviewer 复核。


## Round 11

### Metadata

- reviewer: /root/design_review
- review_mode: closure
- mode_reason: 本次仅补充 R10-W1 的共享 Skill 根事实、启动前记录和退出收尾，未改变需求、产品路径解析、接口或迁移责任；按旧问题及其直接证据复核，无需扩大范围。
- started_at: 2026-09-13T23:33:05+08:00
- completed_at: 2026-09-13T23:35:46+08:00
- duration: 2m41s

### Verdict

Approved — 0 CRITICAL / 0 WARNING

R10-W1 已关闭。当前设计可以交给实施；本结论是设计门禁，不表示产品实现、真实 Skill 创建或正式迁移已经完成。

### 历史问题闭环与证据

| 历史项 | Author Resolution 与本轮独立核实 | 状态 |
|---|---|---|
| R10-W1 | design.md:158 明确实际 global 根是运行用户 ~/.nanoassistant/skills，同机同用户多个 Gateway 共享，不随 node_id/workspace 隔离。reviewer-runbook.md:16–18 将核根、两 scope 唯一测试名和无同名项检查、builtin 原存在状态/内容快照/哈希放在任何 Gateway 启动之前；日常 Gateway 或其他验收共用时改用现成独立环境。:131–133 要求先停止本轮全部进程，再只清启动前不存在且确由本轮创建的 Skill，按记录恢复本轮同步的 builtin，恢复前核对仍是本轮版本，保留其他写入，失败也收尾。这覆盖 Round 10 已核实的 product.py:56–60/512–518 → root_resolver.py:28–40 的真实 global 写根，以及 process_lifecycle.py:154 → builtin_skills/bootstrap.py:16/93–137 的启动同步路径；没有把 workspace 隔离误当成 global 根隔离，也没有新加产品配置或通用框架。 | closed |
| R9-W1 | design.md:156 仍明确 M1 校正 builtin 输入为 agent/global，不增加 pa 别名；runbook 的两 scope 实际发送、工具成功与正确目录写入要求保留。本轮补充其运行前置和收尾，没有把尚待实施的 builtin 校正宣称为已实现。 | closed（设计层，保留 Round 10 结论） |

retained_from: Round 9 / Round 10。Q1–Q10 的需求、成员与机器身份边界、Work、附件、原 IM 功能承接、delta-spec、M1 与 migration-prompt 的既有审查证据未受这次修订影响；原型与产品源码未改。本轮只读取受审文档和相关状态，不启动服务、不操作共享 Skill 根、不执行迁移。

### Issues

无。

### Recommendations

无。按当前方案进入实施，并在实施后执行 Runbook 规定的真实验证即可；正式旧数据转换仍由部署 agent 按 migration-prompt.md 执行。
