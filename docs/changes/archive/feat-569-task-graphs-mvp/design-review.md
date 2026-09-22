# feat-569：任务图 MVP 设计评审

## Round 1

### Metadata

- reviewer_target: Codex `/root`，独立于交接包的 ChatGPT 作者；本轮未修改受审方案。
- review_mode: full
- mode_reason: 首次独立审查，覆盖需求、全部设计决定、两份 delta、原型和唯一 M1，并核对真实产品装配入口。
- started_at: 2026-09-22T15:57:40+08:00（开始解包取证；不含此前目录检查）
- completed_at: 2026-09-22T16:11:38+08:00
- duration: 13m58s
- authored_base: `c0313d9c62891d4d452162d7f1d30a2680556885`
- executed_base: 本地 `main@4394ad4246b2ec3324e2c8aa219212dc0ec2ff75`，有既存 dirty/untracked 内容。
- scope: 文档设计审查与离线原型体验；不是产品实现验收或代码审查。
- verdict: **Issues Found — 0 CRITICAL / 3 WARNING**。
- approval_state: 用户明确说尚未核对包中文字；导入不等于用户确认全部派生需求，当前不宣告 Gate 1/2 通过。

### 导入与证据基线

用户授权将文件放进 change unit。已检查 active/archive/retired：没有同主题任务图 unit。`feat-397-spec-design-agent-team` 的目标是自动完成 spec/design 对齐，与本次运行产品内的任务图不是同一项工作。

执行经过阅读的交接包 `import_unit.py`，仅调用一次仓库编号分配器，登记为 `feat-569-task-graphs-mvp`。导入 spec、design、prototype、sources、两份 delta 和空 M1；只进行了脚本约定的离线代号替换和来源登记。原始 ZIP 保留，包外层说明与 preview 自测资料仍保留在 ZIP 中，不混入产品验收证据。未修改产品代码、既存 unit、current specs，未创建分支或提交。

本地 Git 已有包的 authored_base 对象，`origin/main` 本地跟踪引用也指向该提交；未执行 fetch，故不声称这是远端实时最新状态。两个提交之间的 src/current-spec 差异主要是 bugfix-567 入站附件与 refactor-568 工具生命周期投影。以下评审依赖的 Work 可见性、session binder、internal dispatch、composition、IM connection、Work repository/API 路径在两个基线之间无差异，因此不能将 findings 归咎于本地代码偏旧。

受审文件指纹（导入后、评审前）：

| 文件 | SHA-256 |
|---|---|
| spec.md | `1233865bf84d0119d4da6c4580c10d37678983ae5652673ef3a5df8ec2e20ebe` |
| design.md | `f830e145d4542a6127f78c9b273810a5ee20ee229c3ef43b21e419c4b68ec848` |
| prototype.html | `f022394337eee245bfa6935e585fe43d4faf0e7272372068e01ee7c3795ad3a8` |
| specs/im/task-graphs.md | `35955cdf123e8f788d6bfacefeee03872c1a685460f12d258634d021c6abeda2` |
| specs/gateway/task-graphs.md | `e1c1cfa9e47d1f33e46ef2361f114d479f0c66620879877af43769d5e5322e95` |

原始 ZIP SHA-256：`944b35a718b65db8d088d6e11ce0cb3d212594df0cba6523c29fc80b5bdad288`。

### 总体判断与架构覆盖

核心方案值得保留，不需要重新设计一套任务执行系统。

- **D1/D2：节点内部模式与两种关系分开是正确的。** `container_id` 表达属于哪一层，dependency 表达先后条件，`derived_from_id` 表达探索来源。X 和 Z 都属于 A，Z 从 X 衍生，Z 内还能拥有自己的 DAG；这准确承接原话中的双向嵌套。
- **D3/D4：状态记录与实际运行分离符合 MVP。** 负结果可完成、done 可回到 doing、选择 Z 不自动完成 A、A 完成不启动 B，避免把“先做图”扩成调度器。只由主 Agent 写、只支持哪些聊天来源，是额外产品选择，见下文。
- **D5/D6：IM 唯一存储适合当前在线协作记录。** IM service 持有权限、完整图校验与事务；PA 负责工具、真实执行来源与传输；浏览器负责显示与查询。无需向内核增加业务状态，也无需 Gateway 影子数据库。成员权限与公开 Work 副本之间的边界尚需说清，见 W1。
- **D7/D8：一个工具、四个动作、有限原子批次可以实现。** revision 防止旧更新覆盖新内容，幂等回执处理“已提交但回执丢失”；两者解决不同问题，并非重复抽象。权限先于回执查询的顺序合理。两步 create/apply 的部分成功已明确表达，没有假装整张图原子创建。
- **实际装配：** `src/personal_assistant/product.py` 原生工具注册、`gateway/composition.py:304` 的现有 conversation RPC、`gateway/internal_dispatch.py:505` 的 loopback 模式、`ws/im_connection.py:604` 的 ACK 队列均可作为增量接线基础。新增 command/result 应继续由现有连接 owner 处理，不另建 transport/pending 生命周期。合法来源判定须收口，见 W2。
- **D9：逐层查看与沿用现有 UI 依赖合适，但当前连线实现不能可靠表达所有合法 DAG。** 见已复现的 W3。无需因此强制引入图编辑框架。
- **依赖边界：** IM 不调用 agent，PA 仅通过 SDK 注册工具，Kernel/CLI 无业务 delta，符合 `SPEC.md`。没有发现需要拆出新服务或新常驻进程的理由。

### 需求、delta 与 milestone 覆盖

| 范围 | 审查结论与证据 |
|---|---|
| R1 / S01–S03：讨论、创建、聊天入口、空态 | create/apply、稳定 URL、聊天入口与 P1 有设计；原型聊天示例直接展示已保存图，尚不足以演示“用户明确要求保存”的完整对话，可选改进见 R3。 |
| R2 / S04–S05：DAG 与不自动开工 | 数据约束及显式状态更新闭合；P2 的复杂一点的合法连线存在 W3。 |
| R3 / S06–S08：探索、负结果、选定方向 | 来源与归属分开，selection 不联动 status；选中方向被 dropped 时同批清除/替换的规则闭合。 |
| R4 / S09–S10：两种嵌套、继续细分 | 已实际点击根→A→Z→详情→返回；图保存后重载仍恢复嵌套视图。空叶子改 mode 并加孩子可在一次 apply 内完成。 |
| R5 / S11–S13：查询、结果、返工 | list/get/apply 覆盖。回聊天引用含 graph/node 身份并仅进入草稿。已有 `composer-draft-store` 可复用；`message-pane.tsx:332` 当前 draftSeed 会替换草稿，实施时应按 design:243 新增追加语义、保留 mention 与附件，不能直接复用替换行为。设计已有明确要求，因此不另报 finding。 |
| R6 / S14–S15：非法关系、版本冲突 | 最终候选图统一校验、原子提交、拒绝过时 revision 的设计足够；没有产品实现，未宣称验证数据库行为。 |
| R7 / S16–S17：持久化、失败与未知 | 同一 DB 重开、先确认再报成功、幂等恢复已有明确方案；原型和包内 40 项自测不能证明真实栈持久化及断连语义。 |
| R8 / S18–S19：权限、桌面与手机 | 原型 1440×960 与 390×844 可打开节点、逐层导航、查看详情；权限承诺见 W1/W2。 |
| 两份 delta | 新增 IM/Gateway area 的归并目标正确，当前无同名 area；6/4 条 Requirement，ADDED 没有丢弃现有 MODIFIED 场景的问题。W1 可能只需澄清新 delta；若改变 Work 可见性，则必须增加对现有 `im/agent-work.md` 的 MODIFIED delta。 |
| 唯一 M1 | 完整端到端切片合理，空目录正确，W1–W8/R1–R7 具有可追踪退出条件；不要求人为拆成数据库/API/UI 三个 milestone。补 W2 来源矩阵与 W3 复杂连线验收即可。 |

P1–P6 均已阅读：本轮实际体验了计划/探索/嵌套、节点详情、回聊天引用及手机抽屉；P6 的全部失败场景未逐项重跑。没有运行真实 IM/Gateway/LLM、没有检查或使用生产凭据。模型端点与隔离栈可用性留作实施前核实，不用它们的未核实状态制造设计问题。

### Issues

#### R1-W1：成员可见性承诺未说明公开 Work 中的任务副本

- **位置：** [spec.md](spec.md) S18（148–150）；[design.md](design.md) D5（92–95）、调用路径第6项（220）、风险（285）；[IM delta](specs/im/task-graphs.md) 第5–14行。
- **证据：** 当前 [Work 契约](../../../specs/im/agent-work.md) 第28–43行明确规定，任何登录用户可看包含原聊天内容的完整 Work，工具参数和已有结果不按聊天成员过滤。真实 `src/IM/api/routes/agent_work.py:73–89` 只要求登录及可用 global profile；`src/IM/infra/repositories/agent_work.py:342–355` 将真实工具参数/结果投影到 Work；`src/personal_assistant/gateway/global_work.py:219–227` 记录实际事件。
- **具体场景：** 全局 Agent 在有权限时 `task_graph.get` 私聊任务，或用 `apply` 提交任务名称与结果。另一个并非该私聊成员的登录用户不能打开任务 API，却能从该 Agent 的 Work 看到调用中的内容。普通 assistant 正文也可能复述结果，因此只隐藏一个工具卡片不足以实现端到端保密。
- **问题性质：** 这不是“TaskGraphService 的 ACL 必然会被绕过”的断言，而是文档没有区分受保护任务资源与沿用公开 Work 规则的转录副本。两种理解会导向完全不同的实现与 S18 验收。
- **最小修正：** 若保持当前 Work 契约，在 spec/design/delta 明确“成员限制约束任务查询/图页面及原聊天入口；已进入 Work 的内容遵循现有 Work 可见性”，加入一项区分这两个入口的场景。若用户希望任务内容在 Work 也保密，则必须另行对齐该变化，并补 Work 的设计与 delta，不能只在任务 endpoint 加 ACL 后声称满足。
- **不修后果：** 容易向用户承诺并不存在的隐私边界，或在实施时未经对齐改变整个 Work 产品。

#### R1-W2：“仅 Web IM 主 session”的判定与全局模式没有闭合

- **位置：** [design.md](design.md) D4（87–90）、D5（93）、调用路径第2项（216）；[Gateway delta](specs/gateway/task-graphs.md) 第12–16行。
- **证据：** `src/personal_assistant/gateway/session_binder.py:278–329` 的全局主 session 只有 agent/work_scope 身份，不绑定一个当前聊天；它能在同一上下文读取多个原生和外部来源。`SessionProvenance`（184–189）及 `capture_session_provenance`（745–758）只核对 session→Agent 的归属，并不证明来源是原生聊天或特定主会话。`gateway/kernel_client.py:121–135` 也会登记经该客户端创建的 Agent session，不能把“已登记 provenance”直接当作 native-main 证明。
- **具体歧义：** 全局 Agent 读到一条飞书消息后，更新一张锚定 Web 群的既有图，究竟允许还是 `unsupported_context`？设计一面支持 global 和跨聊天引用，一面按“请求来自外部上下文”拒绝，但没有定义“外部”指触发消息、session，还是图的 home conversation。全局 session 并不存在可直接检查的单一来源频道。
- **最小修正：** 明确按哪一种身份判定。适合当前 MVP 的方案是：global 以当前持久 global-main session 身份确认调用者；single_thread 以真实 native binding 确认；支持范围另按图的 home conversation 判定是否原生；child/cron 等非目标 session 拒绝。若还要按触发消息来源限制，需要说明独立的可信来源依据，不能从模型参数或“最近一次聊天”猜。
- **验收补充：** global 主会话从不同来源唤醒、原生 single_thread、外部 single_thread、child、cron/其他非聊天 session；每类给出允许/拒绝的预期。不需要增加一套 session 注册系统。
- **不修后果：** 可能误拒绝核心 global 路径，或只验证 Agent 归属便放行本期声明不支持的会话。

#### R1-W3：合法跨列依赖在原型中被遮挡，DAG 展示验收过窄

- **位置：** [design.md](design.md) D9（106–107）、P2（264）；[prototype.html](prototype.html) 第99–100行的 layout/renderGraph。
- **真实复现：** 在浏览器 1440×960 打开“计划 DAG”，点击“调整连线”，增加 A→C；工具模拟成功，版本从4变5。文档中存在 A→B、B→C、A→C 三条边，但截图仍只能辨认 A→B→C。
- **DOM 证据：** 三条 SVG path 分别为 `a:b = M220 99 C256 99,252 99,283 99`、`b:c = M492 99 C528 99,524 99,555 99`、`a:c = M220 99 C256 99,524 99,555 99`。A→C 与另两条线共用同一水平线，并从 B 卡片后方穿过；其端点也与 B→C 重合。当前节点详情没有列出依赖关系作为补充，所以用户无法查清直接边。
- **最小修正：** 为跨列边预留绕行空间，避免经过中间卡片与完全重叠；节点详情可补直接前置/后续关系作为可读补充。P2 至少加入跨列边、分叉、汇合三种小图，确认用户能区分实际保存的每条直接关系。保留 SVG/HTML 方案即可，不强制引入新库。
- **不修后果：** 实现若按 must-match 原型照搬，会把“正确保存 DAG”误认为“用户能读懂 DAG”，S04 仍不成立。

### 需要用户核对的作者派生选择

这些不是已发生的用户确认，也不全是设计错误。原话明确要求“图可见、Agent 创建/查询/更新、双模式嵌套、第一版不做自动并行和预算”；以下限制由作者补入，继续实施前应集中对齐：

| 选择 | 包中方案 | 实际影响 / 评审建议 |
|---|---|---|
| 外部聊天是否能操作 | 首文档限定原生 Web IM，design 进一步限制工具上下文 | “不做飞书任务图 UI”与“飞书里不能让 Agent 更新图”是两件事。优先确认这一项，并与 W2 的目标/来源判定同步。 |
| 子 Agent 能否直接记录 | child 不调用，由主 Agent 汇总更新 | 简单且保持一个汇总责任人，但长时间子执行的图进展依赖主 Agent 更新；不应把该限制说成用户已要求。 |
| 任务归属 | 一张图绑定一个 home conversation；可跨聊天引用，但不迁移或额外共享 | ACL 简单；不等于一个脱离聊天的个人全局任务库。评审倾向首版保留，需让用户知道这个使用边界。 |
| 记录可改到什么程度 | 不删除、不换父层、非空图不切模式；保留当前总结，不提供版本历史 | 足够创建、细分和状态更新；改错归属只能新建正确节点并放弃旧节点。暂不要求增加机制，但“更新”并非任意重组。 |

“IM 在线才可用”“没有网页表单编辑器”“最多一个当前选项”也属于方案选择，均与精简 MVP 相容，不单独计为阻断项。

### Recommendations（不阻断）

- **R1-R1：删去没有当前消费者的浏览器写 API。** design:229–230 同时说 MVP 页面没有创建/编辑表单；若唯一写入口是 Agent 的 WS command，HTTP POST create/operations 并非当前需求所必需。可暂留 GET，继续由同一个 service 供 WS 写入，减少一套对外接口及权限测试。若决定保留，写清实际消费者即可。
- **R1-R2：复用已有能力时明确两个实施提醒。** 工具注册不会自动加入已保存 Agent 的显式 allowlist（`product.py:422–442`），应在设计中说清默认可选/固定基础工具的选择；回聊天应复用现有 composer store 的完整快照，避免替换草稿时丢 mention。后者已有明确需求，不必设计新的全局状态管理层。
- **R1-R3：原型聊天样例补上用户“保存这版”的消息。** 当前样例从“先讨论，不要开始执行”直接展示保存结果。补一句用户明确的保存指令，就能更准确展示 U1 的完整旅程，不需要加入审批 UI。

### 历史问题闭环

首次审查，无历史 findings / Author Resolutions。W1–W3 均 open。本轮只导入原文与记录评审，没有代 author 修订或自签 Approved。

### 下一步

先与用户核对派生范围，尤其外部聊天操作与任务归属；由 author 在本 unit 修订相应 spec/design/delta/prototype，并追加 Author Resolutions。复审只覆盖实际变化和这三个问题的闭环；没有证据要求扩成自动编排、预算或新的长期任务运行层。

### Author Resolutions（2026-09-22，权限范围修订）

- author_target: Codex `/root`，本次由原 reviewer 转为修订 author；后续权限闭环交给独立 reviewer，不自签结论。
- R1-W1: **accepted**。用户原话：“权限问题先怎么简单怎么来，自洽就行。”采用既有任务成员 ACL 与既有 Work 可见性并存的最小方案。`spec.md` v1.1 保留原话和 Agent 解读，S18 区分任务入口与 Work 副本；`design.md` D5、调用路径、风险与 R6 验收口径同步；IM delta 增加非成员可看 Work 已有内容但不能打开原图/原聊天的场景。没有改变 current Work 契约，没有新增权限机制。
- R1-W2 / R1-W3: 本次权限表述修订未改变来源判定或连线布局，保留 open。
- R1-R1 / R1-R2 / R1-R3: 保留为后续设计修订的可选建议，本次未改。
- base: 本地主仓已快进至 `c0313d9c62891d4d452162d7f1d30a2680556885`，与原包取证基线一致；R1 已确认权限相关 current 路径在两个基线间无差异。

## Round 2

### Metadata

- reviewer_target: Codex `/root/task_graph_permission_review`，独立替代 reviewer；未参与受审文档修订。
- reviewer_handoff: Round 1 reviewer Codex `/root` 本轮转为权限修订 author，因此更换 reviewer。交接依据为完整 Round 1、Author Resolutions、修订前原文快照与本轮冻结文件；未以 author 的 accepted 状态代替独立闭环。
- review_mode: closure
- mode_reason: 实际差异仅澄清 R1-W1 的任务资源与 Work 副本可见性，并同步 S18、IM delta 和既有 M1/R6 验收口径；没有新增接口、权限机制或 milestone。旧报告、前后原文与 current 接线证据足以支持局部审查。
- retained_from: Round 1；未受影响的需求、D1–D4/D6–D9、Gateway delta、原型和 M1 结构沿用其覆盖记录，旧未解决项仍计入本轮结论。
- started_at: 2026-09-22T16:22:17+08:00（差异与 current 接线核验的计时记录点，不含此前技能及历史报告初读）
- completed_at: 2026-09-22T16:25:14+08:00
- duration: 2m57s
- authored_base / executed_base: `c0313d9c62891d4d452162d7f1d30a2680556885`；本地 `main` 有既存 dirty/untracked 内容。
- scope: 冻结文档的权限闭环审查；只追加本报告，没有修改受审方案、current specs 或产品代码，没有运行产品栈、生产操作、提交或推送。
- verdict: **Issues Found — 0 CRITICAL / 2 WARNING**（继承仍未关闭的 R1-W2、R1-W3；本轮新增 0）。
- gate_state: R1-W1 已闭环，但整个 unit 的 Gate 2 仍未通过；本轮不宣告其余派生范围已获用户确认。

### 冻结版本与 retained 依据

对比修订前原文快照，实际修改为：spec v1.1 的权限澄清与 S18；design 的版本指向、D5、调用路径第 6 项、风险与 M1/R6；IM delta 的入口措辞和新增 Work 场景。Round 1 的原文是当前报告的完整前缀，未被改写。

| 文件 | 本轮 SHA-256 |
|---|---|
| spec.md | `21fdae69a1b9c206cebbd2f0f39ad673765b60fbb9266575070489987e7939fd` |
| design.md | `de6521fb157ba388c1d618ec1f437c0a7aeccb7dcada1201700c4d1bb373fdf2` |
| prototype.html | `f022394337eee245bfa6935e585fe43d4faf0e7272372068e01ee7c3795ad3a8` |
| specs/im/task-graphs.md | `0c4147b2098ac3c342a8aa6f1b4913af0f8ebe57a746cf2fe408224530784ee7` |
| specs/gateway/task-graphs.md | `e1c1cfa9e47d1f33e46ef2361f114d479f0c66620879877af43769d5e5322e95` |

原型与 Gateway delta 的指纹与 Round 1 相同；唯一 milestone 仍为 `M1-task-graphs/.gitkeep`。独立比较 R1 executed_base 与本轮 HEAD：本轮依赖的 IM Work app/router/repository、conversation access、PA composition/global_work/session_binder/kernel_client 以及 current Work spec 没有基线差异。其余原型体验引用 Round 1 已记录的观察，不宣称本轮重复了浏览器验收。

### 历史问题闭环

#### R1-W1 — closed

**Author Resolution：**接受用户“权限问题先怎么简单怎么来，自洽就行”的授权，保留现有两类入口的可见性，补足原先遗漏的 Work 副本说明。

**文档闭环证据：**

- [spec.md](spec.md) 第 35–39 行明确区分用户原话和 Agent 采用方案；S18 第 154–157 行把禁止读取限定为任务入口/查询，同时说明已进入 Work 的任务内容登录可读、原任务图和原聊天仍检查成员关系。没有继续作出端到端副本保密承诺。
- [design.md](design.md) D5 第 92–97 行将责任分开：TaskGraphService 负责任务资源成员 ACL，Work 继续负责既有执行副本展示；第 222 行的 presenter、风险中的权限顺序和第 352 行的 R6 验收要求一致。工具参数、结果、Agent 正文均被明确覆盖，不留下“只隐藏工具卡片就保密”的歧义。
- [IM delta](specs/im/task-graphs.md) 第 5–19 行保留成员读取与撤销场景，并新增非成员可看 Work、但不能打开原图/原聊天的消费者场景。归并仍指向新的 canonical `docs/specs/im/task-graphs.md`；因为 current Work 行为未改变，不需要凭空增加 `im/agent-work.md` 的 MODIFIED delta。
- M1/R6 将两类入口放进同一个 S18 真栈验收要求，能够检验本次澄清；这只是未来验收要求，当前没有任务图实现结果可供宣称通过。

**current 契约与实际接线证据：**

1. [Work current spec](../../../specs/im/agent-work.md) 的“Work 内容完整可见，原聊天仍按成员访问”及执行明细场景明确允许登录用户查看已有跨聊天内容、工具参数和结果。
2. 真实 PA composition 在 `src/personal_assistant/gateway/composition.py:362` 装配 `GlobalWorkRecorder`，第 945–950 行连接现有 relay/runtime；`global_work.py:40–44` 订阅 SDK 事件，第 219–227 行保存真实事件 payload，第 350–352 行通过现有 IM connection 发送 `agent.work.append`。
3. 真实 IM app 在 `src/IM/app.py:416–427` 装配 repository、GatewayWork 与 GatewayRuntime，并在第 489 行挂载 Work router。`src/IM/infra/repositories/agent_work.py:342–376` 保存工具输入、presenter 结果与普通正文；`src/IM/api/routes/agent_work.py:73–89` 的明细读取要求登录和有效 global profile，不要求来源聊天成员身份。
4. 浏览器 `src/IM/frontend/src/features/settings/agents/agent-work-panel.tsx:181–189` 将真实 payload 交给 WorkTool；`agent-work-presenters.tsx:58–65` 继续展示工具细节，没有另加来源聊天过滤。
5. 原聊天资源有独立入口权限：`src/IM/api/deps.py:352–382` 根据当前人类成员或 node-owned Agent 成员身份授权；`src/IM/api/routes/messages.py` 与 `message_images.py` 的数据路由调用该检查。因此 Work 可读本身不提供原聊天资源权限。任务图 endpoint 尚待实现，其 ACL 责任已由 D5 与调用路径明确落在 IM service。

**架构判断：**复用既有 Work 记录、传输、展示和聊天成员检查，比新增任务脱敏器、撤回副本或第二套身份机制更符合本次授权的简单 MVP。IM 持有图资源授权，PA 携带真实调用来源，Work 保留实际执行副本，职责没有互相覆盖。后者不解决 R1-W2 的来源识别问题，两个 finding 应分别判定。

#### R1-W2 — still-open

**Author Resolution：**本次未修改来源判定。

**本轮核验：**design D4 和调用路径仍要求“原生 Web IM 主会话”，Gateway delta 仍以“不支持的外部上下文”拒绝；未补充 global 的可信允许/拒绝规则。`session_binder.py:278–329` 的 global-main 仍是跨聊天持久 session，`SessionProvenance:184–189` 与 `capture_session_provenance:745–758` 仍只给出 session→Agent 归属；`kernel_client.py:121–135` 也会登记其他创建的 Agent session。R1 的证据和误拒绝/误放行后果仍成立。

审查期间 author 转述用户新增选择：“允许，外部聊天也能操作，Web IM 负责看图”。本轮冻结文件尚未纳入该决定；它为后续修订提供方向，但没有自动补齐来源身份、图目标及外部聊天映射规则，因此不能关闭 W2。后续应按实际修订影响选择 delta/full 审查。

#### R1-W3 — still-open

**Author Resolution：**本次未修改原型连线路由或 DAG 展示验收。

**本轮核验：**prototype 指纹与 Round 1 相同；第 99–100 行仍按相同列/中心高度生成 SVG 曲线，第 98 行详情仍不列直接前置/后续关系。design P2 仍仅指定 A→B→C。因此保留 Round 1 已复现的 A→C 被中间 B 遮挡且与其他边重合的证据，本轮未重复浏览器操作，也没有把“文件未改”当作修复。合法 DAG 的直接依赖仍可能无法辨认。

### Issues

- **R1-W2（继承 WARNING，open）：**全局主 session 的允许来源与任务目标范围未写成可实施、可验收的规则；新用户决定待同步。
- **R1-W3（继承 WARNING，open）：**合法跨列直接依赖的显示与验证覆盖仍不足。
- 本轮没有新增 CRITICAL / WARNING；R1-W1 从未解决项中移除。

### Recommendations

保留 Round 1 的 R1-R1 / R1-R2 / R1-R3，均为可选建议，本次未修改也不升级为阻断项。权限闭环本身无需新增机制；继续修订 W2、W3 后，再对冻结的实际变化独立复审。


### Author Resolutions（2026-09-22，工具来源与图展示修订）

- author_target: Codex `/root`；延续原 author，下一轮由独立 `/root/task_graph_permission_review` 复审。
- R1-W2: **accepted**。用户先选择“允许，外部聊天也能操作，Web IM 负责看图（推荐）”，随后明确纠正“外部内部都是输入user prompt，调用工具是agent内的事情，两者都无关”。spec v1.2 保留原话并新增 S20；design D4/D5、工具契约、调用路径、Gateway/IM delta 与 M1/R5/W2/W3 同步。取消按输入渠道或 global_main 判定任务工具准入；沿用工具配置与真实 PA session→Agent 归属。目标 conversation 独立作为业务目标，复用既有映射；get/apply 不要求输入来源与图 home 相同。内核 child 的临时 agent_id 不等于注册 PA Agent，本版沿用子执行返回后由 PA Agent 更新，不扩展代父身份授权。
- R1-W2 取证：`session_binder.py:278–329, 745–758` 为全局跨聊天 session 与 PA 归属；`kernel_client.py:121–135` 登记既有 PA session；`agent/platform/tools/builtins/agent.py:687–705` 与 `agent/sdk/kernel.py:224–289` 区分 child 临时身份。只读研究这些内核实现，不授权 PA import 私有模块或新增内核任务业务。`global_inbox.py:363–377, 574–593` 复用现有 target→conversation 映射，外部四元组回到 current IM 契约核实；`composition.py:260–270` 与 `ws/im_connection.py:398, 604` 提供现有公开用户入口和带回执传输。已核实后明确写入设计，不新增来源认证系统或第二套映射。
- R1-W3: **accepted**。原型按跨列边预留上方通道，分叉/汇合使用不同连接点，并在详情列直接前置/后续。新增“复杂 DAG”演示（A→B→C、A→C、A→D、C→E、D→E）。spec S04、IM delta、design D9/P2/M1-R2 同步要求，不将复杂图演示控件引入产品。
- R1-W3 作者浏览器核验：1440×960 可见 A→C 从 B 上方绕行，A→B/A→D 分叉和 C→E/D→E 汇合分别到达不同端点；C 详情列 B、A 为直接前置，E 为直接后续。390×844 同样可打开完整关系详情，缩放至70%后图内可查看连线；嵌套 Z 内 DAG 返回 A 后仍显示 X→Z 衍生和 Y，面包屑与模式正确。此为离线原型观察，不是产品栈验收。工具模拟输入也从 conversation_id 同步为 target；持久图字段仍为 home_conversation_id。
- R1-R1: **accepted**。删除没有产品消费者的浏览器 POST 写接口；Agent WS 进入 service 写，浏览器只保留 GET。
- R1-R2: **accepted**。D4 明确默认工具集与显式 allowlist，不偷偷扩大显式配置；回聊天引用使用已有 composer store，保留正文与 mentions，不用 draftSeed 覆盖。实际工具/classifier 接线与草稿行为仍由 M1 真栈验收。
- R1-R3: 保留可选演示叙事建议，不作为阻断项；本轮未据此扩展产品。
- 验收资源只读核对：仓库 Python yaml/httpx、Node/npm、前端依赖可用；真实 Chromium 已运行原型。配置模型端点完成一次真实请求（HTTP200、OK、end_turn），仅证明模型资源可用。专用 Feishu E2E 文件0600、必需键齐全，非 default CLI profile 的 auth status --verify 返回 verified=true 且 App 与测试配置一致。未发送外部消息、启动测试 Bot 或产品栈；实施后的 Agent 工具与客户端行为仍须按 Runbook 验收。
- 范围：只修改本 unit 文档/原型/sources 状态说明；未提交、推送、修改产品代码或部署。Round 1 与 Round 2 原文保持不变。

## Round 3

### Metadata

- reviewer_target: Codex `/root/task_graph_permission_review`，延续 Round 2 独立 reviewer；未参与本轮受审方案修订。
- review_mode: full
- mode_reason: 用户明确将输入渠道与 Agent 工具能力解耦；本轮同时改变工具目标参数、可关联会话范围、跨入口链接、DAG 原型与验收覆盖，涉及核心边界及共享接口，超出局部 closure。重新覆盖全部需求、D1–D9、两份 delta、原型及唯一 M1；未变化的 current Work 接线沿用 Round 2 已核实证据。
- started_at: 2026-09-22T16:42:19+08:00
- completed_at: 2026-09-22T16:48:08+08:00
- duration: 5m49s
- validated_at: 冻结 spec v1.2 及以下指纹；审查期间 author 将同一内容提交为 `f296b7cb67e7b2afac93a360ff588fb22edb92bb`，没有改变受审内容。
- executed_base: 开始于 `main@c0313d9c62891d4d452162d7f1d30a2680556885`；完成时 HEAD 为 `f296b7cb67e7b2afac93a360ff588fb22edb92bb`。独立核对增量仅包含本 unit 的 7 个文档/原型/骨架文件，产品代码仍为 c0313d9c。
- scope: 文档设计审查及正式离线原型的独立浏览器检查；没有执行产品实现验收、真实 LLM/Feishu 调用、生产操作、提交或推送。
- verdict: **Approved — 0 CRITICAL / 0 WARNING**。
- approval_boundary: 本轮设计审查通过；不表示任务图已实现、产品验收通过或已部署。后续仍按 workflow 完成 author 核实及实施门禁。

### 冻结版本与历史保留

已对比 Round 2 后快照与正式 unit。Round 1、Round 2 及其原结论完整保留；author 的 accepted 只作为待核实答复，不作为本轮结论。

| 文件 | 本轮 SHA-256 |
|---|---|
| spec.md | `4db31c4a7eeae067124558b931202b37fa6216c012ae91fea89344bf3335a42a` |
| design.md | `d0a7ebcbe12fa3261e8f355bd1303a0e5565975f4753a99be66e10d3fbbafdac` |
| prototype.html | `b2c0b3172d56c8df89a72d67f0f03c60b79239f67ae7db29f93b84efa445ba5d` |
| specs/im/task-graphs.md | `47ed69d16c253c654370f4ee0f1d011bb9570336650c02823890fcc2ff95adeb` |
| specs/gateway/task-graphs.md | `8088e167d0054b5f92adea04bc17e990447117a5ba009f17a54e01a76f87c380` |
| sources.json | `c483d9522f1166a136ca3c2e1dd87871d19775c0016c59a454d23496c2b79d10` |

唯一 milestone 仍是 `M1-task-graphs/.gitkeep`；没有伪造实施记录。`sources.json` 将导入来源限定为原始包快照，并将后续审查状态指向本报告，避免把“not_run”继续当作当前事实。

### 当前组装与架构判断

**身份与业务目标已经分开。** spec 的新增原话、S20，以及 design D4/D5、工具契约和调用路径互相一致：工具配置决定能否调用；PA session 归属提供调用者；IM home conversation 成员关系决定能读写哪张图。输入来自哪里不再用于任务专属准入，也不要求它与 home 相同。此方案承接用户纠正，没有引入每渠道一套任务权限。

- `product.py:422–442` 确认显式 tool allowlist 是实际配置边界。D4 已明确注册默认工具集和目录，但不偷偷向已有显式 allowlist 加入 task_graph；M1 包含实际下发和 classifier 验证。
- `session_binder.py:278–329,745–758` 与 `kernel_client.py:121–135` 证明现有 PA session→Agent provenance 可复用。新的任务 handler 明确不调用带 global-main 限制的 Inbox execute 路径；`global_inbox.py:555–556` 和 `composition.py:310–312` 确实有该限制，不能整段照搬为任务准入。
- 内核 child 通过 `agent/platform/tools/builtins/agent.py:687–704` 写入自己的 agent_id，并由 `agent/sdk/kernel.py:262–289` 创建/关联 session；这不是 PA kernel_client 的注册路径。D4 保留“无法核实 PA 身份则明确失败、子结果交回 PA Agent 更新”，没有把用户关于输入渠道的决定扩成新的代父身份继承。这里只读取内核实现取证，PA 实施仍只能 import `agent.sdk`。
- `global_inbox.py:363–385` 持有 agent-scoped opaque target 的已有路由数据，第 575–593 行已有映射到 conversation_id 的用法。新工具的 create/list 在 PA 归一化业务 target，IM 只接收自己的会话 ID；get/apply 以 graph_id 定位 home，省去无关的输入来源判断。
- 外部映射不是任务系统新建的机制：[current conversations spec](../../../specs/im/conversations-messages.md) 的四元组契约与 `shadow_sync.py:188–240` 对齐。`inbound_pipeline.py:161–178,207` 在 global/single_thread 分流前已有 shadow 结果；`session_run_coordinator.py:357–374` 将真实 shadow conversation 保存到 reply context。design 第 173 行要求 single_thread 把已绑定引用提供给模型，有现存来源可用，无需创建第二套映射或从最近 prompt 猜目标。
- `composition.py:292–295` 已将 listener provider 注入 PA 工具组装；`internal_dispatch.py:505–538` 展示实际 loopback 归属检查方式；`im_connection.py:604–625` 有统一 pending/ACK owner。design 第 229–234 行为新 command/result 指明增量落点，复用该 owner，而不是另建连接或队列。`im_connection.py:966` 的既有 result 分派仍需在实施时增加任务结果分支；设计没有声称只注册工具便已接通。
- `im_connection.py:398–400` 与 `composition.py:260–270` 确认公开用户入口来自已认证 IM 注册。design 第 175 行据此组装 web_url，分别陈述保存结果和链接可用性，避免把 Gateway 本机 URL 发到外部聊天。
- IM service 持有图校验、成员检查、revision 与持久化；PA 持有工具接入及私有 target 翻译；浏览器只读并展示。删除没有消费者的 HTTP POST 接口后，没有重复写入口。D1/D2 的 container、dependency、derived_from 各有明确语义；D3 不根据执行终态自动改图；D6/D8 的中心存储、事务与小型幂等回执足够解决本版问题，不需要任务执行引擎或事件溯源。

本轮未发现与 `SPEC.md`、[SDK boundary](../../../specs/kernel/sdk-boundary.md) 或 current IM/Gateway 职责相冲突的新依赖。保留一个端到端 M1 合理，不要求按数据库、API、前端机械拆分。

### 需求、delta 与 milestone 覆盖

| 需求范围 | 设计与验收覆盖 |
|---|---|
| R1 / S01–S03 | 显式 create→apply、真实保存回执、Chat/Tasks 稳定入口与空态；D4 和 M1/R1 不把讨论等同执行。两步保存的部分成功仍明确说明。 |
| R2 / S04–S05 | D9、P2、IM delta、M1/R2 同时要求链、跨列边、分叉与汇合可辨认，详情列直接前后置；D3/W5 保持状态不触发执行。 |
| R3 / S06–S08 | 来源边与 containment 分开，负结果、暂停/放弃及显式选项保留；selection 不联动父节点，现有操作/校验与 P3 对齐。 |
| R4 / S09–S10 | 逐层 scope、面包屑、空叶子同批改 mode 并加孩子覆盖两种嵌套与渐进细分；P4/M1-R4 明确重读和返回。 |
| R5 / S11–S13、S20 | list/get/apply 维护同一图；create/list 明确 target，get/apply 不依赖输入来源；公开 Web 链接、global/single_thread、显式配置及外部 prompt 的真实接线纳入 Runbook/M1-R5。第 255 行明确复用 composer store 附加引用并保留草稿、mentions，不用 draftSeed 覆盖。 |
| R6 / S14–S15 | 完整候选图校验、原子事务、revision 冲突及同请求回执去重仍闭合；不创建部分修改或新 request_key 的隐式重试。 |
| R7 / S16–S17 | 同一 DB 重启、未知回执与保留旧图的 stale 提示均有设计；Runbook 明确不能重建隔离数据冒充持久化复验。 |
| R8 / S18–S19 | R2 已关闭的 Work 副本边界保持不变；任务成员撤销后清缓存，桌面/手机图与详情可操作；P1–P6 和 M1/R6/W6 覆盖。 |

IM delta 仍是 6 条 ADDED Requirements，Gateway delta 仍是 4 条 ADDED Requirements；两者为新 area，canonical target 正确，需在最终实现后按真实行为归并并更新索引。新增 S20、外部映射不可用、可访问链接与复杂直接依赖场景均已进入 delta；没有覆盖或删除既有 current Scenario。Kernel/CLI 无新的任务业务契约，no spec delta 合理。

### 正式原型独立核验

本轮单独以 `127.0.0.1:18771` 只读提供正式 unit 文件，在新 CUA tab 打开；没有使用 author 的旧临时版本或操作其 tab。未连接 IM、Gateway 或模型。

- **1440×960，复杂 DAG：**100% 下直接看见 A→C 走 B 上方的独立通道；缩到 80% 可同时看到五个节点及全部六条边。A→B/A→D 分叉、B→C/A→C 汇合以及 C→E/D→E 汇合使用可区分端点，不再穿过 B 卡片。C 详情显示直接前置“B、A”，直接后续“E”。
- **390×844：**点击 C 打开底部详情，直接前置 B/A 与后续 E 完整可读；可关闭回到图。图保留横向查看与缩放，不要求把全部节点强行挤进手机宽度。
- **嵌套回归：**打开“嵌套验证”看到 Z 内 Z1→Z2→Z3 与根/A/Z 面包屑；点击 A 返回探索层，仍有 X、Y、Z，X→Z 为标注“衍生”的虚线，Z 仍标计划 DAG。
- 静态核对 `prototype.html:107–126` 的布局：跨列边有额外上方空间、独立 lane 和不同端点；详情第 106 行按直接依赖给出清单。该变更与 D9/P2 的必须匹配语义一致。
- P1/P5/P6 其余未变化部分沿用 Round 1/author 已记录的覆盖，不重复宣称本轮走完每个失败模拟。离线原型始终不是产品栈验收。

本轮临时 tab 已关闭，viewport override 已 reset，18771 服务已停止；没有写入截图缓存或运行数据到 unit。

### 历史问题闭环

| 原 issue | Author Resolution | 本轮独立判断 |
|---|---|---|
| R1-W1 | 保持 Round 2 权限方案 | **closed / retained from Round 2**。spec S18、D5 的 Work 副本段和 IM delta 没有改变其语义，产品代码基线亦未变。 |
| R1-W2 | 输入渠道不参与准入，真实 PA 身份与图目标分开 | **closed**。不再以 provenance 假证原生/global-main；显式 target、映射缺失、graph_id 跨来源、child 未注册身份、公开链接均有真实落点及验收要求。 |
| R1-W3 | 独立跨列通道、分叉汇合端点、直接关系详情 | **closed**。本轮正式原型的独立桌面/手机观察和静态布局核对支持闭环，S04/P2/delta/M1 已同步。 |
| R1-R1 | 去掉无消费者的浏览器写 API | **resolved**。第 237–242 行只保留 GET，Agent WS 是写入口。 |
| R1-R2 | 明确默认工具与 allowlist；复用完整草稿 | **resolved**。D4 与第 255 行消除配置和草稿覆盖歧义；真实下发、classifier 和草稿行为仍需实施后验证。 |
| R1-R3 | 保留可选演示叙事建议 | **optional / retained**，不影响设计通过，不增加产品审批 UI。 |

### 资源与证据边界

Runbook 将依赖可用、模型资源探测、测试 profile 身份核对与产品验收分开，口径准确。本轮接收 author 记录的 HTTP 200/OK/end_turn、私有文件 0600/必需键齐全和专用 profile verified/App 匹配作为资源可用证据，没有重复读取凭据或调用模型；浏览器可用性由本轮直接确认。

[worktree-runtime](../../../development/worktree-runtime.md) 第 30–37 行仍要求真实 Feishu 验收核实专用 App/Bot/User，并通过 `--feishu` 验证 Bot 与 listener lock。design 第 313 行保留该前置，没有把现有只读 auth 结果冒充已经完成 Bot 收发或产品 E2E；资源失效时只应如实阻塞相应产品场景。隔离端口、保留同一 DB 的重启和清理责任也已写明。

### Issues

无未解决 CRITICAL / WARNING。本轮没有新增阻断项。

### Recommendations

R1-R3 继续作为可选演示改进保留。实施时按 design 已明确的职责增量接入，尤其不要直接复用带 global-main 限制的整个 conversation-query handler；这是对已批准决定的执行提醒，不要求新增权限或映射机制。


### Author Resolutions（Round 3 判真与交付）

- author_target: Codex `/root`。
- 已核对 Round 3 的实际接线证据、冻结指纹、独立原型观察与需求/验收映射；同意 Approved（0 CRITICAL / 0 WARNING），无实质异议。R1-W1/W2/W3 均闭环；R1-R3 保留可选，不为演示润色追加审查轮次。
- 受审实质内容已提交为 `f296b7cb6`。本轮完成后仅将 spec 顶部的“Gate 2 仍待完成”和 design 顶部的“待审”状态改为指向本报告 Round 3 的已通过状态；无需求、接口、权限、原型、delta 或 milestone 变化，retained from Round 3，不触发新一轮复审。
- 最终窄验证：unit 内 Markdown 链接与空白检查通过，prototype JavaScript 语法通过；8 Requirements / 20 Scenarios，IM delta 6 Requirements，Gateway delta 4 Requirements，唯一 M1 骨架未预填。原有五个 dirty tracked 文件及源 zip 的六个哈希保持不变。
- 交付范围为设计文档和原型；产品尚未实施或验收，没有部署，也没有发送外部消息。
