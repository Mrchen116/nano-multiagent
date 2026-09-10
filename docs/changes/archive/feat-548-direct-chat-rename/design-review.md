# Design Review: feat-548

## Round 1

### Metadata

- reviewer: `feat548_design_review`
- review_mode: `full`
- mode_reason: 首次独立设计审查，逐项核实五类承重原子与四个架构进攻角度。
- started_at: `2026-09-10T12:54:12+08:00`
- completed_at: `2026-09-10T12:58:14.749071+08:00`
- duration: `242.7 seconds`
- baseline: `/Users/czj/Repos/nano-multiagent/.worktrees/unit-feat-546`，`codex/feat-546`，HEAD `29d9518f7`。只读该 checkout 的受审产物与代码；origin/main 更新不算本轮受审内容。
- scope: 文档设计审查；没有实现、运行产品旅程、重启服务、合并或部署。只写本报告。

### Verdict

Issues Found — 1 CRITICAL / 1 WARNING

### Coverage

完整读取 spec.md、design.md、prototype.html、IM/Gateway 两份 delta，核对 IM/Gateway canonical 入口及 conversations-messages、web-chat-ux、global-agent 相关契约。覆盖全部现状断言、3 个决策、2 条澄清记录、完整用户场景、3 个 Requirement 的全部 6 个 Scenario、范围与全部非目标、4 个 ADDED Requirement、唯一 M1。没有因 M1 目录为空报缺陷。

### 核实台账

下列代码路径均相对此 checkout；引用为 reviewer 自行追查的实际代码证据。

#### 现状断言

| 原子 | 核实动作与证据 | 结论 |
|---|---|---|
| C01 顶部现有配置按钮 | 从 `src/IM/frontend/src/app/router.tsx:31-32` 的 chat 路由进入 workspace，再到 `chat-workspace-page.tsx:1167` 的 MessagePane；`components/message-pane.tsx:789-803` 只有 onOpenConfig 按钮 | 成立，落点在实际产品路径 |
| C02 私聊配置/群设置分流 | `chat-workspace-page.tsx:1201-1206` 按 isGroupKind 打开 GroupSettings 或导航 settings/agents/id；`1317-1329` 实际渲染 GroupSettings | 成立；没有 Agent 的 direct 当前无该按钮，新菜单需独立于 onOpenConfig 的有无 |
| C03 PATCH 可更新 direct 标题、空白校验和 owner 范围 | `src/IM/app.py:449` 注册 web_im_router；`api/routes/web_im.py:510-538` 先 owner-scoped lookup 再 service 更新；`api/deps.py:94-99` 注入真实 repository；`application/web_im_service.py:118-132` 调 `infra/repositories/conversations.py:393-421`，无 group-only 条件，trim 空值拒绝 | 成立；owner 校验在路由，repository 负责持久化 |
| C04 列表/顶部消费 title | `components/conversation-sidebar.tsx:232,266` 输出 c.title；`components/message-pane.tsx:769` 输出 conversation.title | 成立 |
| C05 describe 私聊覆盖名称 | `src/IM/app.py:373-382` 组装 GatewayWork → `ws/gateway/runtime.py:163` 分派 conversation.query → `ws/gateway/work.py:31,80` 调 WorkConversationQuery → `application/work_conversations.py:75-81` 覆盖名称 | 核心断言成立；严格说只有 others 非空时覆盖，不是无条件 |
| C06 list/read 消费存储标题 | `work_conversations.py:124` 的 list 返回 title；`234-242` 的 conversations.read 仅返回 target/messages/history_scope/pagination，没有 name/title | 部分不成立，见 R1-W1 |
| C07 Gateway check/read 前 describe | `personal_assistant/gateway/composition.py:280-292,331-334` 注入真实 conversation_reader；`global_inbox.py:551-564` 仅 Inbox check/read 刷新，`510-535` describe 后更新 target | 成立，限定 Inbox；普通 conversations.read 走 `565-578` |
| C08 保留 ID、消息、Session、成员、owner 与包边界 | PATCH SQL `conversations.py:413-417` 只更新 title/pinned/muted；describe `work_conversations.py:82-84` 只组织响应；当前调用通过 WS，不要求 IM import agent 或 Gateway 内部 | 对 native 私聊成立；标题持久保留仍受 C12 影响 |
| C09 群设置、消息菜单、Agent 配置保留 | 群设置见 C02；消息级 Dialog 仍在 `message-pane.tsx:975-1024`；决策1只替换顶部 direct 操作 | 设计不触及既有消息交互与群设置 |
| C10 renameMutation、查询刷新复用 | `chat-api.ts:153-161` 已有 PATCH；`chat-workspace-page.tsx:915-924` 已有 mutation/invalidate；工作名称是 `features/settings/agents/agent-work-panel.tsx:77` 的独立 work-conversation-names 查询 | 成立，design 接口段明确同时刷新工作名称查询 |
| C11 样式/i18n/表单复用与历史 | `components/group-settings.tsx:83-109` 已有 trim、错误保留、成功关闭模式；`new-group-modal.tsx:188` 现有 chat-modal；`message-pane.tsx:975-1024` 已依赖 Radix Dialog。feat-438/546 能力在上述当前代码中实际存在 | 成立，无需新建通用表单框架 |
| C12 存储标题足以成为稳定用户名称 | 主动检索所有 UPDATE conversations/title，追到 `shadow_sync.py:171-189` → `web_im.py:437-461` → `conversations.py:237-245`；重复外部同步覆盖 title；竞争分支 `350-357` 同样覆盖 | 不成立，设计遗漏真实第二写入者，见 R1-C1 |

#### 决策

| 决策 | 四问与证据 | 结论 |
|---|---|---|
| D1 新增会话菜单 | 动作、位置、无 Agent 情况、群聊保留均已拍板；spec:13-18 明确用户选择新增菜单和按会话改名；chat-types.ts:261-264 的 direct 分类包含外部 direct，没有自动排除 shadow | UI 边界清晰，但“所有 direct”扩大了必须处理的标题写入面，见 R1-C1 |
| D2 统一存储 title | 与 spec:13,22,55-59 同名要求一致；取消 describe 拼名无需新抽象，参与者仍由 work_conversations.py:264-281 独立读 users.display_name；没有与 D1/D3 的字段冲突 | native 路径合理；禁止新增标记且不改 shadow 写入者时无法保住覆盖范围内的自定义标题，见 R1-C1 |
| D3 复用 PATCH 小表单 | spec:45-51 的取消、空白、失败均有明确状态；pending、Escape、外部点击、焦点、切换会话重置均已规定；现有 group-settings.tsx:83-109 提供相同错误模式 | 已拍板，完整且无新接口歧义；交互实现细节可由 worker 决定 |

#### spec 约束

| 原子 | 首文档约束与设计落点 | 结论 |
|---|---|---|
| S01 Q1 | spec:13-14 “按会话改名”；D2 保存 conversation.title、D3 调已有 PATCH | 覆盖；外部同步缺口归 R1-C1 |
| S02 Q2 | spec:16-18 “新增吧”；D1 菜单含重命名与 Agent 配置 | 覆盖，不把未来用途扩成额外动作 |
| S03 完整用户场景 | spec:22 “不同私聊”“不是 Agent 的名字或个人备注”“一致的新名称”“刷新后名字保留”“原聊天内容继续可用”；D1-D3、风险、M1 R2-R4 分别承接 | native 覆盖；所有 direct 的持久性缺口见 R1-C1 |
| S04 菜单 Requirement/Scenario | spec:26-30 桌面/手机及配置可用；D1 与 M1 R1 | 覆盖 |
| S05 改标题 Requirement/保存 Scenario | spec:32-38 “刷新后仍保留”“继续聊天”；D3 PATCH、风险不改 Session、M1 R2/R3 | 外部私聊下次同步不保留，见 R1-C1 |
| S06 同 Agent 其他会话 | spec:40-43 “另一条会话名和 Agent 名称不变”；PATCH WHERE id；D2、不触及 profile、M1 R3 | 覆盖 |
| S07 取消/空白 | spec:45-47 “原标题保留；纯空白不能保存”；D3 trim 禁用及取消 | 覆盖 |
| S08 保存失败 | spec:49-51 “保留输入供重试，不把未保存的名字展示为已生效”；D3 成功后刷新，失败保持表单 | 覆盖 |
| S09 Agent 名称 Requirement/读取 Scenario | spec:53-59 新名称、回复目标不变、Agent 改名不覆盖；D2 describe、既有 target，M1 R4；agent_profiles 更新在 repositories/agents.py:731 不更新 conversations | Inbox 路径覆盖；“读取”现状分类需修正 R1-W1，外部写入保留见 R1-C1 |
| S10 范围 | spec:63 “私聊会话标题…桌面和移动端…已有会话访问范围”；D1 不限制为 native direct，PATCH owner 校验不动 | 权限与设备覆盖；shadow 未被 spec 排除 |
| S11 非目标：个人备注名 | spec:64；D2 无 per-user 字段 | 不越界 |
| S12 非目标：Agent 改名 | spec:64；D3 只 PATCH conversation | 不越界 |
| S13 非目标：自动起标题 | spec:64；D2 保留当前默认 title，不引入生成器 | 不越界 |
| S14 非目标：消息历史 | spec:64；更新 SQL 不操作 messages，M1 R3 | 不越界 |
| S15 非目标：会话身份 | spec:64；接口沿用 id，无新建或映射 | 不越界 |

#### delta-spec

| 条目 | canonical/用法/消费者核对 | 结论 |
|---|---|---|
| IM ADDED 私聊提供会话菜单 | 核 `docs/specs/im/conversations-messages.md:234-273` 原群管理条目仅覆盖群，没有既有私聊菜单条目需被顶替；该目标承接会话管理，不复制消息菜单契约；THEN 是用户操作结果 | ADDED 合理 |
| IM ADDED 私聊可以按会话修改标题 | 与同文件原“群会话支持成员增减、改名与解散”并行；完整包含保存、其他会话、空白、失败 4 场景；无内部函数断言 | ADDED 合理，设计对外部标题的实现落点缺失见 R1-C1 |
| IM ADDED Agent 使用用户设定的会话名 | IM 消费者允许 Gateway/Agent 查询；目标为会话名称，非工作轨迹；THEN 为新名称与稳定回复目标，未强加内部调用 | ADDED 可成立；需配合修正 R1-W1 的接口边界 |
| Gateway ADDED Inbox 与聊天使用同一会话标题 | canonical global-agent.md:148-152 只要求真实可读来源，不规定按参与者拼名；新增同 title 要求不与之冲突，也未删除其消费/身份/预算 Scenario | ADDED 合理，消费者为全局 Agent，THEN 可观察 |
| 未变化包 | design:71 明确 kernel/cli no spec delta；改动不进入其职责 | 齐全 |

#### milestone

| 条目 | 核实 | 结论 |
|---|---|---|
| M1 | design:81 唯一 M 为菜单→持久保存→UI/Inbox 同名的端到端价值，未按前后端或测试横切；不存在并行范围交集；R1-R4 覆盖 spec 的场景，W1 包含测试/构建/契约/真实链路 | 结构合格；R1-C1 修复后必须同步范围和外部私聊持久性验证；R1-W1 应明确 R4 用哪个读取入口 |

### 整体判断

- 上层总览、图、3 句决策足以理解“一个标题字段、两个显示消费者”；没有实现脚本式拆分或 TBD。Unit branch、Changelog、原型链接齐全。
- native 数据流闭合：React 路由→顶部菜单→已有 PATCH→列表/工作查询刷新；Gateway 注入的 reader→IM describe→Inbox 名称。外部 title 第二写入者未纳入图和风险，是本轮核心缺口。
- 原型与文案的正常菜单/改名/取消/空白样式一致，但 prototype.html 没有保存失败状态和异步 pending 演示；design 明文规定失败语义，故不以此单独阻断，可补展示见 R1-R1。
- Runbook 指定保留现场、59669、现有 runtime、构建和健康 endpoint；已只读确认 `/tmp/feat546-reload-preserved.py` 存在，使用固定隔离目录/端口和 config，不是生产启动脚本。本轮不执行重启，也不将其文字中“已验证”的主张当作本轮运行证据。

### 架构进攻

| 角度 | 主动动作与证据 | 结果/长期代价 |
|---|---|---|
| 归属 | 从 app/router、Gateway composition 和 IM app 正向追到真实服务；PATCH 所有权在 IM，表单状态在前端，Gateway 经协议读名称 | 分层自然，无 IM→agent 或产品包互相 import；无需 Gateway 新增名称政策 |
| 该不该存在 | 对 DirectConversationMenu 做删除测试：直接塞入已有大型 MessagePane 会把菜单/表单焦点与失败状态混进消息动作；它集中同一会话操作的短生命周期，且不引入 generic factory/schema | 单一具体组件合理，没有为未来多态加接缝；未来“更多配置”不意味着现在新增配置框架 |
| 深还是浅 | 独立搜既有 rename/updateConversation、GroupSettings、Radix Dialog；现有 API/错误模式可直接复用，design 未新造后端 rename endpoint 或第二标题存储 | 没有发现必然重复封装；实现应继承已有 Dialog 能力，避免手写第二套焦点管理 |
| 治本还是补丁 | 独立搜索全部 title 写入，发现外部同步的既有 title 覆盖，见 C12 | 只改 describe 和 UI 是 native 局部修复；若仍对所有 direct 宣称稳定改名，未来会出现“保存成功后又还原”，继续补消费者缓存无法根治第二写入者。R1-C1 必须在标题所有权/写入处解决 |

### Issues

- [R1-C1][CRITICAL] [现状分析 / 决策 1、2 / M1] **所有 direct 的可改名范围没有处理外部 shadow 同步覆盖标题。** `design.md:39` 给 direct（包括无 Agent 情况）提供改名，`:42` 规定复用 title、不新增标记，`:49-50` 只保留 PATCH 并移除 describe 覆盖；但外部私聊也被 `chat-types.ts:261-264` 分类为 direct，正常同步 `shadow_sync.py:171-189` 调 find-or-create，`conversations.py:237-245` 无条件覆写已有 title，竞争恢复分支 `350-357` 同样覆写。**不改→用户在外部私聊保存成功后，下次外部消息同步即恢复默认标题，违背 spec:35-38、63 的持久改名范围，worker 按当前 M1 完成普通私聊测试仍会漏掉此真实路径。** 请作者拍死用户标题与外部同步标题的优先级，在持久化写入处给出保持用户标题的完整设计并同步 delta/M1；若要限缩到 native 私聊，必须先显式对齐首文档范围，不能由 worker 隐式隐藏入口。
- [R1-W1][WARNING] [现状分析第 3 条 / Agent 读取边界 / M1 R4] **“list/read 则消费存储标题”把两种 read 混在一起。** IM `WorkConversationQuery` 的 list 在 `:124` 返回名称，但普通 conversations.read 的 `:234-242` 不返回名称；Gateway 只在 inbox check/read 前刷新 describe（`global_inbox.py:551-564`），conversations.read 直接返回历史页（`:565-578`）。**不改→worker/reviewer 可能把任意 read 当成已覆盖的新名称读取入口，导致 R4 按错误响应断言验收，或临时扩大 history API。** 请明确名称保证对应 Inbox check/read 与 conversations.list，普通历史 read 当前是否需要新标题字段由设计明确决定，并修正现状断言；不要求为了错误的一句现状描述强行扩 API。

### Recommendations

- [R1-R1] 原型表将“保存失败”标为 must-match，但 prototype.html 无该状态；补一个可切换失败示例，便于人工确认内联错误与保留输入的位置。行为已在 D3 写清，建议不独立阻断。
- [R1-R2] 实施表单优先复用项目已依赖的 Radix Dialog 焦点能力；保留具体 DirectConversationMenu 即可，不新增通用重命名框架。

### Author Resolutions

- R1-C1 accepted：已核对 repository 正常复用与竞争恢复两处 title 写入。设计新增 direct 的 title_is_custom 内部标记和两处存储写入保护，加入 schema 幂等增列、未改名 direct/group 保持测试及 R5 外部同步真实链路。首文档和 IM delta 对已确认私聊范围补充后续同步保留场景，不缩小范围。用户已确认“按会话改名”和新增菜单，存储保护不改变该决策。
- R1-W1 accepted：现状与接口段明确 Inbox check/read、conversations.list 名称保证；普通 conversations.read 不新增字段。R4 对齐实际名称入口。
- R1-R1 accepted：原型补充失败开关、内联错误及保留输入示例。
- R1-R2 accepted：实施使用已有 Radix Dialog，沿用现有焦点与遮罩能力。

## Round 2

### Metadata

- reviewer: `feat548_design_review`
- review_mode: `delta`
- mode_reason: 同一 reviewer 保留 R1 完整台账。新增外部同步 Scenario 是原有全部私聊范围的显式验收补充，不改变用户范围或非目标；语义变化可枚举为内部标记、PATCH 标记写入、两处 shadow 标题保护、名称读取边界和对应 M1/delta。默认值增列不进入 HTTP DTO、不引入跨包接口或迁移既有标题，影响面有界，故选择 delta 而非 closure。
- started_at: `2026-09-10T12:59:40+08:00`
- completed_at: `2026-09-10T13:01:24.506720+08:00`
- duration: `104.5 seconds`
- baseline: `codex/feat-546`，HEAD `29d9518f7`，tracked code 无 diff。只追加报告；未实施、重启或走产品旅程。

### Verdict

Approved — 0 CRITICAL / 0 WARNING

### Coverage

本轮重读全部修订产物与 Author Resolutions；重新核实 R1-C1、R1-W1、R1-R1、R1-R2，R1 台账 C06/C12、D2、原 D3（现 D4）、S03/S05/S09/S10、IM 改标题 delta 与 M1；新增 D3 和数据库幂等迁移路径单列核实。对存储标记重跑四个架构角度。

retained_from: Round 1 — HEAD 与 tracked code 未变；菜单 D1、未改动的 UI/PATCH 生产 wiring、owner 隔离、2 条用户澄清、取消/空白/失败/其他会话和全部非目标、Gateway delta、其余 IM delta、运行现场约束均未发生语义变化。原 D3 仅顺延为 D4，行为保持。C06/C12 的旧错误结论不继承，以下重核证据替代。

### 历史问题闭环

| 历史项 | Author Resolution | 本轮核实 | 状态 |
|---|---|---|---|
| R1-C1 | accepted，内部标记及两处写入保护，补 R5 | design 决策3同时点名正常复用与竞争恢复，规则明确以现存 direct + title_is_custom=1 为准；spec/IM delta 新增“外部私聊后续同步保留手动改名”；M1 增 db.py/repository 与 R5，风险列对应回归验证 | closed（设计闭环，尚非实现证据） |
| R1-W1 | accepted，明确不同 read 入口 | design 现状不再称 conversations.read 返回标题；接口段明确 Inbox check/read 与 conversations.list，普通历史页不扩字段；M1 R4 一致 | closed |
| R1-R1 | accepted，原型演示失败 | prototype.html 的 fail 开关使提交展示 error 后直接 return，保持 nameInput 与原标题；取消开关后重试才更新标题并关闭 | closed |
| R1-R2 | accepted，复用 Radix Dialog | Author Resolution 明确沿用既有 Radix Dialog；design D4 继续规定焦点、遮罩、取消、pending 行为 | closed |

### 本轮重查证据

| Changed atom | 核实动作与证据 | 结论 |
|---|---|---|
| C06 / 名称接口 | 重读 `src/IM/application/work_conversations.py:120-129,234-242`：list 有 name，read 无标题；重读 `src/personal_assistant/gateway/global_inbox.py:551-578`：Inbox 刷新 describe，普通历史 read 直接物化历史页 | 修订的现状/接口/M1 R4 与真实路径一致；对应原始澄清的 Inbox 同名意图，不为错误前提扩 API |
| C12 / 外部第二写入者 | 重读 `src/IM/infra/repositories/conversations.py:237-245,350-357` 两处 UPDATE title；D3 对两处规定同一 SQL 优先规则，使用数据库当前类型和标记 | 保护落在真实写入者，未只保护消费者缓存或漏竞争分支 |
| 新增数据库现状 | 从 `src/IM/app.py:283-284` 追 initialize_schema 到 `infra/db.py:359-363` 初建并调用 migration；`:426-429` 以 PRAGMA 得列名后幂等增列；当前 CREATE 表位于 `:34-51` | D3 指定初建和旧库幂等迁移，落点是启动真路径，不是只供测试的 schema |
| D2 存储标题统一 | `work_conversations.py:75-83` 的 override 被取消后 title 直接输出，参与者仍独立；D2 由“不新增标记”改为“内部标记”，与 D3 自洽 | 字段仍只有一个权威可读标题，标记只表达用户写入优先级 |
| D3 标记初始化和 PATCH | 默认 0 保持所有旧标题原值；`conversations.py:393-417` 已有 title 可选输入与 trim/非空校验，现存 type 可查；D3 明确仅显式非空 title + direct 置1，置顶/静音不改标记 | 无需新增请求参数，调用方不需猜是否手动改名；错误输入不得先落标记由既有校验顺序自然约束 |
| D3 direct/group 边界 | 两处写入以现存 direct 且标记1保留标题，否则来源 title；仍同步 type。规范明确“现存”而非任意新旧类型混用；未改名 direct 与 group 使用原逻辑 | 边界已拍死，正常场景下没有群名行为回归；不新增重置开关或假想类型迁移框架 |
| D3 API/DTO 边界 | `domain/models.py:101-124` 的 Conversation 对外值与 `conversations.py:624` 的读取不依赖新增标记；D3 不让内部标记进入 HTTP DTO | SQL 内部策略可以封闭，不要求把标记贯穿前端/Gateway |
| D4 / 原型 | 正文保持输入预填、trim、失败保留和成功后刷新；prototype.html 新增失败分支而不提前改标题 | 失败演示与原产品行为约束一致，没有新用户操作需求 |
| S03/S05/S10 与新 Scenario | 首文档用户场景仍为“不同私聊”“刷新后名字保留”；新增外部后续同步场景把原已覆盖的 direct 类型具体化，D3/M1 R5 对应 | 没有限缩范围或夹带外部渠道自动改名能力 |
| S09 / R4 | 原澄清点名 Inbox；design R4 明确 Inbox check/read、conversations.list | 不再让 worker 把 conversations.read 当作名称响应，回复目标/消息身份保持 |
| IM delta | 新增 Scenario 的 THEN 是“用户设置的会话名保持，消息继续正常显示”，不暴露 title_is_custom 或 SQL；重新核 canonical `docs/specs/im/conversations-messages.md:100-119` 现有标题场景是初建默认名，并未要求已手改标题持续被重置 | 在新增私聊改名 Requirement 中追加该场景合理，保留现有外部初建默认标题、同四元组身份和群场景；无需顶替初建契约 |
| M1 | 范围补 db.py 和 conversations repository；R5 是同一改名价值的持久性出口，不拆新横切 milestone；风险明确正常复用/竞争恢复/旧库重复初始化/未改名 direct/group 验证 | 单 M1 两轨可验，已覆盖新增写入与迁移风险 |
| 风险与回退 | schema 默认列可留存，原 title 不改写；文档明确退回旧 shadow 写入逻辑会丢失保护，需暂停同步或接受恢复旧行为 | 风险可见，不宣称回退旧代码仍保留新保护 |

### 架构进攻（受影响角度）

| 角度 | 本轮攻击 | 结论 |
|---|---|---|
| 归属 | 检查是否把标题保护放在 Gateway/前端绕过 repository | 标记与优先级同在 IM 持久层；两写入者共享表数据，未倒置包依赖 |
| 该不该存在 | 删除 title_is_custom 后能否分辨用户改名与外部默认标题？只剩 title 值无法可靠还原来源；保留所有旧标题又会改变未改名同步行为 | 一个内部布尔状态是当前已观察双写入冲突所需；无额外历史表、服务或策略类 |
| 深还是浅 | 是否把“判定当前用户标题”交给每个调用方传 flag 或二次 PATCH？ | 现有 PATCH 意图与数据库 SQL 足够封闭，标记不穿透 DTO；无需新公开接口或泛化封装 |
| 治本还是补丁 | 是否只修普通复用、遗漏竞争恢复，或缓存临时覆盖？ | 两处 SQL 均被明确覆盖，当前数据库标记决定优先级，正面解决第二写入者；没有保留已知的标题覆写债务 |

### Issues

无新增问题；R1-C1 与 R1-W1 已在设计层关闭。

### Recommendations

无需新增建议。按现有 M1 实施并完成其中真实链路与迁移/双分支验证即可进入后续验收；本轮 Approved 仅表示设计可交付实施。
