# feat-572-public-im-protection — Gate 2 独立设计审查

## Round 1

### Metadata

- reviewer target：`/root/public_im_design_review`，独立于本轮 spec/design/prototype 作者；执行 `change-design-reviewer`。
- review_mode：`full`。
- mode_reason：首次 Gate 2，覆盖冻结的全部需求、设计、六个 delta、原型和 M1 骨架；不继承 spec-review 的设计放行结论。
- started_at：`2026-09-30T09:29:52+00:00`。
- completed_at：`2026-09-30T09:31:27+00:00`。
- duration：`PT1M35S`，仅统计首次显式时钟采集至结论定稿；此前只读材料核对未采集起始时刻，不冒充完整执行耗时。
- executed_base / validated_at：`main` HEAD `da99b8981576b4f782ec71a7ae51f4c06bdb870a` 加以下冻结的未提交文档；不是产品实现验收。
- 受审 blob：spec `e580b9cf718b427e7583ecbd2a4130de12958ed4`；design `fbf2f4e382da0d6860c860f6cdc0be2b146a4ee5`；prototype `ca0444eb0bea620f901d694afa53cbf839f546d3`。实际 `git hash-object` 与派发版本一致。
- delta blob：IM agents-nodes `e6c98a8a6aae812b1bcea7038426587f99dd88bf`；auth-tenancy `9aa151e0f50352116dd9796111de7726a8941244`；conversations-messages `f3c12c94edc1629f2968aa82a37ff45231cbf761`；task-graphs `05c62ba6f2f9505f33f51ef0bb40f7b06e4f459a`；Gateway external-channels `a095d21c8ca4bfcf849535cfaeb6ecd4c7741edb`；task-graphs `604089a9e1621ea9c11d8014fa885dfc41228d92`。
- 现场：已核对 checkout/branch/status，已有大量无关 dirty/untracked 文件。本轮只新增本报告，不改受审文件、不提交、不启动服务、不操作生产或再派 agent。

### Verdict

**Issues Found — 0 CRITICAL / 3 WARNING。Gate 2 未通过。**

公司的单一边界、任务共享及本机整体交接方案总体可落在既有职责上。阻断项是外部入站资格检查与群背景/既有沟通的边界尚未闭合、对外连接与离线契约 delta 遗漏，以及设计明确要求的必验资源仍未落实。没有将尚未实现的功能或未授权公网发布当作已完成证据。

### Coverage 与独立证据

| 核对面 | 设计/需求覆盖 | 实际入口与判断 |
| --- | --- | --- |
| 生产组装、依赖与复用 | design:13–40、62–67 | IM 实际 `create_app` 在 `src/IM/app.py:278–447` 组装 AuthService、UserStreamRegistry、GatewaySessions、TaskGraphService 与 GatewayRuntime，493–505 注册各 HTTP router；512–577 是两条真实 WS 入口。PA 的 `main.py:126–136` 进入 process lifecycle，`process_lifecycle.py:1008–1012` 默认调用 `compose_gateway`。这不是测试专用 helper。继续由 IM 决定中心资格、对象授权、任务持久事务，PA 负责本机密钥/配置和模型上下文，边界合理，不需要 kernel 或 coding_cli 参与。 |
| 公司准入、会话、管理员、停用 | spec:175–296；design:71–95；auth delta | 当前 AuthService 的 refresh 撤销集确实为进程内集合（`auth_service.py:95–97,149–162`）；`api/deps.py:292–349` 是真人/机器/共享数据入口，`require_conversation_access:352–383` 是实际成员/机器 Agent 授权。持久 session/epoch、写事务内二次检查和统一连接撤销对应现有入口；保留历史、拒绝旧连接，不等于远程关机。初始真人一律 pending、本机指定管理员避免首个公开注册者取得管理权；普通策略只读与管理员不自动获得私聊/设备管理权均覆盖。 |
| 单一 Gateway/Agent 管理者与整体交接 | spec:298–318；design:97–109；agents-nodes delta | 当前 `binding_store.py:55–110` 已有 `BEGIN IMMEDIATE` 和 node/Agent 原子归属变更，但74–75拒绝跨 owner，不能直接声称现有绑定已支持交接。真实组装在 `composition.py:584–604` 加载持久 X25519 key 并上报；`channels/channel_credentials.py:60–121,141–169` 已有 seal/open 和 0600 私钥，IM/PA 各自拥有协议实现。新操作表、域隔离挑战、完整 manifest/revision 与 owner AAD 重封、epoch 撤销和提交后恢复解决本 unit 的实际交接问题，复用密码原语合理；没有引入签名密钥误用、多人管理或管理员额外审批。 |
| 公司任务共享、真实能力、修改/删除 | spec:320–392；design:111–127；两份任务 delta | Web 实际 router `api/routes/task_graphs.py:15–60` 只读并转 TaskGraphService；`app.py:431–439` 把同一服务接入 GatewayTaskGraphs。当前服务 `application/task_graphs.py:113–171,213–241` 在事务内做真实 actor、owner、回执、来源成员和 revision 检查；`ws/gateway/runtime.py:170–175` 要求注册 sender。PA `gateway/task_graphs.py:45–73,98–126` 从真实 session provenance、当前生效配置和实际 run context 取身份/来源。将任务 owner 过滤替换为公司资格，保留工具开关/allowlist 与 on-demand 查询，接口方向成立。删除仅整图/子树、真实用户范围确认、revision、独立有界回执，没有回收站或全历史版本系统，复杂度与需求相称。 |
| 群活动、来源保护与独立生命周期 | spec:394–417；design:113–121；IM task delta | 当前 TaskGraphService:234–236 只更新受影响节点的 last_chat_id；current `im/task-graphs.md:19–31` 要求独立生命周期与逐节点回聊。新增节点×聊天多对多活动关系补上 A/B 群关联，不能靠改 last_chat_id 实现；保留来源成员投影、退群后公司任务读取与解散不删图的决定均覆盖。IM delta 移除旧账号共享 Requirement 后，把可选来源、独立生命周期、逐节点回聊与浏览讨论入口重新投影；其他图结构/展示 Requirements 仍由 current 保留。 |
| 外部身份、上下文泄漏与 Q14 | spec:109–115,356–360,389–392；design:123–129 | 双端证明、provider 验证稳定身份、不可借 owner/模型自报或旧上下文代查，足以表达 Q13；外部群原投递去向和无需核验受众也写出。但真实 PA Pipeline 同时承担背景消息与触发运行，资格门禁没有区分这两类（见 R1-W1）；IM 离线时的对外结果也必须同步 canonical（见 R1-W2）。没有要求为 Q14 建立群受众权限同步。 |
| 附件自动下载、配额与实时资源 | spec:419–438；design:131–151；IM conversations 与 Gateway external delta | 实际 `composition.py:670–674` 把 `build_im_attachment_fetcher` 接到 resolver，而 `image_attachments.py:157–178` 当前能 GET 任意绝对 URL。另有默认 resolver 构造点512及 coordinator fallback、`reply_images.py:338–345` 的自动 Markdown 图片读取入口，必须一起覆盖；design:135–137 已明确这组范围，未以单个安全 helper 代替接线。原上传入口 `messages.py:378–410` 是 Request streaming，新增配额预留/有界流式读取可直接扩展，未误认为它是 multipart UploadFile。限额、来源与目标账号限流、队列/慢连接、错误反馈和正常飞书原生图片回归都有出口。 |
| 前端、原型与验收投影 | design:165–187,207–250；prototype:7–28 | 原型静态包含 pending/suspended、成员停用影响确认、公司/群活动切换、保护来源、设备本机等待/恢复、身份双端提示和限流/配额反馈，响应式 CSS 有手机重排；设计明确 must-match/may-adapt/out-of-scope 及真实截图出口。未把静态样例当真实产品、权限或实际 viewport 验收。浏览器只读打开本地 file URL 被工具协议策略拒绝，未绕过或另起服务；本轮原型结论仅来自静态 HTML/事件处理核对。可选样例改进见 R1-R1。 |
| 迁移、隔离、发布/恢复与 M1 | design:90–95,153–161,199–250 | 公网先关、备份/匹配版本恢复、稳定 secret、单 worker、loopback 与 only-IM Tunnel、可信代理、日志凭据保护对应需求。单 M1 有用户“你自己规划”依据，范围虽大但完整保护先于发布合理，不要求机械拆层或并行 worker。M1 只有 `.gitkeep`，未预写 tasks/progress。E2E 脚本确有隔离配置和真实 `--auto-bind` 入口（`e2e-up.sh:252,324–338`），设计承认需增管理员初始化与新协议，未把旧脚本当新能力。手机/外部/免费配置资源未落实（R1-W3）。 |

架构与复杂度判断：SQLite session、节点操作记录、身份 link、任务活动关联及短期删除回执各有直接需求与明确生命周期；在同一 IM 服务内扩展既有应用/存储边界，比另建权限平台、任务中心或多租户组织层更适当。没有证据要求 Redis、多 worker、任务子树 ACL、全群受众核验或额外审批，因此不将这些作为设计改进项。尚未完成具体代码/集成测试，这一判断不替代之后的 code review 与产品验收。

### 历史问题闭环

这是首个 design review Round，没有历史 Gate 2 issue。本 unit 的 spec-review W1 已在该报告 R2 关闭；本轮独立核对冻结 spec:109–115 与 design:123–129，确认 Q13/Q14 是受审要求。需求审查 Approved 不能消除下面的设计问题。

### Issues

#### R1-W1 — 外部资格门禁尚未区分群背景消息与实际交办人

- **位置**：`design.md:125–129`；关联 `spec.md:112–115`、`specs/gateway/task-graphs.md:32–36`、M1-R7 (`design.md:246`)。
- **证据**：125要求外部消息在进入含公司资料的上下文前核实 sender 的 active 关联，无法核实时只返固定提示，未经核实输入不得进入后续 Inbox；129又要求沿用外部群正常沟通、不核验全群成员。现有生产 `composition.py:960–979` 将外部托管 channel 接入同一 InboundPipeline；`inbound_pipeline.py:192–205` 对 `sync_only` 或不触发回复的消息仍写 group_context。current `gateway/external-channels.md:28–38,307–327,387–391` 明确未 @ 的普通群消息进入背景、后续触发引用，且不启动 run/发送回复。背景消息提供者不是该次公司任务的实际交办人。
- **实际后果**：若实施把125的检查统一放在 Pipeline 入站处，未关联群成员的普通背景会被丢弃或收到关联提示，active 成员随后 @Bot 也失去原背景；群继续原样沟通的要求被实质收紧。若为保留背景直接绕开检查，却未冻结当前触发者/操作发起者，又可能将一个未关联人的背景指令或被拒绝请求伪装为 active 成员交办/自主工作。现有文字不能指导这两条路径共同成立；这不是要求核实群受众。
- **建议闭环**：明确“实际触发/交办请求”和“仅背景/影子同步”的资格检查落点与作用：背景可怎样保留、谁授权本次运行和公司任务操作、如何避免 rejected 请求后续变主动任务。沿用 Q14，不扩展全群审批/身份同步；补一条“未关联成员发普通背景，active 成员随后 @Bot”的具体验证投影，并继续拒绝未关联者主动调用公司任务。
- **状态**：open。

#### R1-W2 — 对外 WS 与外部离线行为的 canonical delta 未闭合

- **位置**：`design.md:125–127,157,190–197`；`specs/im/agents-nodes.md:3–27`、`specs/gateway/external-channels.md:3–14`。
- **证据一（WS）**：157明确改为 HTTPS 取得一次性 session/epoch ticket，长期 JWT 不进连接 URL。现有 current `im/agents-nodes.md:644–673` 却完整规定 `/im/ws/user?token=<jwt>` 或 bearer JWT 子协议，合法 JWT 能 resume；生产 `app.py:553–577` 实际按 query JWT认证。本 unit agents-nodes delta 只替换设备绑定，没有 MODIFIED 这条浏览器事件流 Requirement。新增 `conversations-messages` 中“不放长期 token URL”的一般声明不能替换旧明确连接协议。
- **证据二（离线）**：125将无法核实资格的外部输入固定拒绝，127发送外部结果前再检查；其目标是防止既有上下文代查，不能任意离线放开。但是 current `gateway/external-channels.md:393–407` 明确 IM 不可达时飞书普通私聊/群仍正常回复，419–433又保证 managed channel 从 cache 启动后消息主路径可用。本 unit external-channels delta 只有附件 Requirement；没有定义 IM 不可达时身份关联/资格不可核实的结果、普通外部回复的适用前提以及仍保留的离线 listener/配置自治。
- **实际后果**：按六份 delta 归并之后，current 将同时要求长期 JWT URL 与只准 ticket，并继续承诺离线正常模型回复却没有资格可核实前提。前端/外部消费者、回归测试和后续 unit 会据两套冲突契约实施，或为保旧测试重新留下凭据/资格旁路。
- **建议闭环**：对真正改变的 canonical Requirements 写完整 MODIFIED 条目。浏览器保留既有成员事件、resume/sync、重连及切号语义，明确 ticket 获取/拒绝/重试的消费者结果；外部离线场景先明确新门禁下的可观察结果与保留的配置/listener自治，再同步 delta，不能以一句“正常回复保持”掩盖改变。无需添加第二套认证产品或假想离线权限框架。
- **状态**：open。

#### R1-W3 — Gate 2 必验资源仍未落实

- **位置**：`design.md:67,222–232,238,245–246`。
- **证据**：资源表将真实模型、真实飞书已关联/未关联身份、域名/Cloudflare免费配置与源站能力列为未验证，真实 iPhone/Shadowrocket/Tailscale 状态及参与/上线授权待落实；232明确“Gate 2 在必验资源未落实时保持未通过”，238也把资源确认列为 M1 依赖。本轮只独立确认仓内 `.venv`、`config/e2e/gateway.yaml` 和既有私有飞书 env 文件存在，没有读取/公开 secret，没有证明模型在线、两个真实身份可用、Bot监听归属、Cloudflare权限或手机参与。
- **实际后果**：目前若 Approved，实施 owner 会收到“前置已满足”的错误信号；最后无法完成 M1-R6/R7 时，只能偷偷降成 mock/窄屏验收，或因未获上线授权而卡在完整交付之外。资源状态写得诚实，但这不等于已经落实其自定 Gate 2 条件。
- **建议闭环**：落实必需资源来源、可用性/权限与真实外部身份/手机参与安排，证据放本 unit 且脱敏；涉及真实公网开放保留独立授权，不能为通过设计审查直接发布。这里不要求预先验收尚未实现的新功能，也不要求当前 reviewer操作生产。若确实要把某前置移到后续门禁，应明确调整依赖及真实验收保障，不可只删“不通过”一句而保留无法执行的完整 M1承诺。
- **状态**：open。

### Recommendations

#### R1-R1 — 可选：让原型状态边界与产品导航更容易核对

`prototype.html:11,25–28` 中 pending/suspended 仍保留可切换 Tasks/Agents 的桌面主导航；仅顶部“查看状态”被设计列为 out-of-scope。身份页也只有演示确认码/解除提示，没有完整已完成/失效的样例。可以让产品导航在无资格演示状态不可用，并补完整/失效示例，或明确哪些演示控件只是跨状态跳转。实际产品的路由/cache保护已在 design:86 与 must-match表写明，因此这一 mock交互润色不单独阻断，不能据它反推真实产品已存在权限漏洞。

### 待处理与结论边界

作者核实并按 workflow 追加 Author Resolutions，完成 R1-W1/R1-W2 的设计/delta修订及 R1-W3 的资源落实后，再冻结版本交独立复核。R1-R1 可选，不要求实施审查循环追逐样例细节。

本报告只审文档能否指导实现，未执行产品测试、未发布公网、未验证外部平台或手机；没有把 current 代码当作新功能已具备，也没有把 spec-review 已 Approved 当作 Gate 2 通过。

### Author Resolutions

- **R1-W1 — accepted**：design 外部输入段改为既有触发判定之后、可执行 Inbox/run 入队之前核实实际交办人；非触发群背景保留、不发身份提示；执行身份固定到真实触发消息，背景不升级为指令或确认，被拒请求不进入稍后自主执行。Gateway external-channels delta 同步场景；不建设全群成员核验。
- **R1-W2 — accepted**：IM agents-nodes delta 完整修改用户 WS Requirement，保留 resume/sync/重连/切号场景，补 ticket 获取与拒绝；新增 IM gateway-relay delta，并完整修改 Gateway 两条离线 Requirements。公司 Agent 无法在线核实资格时拒绝含公司上下文的模型工作，但 listener/密文配置/非触发背景自治保留；未绑定公司的独立 PA 保留离线主路径。没有引入离线身份平台或旧 JWT 公网旁路。
- **R1-W3 — escalated，仍未关闭**：本轮模型代理 health=200、Python/E2E 配置与飞书私有凭据文件存在；没有把这些等同真实模型/外部身份验收。已向用户说明 iPhone 和飞书测试的具体目的，尚未确认参与安排；Chrome tab 读取失败，当前 Cloudflare 权限/免费配置未复核。更新资源表事实，仍不宣称 Gate 2 通过；不为关闭此项提前发布、不降成 mock。
- **R1-R1 — accepted（有界样例修正）**：pending/suspended 原型隐藏产品主导航；管理员样例显示对应账号角色；任务卡不展示受保护来源群的名称。未把演示点击当真实权限验证。原型补全其他非关键样例不作为继续审查的理由。
- 附带文档修正：auth delta 两个继承的相对链接改为实际 canonical 路径；未改 current specs。

**R1-W3 后续事实与范围修订**：用户原话“iPhone你先不用测，你只要用本机域名访问能打通就行。飞书，本机有飞书，之前有成熟的方式做测试，复用”。已补 spec Q15 并同步本机真实域名场景、design 资源表和 M1-R6，取消真实 iPhone 前置，保留真实飞书和实际 HTTPS 域名链路。复用现有专用 Feishu E2E profile 只读核验：App/Bot 与 fixture 匹配、Bot verified=true，用户授权 tokenStatus=expired / status=missing；尚未恢复用户授权，不把 Bot verified 当用户也有效。公网 HTTPS 当前未打通，设计阶段未提前发布。R1-W3 的资源问题仅部分关闭，待独立复核；不改写首轮报告结论。

## Round 2

### Metadata

- reviewer target：`/root/public_im_design_review`，继续由 R1 独立 reviewer 复核，没有参与受审修订。
- review_mode：`full`。
- mode_reason：Q15 实质改变 M1-R6 的真实验收范围；本轮补全 WS 消费者协议及 IM/Gateway 离线共享契约并新增一个 canonical target，按 skill 的 milestone/共享接口影响扩大为 full。核对所有受审产物与真实入口，未变化部分复用 R1 同一代码基线证据，避免无意义重跑。
- started_at：`2026-09-30T09:43:38+00:00`。
- completed_at：`2026-09-30T09:46:14+00:00`。
- duration：`PT2M36S`，从本轮首次显式时钟采集计；首次并行只读命令与时钟在同一调用。
- executed_base / validated_at：`main` HEAD `da99b8981576b4f782ec71a7ae51f4c06bdb870a` 加冻结未提交文档。spec `098d4a810b9c9817f29db0e45a742b25162c7358`；design `b4dd86ca2e29cec066d9f12d3bc537b2ebd56543`；prototype `1ff55b810ef56e479a1914ec89879ab5e0d03cc2`，与派发版本一致。
- 七个 delta blob：IM agents-nodes `e41b09740f4b9e26c25b99016dbb90fca6b65e86`；auth-tenancy `d99db667ae7e3e4486f3410a1be6335ec2036537`；conversations-messages `f3c12c94edc1629f2968aa82a37ff45231cbf761`；gateway-relay `87338784df561664071bac8e01a623695003fbb4`；task-graphs `05c62ba6f2f9505f33f51ef0bb40f7b06e4f459a`；Gateway external-channels `3150dda56a7e4a9be8dca3119f3d9fba5bb829d3`；task-graphs `604089a9e1621ea9c11d8014fa885dfc41228d92`。
- 本轮只追加报告；不修改首文档/设计/delta/原型/代码，不提交，不启动服务，不发飞书探针，不操作生产。资源即时状态采用作者提供的只读核验结果，另核实真实探针脚本/规范如何依赖该身份；没有重跑外部认证或把报告文字当独立实测。

### Verdict

**Issues Found — 0 CRITICAL / 1 WARNING。**

**R1-W1、R1-W2 已关闭；R1-W3 部分关闭、仍 open。** 本轮未发现新的实质接口矛盾或需要阻断的复杂度问题。剩余 Warning 是真实飞书验收身份当前不可用与 M1 资源依赖尚未满足，不能将这一项改称设计接口错误，也不能因已有 Bot/config/health 就宣称资源齐备。无需为设计放行提前发布 HTTPS，更不要求已被用户移除的真实 iPhone 验收。

### Full 覆盖与影响核对

| 范围 | 本轮证据与判断 |
| --- | --- |
| 需求、用户决定与 M1 | `spec.md:116–119,187–194`、`design.md:67,227–255` 对齐用户 Q15：本机通过真实域名验完整链路，飞书沿用已有成熟方式；响应式移动界面目标保留，但不宣称 iPhone/Shadowrocket 实测。M1-R6 明确真实 HTTPS、无 Tailscale/hosts旁路、授权后发布和真实结果。单 M1、其余 R1–R7/W1–W4 范围保持，没有新增 worker/并行冲突；资源依赖见下文 R1-W3。 |
| 公司准入、撤销、策略、共享 Work、对象权限 | 重读 `design.md:23–39,58–95` 及 auth/conversations delta。R1 的生产入口证据保持有效：`app.py` 的真实组装/HTTP/WS、`api/deps.py` 真人/机器与会话访问检查、AuthService进程内 refresh 现状均未改变。本轮没有削弱默认公司门禁、事务内复核、session/epoch撤销、管理员不自动取得对象权限或完整共享 Work。auth delta 的相对链接已指向实际 canonical；这属于非实质文档修正。 |
| Gateway 本机换绑 | 重读 `design.md:96–107` 与 agents-nodes 绑定条目。本机 X25519 设备挑战、active接收者、完整 owner-AAD/revision 迁移、node/全部Agent单事务和提交后恢复均保持；R1 的 BindingStore/channel key真实组装证据仍适用。没有新增多管理者、远程抢绑兜底或管理员额外审批。 |
| 公司任务、群活动、明确删除 | 重读 `design.md:111–123`、两份 task-graphs delta；这两份 delta blob 与 R1 一致。公司全图读、真实能力/会话、原聊天附件权限、多对多活动、解散保留、逐节点回聊、revision与真实删除确认保持。继续扩展现有 TaskGraphService/Bridge，比另建任务服务或权限层适当。 |
| 外部背景、实际发起者、拒绝输入 | `design.md:125–133` 明确在已有触发判定之后、可执行run/Inbox之前检查实际交办人；背景与sync_only保留，运行身份冻结于通过验证的原触发消息，背景不能成为指令/删除确认，global多个输入逐个来源复核，被拒输入不能通过heartbeat重新执行。`specs/gateway/external-channels.md:17–22` 增加未关联背景→active交办的具体场景。与真实 `inbound_pipeline.py:139–147,192–205` 的触发/背景分支及 `composition.py:960–979` 接线相容；Q14不变。措辞建议见 R2-R1，不另造全群验证机制。 |
| WS 消费者协议 | `design.md:161` 已闭合 Bearer→30秒一次性ticket→原子消费→resume；明确active、session/epoch、Origin、限额、旧JWT拒绝、重连重新取票和前后端同步升级。`specs/im/agents-nodes.md:29–61` 用完整 MODIFIED替换实际 canonical同名Requirement，保留成员事件、owner事件、sync游标、重连与切号全部未变化场景，消除了 R1 中查询串JWT与ticket并存的长期契约。不是要求当前未实施 `app.py` 已支持ticket。 |
| 外部离线与跨包协议 | `design.md:129`、`specs/gateway/external-channels.md:27–89`、新增 `specs/im/gateway-relay.md:5–25` 对齐：绑定公司者失去在线核验时固定反馈且不运行/恢复公司上下文，listener/密文cache/非触发背景保留，独立未绑定PA仍自治，恢复不自动执行拒绝请求。IM target精确对应current `gateway-relay.md:100–114`，保留关闭中继不影响配置中心；Gateway完整MODIFIED两条Requirement保留channel调和、remove/replay、稳定身份、换App和多Bot隔离场景。本轮没有引入离线权限租约、另一个身份平台或旧鉴权兼容旁路。 |
| 附件、资源保护、发布/恢复 | `design.md:135–165,204–225` 和两份附件/资源 delta 对比 R1 保持：生产fetcher/resolver/Markdown图片读取全部覆盖、流式限额与原子配额、可行动限流、单worker、only-IM/loopback/Tunnel、稳定secret及脱敏日志；匹配版本/DB/附件备份恢复不变。真实公网未上线是当前事实，不是必须在设计阶段解除的产品故障。 |
| 原型与验收前置 | `prototype.html:21,25` 修正受保护来源A群名称和无资格产品导航控制，角色显示区分管理员；既有must-match表 `design.md:182–191` 与M1-W1保持。R1-R1属于已接受的有界样例调整，不因仍缺某些演示完成/失效状态追加阻断。作者提供已做两种viewport检查，本轮没有独立浏览器重验或冒称真实UI验收；当前仍是设计原型。飞书成熟流程的实际依赖核对见下文。 |

### 历史问题闭环

| Issue ID | Author Resolution | 本轮关闭/保留证据 | 状态 |
| --- | --- | --- | --- |
| R1-W1 | accepted：区分背景与触发人、冻结执行来源、禁止背景或拒绝输入升级 | `design.md:125–133`、external delta:17–22；真实Pipeline分支及current背景契约仍由已有触发判断驱动。资格边界现在约束实际交办，不要求每个背景发言人关联，也不会给背景发关联提示。 | **closed** |
| R1-W2 | accepted：补完整WS delta及IM/Gateway离线修改 | agents-nodes delta:29–61；gateway-relay delta:5–25；external delta:27–89。消费者可辨認ticket获取/拒绝/重试，既有resume/sync/切号保留；公司与独立PA的离线适用范围已收口，并且canonical对应项完整替换。 | **closed** |
| R1-W3 | escalated/部分关闭：用户缩小硬件验收，已有资源只读核验 | `spec.md:116–119`、`design.md:232–237,243,250–251`。iPhone依赖已合法移除，本机实际域名验收目标可执行；即时飞书用户资格仍missing/expired，模型health≠真实turn，未核实Cloudflare权限不是已具备上线权限。 | **still-open，范围缩小** |
| R1-R1 | accepted：修正无资格导航、角色与受保护群名 | prototype:21,25有对应有界修订。真实产品路由/缓存仍由must-match与实现验收保证；其余样例润色不阻断。 | **已接受，不阻断** |

### Issues

#### R1-W3（沿用稳定 ID）— 专用飞书用户验收身份仍不可用

- **本轮位置**：`design.md:233,237,243,251`。
- **实际未满足部分**：资源表记录专用非default App/Bot匹配、Bot verified=true，但用户 `status=missing / tokenStatus=expired`。这不是同一种资格；尚不能作为已可用的真人外部探针。M1仍依赖“必验资源确认”，M1-R7仍要求真实未关联→关联→解除/停用的端到端结果。
- **独立依据**：`docs/development/worktree-runtime.md:30–37` 要求该非default profile完成测试用户登录且同时验证App/Bot/测试用户；`scripts/e2e-feishu-probe.py:26–67` 核验专用profile和App/Bot，118–150明确通过 `--as user` 发送并读取真实聊天，228–246把这些步骤接到实际探针。只恢复Bot凭据或本地飞书App存在不能完成这条用户路径。作者提供的missing/expired状态已经足以证明这项资源未就绪，无须 reviewer 擅自发消息、改用生产profile或重做测试工具。
- **后果与闭环**：没有恢复该测试用户授权，既有成熟探针及关联身份旅程无法实际执行；不能用API mock、Bot verified或health替代。本轮只需继续复用原专用profile恢复用户授权、核对实际用户身份可用，并在进入真实飞书验收前保持该资源门槛。无需重新征求iPhone参与，也无需另建飞书流程。
- **明确不再要求**：Q15已移除真实iPhone。本机HTTPS未打通与当次上线授权/免费配置核验现在明确属于实际发布门槛；不要求设计review为关闭资源项提前配置DNS/Tunnel或公开服务，也不以“尚未上线”本身新增设计Warning。健康检查200只证明代理服务健康，实际模型turn/工具验证仍由M1-W3完成，不冒称已通过。
- **状态**：open；未解决计数为1 WARNING，沿用R1-W3，不重复生成新ID。

### Recommendations

#### R2-R1 — 可选：统一 mention-only 的术语

`design.md:125` 的“未 @、mention-only、sync_only等不触发工作的群消息”容易将“MENTION策略下未触发消息”与“正文只有 @Bot 的消息”混淆。current `gateway/external-channels.md:311–315` 要求纯 @Bot使用背景并触发回复；生产Pipeline按已存在的 `should_process/sync_only` 分支判定。建议仅以这两个实际判定描述背景分支，或将mention-only明确写成群回复策略，纯 @Bot仍按已有触发规则做实际发起者检查。整体设计已明确保留已有触发判断，delta也明确说“未触发Agent的消息”，所以这是局部措辞消歧，不另计WARNING。

### 下一步与结论边界

R1-W1/R1-W2不再要求反复设计返工；受审版本改变之前，本轮关闭结论有效。继续落实R1-W3所需的专用测试用户身份；按用户Q15，真实域名验收和当次发布授权保留到实际上线步骤。本轮没有新的实现、产品体验或上线完成结论。全部历史Round及Author Resolutions保持原样，本轮只追加独立结论。

### Author Resolutions

- **R1-W3 — accepted，未关闭**：保留专用飞书用户授权恢复前置，不另建流程、不用生产 profile 或 mock 代替；本轮止于可审设计，不宣称 Gate 2 已通过或已经开始实施。
- **R2-R1 — retained**：实现以既有 should_process/sync_only 的实际触发判定为准；纯 @Bot 的既有触发语义不变，不为可选措辞建议再开审查循环。
- **受审后元数据变化 — retained**：仅将 design 顶部状态更新为“两轮独立审查、技术问题已关闭、1 项资源 WARNING”，未改变方案、delta、原型或里程碑。R2 技术闭环证据继续有效。


## Author Correction — 用户 Q16 修正外部渠道授权主体

用户明确要求复用现有 `ownerOpenId`，不新增飞书与 IM 账号关联流程。此前将 Q13 解释为逐外部发言人公司资格检查，是作者误读；相关历史审查结论保留为当时版本的记录，不再作为当前规则或关联功能的依据。最终要求以 spec Q16 为准。

已同步修订 spec、design、IM auth/task 与 Gateway task delta，移除原型关联页面及身份关联设计。Gateway external-channels delta 仅保留附件安全改动；撤回新增的 IM gateway-relay delta，普通飞书对话、背景、触发及离线自治沿用 current。IM 任务读写仍由服务端验证 Agent/Gateway、管理者有效公司资格和任务能力，外部来源身份只作真实溯源，不冒写管理者身份。

本次是实质权限边界修订，提交独立设计复核，不沿用此前关联机制的 Approved/技术关闭结论。专用飞书测试用户授权资源前置仍保留；尚未实施或发布。

## Round 3

### Metadata

- reviewer target：`/root/public_im_design_review`，独立 reviewer，未参与受审修订。
- review_mode：`full`。
- mode_reason：用户 Q16 实质改变外部渠道的授权主体，撤回跨身份映射、整轮拦截与离线行为修改，属于核心边界变化；因此核对全部设计覆盖、六份 delta、原型与 M1。未变化的代码基线证据保留自 Round 1/2，本轮另沿真实生产组装核实 ownerOpenId，而非仅确认文档引用存在。
- started_at：`2026-09-30T10:06:13+00:00`。
- completed_at：`2026-09-30T10:12:14+00:00`。
- duration：`PT6M1S`，从本轮首次显式时钟采集至审查证据核对完成。
- executed_base / validated_at：`main` HEAD `da99b8981576b4f782ec71a7ae51f4c06bdb870a` 加冻结未提交文档；spec blob `988df7f75f56dc24afdb48ee8d8f108f311d26ff`，design `9c53df5a3fd47d6ee227ecb7efd3ac4d1a385712`，prototype `229b2c9e40abb81458bf15c473c082c0b0e66059`。
- 六个 delta blob：IM agents-nodes `e41b09740f4b9e26c25b99016dbb90fca6b65e86`；auth-tenancy `3df0daca4a250776ac08ee848a1cece5aa629945`；conversations-messages `f3c12c94edc1629f2968aa82a37ff45231cbf761`；task-graphs `400e0786cf256e223a01b345802ad484dcc42126`；Gateway external-channels `a095d21c8ca4bfcf849535cfaeb6ecd4c7741edb`；task-graphs `5a1b8b23ebb76ced1f3f2e5f0fa9a508f978e12d`。新增 IM gateway-relay delta 已撤回。
- 受审期间用户进一步明确：聊天附件反馈必须处于真实 IM 聊天上下文，原型入口与旅程须补齐；全局 Tasks 沿用原页，只扩大公司可见范围，任意群聊天内查看本群相关任务，不接受全局页固定 B 群或公司/群切换。作者通知将在本轮完成后修改，故本轮只审上述冻结版本，不将后续修订当成证据。
- 只追加本报告；不修改受审产物、产品代码或其他文件，不提交、不启动服务、不登录或发送飞书消息、不操作生产、不派其他 agent。无关 dirty/untracked 保留。

### Verdict

**Issues Found — 0 CRITICAL / 2 WARNING。Gate 2 未通过。**

Q16 的技术权限修正成立：复用既有 ownerOpenId，不新增外部发言人与 IM 账号关联；IM 对 Agent/Gateway、管理者公司资格和任务能力授权，来源身份只作真实溯源。未发现新的实质接口矛盾或复杂度问题。剩余项是稳定 ID **R1-W3**（专用飞书测试用户授权未恢复）和新增 **R3-W1**（冻结原型的聊天/任务入口与用户明确要求不符）。后者是产品旅程问题，不能据它宣称现有产品已存在权限漏洞。

### Full Coverage 与独立证据

| 核对面 | 本轮判断与证据 |
| --- | --- |
| 用户授权主体与历史纠错 | `spec.md:109–124` 明确 Q13 的旧解释已撤回，Q14 维持正常群沟通，Q16 不要求每个外部发言人具备 IM 账号。`design.md:123–129`、IM task delta:16–18 与 Gateway task delta:30–38 同步，无关联表、确认码或关联页面；原型中相关页面和处理函数已删除。不能继续依据历史 R1/R2 的逐发言人方案要求实现。 |
| ownerOpenId 的真实静态入口 | PA `composition.py:374–381` 构建 registry 并注入本地 binder，1183–1200 实际构造 FeishuAdapter，传入现有 ownerOpenId 与 binder。`config/local_store.py:595–643` 的 binder 仅处理有效飞书 channel，已有 owner 不覆盖，缺失时写入真实 sender 并持久化；有 RuntimeConfigOwner 串行更新，持久化失败不假装绑定成功。复用现有配置能力有直接落点，无需新映射服务。 |
| ownerOpenId 的真实托管入口 | `composition.py:970–979` 构建 ManagedChannelControl 并接真实 inbound pipeline；`managed_channel_control.py:364–410` 从 provider_runtime 读取 owner_open_id，callback 将首个 owner 写回 metadata 并传给同一 FeishuAdapter。`channel_manager.py:558–610` 的 record_provider_metadata 只接受当前 generation，对 owner/bot 采用 set-if-null，并更新 manifest/report。托管 channel 也有现成持久与重启路径，不应只修改静态 config。 |
| 主人识别、真实来源与普通沟通 | `feishu/adapter.py:351–376,498–523,538–576` 使用现有消息接收/自发消息过滤与历史 catchup；群 metadata 只有 live event 可绑定 owner，背景同步不制造历史主人。736–753 优先保留现有 owner，缺失才经 binder 自动绑定。708–734 保留真实 sender 与 external_source；ownerOpenId 不转换成管理者 IM user_id。`design.md:127–129` 保留普通背景、@Bot、Inbox、回复去向与 IM 离线自治；没有新增逐外部发言人整轮门禁。 |
| 中心任务授权及来源接口 | `design.md:111,123–129` 将公司任务检查放在 IM TaskGraphService/机器协议上。生产 `app.py:431–439` 给 GatewayTaskGraphs 与 Web router 共享同一 TaskGraphService，`ws/gateway/runtime.py:170–175` 先检查注册 sender；PA TaskGraphBridge:45–73,98–126 从真实 session/run provenance 提交。现有实现尚无新增公司资格，但接口可扩展实际 actor/node/owner 检查，不依赖模型自报或 ownerOpenId 代认证。Gateway task delta:30–43 保留能力开关、真实来源、无来源操作及 IM 不可达时明确失败，不新建离线任务副本。 |
| 公司准入、session/epoch、停用、策略与 Work | 重核 `design.md:23–39,71–95` 和 auth delta；撤回的只有外部关联 Requirement。pending/active/suspended、事务内资格复核、持久 session、连接撤销与对象权限继续由 IM 的 AuthService/deps/stream 入口承担，R1 实际组装证据仍有效。停用公司接入不等于 OS 关机或停止普通本地飞书；完整 Work/联系人共享与普通成员策略只读保持。 |
| 单一管理者、本机整体交接 | `design.md:96–107` 与 agents-nodes delta 保留 X25519 本机挑战、完整 node/Agent manifest、owner-AAD 重封、revision/epoch 撤销和提交后恢复；旧 owner 停用仍可由有本机证明的 active 接收者交接。R1 对 BindingStore、设备密钥与真实 composition 的证据仍适用。没有新增多人 owner、管理员审批或另一组签名密钥。 |
| 公司全图、修改删除与群活动 | `design.md:111–121`、IM task delta:9–47 和 Gateway task delta:5–56 保留跨 owner/Gateway 的按需全图读写、有效能力、受保护来源投影、明确真实用户删除、revision/回执，以及节点×群多对多活动。群解散/退群不删除任务，无来源不伪造来源。用户最新反馈改变的是 UI 入口而非这些权限规则；冻结原型仍不满足该入口要求（R3-W1）。 |
| WS 与 canonical delta 完整性 | agents-nodes delta:29–61 继续完整 MODIFIED 浏览器 ticket Requirement，保留 resume/sync/重连/切号。外部整轮资格门禁已撤回，所以取消 im/gateway-relay delta、将 external-channels delta恢复为只增加附件保护是正确回到 current，不再需要变更普通离线对话契约。六份 delta 对应实际 canonical target，未重新留下长期 JWT URL 条目与新 ticket 并存问题。 |
| 附件、限额、发布/恢复 | `design.md:131–161,198–219`、conversations 与 external 附件 delta 沿用先前完整接线覆盖：默认 resolver、IM fetcher、coordinator fallback 与 Markdown 自动图片读取都受保护；有界上传、原子配额、来源与账号限流、连接撤销与日志脱敏保持。生产入口证据 retained from R1，未因 Q16 撤回 SSRF 或公司门禁。单 worker、loopback only-IM Tunnel、备份匹配版本恢复与独立发布授权不变。 |
| 原型与 M1/资源 | `design.md:165–186,237–249` 仍明确 must-match、完整单 M1 和真实 UI 验收，资源227记录专用用户 token expired 而非声称成功。手机实测已由 Q15 移除，本机实际域名验收与发布授权属于后续真实门槛；未上线不是本轮新增 Warning。原型的导航/聊天上下文缺口已经由用户明确要求补齐，本轮冻结版本尚未修复，见 R3-W1。 |

架构判断：Q16 移除一套用户未要求的跨账号身份平台，复用已经在静态与托管生产入口持久化的主人识别；任务资格仍统一由 IM 扩展实际服务与事务检查，职责更直接。session、设备交接、任务活动关系及短期回执仍分别服务明确需求，没有依据要求离线租约、全群身份同步或新审批层。此判断只证明方案可指导实施，不表示公司资格或公网保护已经实现。

### 历史问题闭环

| Issue ID | 本轮处理及证据 | 状态 |
| --- | --- | --- |
| R1-W1 | Author Correction 与 spec Q16 撤回逐发言人资格门禁及关联机制，旧问题所审的实现前提已不存在。当前保留既有背景/触发行为，由 Agent 的公司任务资格决定能否访问 IM；不再要求曾在 R2 接受的外部关联门禁。 | **superseded by Q16，无未解决项** |
| R1-W2 | 浏览器 ticket delta保持完整，WS 部分继续 closed；外部离线改变已由 Q16 撤回，相关 IM/Gateway delta恢复 current，不将历史新增离线门禁作为当前必需。 | **WS closed；离线部分 superseded by Q16** |
| R1-W3 | 专用真实飞书探针仍需用户身份，而当前 missing/expired。取消外部↔IM关联旅程不消除探针发送/读回对该 CLI 用户授权的依赖。 | **still-open，1 WARNING** |
| R1-R1 / R2-R1 | 已移除身份页和新背景门禁，原关联样例/mention-only措辞建议不再适用；无资格导航修订保留。用户新的明确入口要求另按 R3-W1 处理，不把可选润色回溯成旧阻断。 | **相关旧建议 superseded，不阻断** |

### Issues

#### R1-W3（沿用稳定 ID）— 专用飞书用户验收身份仍不可用

- **本轮位置**：`design.md:227,231,237,245`。
- **证据**：专用非 default profile 的 App/Bot 匹配、Bot verified=true，但用户 status=missing / tokenStatus=expired；M1仍以必验资源确认为依赖。独立核对 `docs/development/worktree-runtime.md:30–37` 和 `scripts/e2e-feishu-probe.py:26–67,118–150,228–246`，成熟流程实际以 `--as user` 发送并读回消息，不是仅有 Bot凭据即可执行。即时状态来源为作者本轮前的只读核验，本 reviewer 未擅自登录或发消息。
- **后果/闭环**：现有专用探针尚不能执行真实飞书普通沟通与 Agent管理者 pending→active→suspended 任务权限旅程。沿用同一专用 profile 恢复用户授权并证明可用；不要改用生产/default profile 或 API mock。此项不再要求飞书发言人与 IM关联，不要求重新加上 iPhone，更不要求为设计放行提前发布 HTTPS。
- **状态**：open，计1 WARNING。

#### R3-W1 — 冻结原型没有闭合真实聊天中的群任务与附件旅程

- **位置**：`prototype.html:10–14,21,23–27`；`design.md:172–184,208,241,243,246`。
- **证据**：原型桌面/手机 Chat 的 data-nav 都是 tasks，Agents 直接跳交接卡，相关聊天按钮只 toast；没有聊天列表、真实群聊天标题/消息区、草稿与附件状态。Tasks 默认固定 B群，利用页内 scope按钮在公司与 B群之间切换；群内入口不存在。附件配额反馈位于独立 feedback卡，移除附件也仅 toast，不能看见正文草稿仍在或继续发送。用户本轮明确要求附件置于实际 IM上下文，并明确全局 Tasks沿用原页、任意群聊天内查看本群相关任务，拒绝全局页固定 B群/公司群切换；冻结版本尚未对应修改。
- **真实产品 grounding**：`frontend/src/app/router.tsx:30–36,45–72` 将 Chat、Tasks、Agents/Nodes分为真实入口。`chat-workspace-page.tsx:1051–1057,1071–1098,1100–1146` 的附件错误绑定当前会话，ConversationSidebar、MessagePane及 draftSeed/onSend同处聊天工作区。`tasks/task-graphs-page.tsx:202–204` 的讨论动作真实追加节点引用并回到对应聊天，229提供全局任务到Chat的入口。原型可简化数据和样式，但现有must-match与用户明确旅程不能由跳到另一页/提示文字替代。
- **实际后果**：下游依据当前原型容易实现全局任务页的群切换器，仍无法在当前群方便找到本群任务；附件失败也可能成为脱离草稿的独立说明页。M1-W1即使逐张卡截图匹配，也无法证明群→同图→回群讨论/保留草稿和附件失败→移除→继续发送的完整入口，违背用户当前明确选择。
- **建议闭环**：在原型中用真实 IM聊天结构演示任意群上下文入口、该群任务视图、打开同图并回到原群的引用/草稿；全局 Tasks沿用原页仅扩大公司范围。把上传失败、剩余附件和正文保留、移除后继续发送置于同一聊天草稿，并补齐本 unit新增/受影响入口与must-match旅程映射；可继续使用演示数据，不要求全量复制产品或提前写代码。设计的入口/对齐表同步修正，明确演示跨状态控件。作者已承诺下一版修订，本轮不提前将其视为 closed。
- **状态**：open，计1 WARNING。

### Recommendations 与结论边界

本轮无新增可选润色建议。Q16 的 ownerOpenId 与中心资格方案无需继续返工；原型补齐后按真实改动选择有界复核，继续保留专用飞书测试资源前置。没有产品实现、平台实测或公网发布完成结论；历史报告与 Author Resolutions 均保持原样。


### Author Resolutions — R3 后原型旅程修订

- **R3-W1 — accepted，待复核**：重写 prototype 的实际导航与聊天布局。默认 Chat；任意群内“任务”打开上下文活动侧栏，两个群的不同节点打开同图，支持回原群与草稿保留；全局 Tasks 沿用现有页面，不再固定 B 群或提供公司/群活动切换。附件失败进入对应 composer chip，逐项移除/网络重试/冷却/其他成功文件与文字保留、发送失败及重试均可操作。成员管理由桌面头像或手机 Me 进入，设备从列表经本机说明、链接、接收账号、本机确认到结果，不再使用跳错页/仅 toast 代替旅程。同步 spec Q17、design must-match、task/upload delta。
- **证据与局限**：jsdom 交互检查覆盖上述 DOM 旅程，无脚本错误；新版浏览器 file:// 访问被工具策略拒绝，未绕过，未声称浏览器视觉验收。原型仍是演示数据，实际产品验收留在 M1。
- **R1-W3 — retained，未关闭**：专用飞书测试用户授权仍需恢复，未操作生产或另建验收流程。

## Round 4

### Metadata

- reviewer target：`/root/public_im_design_review`，继续独立复核，未参与作者修订。
- review_mode：`delta`。
- mode_reason：R3-W1 的修订有界于原型旅程、Q17 入口消歧、must-match 与 IM task/upload 消费者投影；不改变公司权限、Q16 授权主体或共享接口。除闭环检查外，核对两份新增消费者场景与当前产品入口的相容性，因此采用 delta；不重跑整套架构调查。
- started_at：`2026-09-30T10:24:55+00:00`；completed_at：`2026-09-30T10:27:29+00:00`；duration：`PT2M34S`。
- executed_base / validated_at：HEAD 仍为 `da99b8981576b4f782ec71a7ae51f4c06bdb870a`，冻结 spec blob `3a522d639efe1d6a356be65485574541e3966b8d`、design `e1f8ed04a1c86a2e83e24c5d78521a433ab6c655`、prototype `033c1da44752f6fe19575d8de8d2ed070b300b29`；IM task delta `a257097514f9fdc6d53e82b689e70f7f3f61b2c9`，IM conversations/upload delta `9dfa950842d18da5792df3593caf3b0a0c53b581`。
- 独立证据方式：静态源文件与当前入口对照，加本仓 `frontend/node_modules/jsdom` 执行原型实际 DOM 操作，共49项检查通过，脚本错误0。未调用浏览器访问 file://，未另起 HTTP 或通过其他浏览器绕过已知工具禁令，没有新版截图或视觉验收结论。
- 只追加本报告，受审产物和代码不改、不提交、不运行真实服务、不操作外部身份或生产。保留已有 dirty/untracked。

### Verdict

**Issues Found — 0 CRITICAL / 1 WARNING。R3-W1 已关闭。**

本轮未发现新增实质设计问题。原型与消费者契约已能指导实现用户指定的完整入口；剩余唯一 Warning 是 **R1-W3** 专用飞书测试用户授权资源，retained from Round 3。资源未恢复之前 Gate 2 仍未通过。DOM 交互证据只用于原型闭环，M1 的真实客户端视口、后端和平台验收保持必需。

### Delta Coverage 与闭环证据

| 变化/影响面 | 独立核对结果 |
| --- | --- |
| 用户 Q17 与群任务入口 | `spec.md:126–128` 明确全局 Tasks沿用原页、任意群内查看本群节点。`prototype.html:10–12,27–30,45,53–56` 默认Chat，三个群使用当前群上下文；交付群含n2，规划群含n1/n3，设计群空活动。实际DOM确认两个群打开同一公司图、各自返回原群、正文草稿保留；讨论追加引用且不自动发送。全局Tasks导航清除群来源，不包含固定B群或公司/群切换器。`design.md:173–174,183–184,248`与IM task delta:34–37同步完整路径，没有修改公司共享或群成员保护规则。 |
| 全局 Tasks与现有浏览能力 | 原型保留列表/图/详情、搜索无结果、空/错误/重试、受保护来源和引用/回聊；DOM验证私聊来源保护无跳转、搜索空结果和列表错误恢复。`design.md:183,188` 明确原有层级/配置/完整编辑器继续存在，简化样例不能删除current行为。IM task delta:39–52继续保留多群活动、独立生命周期、逐节点最后聊天、既有层级与回聊。R3对 `router.tsx:30–36` 和 `task-graphs-page.tsx:202–204` 的真实产品grounding仍适用；不是另建全局群活动产品页。 |
| 聊天附件与逐文件恢复 | `prototype.html:26–27,47–52,69` 将文件chip放在当前composer内；失败文件有原因和逐项动作，失败不写成消息。独立DOM验证成功+配额失败并存时草稿和成功文件保留、禁止静默发送，移除仅失败项；网络重试成功、上传限流冷却、大小/格式/服务空间错误均定位文件。发送失败保留正文和已上传文件，重试成功才移入消息并清理本次草稿。`design.md:186,191,250` 与upload delta:12–15同步；Retry-After、真实上传选择/拖入/粘贴由实际产品提供，黄色控件与示例文件仅演示。当前 `chat-workspace-page.tsx` 的会话绑定错误/MessagePane/draft/onSend接线证据retained from R3，没有孤立附件反馈产品页。 |
| 身份、成员与真实导航 | `prototype.html:18,31–33,39–40,58–60,65–70` 提供真实Chat/Tasks/Agents入口、头像/Me到成员管理、普通成员无入口；批准失败不改变状态、停用取消不改变状态，成功显示结果。DOM确认头像和Me管理员入口、普通成员隐藏、成员失败/取消/成功，以及注册pending→批准刷新→Chat、停用无产品导航、登录冷却保留输入。`design.md:171–172,181–182`把受影响旅程映射到实际入口，黄色身份/结果选择器不混入产品。 |
| 设备交接完整路径 | `prototype.html:34–38,62–64` 从设备页进入本机操作说明，显式演示本机链接、接收账号/换账号登录、全部Agent影响、网页接收、等待本机终端确认、结果设备列表；DOM确认换账号后回交接、取消不转移、过期、中断恢复与成功结果。`design.md:175,185,189` 明确本机按钮是另一端的演示，实际确认在CLI执行，设备列表不替代本机证明。没有变更R3已核实的挑战/事务协议。 |
| must-match、验收边界与delta完整性 | `design.md:181–193,248–253`逐条对应新增/受影响入口和状态，保留真实desktop/mobile产品对照，显式承认新版缺视觉截图。两份delta只新增群入口/附件反馈消费者场景，原有公司全图、能力、来源保护、删除revision及实时资源/HTTPS条目保持，canonical对应正确。M1仍是原单里程碑；本轮没有新增实施权限或公网授权。 |

### Retained 范围

`retained_from: Round 3`：Q16/ownerOpenId 的静态与托管生产接线、任务中心资格、公司准入及session/epoch、Gateway整体交接协议、群多对多数据关系、附件SSRF接线、WS ticket、发布/恢复及架构复杂度判断均不受本轮入口修订影响，继续引用R3的实际代码证据。没有因原型增加三组演示数据而引入固定群产品规则、第二套任务存储或新的权限服务。

### 历史问题闭环

| Issue ID | Author Resolution与本轮结论 | 状态 |
| --- | --- | --- |
| R3-W1 | accepted；原型改为真实Chat入口、群内活动侧栏、同图往返、composer逐文件反馈及完整成员/设备路径。静态核对和49项独立DOM检查均支持上述闭环；Q17、must-match和两份delta同步，受影响入口不再仅toast/跳错页。 | **closed** |
| R1-W3 | retained；`design.md:234,238,244`仍记录专用CLI用户missing/expired，仍依赖资源确认；R3对真实probe的用户身份依赖证据保持有效。本轮不重新登录、发消息或改用生产profile。 | **still-open，1 WARNING** |
| R1-W1 / R1-W2 | Q16已替代逐发言人/离线门禁要求，浏览器ticket部分已closed；本轮无相关权限或协议变化。 | **retained from Round 3，不新增问题** |

### Issues 与 Recommendations

没有新Issue或可选样式优化。唯一未解决项沿用 **R1-W3**：缺少可用专用测试用户授权会使真实飞书探针无法发送/读回；继续复用既有profile恢复该资源，闭环见R3，不重开身份产品设计。没有要求恢复已取消的外部↔IM关联或iPhone测试，也没有把未上线域名作为新阻断。

本轮只关闭原型文档旅程问题；未验产品实现、实际屏幕布局、真实模型、飞书或公网。后续M1-W1的真实客户端截图与对照仍必须执行，不能以49项DOM检查替代。


### Author Resolutions — R4

- **R3-W1 — accepted closed**：独立 reviewer 的 49 项 DOM 检查与作者检查一致，群内任务/全局 Tasks 区分、原群返回及草稿、附件局部失败与发送恢复、成员和设备入口已闭合；不据此宣称浏览器视觉或产品后端验收。
- **R1-W3 — retained open**：保留专用飞书用户授权前置，当前不进行外部发消息、登录或部署。
- **审后元数据 — retained**：仅更新 design 顶部状态为 R4 结论，方案、原型、delta 与 milestone 未变；不触发新一轮审查。


### Author Resolutions — 用户 Q18 容量反馈修订

用户确认“暂时无法上传附件；容量告警和处理交给管理员，文字聊天继续可用”。已调整原型默认正常上传；普通聊天隐藏配额管理文案，提供“仅发送文字”并保留全部附件；全局策略页仅管理员可见容量状态告警。同步 spec Q18、upload delta、design 反馈/告警责任和验收条款。此前 R4 对强制移除失败附件才能发文字的检查被该明确决定替代，其余结论保持。等待有界复核，未改产品代码。

## Round 5

### Metadata

- reviewer target：`/root/public_im_design_review`，独立 reviewer，未参与作者修订。
- review_mode：`delta`；mode_reason：用户 Q18 有界修改容量反馈、正文独立提交和管理员告警归属，只审这些消费者行为及文档一致性。其他架构/入口与资源判断 retained from Round 4，不扩大为附件管理或告警平台设计。
- started_at：`2026-09-30T10:41:48+00:00`；completed_at：`2026-09-30T10:42:37+00:00`；duration：`PT49S`。
- executed_base / validated_at：HEAD `da99b8981576b4f782ec71a7ae51f4c06bdb870a`；冻结 spec blob `817777b10b3f527d242df8fe187d5cc7e6eace2e`、design `0421fe489676915ed13f4273d56bc44396d646f6`、prototype `3820cd125219971f5dd63e03b3f63258b98ca156`、IM conversations/upload delta `95f8912f4176c7f651660e3df7206f1b77b08e93`。
- 独立验证：使用本仓 jsdom 运行17项定向DOM检查，全部通过、脚本错误0；没有浏览器截图或视觉验收。本轮只追加报告，不改其他文件、不提交、不启动服务、不操作外部身份或生产、不绕过 file:// 禁令。

### Verdict

**Issues Found — 0 CRITICAL / 1 WARNING。Q18 本次修订通过有界复核，无新增问题。**

唯一未解决项仍为 **R1-W3** 专用飞书测试用户授权，retained from Round 4，因此 Gate 2 尚未通过。本轮不把用户已替代的“移除失败文件后才能发送文字”作为继续实施的要求。

### Delta Coverage 与证据

- **普通聊天反馈与默认路径**：`spec.md:130–132,455–457`、`design.md:186–194,253`、upload delta:12–20 与 `prototype.html:10,26–27` 一致。默认上传成功，账号/服务容量失败均仅显示“暂时无法上传附件”，不要求普通聊天用户管理容量、清理或联系管理员；文件名和未上传状态仍可辨认，没有谎称发送成功。独立DOM确认默认成功、两个维度简短文案与无存储管理任务。
- **文字独立提交与附件保留**：`prototype.html:27,54,71` 的显式 send-text只提交正文、消息不含附件，不清理任何未发文件；普通全内容发送仍不能静默忽略失败文件。独立DOM验证成功文件+配额失败文件并存，文字发送失败保留正文和两项附件，重试成功只清正文、全部附件留在原聊天；空正文禁用文字按钮，继续输入重新可发；服务满后仍能再次发文字，切页后附件仍在。这与 `design.md:192` 和 upload delta:15 对“本次提交项”的清理定义一致，不要求先移除失败项。
- **管理员告警职责与访问边界**：`design.md:187,194`明确IM从既有配额账本聚合当前状态，沿全局策略提供管理员专属只读存储状态，不能把相关账号/实际容量明细混入普通成员可读的策略响应；容量恢复解除，不逐失败刷屏、不新建通知渠道或清理平台。upload delta:17–20同步消费者结果。`prototype.html:40,43–44,49,51`仅管理员渲染存储状态区，上传容量失败投影告警。DOM验证普通成员无状态/告警明细、管理员能看到服务触顶、切回普通成员隐藏；公开可读的配置上限不等于实际用量/账号告警，二者没有混淆。
- **实施与验收投影**：must-match新增管理员存储状态并更新聊天文字路径，M1-R5要求普通文字可用与管理员告警；未修改上传累计事务、附件来源保护或此前群任务入口。原型仍是示例数据，没有把模拟失败产生的状态当成真实配额账本实测；实际客户端/后台资格校验与容量恢复由M1验证。

### 历史问题闭环与 Retained

| 项目 | 本轮结论 | 状态 |
| --- | --- | --- |
| R3-W1 | 原型完整聊天旅程的R4关闭结论保留；其中强制先移除失败附件才能发文字的旧断言由用户Q18替代。当前明确正文提交保留附件，17项DOM检查支持新行为。 | **closed，Q18有界替代** |
| R1-W3 | `design.md`资源表仍为专用CLI用户missing/expired；实际飞书探针对用户授权的依赖没有被容量UI改变。沿用R3/R4证据，不重做登录或发消息。 | **still-open，1 WARNING** |
| 其余设计 | `retained_from: Round 4`，Q16/ownerOpenId、群入口、绑定、WS、SSRF、中心权限、发布/恢复及单M1未受影响。 | **retained** |

### Issues 与 Recommendations

无新增Issue，无需可选样式或平台扩展。只保留稳定ID **R1-W3** 的资源闭环要求；本轮没有实际产品、视觉、飞书、模型或公网完成结论。


### Author Resolutions — R5

Q18 修订复核结果 accepted：17 项独立 DOM 检查与作者验证一致，无新增问题；R1-W3 保留。审后仅更新 design 顶部状态，受审方案/原型/delta 未再变化，不另开复核。尚未实施或发布。


### Author UI Refinement — 用户截图反馈

根据用户标注精简群任务面板：移除重复群名与规则解释段，关闭改为右上角轻量图标；大卡片改为紧凑任务列表，移除重复活动徽标和内部 ID，保留任务名、必要总目标、状态/时间。同步清理正常聊天、任务及设置页中的实现说明和重复权限提示；关键设备交接影响提示保留。入口、群筛选、同图返回、附件处理和权限状态未改，属于视觉/文案修订，R5 行为结论 retained，不重复启动架构审查。DOM 检查只证明结构与交互，不能证明视觉体验合格。


### Author UI Refinement — 全页表单与反馈间距

用户追加登录截图指出错误框紧贴输入框。已重整共享 CSS 为一致间距、字体/按钮层级及窄屏规则，登录注册使用字段分组、独立间距的文本反馈与提交区；聊天/成员错误简短就地反馈，卡片/弹窗/设置/任务/设备页统一留白。保留危险操作后果提示。检查各页面与状态可渲染、表单反馈关联/间距规则、任务往返及成员/设备/附件关键交互，无脚本或 CSS 解析错误；不将此表述为视觉验收。业务/权限/接口/里程碑未变，R5 行为结论 retained，不为纯视觉文案调整重复架构审查。


### Author Correction — current IM grounding

User requested a complete prototype audit against the existing IM. Removed invented settings sidebar, device tutorial cards and the two-column binding poster. Reused current design tokens, NanoBrand, 48px shell, centered tabs, 768px breakpoint and mobile icons. Binding now uses the existing centered card with one full-width primary action, account switching by identity, and a quiet cancel action. Local simulation controls and per-page scope notes live outside the product UI. Updated design boundaries; current device configuration functionality remains intact. Pending bounded review of these presentation/scope corrections; no protocol or product-code changes.

## Round 6

### Metadata

- reviewer target：`/root/public_im_design_review`，独立 reviewer，未参与作者修订。
- review_mode：`delta`；mode_reason：本轮除了视觉层级，还撤回原型曾自行加入的设置侧栏/设备教程并重界定实施范围，故有界核对current grounding、原型结构、must-match和受影响交互；不重扫已关闭权限协议。
- started_at：`2026-09-30T11:07:11+00:00`；completed_at：`2026-09-30T11:10:32+00:00`；duration：`PT3M21S`。
- executed_base / validated_at：HEAD `da99b8981576b4f782ec71a7ae51f4c06bdb870a`；spec blob仍为 `817777b10b3f527d242df8fe187d5cc7e6eace2e`，冻结design `8550d20c563adef308714fde8b0e12d5a19ae028`，prototype `b65c52d20087b3b01cfe8c1c5d8a44fd98af92db`。
- 独立验证：71项源码token/DOM/样式规则检查通过，其中35项逐一匹配current `global.css` 的全部root IM变量；其余检查覆盖grounding结构和受影响交互，jsdom脚本错误0。静态对照current组件，未调用浏览器绕过已知file安全禁令，没有新版视觉截图证据。
- 只追加报告；不改受审文件/代码，不提交、不启动服务、不操作外部身份或生产。

### Verdict

**Issues Found — 0 CRITICAL / 1 WARNING。本轮grounding与实施范围修订通过有界复核，无新增阻断。**

剩余Warning仍为稳定ID **R1-W3** 飞书测试用户授权资源，retained from Round 5，Gate 2尚未通过。当前原型可以作为新增路径和状态的实现参考；已有Devices/Agents/Tasks的简化背景不能当整页替换方案，已撤回教程/二级侧栏不属于实施要求。是否在真实屏幕上达到用户期望的观感，仍需M1真实视口对照，本轮不作视觉通过结论。

### Delta Coverage 与独立证据

| 核对面 | 本轮证据与判断 |
| --- | --- |
| current颜色、字体与品牌 | `global.css:5–43`定义35个IM root变量，原型逐项值一致；`nano-brand.tsx:6–29`的20px标记、勾线和internal标识在原型208复用。没有另造产品品牌；DOM/样式值证明源码grounding，不证明本机实际字体加载或屏幕渲染结果。 |
| Shell与移动结构 | `app-shell.tsx:14–18,39–88`、`global.css:92–146`真实使用48px顶栏、居中tabs和移动列表底栏；`hooks/use-is-mobile.ts:3–10`在小于768px切换。原型174–206的最终CSS、213的现有图标路径及219的导航状态对应这些结构，独立DOM computedStyle确认顶栏48px和tabs居中，静态核对767px media和移动App顶栏隐藏。没有将早先被覆盖的58px规则误当最终尺寸。 |
| 独立设置页与设备背景 | `settings-page-shell.tsx:3–9`明确只透传Outlet，current无二级侧栏；原型233取消该侧栏，成员/设备DOM均无settings rail。`nodes-page.tsx:203–225,233–345`保留KPI、设备卡、别名编辑、保存与新Agent入口；原型237只示意KPI/归属结果，244的实施说明及 `design.md:175,204–206`明确完整current功能继续保留。产品画面内没有教程卡/交接教程按钮，不要求实现已撤回的新增页面。 |
| 绑定结构及本机/浏览器边界 | current `bind-confirm-page.tsx:72–109`是居中单卡，不是营销双栏。原型186–190,238使用居中bind-card、身份行换账号、44px整行主确认及弱化取消；DOM确认单卡、身份行、列式按钮和44px规则。225的本机确认/恢复按钮仅在黄色demo区，等待状态的真实画面无这些按钮。换账号登录回到接收页、本机演示确认后结果设备列表可达； `design.md:185,190,206`同步CLI起点与模拟控件边界，不再沿用R4的设备页教程起点。 |
| 逐页实施范围与现有能力 | 原型241–253在产品画面外的可展开说明区区分沿用、新增和演示；设备、Agents和Tasks均明确不是整页重做，前置本机说明不作为新增产品教程。`design.md:173,175,189–190,202–208`保留完整配置/Work/图层级与current页面，无新增协议或canonical行为需求；不要求仅为示例CSS/背景另补长期spec。 |
| 群任务、附件及发送状态 | 定向DOM确认群任务Escape关闭且焦点回入口、同图返回保留原群草稿，当前群发送失败保留后切到另一群不污染，返回原群仍可重试。原型210,269采用按chat的sendFailures。Q18文字独立提交保留附件仍成立。修改视觉和文案没有改公司范围/来源保护/任务权限，相关结论retained from R4/R5。 |
| 登录、成员与路由状态 | DOM确认凭据错误保留输入、aria-describedby关联简短反馈，冷却禁用提交且保留密码；成员批准及Escape取消停用可用，绑定换账号回路成立。Chat/Tasks/成员/设备/交接/登录/pending/suspended各页面及对应范围说明均渲染无脚本错误。`design.md:181–200`与M1-W1保留真实desktop/mobile检查及无回归要求；没有把DOM/CSS解析当真实视觉或后端验收。 |

### 历史问题与 Retained

`retained_from: Round 5`：Q16授权主体、公司/机器权限、WS、SSRF、任务活动/删除一致性、Q18容量和管理员告警、M1资源及发布恢复不受本轮presentation/scope纠偏影响。R3-W1已关闭；R4中曾接受的设备教程路径被本轮明确撤回，不能要求下游再次实现。R1-W3在当前 `design.md:251`仍为专用用户missing/expired，保留1 WARNING；无需重新登录、发探针或提前发布。

### Issues

无新增Issue。唯一未解决项 **R1-W3** 的证据与后果继续引用R3/R4/R5：专用用户授权未恢复，成熟真实飞书探针不可执行。当前grounding修订不消除这项资源依赖。

### Recommendations

#### R6-R1 — 可选：Me本页不显示返回自身按钮

`prototype.html:233,235`统一settings包装会让Me页也出现指向Me的手机返回按钮；它只重渲染当前页，不损失状态或阻断其他入口，因此为原型小修，不计WARNING。作者已在受审期间指出并计划本轮后处理；可只在非Me设置页保留返回。不要据此扩展设置结构或重开架构审查。

### 结论边界

当前源码grounding与实施范围闭合，受影响DOM路径通过；色值/布局规则相同仍不能保证字体、溢出、触达和视觉层级在真实屏幕上全部合格。已知浏览器file禁令未绕过，真实视口截图及产品对照由M1-W1执行。没有产品实现、外部平台或公网完成结论。


### Author Resolutions — R6

R6 grounding/scope findings accepted. Fixed the non-blocking Me self-return button by rendering the mobile back control only on other settings pages. Confirmed Me has no self-return and Devices still returns to Me. This local presentation fix does not change the reviewed behavior or interfaces; R6 retained. R1-W3 remains open. No browser visual or production acceptance claimed.


### Author Resolutions — R6 后原型纠偏与提交检查

用户继续指出 UserMenu 与 PoliciesPage 未忠实保留 current UI。作者已按实际组件补回头像身份条、图标、原有菜单名称/说明/语言/退出，账号独立进入 AccountPage；补回策略六字段、双卡布局、保存/放弃及失败保留草稿，权限仅按已审设计限定管理员写。新增策略页外部演示控件直接查看正常、账号满、服务满，告警补齐已审设计要求的相关账号及用量/上限；不新增产品控件、策略字段或权限语义。示例数据不来自生产。

定向 DOM 检查覆盖菜单、账号/Me 路径、六字段、成员只读、管理员保存/放弃/失败重试、容量三状态及管理员专属可见，并回归群任务往返/草稿和聊天容量失败时仅发文字。属于现有契约的呈现纠偏，R6 架构与权限结论 retained；不得再将早先的源码样式对照表述为视觉验收。浏览器 file URL 限制及 R1-W3 飞书测试用户授权缺口仍保留，Gate 2 未通过。本次按用户要求仅提交 unit 设计快照，不代表实施、发布或验收完成。
