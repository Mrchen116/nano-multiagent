# Design Review: refactor-550

## Round 1

### Metadata

- reviewer: `/root/ref550_design_review`
- review_mode: `full`
- mode_reason: R1，完整核实五类承重原子和四个架构角度。
- started_at: `2026-09-10T07:11:23+00:00`
- completed_at: `2026-09-10T07:16:00+00:00`
- duration: `4m37s`
- checkout: `codex/feat-546`，隔离 worktree `unit-feat-546`。
- 只读文档与必要代码；仅写此报告。未迁移、重启共享演示或生产，未修改产品或提交。

### Verdict

Issues Found — 2 CRITICAL / 0 WARNING

### Coverage

完整读取 motivation.md、design.md、两个 delta-spec、prototype.html、migration-prompt.md；核对 IM/Gateway canonical 入口及 conversations-messages、global-agent 相关契约。从生产 HTTP/WS 组装追到查询/持久化，从 PA 入站追到 Inbox/序列化，并核对真实前端 picker/parser。未把静态原型源码当浏览器验收，也未执行迁移。未使用历史记忆作为结论证据。

以下路径以仓库根为基准；表中 IM=`src/IM`，PA=`src/personal_assistant`。

### 核实台账：现状断言

| 原子 | 核实结果与证据 |
|---|---|
| S1 用户生成 UUID | 成立。`IM/api/routes/auth.py:94` 注入 AuthService，`IM/application/auth_service.py:123` 调 users；`IM/infra/repositories/users.py:76` 生成 UUID。 |
| S2 两个会话创建入口生成 UUID | 成立。真实路由 `IM/api/routes/web_im.py:225` → `IM/application/web_im_service.py:83`；`IM/infra/repositories/conversations.py:99,286` 两处生成。 |
| S3 agent_id 全 IM 唯一、Agent 对应 users | 成立。`IM/infra/db.py:55` agent_id 为 PRIMARY KEY；`IM/infra/gateway_persistence.py:359` 按 agent:username 查实际 user。 |
| S4 成员/消息用 user_id，Inbox Agent 用业务 ID | 成立。`IM/application/work_conversations.py:259` 从 users 查成员；其 read 使用 m.sender_user_id；`PA/gateway/global_run_coordinator.py:490` 优先 sender_agent_id，`global_inbox.py:1069` 投影回业务 ID。 |
| S5 Relay 只认 Agent 标签 | 成立。`IM/app.py:365` 和 `IM/api/deps.py:219` 组装 RelayService；`application/relay_service.py:333-368` 解析 agent 标签并限制参与 Agent。 |
| S6 picker 用 agent_id | 成立。`IM/frontend/src/features/chat/chat-workspace-page.tsx:399,1173` 构造并传候选；`components/mention-picker.tsx:78,91` 使用 agent_id。 |
| S7 两种模式提示差异 | 成立。`PA/product.py:242-272` 写旧群格式；`:383` global_main 不注入该 tail。 |
| S8 send/query 参数不一致 | 成立。`PA/tools/send_message.py:98-112` 接受 to；`tools/conversations.py:24`、`tools/inbox.py:154` 接受 target。 |
| S9 分包约束与非目标 | 成立。IM/Gateway spec 入口明确 IM 不调用内核、PA 仅用 SDK；设计不改变消息/执行身份与权限。 |
| S10 复用查询/摄取/发送真实路径 | 成立。`IM/app.py:373` 组装 GatewayWork；`IM/ws/gateway/runtime.py:163` 派发 conversation.query 到 `work.py:80`；PA `global_inbox.py:524` 已调 describe；`tools/send_message.py:192,201` 实际 HTTP 发送并区分 held。 |
| S11 既有映射足以统一外部发送者 | **不成立**。`PA/gateway/shadow_sync.py:184-210` 只写 owner 与 Agent 参与者，外部用户消息存 owner_user_id；`global_run_coordinator.py:490-493` 却存 external_user_id。无外部联系人到 IM users 的一一映射。见 C1。 |
| S12 mention 渲染结构可复用 | 成立。`IM/frontend/.../components/mention-parser.ts:13,20,66` 已有标签和名字映射，收敛为 user 即可。 |
| S13 历史与痛点 | motivation 原话要求工具整合并拒绝 Bash 封禁；设计未把本地“20次 Bash”统计当实现可行性的前提，无需据其推导迁移正确性。 |

### 核实台账：决策

| 原子 | 完整/拍定/自洽/有据核实 |
|---|---|
| D1 短 ID | 字符集、长度、同表冲突重试已拍定；users/conversations 主键约束可承载，符合跨群稳定短身份。无别名实体。 |
| D2 一次性迁移 | 已拍定。migration-prompt §1-7 覆盖停写、全备份、副本、正式应用及整体回退；无启动迁移，符合用户澄清。 |
| D3 info/list/describe | 已拍定。复用 WorkConversationQuery 授权成员集和 describe；info 不读历史、list 保留名称/成员检索；无新运输层。 |
| D4 模型身份 | 内置 IM 可按 users 统一；外部例外与接口表不闭合且映射前提错误。未定义来源字段、user_id 缺省形式以及历史 owner 代记的表现。C1。 |
| D5 user mention | 标签、成员校验、真人不唤醒、两种提示、命令范围已拍定；与 RelayService 当前职责相容，parser 可直接收敛。 |
| D6 target/回执 | 已拍定只接受 user/conversation；内部 payload 的 to 不等于模型兼容。现状 `IM/infra/gateway_persistence.py:515-524` user 分支直接走 user-agent，实施须按设计完成 user→agent 路由，不能只改 schema；设计已明确这一要求，不另报重复问题。 |
| D7 统一表达/保留摄取 | 已拍定。`PA/tools/inbox_result.py:45` 已隔离模型投影，`global_inbox.py:1030-1095` 保留分片记账；IM read 的 reversed(messages) 是现有最新页规则。设计明确保留这些行为，无矛盾。 |

### 核实台账：首文档约束

| 原子 | 覆盖及边界证据 |
|---|---|
| Q1 工具优先、不封 Bash、不改推进规则 | D3-D7 改查询/身份/通信格式，无新增任务推进规则或封禁。 |
| Q2 同 ID 不得随群变成不同人 | D1 全 IM users 主键，无 group-local alias。 |
| Q3 不支持跨 Gateway 重复 agent_id | D1 保留 agent_profiles 全局主键。 |
| Q4 开始改/沿用 PR287 | Unit branch 与实际 codex/feat-546 checkout 一致，不需新集成分支。 |
| Q5 一次性迁移、不要兼容代码 | D2 和 migration-prompt 首段及 §7 禁止 alias、自动升级、双格式 fallback。 |
| Q6 unit 内迁移 prompt 交部署 Agent | 文件存在，开头明确需部署授权，§6 要求副本通过再正式应用。 |
| R1 两群同人/可直接联系 | D1/D4/D6 与 IM delta 覆盖；内置 IM 可行，外部范围见 C1。 |
| R1 查询群、含未发言成员、区分无权 | D3 info 从参与者表查完整 members，拒绝无权目标，不从消息猜成员。 |
| R2 两种模式提及人/Agent，群目标保持 | D5 共享格式、真人不唤醒、普通名字无效；原型展示人和 Agent。 |
| R3 Inbox/历史辨认发送者、内容顺序附件保持 | D7 保留消费边界/附件/分页；外部同人辨认仍缺具体契约，C1。 |
| R3 查询后发送/失败或 held 未发送 | D6 与接口明确 ok/held、读取目标，不回显正文。 |
| R4 迁移继续已有聊天并重启 | migration-prompt §2-7 明确账号/标题/Session/未读/凭据/重启校验及整套回滚。 |
| N1 不缩短 message/run/call ID | D1/D2 与迁移目标明确保持，§5 保留历史链和配对。 |
| N2 不改权限及群回复策略 | D3 授权、D5 群成员校验及命令触达不扩散。 |
| N3 不部署生产/合并/动主仓 | motivation、runbook、迁移 prompt 授权边界一致，本审查未执行。 |
| N4 旧书签不兼容/外部原生 ID 不盲改 | 风险段及迁移 §3/5/6 只转换本 IM 语义引用并输出新链接。 |

### 核实台账：delta-spec

| 原子 | canonical/用法/可观察性 |
|---|---|
| IM ADDED 身份跨群一致/查询后联系或提及 | conversations-messages 是正确 area；既有“会话参与者带 user_id 供成员管理”仍可保留 Actor 配置身份，新条目增加聊天寻址一致性，不要求删除旧 Actor 场景。THEN 为触达结果。外部范围需随 C1 对齐。 |
| Gateway ADDED 连续查询发送/已知群查询成员 | global-agent 是正确 area；info 是新增能力，完整成员和发送结果均可观察。 |
| 同条目/未读历史同一发送者 | 与 canonical“读历史不消费 Inbox”相容，新增跨结果一致性，无旧场景删除；外部例外需随 C1 对齐。 |
| kernel/cli | 显式 no spec delta，无新内核接口行为。 |

### 核实台账：Milestones

| 原子 | 核实结果 |
|---|---|
| M1 IM后端 | 文件所有权不与 M2 重叠，worker 检查可执行；但 picker/prompt 仍发旧标签时，不能独立实现其 reviewer 私信/mention 退出。C2。 |
| M2 PA和前端 | 两轨含真实模型/浏览器/副本重启，方向正确；明确依赖 M1 集成才能验收，是同一垂直功能的另半层。C2。 |
| 拆分举证/root迁移 owner | 可并行编码且文件无交集，但不是独立交付 milestone。可保留并行 owner 工作包，合为单个端到端 M。 |

### 整体判断

综述、图、七条决策足以理解“IM短主键、模型统一身份、内部调度不变”。原型只替换既有候选/名字展示，无新增页面。branch、Changelog、命名和范围声明齐备。AAD 风险真实：`IM/infra/channel_credentials.py:30-38` 把 owner_id 绑定密文；已有加解密入口可供一次性迁移复用。prompt 对密文/外部原生 ID 不盲替换、JWT 重新登录、未迁移 Gateway 禁止接入及整套回滚均可行动。

runbook 指向 e2e 脚本并要求实际副本启停参数记入 progress。当前未获共享现场变更授权，不应为补“现成命令”重启原现场；独立副本准备时记录即可，不增门禁。主要接口数据流断裂为 C1 外部 sender。

### 架构进攻

| 角度 | 实际攻击与结论 |
|---|---|
| 归属 | ID 生成放 IM.infra、成员解析放 IM、模型投影放 PA，无逆向 import。D4 假定 shadow 具备外部身份映射不成立；继续会把外部联系人认成 owner，造成误路由和历史身份污染。C1。 |
| 该不该存在 | 删除测试：无 alias 表、证书、Session编号或新运输层。ID helper 集中真实复用；info 隐藏授权/成员查询，避免从历史猜成员；describe 为已有入口。迁移映射限运维资产，业务无需 resolver。 |
| 深还是浅 | 复用 WorkConversationQuery._participants、GatewayConversationPersistence、inbox_result，无平行查询/投影层。简洁结构隐藏真实 receipt/part 复杂度。横切 milestone 造成错误验收时机，C2。 |
| 治本还是补丁 | 改主键和单一 mention 协议正面解决两套寻址，未硬编码群或用推进规则遮掩工具问题；但不能把所有外部成员的 owner 代记包装成统一 user_id，需明确限界。C1。 |

### Issues

- [R1-C1][CRITICAL] [现状可复用能力/决策4/消息接口/migration-prompt §5] 外部发送者统一依赖不存在的一一映射。`PA/gateway/shadow_sync.py:184-210` 将外部群里所有发送者存为 owner_user_id，只另存显示名；`global_run_coordinator.py:490-493` 在 Inbox 使用 external_user_id；IM历史直接返回 m.sender_user_id。“已有 IM shadow 参与者身份物化/映射”无法让两条路径自动一致。D4 允许“无法确定身份时保留来源身份属性”，但固定 sender 结构只有 user_id/name/type，没有定义来源字段、user_id 缺省形式及历史 owner 代记如何避免误认。**不改→worker 可能把不同飞书成员全部变成 owner 的可私信 user_id，或各自发明不兼容例外；迁移也无法凭显示名可靠补齐真实身份。** 请明确现有数据限制、具体输出及路由边界，并同步接口和 delta。若本次只统一真实 IM 用户，明确外部来源无映射时不可私信、不能当 owner，并定义两种读取对这类历史的表现；无需新增跨平台通讯录或运行时旧 ID 兼容。
- [R1-C2][CRITICAL] [Milestones M1/M2] 按“IM后端”和“PA+前端”拆 milestone，并明示 M2 集成依赖 M1，是 skill 禁止的横切拆分。M1 的 reviewer 要求私信/mention 正确，但 M2 未完成时真实 picker/prompt 仍发送旧标签；两块都不能独立交付统一协议。**不改→下游可能把后端测试通过当成 M1 用户价值退出，为只能集成完成的工作安排独立验收。** 合为单个端到端 milestone，保留当前无交集 owner 作为内部并行工作包即可；不增加 reviewer/code-review 或延长流程。

### Recommendations

无额外建议。修复上述两处后，由同一 reviewer 按真实修改范围复核。本报告不授权生产部署或共享演示变更。

### 时间记录校正

本轮实际落盘前时钟返回 `2026-09-10T07:17:24+00:00`，因此 completed_at 为该时间，duration 为 `6m01s`。Metadata 中较早的结束时间为成稿时预填值，以此实际工具时钟记录为准；不改写已落盘段落。


## Round 2

### Metadata

- reviewer: `/root/ref550_design_review`
- review_mode: `delta`
- mode_reason: 外部 sender 例外的有界语义补全，以及同一功能内 milestone 合并；影响可枚举为 D4、消息接口、两份 delta、迁移身份边界及 M1 退出，不改变权限、IM/PA 分层、短 ID 算法或运行时兼容策略。
- started_at: `2026-09-10T07:21:26+00:00`
- completed_at: `2026-09-10T07:22:28+00:00`
- duration: `62s`

### Verdict

Approved — 0 CRITICAL / 0 WARNING

### Coverage

重读修订后的 design.md、两份 delta-spec、migration-prompt.md，核对 R1 问题及直接上下游；检查最终目录为 M1-chat-identities，确认旧 M2 的原型/验收引用已改为 M1。retained_from: Round 1 — D1-D3、D5-D7 的生成、授权、提及、发送和摄取机制未变化；原型交互、生产路径、AAD 和整套回退的原证据未失效，不重复整本台账。

### 历史问题闭环

| 历史项 | Author Resolution | 本轮核实 | 状态 |
|---|---|---|---|
| R1-C1 | 已接受，定义 external sender、禁止 owner 代记冒充真实人，同步历史和迁移 | design.md:47 固定外部结构为 name/type=external/channel/source_id?，明确无 user_id、不能按 source_id 私信、未知历史不猜；两种 read 引用同一结构；两个 delta 添加外部无映射场景；migration-prompt.md:84 明确 owner 代记不能解释成发送者映射 | closed |
| R1-C2 | 已接受，唯一端到端 M1，原两侧改为内部工作包 | design.md:114-120 明确 A/B 不独立签收、root 集成退出；范围无重叠，退出保留浏览器、模型和迁移副本重启，原型/Runbook 引用都指向 M1 | closed |

### Changed atoms 与波及链

| 本轮原子 | 核实证据与结论 |
|---|---|
| D4 现状前提 | 修订准确反映 R1 代码事实：shadow_sync.py:184-210 用 owner 代记，global_run_coordinator.py:490-493 可掌握平台 ID；不再声称存在联系人映射。 |
| D4 新消息与旧历史结构 | 已明确真实 IM sender 与 external sender 两种结构；已知 source_id 保留，缺失则省略，且不将显示名当身份。可执行，不需要为缺失历史伪造用户。 |
| 写入→持久→历史→投影 | 新 shadow 保留来源元数据已作为 A/B 的明确职责：A 处理 IM 元数据读取，B 处理 shadow 写入/模型投影。现有 messages API/model 只有 sender/显示名（src/IM/api/routes/messages.py:76-82，domain/models.py:348-351），因此这是一项实际要贯通的新增数据，而非改名字即可；设计现已覆盖其写入与读取两端。具体列名属于该工作包实施。 |
| info/发送 | 仍返回实际 IM 成员；source_id 不是可发送 target，回复去 shadow conversation target。未引入外部账号系统或改变发送权限。 |
| 两份 delta | 新增外部无映射 Scenario 的 THEN 都是消费者可观察的身份/回复结果；限定旧“身份一致”声明的适用边界，不删除既有场景。 |
| 迁移 | 追加的外部边界明确真实 IM 引用照常改，外部 ID 保持、代记不冒充、未知不猜；与 §5“没有IM用户记录不编造user_id”一致。无需运行时别名或回退解析。 |
| 唯一 M1 | 合并保留两轨退出及原范围，只取消错误的独立验收时机；无交集 owner 并行仍可进行，没有新增流程。 |

### 受影响的架构进攻

- 归属：外部来源由 PA 掌握并传入，IM 保存查询所需事实，模型投影由 PA 输出；不要求 IM 访问平台或 PA 建全局账号系统，依赖方向正确。
- 该不该存在：已知 source_id 的保存避免新消息重复产生不可恢复的身份缺失，具有当前消费者价值；无联系人表、别名 resolver 或假想多态层。
- 深还是浅：同一消息表达承载两种真实身份状态，避免两个 reader 各自猜测；不新增平行读取入口。A/B 为实现所有权而非虚假的独立产品层级。
- 治本还是补丁：显式保留数据可知范围，不把 owner 代记伪装成真正统一身份，也不承诺补齐已丢失来源；解决 C1 指出的误路由诱因，保持此次工具整合范围。

### Issues

无。两项历史 CRITICAL 均关闭。

### Recommendations

无额外建议。可按已确认范围实施并完成 root 集成实测；本次通过仅为设计可行性，不代表实现或迁移已经验证。未操作共享演示、生产或提交。
